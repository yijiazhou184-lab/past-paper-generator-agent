"""Browser acceptance for reference roles. Reads local fixture/historical tasks; blocks mutations after login."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
fixture=json.loads((ROOT/"var/source-policy-fixture.json").read_text(encoding="utf-8"))
out=ROOT/"var/screenshots"
out.mkdir(parents=True,exist_ok=True)
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[]; answers=[]; writes=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("request",lambda r:answers.append(r.url) if r.url.endswith("/answers") else None)
    try:
        page.goto("http://127.0.0.1:5173")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button",name="Open local workspace").click()
        expect(page.get_by_role("heading",name="Materials",exact=True)).to_be_visible()
        def read_only(route):
            if route.request.method not in ("GET","HEAD","OPTIONS"):
                writes.append(route.request.url)
                route.abort()
            else: route.continue_()
        page.route("**/api/**",read_only)
        page.goto(fixture["task_url"])
        expect(page.get_by_role("heading",name="Candidate preview",exact=True)).to_be_visible()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Synthetic fixture · no model call",exact=True)).to_be_visible()
        expect(page.locator(".candidate-question")).to_have_count(3)
        assert not answers
        checks.append("Synthetic candidate completes with a source notice; answers are not prefetched.")
        first=page.locator(".candidate-sources").first
        first.locator("summary").click()
        expect(first.get_by_text("Academic / teaching evidence",exact=True)).to_be_visible()
        expect(first.get_by_text("Unresolved reference · not verified",exact=True)).to_be_visible()
        expect(first.locator('a[href*="unresolved-context-example"]')).to_have_count(0)
        expect(first.get_by_text("Background references",exact=True)).to_be_visible()
        expect(page.get_by_text("Synthetic business setting",exact=True)).to_have_count(0)
        page.locator(".candidate-question").first.screenshot(path=str(out/"source-policy-teaching.png"))
        checks.append("Academic evidence and background counts are distinct; unresolved references have no broken links.")
        first.get_by_role("link").first.click()
        expect(page.get_by_role("dialog",name="Topic 2 - SYNTHETIC teaching fixture.pdf")).to_be_visible()
        expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("1")
        assert "source="+fixture["source_id"] in page.url
        page.reload()
        expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("1")
        checks.append("Teaching source opens its frozen physical page and survives refresh.")
        page.goto(fixture["task_url"])
        expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
        page.get_by_role("button",name="Show answers",exact=True).click()
        expect(page.get_by_text("Synthetic business setting",exact=True)).to_be_visible()
        refs=page.locator(".background-references")
        expect(refs.get_by_role("link",name="Open external reference (unverified)")).to_have_attribute("href","https://example.com/")
        expect(refs.get_by_role("link",name="FX01 · physical page 1")).to_have_attribute("href",
            "/courses/"+fixture["course_id"]+"/materials?source="+fixture["source_id"])
        assert len(answers)==1
        refs.screenshot(path=str(out/"source-policy-background.png"))
        page.get_by_role("button",name="Hide answers",exact=True).click()
        expect(page.get_by_text("Synthetic business setting",exact=True)).to_have_count(0)
        page.reload()
        expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
        assert len(answers)==1
        checks.append("Background details require explicit answers; external links stay unverified; hiding and reload conceal them.")
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_load_state("networkidle")
        page.locator(".candidate-sources summary").first.click()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 2")
        page.locator(".candidate-question").first.screenshot(path=str(out/"source-policy-mobile.png"))
        checks.append("390px view has no horizontal page overflow with long unresolved IDs.")
        page.goto("http://127.0.0.1:5173/tasks/344da144-1127-46b2-b137-4707f98a6a04")
        expect(page.locator(".candidate-question")).to_have_count(3)
        page.locator(".candidate-sources summary").first.click()
        expect(page.get_by_text("Academic / teaching evidence",exact=True).first).to_be_visible()
        assert len(answers)==1
        checks.append("Historical candidate without background fields still renders; original report stays failed.")
        page.goto("http://127.0.0.1:5173/tasks/8f2e167c-6d30-4dcf-9bcb-70caacd7c59e")
        expect(page.get_by_text("No complete candidate was saved. Review the task and call records before starting a new attempt.",exact=True)).to_be_visible()
        checks.append("Original source-failure task remains an unchanged historical failure, not relabelled success.")
        assert not errors,errors
        assert not writes,writes
        result={"mode":"fixture_and_read_only_history","task_url":fixture["task_url"],"checks":checks,
                "errors":errors,"blocked_mutations":writes,"new_model_calls":0}
        (ROOT/"var/source-policy-browser-check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
    except Exception:
        page.screenshot(path=str(out/"source-policy-browser-failure.png"),full_page=True)
        raise
    finally:
        browser.close()
