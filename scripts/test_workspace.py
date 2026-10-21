"""Real local browser smoke checks. No model calls, no mocked HTTP responses."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "var/screenshots"
OUTPUT.mkdir(parents=True, exist_ok=True)
checks = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:5173")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("button", name="Open local workspace")).to_be_visible()
    page.get_by_role("button", name="Open local workspace").click()
    expect(page.get_by_role("heading", name="Materials", exact=True)).to_be_visible()
    expect(page.locator(".material-row")).to_have_count(11)
    checks.append("Local session and 11 real material rows")
    page.screenshot(path=str(OUTPUT / "materials-desktop.png"), full_page=True)
    search = page.get_by_role("textbox", name="Search materials")
    search.fill("Topic 2 - Lecture 2")
    expect(page.locator(".material-row")).to_have_count(1)
    row = page.locator(".material-row")
    row.locator(".type-button").click()
    expect(page.get_by_role("dialog", name="Material type")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Material type")).not_to_be_visible()
    checks.append("Classification dialog keyboard dismissal")
    row.get_by_role("button", name="View source:").click()
    page.get_by_role("spinbutton", name="PDF page").fill("14")
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("14")
    image = page.get_by_role("img", name="Original PDF page 14", exact=False)
    expect(image).to_be_visible()
    page.wait_for_function("document.querySelector('.source-image img')?.naturalWidth > 0")
    url = page.url
    page.screenshot(path=str(OUTPUT / "source-desktop.png"))
    page.reload()
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("14")
    assert page.url == url
    checks.append("Physical page 14 and fixed source URL survive refresh")
    page.get_by_role("link", name="Processing task").click()
    expect(page.get_by_role("heading", name="Complete", exact=True)).to_be_visible()
    task_url = page.url
    page.reload()
    expect(page.get_by_role("heading", name="Complete", exact=True)).to_be_visible()
    assert page.url == task_url
    page.get_by_role("link", name="Back to materials").click()
    page.wait_for_url("**/materials")
    expect(page.get_by_role("heading", name="Materials", exact=True)).to_be_visible()
    checks.append("Processing task navigation and task identity survive refresh")
    search.fill("no such material")
    expect(search).to_have_value("no such material")
    expect(page.get_by_role("heading", name="No matching materials")).to_be_visible()
    search.fill("")
    checks.append("Search empty state and recovery")
    fixture = json.loads((ROOT / "backend/tests/fixtures/qm_manifest.json").read_text())[0]
    page.locator('input[type="file"]').set_input_files([
        {"name": Path(fixture["path"]).name, "mimeType": "application/pdf",
         "buffer": (ROOT / "Quantitaive methods" / fixture["path"]).read_bytes()},
        {"name": "invalid.pdf", "mimeType": "application/pdf", "buffer": b"not a PDF"},
    ])
    expect(page.get_by_text("Already imported — original path retained")).to_be_visible()
    expect(page.get_by_role("button", name="Retry upload")).to_be_visible()
    expect(page.locator(".material-row")).to_have_count(11)
    checks.append("Mixed upload retains successful duplicate and shows per-file failure")
    page.reload()
    expect(page.locator(".material-row")).to_have_count(11)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUTPUT / "materials-mobile.png"), full_page=True)
    search.fill("Topic 2 - Lecture 2")
    page.get_by_role("button", name="View source:").click()
    expect(page.get_by_role("button", name="Close source")).to_be_visible()
    page.screenshot(path=str(OUTPUT / "source-mobile.png"))
    checks.append("390px layout and source dialog have no page overflow")
    assert not errors, errors
    checks.append("No browser runtime errors")
    browser.close()
(ROOT / "var/browser-checks.json").write_text(json.dumps({"mode": "real_local_no_models", "passed": checks}, indent=2))
print(json.dumps({"passed": len(checks), "checks": checks}, indent=2))
