"""教师证明文档生成（PDF + PNG）"""
import random
from datetime import datetime
from io import BytesIO
from pathlib import Path


def _render_template(first_name: str, last_name: str) -> str:
    """读取模板，替换姓名/工号/日期，并展开 CSS 变量。"""
    full_name = f"{first_name} {last_name}"
    employee_id = random.randint(1000000, 9999999)
    current_date = datetime.now().strftime("%m/%d/%Y %I:%M %p")

    template_path = Path(__file__).parent / "card-temp.html"
    html = template_path.read_text(encoding="utf-8")

    # 展开 CSS 变量，兼容 xhtml2pdf
    color_map = {
        "var(--primary-blue)": "#0056b3",
        "var(--border-gray)": "#dee2e6",
        "var(--bg-gray)": "#f8f9fa",
    }
    for placeholder, color in color_map.items():
        html = html.replace(placeholder, color)

    # 替换示例姓名 / 员工号 / 日期（模板里出现两处姓名 + span）
    html = html.replace("Sarah J. Connor", full_name)
    html = html.replace("E-9928104", f"E-{employee_id}")
    html = html.replace('id="currentDate"></span>', f'id="currentDate">{current_date}</span>')

    return html


def _get_playwright() -> "object":
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "需要安装 playwright，请执行 `pip install playwright` 然后 `playwright install chromium`"
        ) from exc
    return sync_playwright


def generate_teacher_pdf(first_name: str, last_name: str) -> bytes:
    """使用 Playwright 渲染 HTML 并生成 PDF 字节。"""
    html = _render_template(first_name, last_name)

    sync_playwright = _get_playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 1000})
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(500)  # 让样式稳定
        pdf_bytes = page.pdf(format="A4", print_background=True)
        browser.close()

    return pdf_bytes


def generate_teacher_png(first_name: str, last_name: str) -> bytes:
    """使用 Playwright 截图生成 PNG（需要 playwright + chromium 已安装）。"""
    sync_playwright = _get_playwright()
    html = _render_template(first_name, last_name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 1000})
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(500)  # 让样式稳定
        card = page.locator(".browser-mockup")
        png_bytes = card.screenshot(type="png")
        browser.close()

    return png_bytes


# 兼容旧调用：默认生成 PDF
def generate_teacher_image(first_name: str, last_name: str) -> bytes:
    return generate_teacher_pdf(first_name, last_name)
