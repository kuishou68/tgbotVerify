import asyncio
import random
import os
import time
import pandas as pd
from playwright.async_api import async_playwright
from faker import Faker
from .config import EXCEL_FILE, SIGNUP_URL
import logging

logger = logging.getLogger(__name__)
fake = Faker()

# Global lock to prevent multiple concurrent registrations which trigger IP bans
registration_lock = asyncio.Lock()
NEXT_BUTTON_SEL = '#nextButton, #iSignupAction, button:has-text("下一步"), button:has-text("Next")'

async def human_type(page, selector, text):
    """Simulates real human typing with random delays between keys."""
    element = page.locator(selector).first
    await element.click()
    for char in text:
        await page.keyboard.type(char, delay=random.randint(50, 150))
        if random.random() > 0.9: # Occasional pause
            await asyncio.sleep(random.uniform(0.2, 0.5))

async def human_click(page, selector):
    """Simulates moving mouse to element before clicking."""
    if hasattr(selector, "hover") and hasattr(selector, "click"):
        element = selector.first if hasattr(selector, "first") else selector
    else:
        element = page.locator(selector).first
    try:
        await element.hover()
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await element.click()
    except Exception:
        try:
            await element.click(force=True)
        except Exception:
            raise

async def click_next(page):
    """Click the Next button if present, otherwise press Enter."""
    next_button = page.locator(NEXT_BUTTON_SEL)
    if await next_button.count() > 0:
        try:
            if await next_button.first.is_visible():
                await human_click(page, next_button)
                return True
        except Exception:
            try:
                await next_button.first.click()
                return True
            except Exception:
                pass
    try:
        await page.keyboard.press("Enter")
        return True
    except Exception:
        return False

async def random_mouse_noise(page):
    """Performs small random mouse movements to simulate human presence."""
    try:
        x, y = random.randint(100, 1000), random.randint(100, 700)
        await page.mouse.move(x, y, steps=10)
    except Exception:
        pass

async def select_dropdown_option(page, button_selector, option_texts, fallback_index=None):
    """Select an option from a custom dropdown (combobox)."""
    button = page.locator(button_selector).first
    if await button.count() == 0:
        return False

    async def open_dropdown():
        try:
            await button.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            await human_click(page, button)
        except Exception:
            try:
                await button.click(force=True)
            except Exception:
                return False
        await asyncio.sleep(random.uniform(0.4, 0.8))
        try:
            await page.wait_for_selector('[role="listbox"]:visible, [role="option"]:visible', timeout=5000)
        except Exception:
            pass
        return True

    for attempt in range(3):
        if not await open_dropdown():
            return False
        listbox = page.locator('[role="listbox"]:visible')
        has_listbox = await listbox.count() > 0
        container = listbox.first if has_listbox else page
        try:
            option_count = await container.locator('[role="option"]:visible').count()
        except Exception:
            option_count = 0

        if option_count > 100:
            await close_open_listbox(page)
            continue

        for text in option_texts:
            option = container.locator(f'[role="option"]:visible:has-text("{text}")')
            if await option.count() == 0:
                option = page.locator(f'[role="option"]:visible:has-text("{text}")')
            if await option.count() == 0 and not has_listbox:
                option = container.locator(f'button:visible:has-text("{text}")')
            if await option.count() > 0:
                try:
                    await human_click(page, option.first)
                    return True
                except Exception:
                    try:
                        await option.first.click()
                        return True
                    except Exception:
                        return False

        if fallback_index is not None:
            try:
                await button.focus()
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
                for _ in range(int(fallback_index)):
                    await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                return True
            except Exception:
                return False

        await close_open_listbox(page)

    return False

async def close_open_listbox(page):
    """Close any visible listbox overlays if present."""
    listbox = page.locator('[role="listbox"]:visible')
    if await listbox.count() == 0:
        return
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    await page.wait_for_timeout(300)

async def combobox_has_value(page, selector) -> bool:
    """Check if a combobox button shows a selected value."""
    button = page.locator(selector).first
    if await button.count() == 0:
        return False
    try:
        text = (await button.inner_text()).strip()
    except Exception:
        text = ""
    try:
        value = (await button.get_attribute("value") or "").strip()
    except Exception:
        value = ""
    return bool(text or value)

HUMAN_IFRAME_SEL = (
    'iframe[src*="hsprotect.net"], iframe[title*="Human"], '
    'iframe[src*="arkoselabs"], iframe[src*="hcaptcha"], iframe[src*="recaptcha"]'
)

