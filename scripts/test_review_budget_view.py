"""Read-only browser checks after local login. No generation or model requests."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
fixture=json.loads((ROOT/"var/review-budget-fixture.json").read_text())
out=ROOT/"var/screenshots"
out.mkdir(exist_ok=True,parents=True)
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[];writes=[];answers=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("request",lambda r:answers.append(r.url) if r.url.endswith("/answers") else None)
    try:
        page.goto("http://127.0.0.1:5173")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button",name="Open local workspace").click()
        expect(page.get_by_role("heading",name="Materials",exact=True)).to_be_visible()
        def read_only(route):
            if route.request.method not in ("GET","HEAD","OPTIONS"):
                writes.append(route.request.url);route.abort()
            else:route.continue_()
        page.route("**/api/**",read_only)
        page.goto(fixture["success_url"])
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Some optional checks were skipped. All required checks passed.",exact=True)).to_be_visible()
        expect(page.locator(".status.succeeded")).to_be_visible()
        expect(page.locator(".candidate-question")).to_have_count(3)
        assert not answers
        checks.append("Optional overflow does not block a fixture whose required checks passed; no answers prefetched.")
        page.get_by_text("Check progress",exact=True).click()
        expect(page.get_by_text("Optional checks — skipped",exact=True)).to_be_visible()
        expect(page.get_by_role("button",name="Resume validation",exact=True)).to_have_count(0)
        page.locator(".candidate-status").screenshot(path=str(out/"review-budget-success.png"))
        checks.append("Stages and skipped optional checks are visible inside the generation task; no separate validation action.")
        page.goto(fixture["failed_url"])
        expect(page.get_by_text("Questions and answers saved. Required checks did not finish. Completed stages are retained.",exact=True)).to_be_visible()
        expect(page.locator(".status.failed")).to_be_visible()
        page.get_by_text("Check progress",exact=True).click()
        expect(page.get_by_text("Mathematical checks — complete",exact=True)).to_be_visible()
        expect(page.get_by_text("Validation interrupted — blocked",exact=True)).to_be_visible()
        page.get_by_text("Check summary",exact=True).click()
        expect(page.locator(".candidate-status").get_by_text("semantic:q2:conditions — not checked (required)",exact=True)).to_be_visible()
        assert not answers
        page.locator(".candidate-status").screenshot(path=str(out/"review-budget-partial.png"))
        checks.append("Partial required results survive a later single-question overflow and never imply successful generation.")
        page.get_by_role("button",name="Show answers",exact=True).click()
        expect(page.get_by_label("Worked answers")).to_be_visible()
        page.get_by_text("Detailed check report",exact=True).click()
        expect(page.locator(".detailed-check")).not_to_have_count(0)
        assert len(answers)==1
        page.reload()
        expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
        assert len(answers)==1
        checks.append("Detailed partial results require opening answers; refresh restores the task without reopening answers.")
        page.set_viewport_size({"width":390,"height":844})
        page.get_by_text("Check progress",exact=True).click()
        page.wait_for_load_state("networkidle")
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth+2")
        page.locator(".candidate-status").screenshot(path=str(out/"review-budget-mobile.png"))
        checks.append("390px mobile progress has no horizontal page overflow.")
        page.goto("http://127.0.0.1:5173/tasks/32bb6d9c-2121-4f4a-9a6a-b89c585b7b32")
        expect(page.locator(".candidate-question")).to_have_count(4)
        expect(page.get_by_text("Checks did not finish. This candidate has no complete check report.",exact=True)).to_be_visible()
        assert len(answers)==1
        checks.append("Historical live candidate remains failed and unmodified; no fake stage report was backfilled.")
        assert not errors,errors
        assert not writes,writes
        result={"checks":checks,"errors":errors,"blocked_writes":writes,"mode":"synthetic_and_read_only_history","new_model_calls":0,
                "success_url":fixture["success_url"],"failed_url":fixture["failed_url"]}
        (ROOT/"var/review-budget-browser-check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
    except Exception:
        page.screenshot(path=str(out/"review-budget-browser-failure.png"),full_page=True)
        raise
    finally:browser.close()
