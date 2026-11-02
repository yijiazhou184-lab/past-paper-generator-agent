"""Synthetic UI integration. A separate owner/course is created only with --fixture."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from round1_fixture import create_fixture
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:5173"

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--fixture",action="store_true");args=parser.parse_args()
    if not args.fixture:parser.error("--fixture is required; this does not run a real acceptance.")
    f=create_fixture();a,b,c=f["topic_ids"];checks=[];errors=[];answers=[]
    out=ROOT/"var/batch6";out.mkdir(exist_ok=True)
    # Session stays private; only a redacted fixture identity is saved for subsequent view checks.
    (out/"flow-fixture.json").write_text(json.dumps({k:v for k,v in f.items() if k!="session_key"},indent=2))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport={"width":1440,"height":1000})
        context.add_cookies([{"name":"sessionid","value":f["session_key"],"url":BASE,"httpOnly":True,"sameSite":"Strict"}])
        page=context.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("request",lambda r:answers.append(r.url) if r.url.endswith("/answers") and "/files/" not in r.url and r.method=="GET" else None)
        root=BASE+"/courses/"+f["course_id"]
        page.goto(root+"/materials?topic="+b);page.wait_for_load_state("networkidle")
        expect(page.locator(".material-row")).to_have_count(1)
        expect(page.locator(".file-title",has_text="Beta lecture")).to_be_visible()
        page.get_by_label("Include course-wide materials").click()
        expect(page.locator(".material-row")).to_have_count(2)
        checks.append("Topic B excludes A; shared material is explicitly included once.")
        page.goto(root+"/profile?topic="+c)
        expect(page.get_by_role("button",name="Analyse this topic")).to_be_visible()
        expect(page.get_by_label("Learning requirements",exact=True)).to_have_count(0)
        page.get_by_role("combobox",name="Review scope").select_option(a)
        requirement=page.get_by_label("Learning requirements",exact=True)
        expect(requirement).to_have_value("Synthetic learning requirement A")
        requirement.fill("First saved A edit")
        expect(page.locator(".save-bar strong")).to_have_text("Saved",timeout=10000)
        save_url="**/api/v1/courses/"+f["course_id"]+"/draft"
        page.route(save_url,lambda route:route.abort("failed"))
        requirement.fill("Retained A edit after failure")
        expect(page.locator(".save-bar strong")).to_have_text("Could not save — Retry")
        page.get_by_role("combobox",name="Review scope").select_option(b)
        expect(page.get_by_role("heading",name="Changes need attention")).to_be_visible()
        assert "topic="+a in page.url
        page.get_by_role("button",name="Keep draft and switch").click()
        expect(requirement).to_have_value("Synthetic learning requirement B")
        page.unroute(save_url)
        page.get_by_role("combobox",name="Review scope").select_option(a)
        expect(requirement).to_have_value("Retained A edit after failure")
        page.get_by_role("button",name="Save changes",exact=True).click()
        expect(page.locator(".save-bar strong")).to_have_text("Saved")
        page.reload();expect(requirement).to_have_value("Retained A edit after failure")
        checks.append("Unanalysed topic stays empty; save failure retains A edits, switching to B isolates them, recovery persists after reload.")
        page.get_by_role("combobox",name="Review scope").select_option(b)
        page.get_by_role("button",name="Review & confirm",exact=False).click()
        page.get_by_role("button",name="Confirm topic",exact=True).click()
        expect(page.get_by_role("heading",name="Plan a focused practice.")).to_be_visible()
        page.get_by_role("button",name="Clear selection").click()
        beta=page.locator(".knowledge-topic").filter(has=page.locator("summary",has_text="Accumulation"))
        beta.get_by_role("checkbox",name="Select all eligible knowledge").click()
        page.get_by_role("button",name="Save configuration",exact=True).click()
        expect(page.get_by_role("button",name="Review structure",exact=False)).to_be_enabled()
        page.get_by_role("button",name="Review structure",exact=False).click()
        page.get_by_role("button",name="Plan with local fixture").click()
        expect(page.get_by_role("button",name="Confirm structure",exact=True)).to_be_enabled(timeout=60000)
        page.get_by_role("button",name="Confirm structure",exact=True).click()
        page.get_by_role("button",name="Confirm reviewed structure").click()
        expect(page.get_by_text("Structure confirmed",exact=True)).to_be_visible()
        difficulty=page.get_by_label("Difficulty",exact=True)
        difficulty.select_option("foundation");difficulty.select_option("exam_standard")
        expect(page.get_by_role("button",name="Confirm structure",exact=True)).to_be_disabled()
        page.get_by_role("button",name="Save configuration",exact=True).click()
        page.get_by_role("button",name="Review structure",exact=False).click()
        page.get_by_role("button",name="Plan with local fixture").click()
        expect(page.get_by_role("button",name="Confirm structure",exact=True)).to_be_enabled(timeout=60000)
        page.get_by_role("button",name="Confirm structure",exact=True).click()
        page.get_by_role("button",name="Confirm reviewed structure").click()
        checks.append("Scoped confirmation reaches generation; v2 selects B; changing a parameter and back still expires structure confirmation.")
        page.get_by_role("button",name="Generate practice",exact=True).click()
        page.get_by_role("button",name="Generate with local fixture").click()
        expect(page.get_by_role("button",name="Generate PDFs",exact=True)).to_be_visible(timeout=120000)
        generation_url=page.url
        assert not answers
        page.reload();expect(page.get_by_role("button",name="Generate PDFs",exact=True)).to_be_visible()
        page.get_by_role("button",name="Show answers",exact=True).click()
        expect(page.locator(".answer-question")).to_have_count(3)
        assert len(answers)==1
        page.get_by_role("button",name="Generate PDFs",exact=True).click()
        expect(page.get_by_role("link",name="Download question paper",exact=False)).to_be_visible(timeout=120000)
        expect(page.get_by_role("link",name="Download mark scheme",exact=False)).to_be_visible()
        assert page.url!=generation_url and "/papers/" in page.url
        paper_url=page.url
        for label in ("Download question paper","Download mark scheme"):
            with page.expect_download() as download:page.get_by_role("link",name=label,exact=False).click()
            target=out/("fixture-"+download.value.suggested_filename);download.value.save_as(target)
            assert target.read_bytes().startswith(b"%PDF")
        page.reload();expect(page.locator(".answer-question")).to_have_count(0)
        assert len(answers)==1
        checks.append("Synthetic generation recovers after refresh; answers load only on demand; explicit export opens Papers with both same-content PDFs.")
        for width in (1440,1024,768,320):
            page.set_viewport_size({"width":width,"height":1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),width
        assert not errors,errors
        (out/"flow-browser.json").write_text(json.dumps({"fixture":True,"course_id":f["course_id"],"paper_url":paper_url,"generation_url":generation_url,"checks":checks,"errors":errors},indent=2))
        browser.close()
    print(json.dumps({"fixture":True,"checks":checks,"paper_url":paper_url}))
if __name__=="__main__":main()
