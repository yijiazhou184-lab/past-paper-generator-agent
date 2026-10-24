"""Batch-4 browser acceptance: actual local API/worker, synthetic content, zero provider calls."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
fixture=json.loads((ROOT/"var/batch4-browser-fixture.json").read_text(encoding="utf-8"))
OUT=ROOT/"var/screenshots"
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={"width":1440,"height":1000})
    page=context.new_page()
    errors=[]; answer_requests=[]; task_ids=[]; request_keys=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("request",lambda r:answer_requests.append(r.url) if r.url.endswith("/answers") else None)
    try:
        page.goto("http://127.0.0.1:5173")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button",name="Open local workspace").click()
        expect(page.get_by_role("heading",name="Materials",exact=True)).to_be_visible()
        page.goto(fixture["url"])
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Structure confirmed",exact=True)).to_be_visible()
        expect(page.get_by_role("button",name="Prepare generation",exact=True)).to_have_count(0)
        page.get_by_role("button",name="Generate practice",exact=True).click()
        expect(page.get_by_role("heading",name="Review generation inputs",exact=True)).to_be_visible()
        expect(page.get_by_role("button",name="Generate with local fixture")).to_be_enabled()
        checks.append("Merged Generate practice entry freezes inputs and shows fixture preflight without paid consent.")
        def lose_ack(route):
            request_keys.append(route.request.headers["idempotency-key"])
            response=route.fetch()
            assert response.status==202,response.text()
            task_ids.append(response.json()["id"])
            route.abort()
        page.route("**/generations",lose_ack,times=1)
        page.get_by_role("button",name="Generate with local fixture").click()
        expect(page.get_by_role("button",name="Recover generation action")).to_be_visible()
        page.reload()
        expect(page.get_by_role("button",name="Recover generation action")).to_be_visible()
        page.get_by_role("button",name="Recover generation action").click()
        page.wait_for_url(re.compile(r".*/tasks/"+task_ids[0]),timeout=15000)
        checks.append("Lost acknowledgement survives refresh and recovers the same generation task.")
        page.reload()
        expect(page.locator(".candidate-question")).to_have_count(3,timeout=120000)
        expect(page.get_by_text("Checks passed for this candidate · publication arrives in batch 5",exact=True)).to_be_visible(timeout=120000)
        expect(page.get_by_role("heading",name="Complete",exact=True)).to_be_visible(timeout=15000)
        expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
        assert answer_requests==[],answer_requests
        assert page.locator(".answer-question").count()==0
        task_url=page.url
        expect(page.locator(".course-name")).to_contain_text("B4-FIXTURE")
        checks.append("Real worker completes the fixture pipeline; task refresh restores it without fetching answers.")
        page.screenshot(path=str(OUT/"batch4-questions.png"),full_page=True)
        page.get_by_role("button",name="Show answers",exact=True).click()
        expect(page.locator(".answer-question")).to_have_count(3)
        assert len(answer_requests)==1
        expect(page.locator(".katex").first).to_be_visible()
        page.screenshot(path=str(OUT/"batch4-answers.png"),full_page=True)
        checks.append("Answers, marking guidance and detailed reports are fetched only on explicit opening; maths renders.")
        page.get_by_role("button",name="Hide answers",exact=True).click()
        expect(page.locator(".answer-question")).to_have_count(0)
        page.reload()
        expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
        assert len(answer_requests)==1
        checks.append("Hide and reload return to question-only reading without answer prefetch.")
        page.locator(".candidate-sources summary").first.click()
        page.locator(".candidate-sources a").first.click()
        page.wait_for_url(re.compile(".*source="+fixture["source_id"]))
        expect(page.get_by_role("dialog",name="Topic 2 - SYNTHETIC teaching fixture.pdf")).to_be_visible()
        expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("1")
        checks.append("Source link opens the same synthetic material version and physical page.")
        page.goto(task_url)
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT/"batch4-mobile.png"),full_page=True)
        overflow=page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
        assert not overflow,"Mobile document overflow"
        checks.append("390px layout has no document-wide horizontal overflow.")
        assert not errors,errors
        checks.append("No uncaught browser JavaScript errors.")
        result={"mode":"fixture","course_id":fixture["course_id"],"task_id":task_ids[0],"task_url":task_url,"checks":checks,"errors":errors}
        (ROOT/"var/batch4-browser-check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
    except Exception:
        page.screenshot(path=str(OUT/"batch4-failure.png"),full_page=True)
        raise
    finally:
        browser.close()
