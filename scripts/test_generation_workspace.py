"""Batch-3 local UI acceptance. Real backend/queue; synthetic course, no model requests.
One deliberately aborted local write tests recovery. The real QM course is read only.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
fixture = json.loads((ROOT / "var/batch3-browser-fixture.json").read_text(encoding="utf-8"))
BASE = "http://127.0.0.1:5173"
URL = fixture["url"]
OUT = ROOT / "var/screenshots"
OUT.mkdir(exist_ok=True, parents=True)
checks = []


def plan(page, count):
    page.get_by_role("button", name="Review structure", exact=True).click()
    expect(page.get_by_role("heading", name="Review planning inputs")).to_be_visible()
    expect(page.get_by_text("No raw page text or new page images are sent.", exact=False)).to_be_visible()
    page.get_by_role("button", name="Plan with local fixture").click()
    expect(page.get_by_role("heading", name="Review planning inputs")).not_to_be_visible(timeout=15000)
    page.reload()
    expect(page.locator(".blueprint-question")).to_have_count(count, timeout=45000)
    expect(page.get_by_role("button", name="Confirm structure", exact=True)).to_be_enabled(timeout=15000)


def confirm(page):
    page.get_by_role("button", name="Confirm structure", exact=True).click()
    page.get_by_role("button", name="Confirm reviewed structure").click()
    expect(page.get_by_text("Structure confirmed", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Prepare generation", exact=True)).to_be_enabled()


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Open local workspace").click()
    expect(page.get_by_role("heading", name="Materials", exact=True)).to_be_visible()
    try:
        page.goto(f"{BASE}/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Confirm your course first")).to_be_visible()
        expect(page.get_by_role("button", name="Review structure", exact=True)).to_have_count(0)
        checks.append("Real QM: no confirmed version, no model planning action; read only")
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Fixture data · no model call", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Prepare generation", exact=True)).to_be_disabled()
        plan(page, 3)
        checks.append("Persisted planning task through real worker; refresh restores three-question fixture structure")

        page.get_by_label("Q1 (a) marks", exact=True).fill("3.5")
        page.get_by_label("Suggested minutes", exact=True).fill("45")
        expect(page.get_by_role("button", name="Confirm structure", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Save structure", exact=True).click()
        expect(page.get_by_role("button", name="Save structure", exact=True)).to_have_count(0)
        expect(page.get_by_label("Suggested minutes", exact=True)).to_have_value("45")
        expect(page.locator(".structure-numbers")).to_contain_text("24")
        checks.append("Structure edits invalidate confirmation; server recalculates marks and saves a new revision")

        page.get_by_label("Answer rule for Topic 2 practice").select_option("choose")
        page.get_by_role("button", name="Save structure", exact=True).click()
        expect(page.get_by_text("Every permitted choice must have the same total marks.", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Confirm structure", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Discard structure edits").click()
        checks.append("Unequal choice marks rejected with readable error; invalid structure cannot be confirmed")

        confirm(page)
        page.reload()
        expect(page.get_by_role("button", name="Prepare generation", exact=True)).to_be_enabled()
        page.get_by_role("button", name="Prepare generation", exact=True).click()
        expect(page.get_by_role("heading", name="Generation inputs saved")).to_be_visible()
        first_snapshot_url = page.url
        page.reload()
        expect(page.get_by_role("heading", name="Generation inputs saved")).to_be_visible()
        expect(page.get_by_text("No questions, answers or PDFs have been generated.", exact=False)).to_be_visible()
        page.get_by_role("button", name="Close snapshot").click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        checks.append("Confirmed binding and immutable snapshot survive reload; future generation boundary remains explicit")

        count = page.get_by_role("spinbutton", name=re.compile("Main questions"))
        count.fill("4")
        expect(page.get_by_role("button", name="Prepare generation", exact=True)).to_be_disabled()
        count.fill("3")
        expect(page.get_by_role("button", name="Prepare generation", exact=True)).to_be_disabled()
        expect(page.get_by_text("Configuration changed — review the updated structure", exact=True)).to_be_visible()
        page.get_by_role("button", name="Save configuration", exact=True).click()
        expect(page.locator(".config-save-status")).to_contain_text("Configuration saved")
        expect(page.get_by_role("button", name="Confirm structure", exact=True)).to_have_count(0)
        checks.append("3 → 4 → 3 invalidates confirmation locally and after saving; old structure is not revived")

        count.fill("4")
        page.get_by_role("button", name="Save configuration", exact=True).click()
        expect(page.locator(".config-save-status")).to_contain_text("Configuration saved")
        plan(page, 4)
        expect(page.locator(".structure-differences")).to_contain_text("Main questions: 3 → 4")
        checks.append("Four questions produce a new structure and a computed difference from the previous plan")

        page.get_by_role("link", name="FX01 · p1", exact=True).first.click()
        expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("1")
        page.wait_for_function("document.querySelector('.source-image img')?.naturalWidth > 0")
        assert fixture["source_id"] in page.url
        page.reload()
        expect(page.get_by_role("spinbutton", name="PDF page")).to_have_value("1")
        page.get_by_role("button", name="Close source").click()
        page.goto(URL)
        expect(page.locator(".blueprint-question")).to_have_count(4)
        checks.append("Blueprint source link opens exact synthetic PDF version/page and survives refresh")

        second = context.new_page()
        second.goto(URL)
        second.wait_for_load_state("networkidle")
        second.get_by_label("Difficulty", exact=True).select_option("challenge")
        page.get_by_label("Difficulty", exact=True).select_option("foundation")
        page.get_by_role("button", name="Save configuration", exact=True).click()
        expect(page.locator(".config-save-status")).to_contain_text("Configuration saved")
        second.get_by_role("button", name="Save configuration", exact=True).click()
        expect(second.get_by_role("heading", name="A newer configuration was saved")).to_be_visible()
        expect(second.get_by_label("Difficulty", exact=True)).to_have_value("challenge")
        second.get_by_role("button", name="Use saved configuration").click()
        expect(second.get_by_label("Difficulty", exact=True)).to_have_value("foundation")
        second.close()
        checks.append("Two tabs receive actual HTTP 409; local edits preserved until explicit conflict resolution")

        page.get_by_label("Difficulty", exact=True).select_option("challenge")
        endpoint = f"**/courses/{fixture['course_id']}/generation-config"
        page.route(endpoint, lambda route: route.abort(), times=1)
        page.get_by_role("button", name="Save configuration", exact=True).click()
        expect(page.get_by_text("Failed to fetch", exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_label("Difficulty", exact=True)).to_have_value("challenge")
        expect(page.get_by_text("Recovered your unsaved configuration from this tab.", exact=True)).to_be_visible()
        page.get_by_role("button", name="Save configuration", exact=True).click()
        expect(page.locator(".config-save-status")).to_contain_text("Configuration saved")
        checks.append("Aborted local save retains input and request identity through browser refresh")

        plan(page, 4)
        confirm(page)
        page.get_by_role("button", name="Prepare generation", exact=True).click()
        expect(page.get_by_role("heading", name="Generation inputs saved")).to_be_visible()
        page.get_by_role("button", name="Close snapshot").click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        page.screenshot(path=str(OUT / "generate-desktop.png"), full_page=True)
        page.locator(".blueprint-question").first.locator("summary").click()
        page.screenshot(path=str(OUT / "generate-overview.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUT / "generate-mobile.png"), full_page=True)
        checks.append("390px layout has no horizontal overflow; desktop/mobile screenshots retained")

        page.goto(first_snapshot_url)
        expect(page.get_by_role("heading", name="Generation inputs saved")).to_be_visible()
        page.get_by_text("Inspect frozen inputs", exact=True).click()
        expect(page.locator("dialog pre")).to_contain_text('"main_question_count": 3')
        checks.append("Earlier three-question snapshot remains unchanged after later four-question configurations")
        assert not errors, errors
        checks.append("No uncaught browser JavaScript exceptions")
        report = {"mode": "fixture", "course_id": fixture["course_id"], "passed": len(checks), "checks": checks, "real_api_calls": 0}
        (ROOT / "var/batch3-browser-checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    except Exception:
        page.screenshot(path=str(OUT / "generate-failure.png"), full_page=True)
        (ROOT / "var/batch3-browser-failure.json").write_text(json.dumps({"passed_before_failure": checks, "url": page.url, "errors": errors,
            "pages": [{"url": p.url, "title": p.title()} for p in context.pages]}, indent=2), encoding="utf-8")
        raise
    finally:
        browser.close()
