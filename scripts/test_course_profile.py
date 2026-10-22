"""Live local UI checks; edits use a separate FIXTURE course, never the real QM draft.
One deliberately aborted local save simulates a network failure. No model calls.
"""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "var/screenshots"
OUTPUT.mkdir(exist_ok=True, parents=True)
fixture = json.loads((ROOT / "var/batch2-browser-fixture.json").read_text(encoding="utf-8"))
BASE = "http://127.0.0.1:5173"
QM = "68caa35d-6e08-42d7-84bd-70a23e369b1f"
checks = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Open local workspace").click()
    expect(page.get_by_role("heading", name="Materials", exact=True)).to_be_visible()
    page.goto(f"{BASE}/courses/{QM}/profile")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Real model draft · review required", exact=True)).to_be_visible()
    expect(page.locator(".knowledge-card")).to_have_count(8)
    expect(page.get_by_role("button", name="Review & confirm")).to_be_disabled()
    expect(page.get_by_text("Review the existing source page images for missing mathematical notation.", exact=True)).to_be_visible()
    page.screenshot(path=str(OUTPUT / "course-profile-desktop.png"), full_page=True)
    checks.append("Real model draft: eight groups, truthful gaps, confirmation blocked")
    page.get_by_role("button", name="M35 · p4", exact=True).first.click()
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("4")
    page.wait_for_function("document.querySelector('.source-image img')?.naturalWidth > 0")
    source_url = page.url
    page.reload()
    expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("4")
    assert page.url == source_url
    page.get_by_role("button", name="Close source").click()
    checks.append("Exact saved source version/page opens and survives refresh")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUTPUT / "course-profile-mobile.png"), full_page=True)
    checks.append("Real profile at 390px without horizontal overflow")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{BASE}/courses/{fixture['course_id']}/profile")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Fixture data · not a real model result", exact=True)).to_be_visible()
    requirement = page.get_by_label("Learning requirements", exact=True)
    requirement.fill("Browser-tested saved requirement")
    expect(page.locator(".save-bar strong")).to_have_text("Saved")
    page.reload()
    expect(requirement).to_have_value("Browser-tested saved requirement")
    checks.append("Fixture edit autosaves and survives reload")
    save_url = f"**/api/v1/courses/{fixture['course_id']}/draft"
    page.route(save_url, lambda route: route.abort("failed"))
    requirement.fill("Retained after simulated network failure")
    expect(page.locator(".save-bar strong")).to_have_text("Could not save — Retry")
    expect(requirement).to_have_value("Retained after simulated network failure")
    expect(page.get_by_role("button", name="Review & confirm")).to_be_disabled()
    page.unroute(save_url)
    page.get_by_role("button", name="Save changes", exact=True).click()
    expect(page.locator(".save-bar strong")).to_have_text("Saved")
    checks.append("Simulated failed save retains input, blocks confirmation and safely retries")
    second = context.new_page()
    second.goto(page.url)
    second.wait_for_load_state("networkidle")
    page.get_by_label("Course title", exact=True).fill("Fixture title saved in tab one")
    expect(page.locator(".save-bar strong")).to_have_text("Saved")
    second.get_by_label("Course title", exact=True).fill("Fixture title reconciled in tab two")
    expect(second.get_by_role("heading", name="Compare before saving")).to_be_visible()
    expect(second.get_by_role("button", name="Review & confirm")).to_be_disabled()
    second.get_by_role("button", name="Keep my edits on latest version").click()
    expect(second.locator(".save-bar strong")).to_have_text("Saved")
    expect(second.get_by_label("Course title", exact=True)).to_have_value("Fixture title reconciled in tab two")
    second.close()
    page.reload()
    expect(page.get_by_label("Course title", exact=True)).to_have_value("Fixture title reconciled in tab two")
    checks.append("Two real tabs trigger revision conflict; explicit merge keeps local edits")
    page.get_by_role("button", name="Review & confirm").click()
    expect(page.get_by_role("dialog", name="Confirm this course version")).to_be_visible()
    page.get_by_role("button", name="Confirm course", exact=True).click()
    expect(page.get_by_role("heading", name="Course version 1 confirmed")).to_be_visible()
    first_version = parse_qs(urlparse(page.url).query)["courseVersion"][0]
    first_url = f"{BASE}/api/v1/courses/{fixture['course_id']}/versions/{first_version}"
    frozen = context.request.get(first_url).json()
    page.get_by_role("link", name="Return to course profile").click()
    page.wait_for_load_state("networkidle")
    requirement.fill("Changed after the first confirmation")
    expect(page.locator(".save-bar strong")).to_have_text("Saved")
    page.get_by_role("button", name="Review & confirm").click()
    page.get_by_role("button", name="Confirm course", exact=True).click()
    expect(page.get_by_role("heading", name="Course version 2 confirmed")).to_be_visible()
    assert context.request.get(first_url).json()["frozen_payload"] == frozen["frozen_payload"]
    checks.append("Confirmation uses a saved revision; later edits leave version 1 unchanged")
    page.get_by_role("link", name="Return to course profile").click()
    page.wait_for_load_state("networkidle")
    page.get_by_label("Answer", exact=True).fill("A synthetic clarification answer")
    with page.expect_response("**/answers") as response:
        page.get_by_role("button", name="Save answer", exact=True).click()
    assert response.value.ok, {"status": response.value.status, "request": response.value.request.post_data_json, "response": response.value.json()}
    expect(page.get_by_role("button", name="Save answer", exact=True)).to_have_count(0)
    expect(page.get_by_text("A synthetic clarification answer", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Review & confirm")).to_be_disabled()
    page.reload()
    expect(page.get_by_text("A synthetic clarification answer", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Save answer", exact=True)).to_have_count(0)
    checks.append("Answer is saved once, survives refresh, and awaits analysis without repeated questioning")
    assert not errors, errors
    checks.append("No browser runtime exceptions")
    browser.close()

result = {"mode": "real_local_ui_with_separate_fixture_course", "model_calls": 0,
    "simulated_conditions": ["aborted local save request"], "fixture_course_id": fixture["course_id"], "passed": checks}
(ROOT / "var/batch2-browser-checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"passed": len(checks), "checks": checks}, indent=2))
