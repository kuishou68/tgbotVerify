import asyncio
import logging
import sys
import os

# 将当前目录加入路径以便导入
sys.path.append(os.getcwd())

from outlook.register import run_registration_flow
from playwright.async_api import async_playwright

# 配置日志到控制台
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def self_test():
    logger.info("开始自动化注册流程自测...")
    
    # 我们修改逻辑，仅测试前几步，避免触发复杂的验证码流程
    # 并且使用 headless=True 因为当前环境可能没有显示器
    try:
        # 注意：这里我们直接调用逻辑，但为了测试，我们临时修改代码中的 headless 参数
        # 或者我们写一个精简版的测试逻辑
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            url = "https://signup.live.com/signup"
            logger.info(f"正在访问: {url}")
            await page.goto(url, timeout=60000)
            
            logger.info(f"实际到达 URL: {page.url}")
            
            # 1. 检查是否在登录页，若是则寻找“创建一个”
            if "login.live.com" in page.url and "signup" not in page.url:
                logger.info("检测到重定向至登录页，寻找注册链接...")
                create_link = page.locator('#signup, a:has-text("Create one!"), a:has-text("创建一个!"), a:has-text("立即创建一个")')
                if await create_link.count() > 0:
                    logger.info("找到注册链接，点击跳转...")
                    await create_link.first.click()
                    await page.wait_for_load_state('networkidle')
            
            # 2. 检查“获取新的电子邮件地址”
            switch_to_email = page.locator('#liveSwitch, #signup-with-email, a:has-text("Get a new email address"), a:has-text("获得新的电子邮件地址")')
            if await switch_to_email.count() > 0:
                logger.info("找到‘获取新邮箱’切换按钮，执行切换...")
                await switch_to_email.first.click()
                await asyncio.sleep(1)

            # 3. 寻找输入框
            email_input = page.locator('input[name="MemberName"], input[type="email"], input[aria-label="New email"]')
            await email_input.first.wait_for(state='visible', timeout=20000)
            logger.info("✅ 成功定位到邮箱输入框！")
            
            await email_input.first.fill("testuser" + str(os.getpid()))
            logger.info("✅ 成功模拟填入用户名。")
            
            await browser.close()
            logger.info("自测成功结束。")
            return True
            
    except Exception as e:
        logger.error(f"❌ 自测失败: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(self_test())
