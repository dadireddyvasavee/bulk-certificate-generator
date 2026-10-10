"""Optional Playwright workflow against the real running frontend/API/worker."""
from playwright.sync_api import sync_playwright
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:5173/new")
    page.get_by_label("Event or course").fill("Browser workflow")
    page.get_by_label("Organization", exact=True).fill("Learning Lab")
    page.get_by_label("Name 1", exact=True).fill("Alex Rivera")
    page.get_by_label("Email 1", exact=True).fill("alex@example.com")
    page.get_by_role("button", name="Add recipient").click()
    page.get_by_label("Name 2", exact=True).fill("Sam Taylor")
    page.get_by_label("Email 2", exact=True).fill("sam@example.com")
    page.get_by_role("button", name="Review batch").click()
    page.get_by_role("button", name="Generate certificates").click()
    page.wait_for_url("**/jobs/*")
    page.get_by_text("Download successful certificates (ZIP)", exact=True).wait_for(timeout=60000)
    with page.expect_download() as event:
        page.get_by_text("Download successful certificates (ZIP)", exact=True).click()
    assert event.value.suggested_filename.endswith(".zip")
    page.reload()
    page.get_by_text("Alex Rivera", exact=True).wait_for()
    print("PASS: browser create, progress, ZIP download and refresh")
    browser.close()
