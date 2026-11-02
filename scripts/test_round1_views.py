"""Five-view responsive reading and synthetic failure states; --fixture required."""
import argparse,json,os,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--fixture",action="store_true");args=parser.parse_args()
    if not args.fixture:parser.error("--fixture required")
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.backends.db import SessionStore
    from django.utils import timezone
    from app.core.models import Task,ModelInvocation
    f=json.loads((ROOT/"var/batch6/flow-fixture.json").read_text());flow=json.loads((ROOT/"var/batch6/flow-browser.json").read_text())
    assert f["course_id"]==flow["course_id"]
    owner=get_user_model().objects.get(pk=f["owner_id"])
    session=SessionStore();session["_auth_user_id"]=str(owner.id);session["_auth_user_backend"]="django.contrib.auth.backends.ModelBackend";session["_auth_user_hash"]=owner.get_session_auth_hash();session.save()
    failure=Task.objects.create(course_id=f["course_id"],kind="parse",state="failed",stage="Failed",finished_at=timezone.now(),error={"code":"SYNTHETIC_TIMEOUT","message":"Synthetic timeout. The original upload is retained.","retryable":True})
    base="http://127.0.0.1:5173";course=base+"/courses/"+f["course_id"]
    views={"materials":course+"/materials","profile":course+"/profile?topic="+f["topic_ids"][1],"generate":course+"/generate","task":flow["generation_url"],"paper":flow["paper_url"]}
    out=ROOT/"var/screenshots";out.mkdir(exist_ok=True);checks=[];errors=[];answers=[]
    calls=ModelInvocation.objects.count()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context()
        context.add_cookies([{"name":"sessionid","value":session.session_key,"url":base,"httpOnly":True,"sameSite":"Strict"}])
        page=context.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("request",lambda r:answers.append(r.url) if r.url.endswith("/answers") and "/files/" not in r.url and r.method=="GET" else None)
        for view,url in views.items():
            page.goto(url);page.wait_for_load_state("networkidle")
            expect(page.get_by_role("navigation",name="Course navigation")).to_be_visible()
            for width in (1440,1024,768,320):
                page.set_viewport_size({"width":width,"height":1000})
                page.wait_for_timeout(100)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),(view,width)
                page.screenshot(path=str(out/f"batch6-{view}-{width}.png"))
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.tagName")!="BODY"
            checks.append(view+": four widths and keyboard focus")
        page.goto(base+"/tasks/"+str(failure.id))
        expect(page.get_by_role("alert")).to_contain_text("Synthetic timeout")
        assert page.get_by_role("alert").locator("xpath=ancestor::details").count()==0
        checks.append("Synthetic timeout remains visible outside collapsed run details")
        page.set_viewport_size({"width":1440,"height":1000})
        # Local network failure: material query error remains recoverable.
        page.route("**/api/v1/courses/"+f["course_id"]+"/materials*",lambda route:route.abort("failed"))
        page.goto(views["materials"])
        expect(page.get_by_role("button",name="Retry",exact=True)).to_be_visible(timeout=20000)
        page.unroute("**/api/v1/courses/"+f["course_id"]+"/materials*")
        page.get_by_role("button",name="Retry",exact=True).click()
        expect(page.locator(".material-row")).to_have_count(3)
        checks.append("Synthetic network failure shows Retry and restores the same material view")
        assert not errors,errors
        assert not answers,answers
        browser.close()
    assert ModelInvocation.objects.count()==calls
    (ROOT/"var/batch6/views-browser.json").write_text(json.dumps({"fixture":True,"checks":checks,"errors":errors,"answers_fetched":answers},indent=2))
    print(json.dumps({"fixture":True,"checks":checks}))
if __name__=="__main__":main()
