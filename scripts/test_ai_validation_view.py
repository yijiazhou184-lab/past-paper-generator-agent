"""Inspect a saved real validation task in the running local app; no API/model calls are submitted."""
import argparse
import json
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task_id", type=uuid.UUID)
args = parser.parse_args()
checks = []
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:5173/tasks/{args.task_id}")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Open local workspace").click()
    expect(page.get_by_role("heading", name="Complete", exact=True)).to_be_visible()
    expect(page.locator(".model-call")).to_have_count(6)
    checks.append("Six saved live call records")
    page.reload()
    expect(page.locator(".model-call")).to_have_count(6)
    checks.append("Task and call records survive refresh")
    call = page.locator(".model-call").filter(has=page.get_by_role("heading", name="M33-p22", exact=False))
    call.locator("summary").click()
    expect(call.locator("pre")).to_contain_text("source_issue")
    page.screenshot(path=str(ROOT / "var/screenshots/ai-validation-desktop.png"), full_page=True)
    checks.append("Real source-issue interpretation is inspectable")
    call.get_by_role("link", name="View exact source page").click()
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("22")
    expect(page.get_by_role("heading", name="MSIN0180 Math Background for topic 2 11_01_2026.pdf", exact=True)).to_be_visible()
    source_url = page.url
    page.reload()
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("22")
    assert page.url == source_url
    checks.append("Model result opens the exact original version/page and survives refresh")
    page.get_by_role("button", name="Close source").click()
    links = page.get_by_role("link", name="View saved call records")
    target = links.filter(has_text="View saved call records").locator(f'xpath=self::a[contains(@href,"{args.task_id}")]')
    # The saved task URL is observed above and its link is visible in the Materials list.
    expect(target).to_have_count(1)
    target.click()
    expect(page.locator(".model-call")).to_have_count(6)
    checks.append("Materials can recover the completed validation")
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator(".model-call").filter(has=page.get_by_role("heading", name="M33-p22", exact=False)).locator("summary").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "var/screenshots/ai-validation-mobile.png"), full_page=True)
    checks.append("Expanded results fit a 390px viewport")
    assert not errors, errors
    checks.append("No browser runtime errors")
    browser.close()
output = ROOT / f"var/ai-validation-browser-{args.task_id}.json"
output.write_text(json.dumps({"mode": "real_local_read_only", "passed": checks}, indent=2), encoding="utf-8")
print(json.dumps({"passed": len(checks), "checks": checks}, indent=2))