async def wait_for_human_verification(page, timeout_ms=600000) -> bool:
    """Wait for human verification iframe to disappear if present."""
    human_iframe = page.locator(HUMAN_IFRAME_SEL)
    if await human_iframe.count() == 0:
        return True
    logger.warning("Human verification detected, waiting for manual completion...")
    start = time.monotonic()
    while (time.monotonic() - start) * 1000 < timeout_ms:
        try:
            if await human_iframe.count() == 0:
                return True
            if await human_iframe.first.is_visible() is False:
                return True
        except Exception:
            return True
        await page.wait_for_timeout(2000)
    return False

async def accept_consent_if_present(page, timeout_ms=5000) -> bool:
    """Accept consent screens when they appear."""
    selectors = [
        'button#nextButton:has-text("同意并继续")',
        'button:has-text("同意并继续")',
        'button:has-text("Accept")',
        'button:has-text("Agree")',
    ]
    pipl_btn = page.locator(", ".join(selectors))
    if await pipl_btn.count() == 0:
        return False
    try:
        await pipl_btn.first.wait_for(state="visible", timeout=timeout_ms)
        if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
            if not await wait_for_human_verification(page):
                return False
        await pipl_btn.first.scroll_into_view_if_needed()
        await pipl_btn.first.click(timeout=5000)
        await page.wait_for_timeout(1000)
        return True
    except Exception as e:
        logger.warning("PIPL consent click failed: %s", e)
        return False

async def accept_consent_with_retry(page, timeout_ms=20000) -> bool:
    """Retry consent acceptance for a short window after page transitions."""
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if await accept_consent_if_present(page, timeout_ms=2000):
            return True
        await page.wait_for_timeout(500)
    return False

async def settle_interstitials(page, save_debug_info, account) -> tuple:
    """Handle consent pages and human verification if they appear."""
    if await accept_consent_if_present(page):
        logger.info("Consent accepted.")
        await page.wait_for_load_state("domcontentloaded")
    return True, "", account

async def wait_for_and_accept_consent(page, timeout_ms=30000) -> bool:
    """Wait for a consent page to appear and accept it."""
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if await accept_consent_if_present(page, timeout_ms=2000):
            return True
        await page.wait_for_timeout(500)
    return False

def generate_credentials():
    """Generate random credentials."""
    first_name = fake.first_name()
    last_name = fake.last_name()
    # Add some random numbers to ensure uniqueness
    username_only = f"{first_name.lower()}{last_name.lower()}{random.randint(1000, 99999)}"
    # Microsoft requires complex passwords
    password = fake.password(length=12, special_chars=True, digits=True, upper_case=True, lower_case=True)
    return {
        "first_name": first_name,
        "last_name": last_name,
        "username_only": username_only,
        "email": f"{username_only}@outlook.com",
        "password": password,
        "birth_day": str(random.randint(1, 28)),
        "birth_month": str(random.randint(1, 12)),
        "birth_year": str(random.randint(1980, 2005))
    }

def save_to_excel(account_data):
    """Save account data to Excel file."""
    try:
        if os.path.exists(EXCEL_FILE):
            df = pd.read_excel(EXCEL_FILE)
            new_df = pd.DataFrame([account_data])
            df = pd.concat([df, new_df], ignore_index=True)
        else:
            df = pd.DataFrame([account_data])
        
        df.to_excel(EXCEL_FILE, index=False)
        logger.info(f"Account saved to {EXCEL_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to Excel: {e}")
        return False

