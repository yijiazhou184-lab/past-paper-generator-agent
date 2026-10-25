"""Read-only browser verification of a retained real generation; never submits a model task."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]


def run(task_id):
    url=f"http://127.0.0.1:5173/tasks/{task_id}"
    out=ROOT/"var/screenshots"
    out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];answer_requests=[];writes=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1440,"height":1000})
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("request",lambda r:answer_requests.append(r.url) if r.url.endswith("/answers") else None)
        page.goto("http://127.0.0.1:5173")
        page.get_by_role("button",name="Open local workspace").click()
        expect(page.get_by_role("heading",name="Materials",exact=True)).to_be_visible()
        def block_writes(route):
            if route.request.method not in ("GET","HEAD","OPTIONS"):
                writes.append(route.request.url)
                route.abort()
            else:
                route.continue_()
        page.route("**/api/v1/**",block_writes)
        try:
            page.goto(url)
            expect(page.locator(".candidate-question")).to_have_count(3,timeout=20000)
            expect(page.get_by_text("Required checks did not pass. This candidate is retained for review.",exact=True)).to_be_visible()
            assert not answer_requests and page.locator(".answer-question").count()==0
            task=page.request.get(f"http://127.0.0.1:5173/api/v1/tasks/{task_id}").json()
            assert task["state"]=="failed" and task["error"]["code"]=="GENERATION_NEEDS_INFO"
            before_calls=[c["id"] for c in task["model_calls"]]
            assert len(before_calls)==18
            checks.append("Retained failed task shows three real questions and original blocked gate; no answer request on load.")
            page.screenshot(path=str(out/"batch4-live-retained-questions.png"))
            page.get_by_role("button",name="Show answers",exact=True).click()
            expect(page.locator(".answer-question")).to_have_count(3)
            assert len(answer_requests)==1
            expect(page.locator(".answer-question .katex").first).to_be_visible()
            assert page.locator(".katex-error").count()==0
            page.locator(".answer-question").first.scroll_into_view_if_needed()
            page.screenshot(path=str(out/"batch4-live-retained-answers.png"))
            page.get_by_text("Detailed check report",exact=True).click()
            expect(page.locator(".detailed-check").first).to_be_visible()
            checks.append("Answers, suggested marking and original detailed report open explicitly; no KaTeX error elements.")
            page.reload()
            expect(page.get_by_role("button",name="Show answers",exact=True)).to_be_visible()
            assert len(answer_requests)==1
            checks.append("Reload restores the same terminal task and hides answers without another answer fetch.")
            content=page.request.get(f"http://127.0.0.1:5173/api/v1/tasks/{task_id}/generation-content").json()
            candidate=content["candidates"][-1]
            eid=candidate["pairs"][0]["evidence_ids"][0]
            source=next(s for s in candidate["sources"] if s["id"]==eid)
            page.locator(".candidate-sources summary").first.click()
            page.locator(".candidate-sources a").first.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value(str(source["physical_page"]))
            assert f"source={eid}" in page.url
            checks.append("Source opens retained evidence identity and physical page from the original candidate.")
            page.goto(url)
            page.set_viewport_size({"width":390,"height":844})
            expect(page.locator(".candidate-question")).to_have_count(3)
            assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
            page.screenshot(path=str(out/"batch4-live-retained-mobile.png"))
            after=page.request.get(f"http://127.0.0.1:5173/api/v1/tasks/{task_id}").json()
            assert before_calls==[c["id"] for c in after["model_calls"]]
            assert after["state"]==task["state"]
            assert not errors and not writes,{"errors":errors,"unexpected_write_requests":writes}
            checks.append("390px viewport has no document overflow; no JS errors, writes or new call records.")
            result={"mode":"read_only_saved_real_result","task_id":task_id,"url":url,"checks":checks,
                    "errors":errors,"new_model_calls":0,"unexpected_write_requests":writes}
            (ROOT/"var"/"batch4-live-browser-audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result,indent=2))
        except Exception:
            page.screenshot(path=str(out/"batch4-live-browser-audit-failure.png"))
            raise
        finally:
            browser.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    run(parser.parse_args().task_id)
