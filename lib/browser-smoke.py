"""Local, network-free browser startup qualification."""
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("<title>browser-gate-ok</title><p>Ready</p>")
    assert page.title() == "browser-gate-ok"
    assert page.locator("p").inner_text() == "Ready"
    browser.close()
print("PASS: Playwright Chromium startup and DOM execution")