async def run_registration_flow():
    """
    Runs the Outlook registration flow with high stealth.
    Returns a tuple: (success_bool, message_string, account_data_dict)
    """
    async with registration_lock:
        account = generate_credentials()
        logger.info(f"Starting registration for: {account['email']}")

        async def save_debug_info(page, name):
            try:
                await page.screenshot(path=f"{name}.png")
                with open(f"{name}.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                logger.error(f"Debug info saved to {name}.png and {name}.html. URL: {page.url}")
            except Exception as e:
                logger.error(f"Failed to save debug info: {e}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False, 
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--use-fake-ui-for-media-stream",
                    "--no-sandbox"
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            
            # Advanced Stealth Init Script
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
            
            page = await context.new_page()

            try:
                logger.info(f"Navigating to {SIGNUP_URL}...")
                await page.goto(SIGNUP_URL, timeout=60000)
                await page.wait_for_load_state("networkidle")
                await random_mouse_noise(page)

                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account
                if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
                    if not await wait_for_human_verification(page):
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete it in the browser and try again.", account

                # 1. Email Page
                logger.info("Filling Email...")
                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account
                if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
                    if not await wait_for_human_verification(page):
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete it in the browser and try again.", account

                pipl_form = page.locator('form[data-testid="china-pipl-form"]')
                if await pipl_form.count() > 0 and await pipl_form.first.is_visible():
                    await save_debug_info(page, "error_pipl_consent")
                    return False, "PIPL consent required. Please click '同意并继续' in the opened browser window.", account
                # Try to handle login page redirect
                try:
                    create_link = page.locator('#signup, a:has-text("创建一个"), a:has-text("Create one")')
                    if await create_link.count() > 0 and await create_link.first.is_visible(timeout=2000):
                        await human_click(page, create_link)
                        await page.wait_for_load_state('networkidle')
                except Exception: pass

                switch_to_email = page.locator('#liveSwitch, #signup-with-email, a:has-text("获得新的电子邮件地址"), a:has-text("Get a new email")')
                if await switch_to_email.count() > 0 and await switch_to_email.first.is_visible(timeout=5000):
                    await human_click(page, switch_to_email)
                    await asyncio.sleep(random.uniform(1.0, 2.0))

                email_input_sel = (
                    'input[name="MemberName"], input[type="email"], #MemberName, '
                    'input[aria-label="电子邮件"], #floatingLabelInput6'
                )
                try:
                    await page.wait_for_selector(email_input_sel, state='visible', timeout=30000)
                except Exception:
                    human_iframe = page.locator(HUMAN_IFRAME_SEL)
                    if await human_iframe.count() > 0:
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete the CAPTCHA in the opened browser window and try again.", account
                    await save_debug_info(page, "error_email_input")
                    return False, "Email input not found. The sign-up flow may have changed or is blocked.", account
                email_input = page.locator(email_input_sel).first
                domain_picker = page.locator(
                    'select[id*="domain"], select[name*="domain"], #domain, #Domain, '
                    'button:has-text("@outlook"), button:has-text("@hotmail")'
                )
                input_type = (await email_input.get_attribute("type") or "").lower()
                use_full_email = input_type == "email" or await domain_picker.count() == 0
                email_value = account['email'] if use_full_email else account['username_only']
                await human_type(page, email_input_sel, email_value)
                await asyncio.sleep(random.uniform(0.8, 1.5))
                next_button = page.locator(NEXT_BUTTON_SEL)
                if await next_button.count() > 0 and await next_button.first.is_visible():
                    await human_click(page, next_button)
                else:
                    await page.keyboard.press("Enter")

                # Check for validation/taken username
                await asyncio.sleep(2)
                validation = page.locator('#MemberNameError, #field-7__validationMessage, [role="alert"]')
                if await validation.count() > 0:
                    try:
                        message = (await validation.first.inner_text()).strip()
                    except Exception:
                        message = ""
                    if message:
                        if "someone@example.com" in message or "电子邮件地址" in message or "email address" in message:
                            await page.click(email_input_sel)
                            await page.keyboard.press("Control+A")
                            await page.keyboard.type(account['email'], delay=random.randint(50, 150))
                            await asyncio.sleep(random.uniform(0.5, 1.0))
                            await click_next(page)
                            await asyncio.sleep(2)
                            if await validation.count() > 0:
                                followup = (await validation.first.inner_text()).strip()
                                if "已被使用" in followup or "taken" in followup or "exists" in followup:
                                    return False, "Email already taken.", account
                        elif "已被使用" in message or "taken" in message or "exists" in message:
                            return False, "Username already taken.", account

                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account

                # 2. Password Page
                logger.info("Filling Password...")
                pass_input_sel = 'input[name="PasswordInput"], input[type="password"], #PasswordInput'
                await page.wait_for_selector(pass_input_sel, state='visible', timeout=20000)
                await human_type(page, pass_input_sel, account['password'])
                await asyncio.sleep(random.uniform(0.5, 1.2))
                await page.keyboard.press("Enter")

                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account
                if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
                    if not await wait_for_human_verification(page):
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete it in the browser and try again.", account

                # 3. Name Page
                logger.info("Filling Name...")
                fn_input_sel = 'input[id*="firstName"], input[name*="FirstName"]'
                await page.wait_for_selector(fn_input_sel, state='visible', timeout=20000)
                await human_type(page, fn_input_sel, account['first_name'])
                await human_type(page, 'input[id*="lastName"], input[name*="LastName"]', account['last_name'])
                await asyncio.sleep(random.uniform(0.5, 1.0))
                await click_next(page)

                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account
                if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
                    if not await wait_for_human_verification(page):
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete it in the browser and try again.", account

                # 4. DOB Page
                logger.info("Filling DOB...")
                await close_open_listbox(page)
                year_input_sel = (
                    'input[name="BirthYear"], input[aria-label*="出生年份"], '
                    'input[id*="BirthYear"], input[id*="birthYear"]'
                )
                await page.wait_for_selector(year_input_sel, state='visible', timeout=20000)
                await human_type(page, year_input_sel, account['birth_year'])

                month_value = str(int(account['birth_month']))
                day_value = str(int(account['birth_day']))
                await close_open_listbox(page)
                month_select = page.locator('select[id*="birthMonth"], select[name*="BirthMonth"], select[id*="BirthMonth"]')
                day_select = page.locator('select[id*="birthDay"], select[name*="BirthDay"], select[id*="BirthDay"]')
                if await month_select.count() > 0:
                    await page.select_option(month_select.first, value=month_value)
                else:
                    month_texts = [f"{month_value}月", f"{month_value} 月", month_value]
                    await close_open_listbox(page)
                    ok = await select_dropdown_option(
                        page,
                        '#BirthMonthDropdown, button[aria-label*="出生月份"], button[aria-label*="月"]',
                        month_texts,
                        fallback_index=month_value
                    )
                    if not ok or not await combobox_has_value(page, '#BirthMonthDropdown'):
                        await save_debug_info(page, "error_birth_month")
                        logger.warning("Birth month not selected, waiting for manual input...")
                        try:
                            await page.wait_for_function(
                                "() => { const m = document.querySelector('#BirthMonthDropdown'); return m && m.textContent.trim().length > 0; }",
                                timeout=300000
                            )
                        except Exception:
                            return False, "Birth month selection failed. Please select month/day manually in the browser and try again.", account

                if await day_select.count() > 0:
                    await page.select_option(day_select.first, value=day_value)
                else:
                    day_texts = [f"{day_value}日", f"{day_value} 日", day_value]
                    await close_open_listbox(page)
                    ok = await select_dropdown_option(
                        page,
                        '#BirthDayDropdown, button[aria-label*="出生日期"], button[aria-label*="日"]',
                        day_texts,
                        fallback_index=day_value
                    )
                    if not ok or not await combobox_has_value(page, '#BirthDayDropdown'):
                        await save_debug_info(page, "error_birth_day")
                        logger.warning("Birth day not selected, waiting for manual input...")
                        try:
                            await page.wait_for_function(
                                "() => { const d = document.querySelector('#BirthDayDropdown'); return d && d.textContent.trim().length > 0; }",
                                timeout=300000
                            )
                        except Exception:
                            return False, "Birth day selection failed. Please select month/day manually in the browser and try again.", account

                await asyncio.sleep(random.uniform(0.5, 1.5))
                await click_next(page)

                ok, msg, _ = await settle_interstitials(page, save_debug_info, account)
                if not ok:
                    return False, msg, account
                await accept_consent_with_retry(page, timeout_ms=30000)
                if await page.locator('button#nextButton:has-text("同意并继续")').count() > 0:
                    await wait_for_and_accept_consent(page, timeout_ms=30000)
                await page.wait_for_timeout(1000)
                if await page.locator(HUMAN_IFRAME_SEL).count() > 0:
                    if not await wait_for_human_verification(page):
                        await save_debug_info(page, "error_human_check")
                        return False, "Human verification detected. Please complete it in the browser and try again.", account

                # Block check
                await asyncio.sleep(3)
                content = await page.content()
                if "blocked" in content.lower() or "unusual activity" in content.lower():
                    await save_debug_info(page, "error_account_blocked")
                    return False, "Account creation blocked by security.", account

                save_to_excel(account)
                logger.info("Waiting for manual CAPTCHA solving...")
                
                try:
                    # Wait for redirect to inbox or stay-signed-in page
                    await page.wait_for_url(lambda url: "outlook.live.com" in url or "kmsi" in url or "SummaryPage" in url, timeout=300000)
                    return True, "Registration successful!", account
                except Exception:
                    return False, "Timed out waiting for completion.", account

            except Exception as e:
                await save_debug_info(page, "error_flow")
                return False, f"Flow error: {str(e)}", account
            finally:
                await browser.close()
