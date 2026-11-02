"""Hold an old Topic A response until Topic B is visible; no business writes."""
import json,os,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from app.materials.topic_assignments import filter_materials
f=json.loads((ROOT/"var/batch6/flow-fixture.json").read_text());owner=get_user_model().objects.get(pk=f["owner_id"])
expected=filter_materials(owner,f["course_id"],f["topic_ids"][1]).count()
session=SessionStore();session["_auth_user_id"]=str(owner.id);session["_auth_user_backend"]="django.contrib.auth.backends.ModelBackend";session["_auth_user_hash"]=owner.get_session_auth_hash();session.save()
BASE="http://127.0.0.1:5173";held=[];writes=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True);ctx=b.new_context(viewport={"width":1440,"height":1000})
 ctx.add_cookies([{"name":"sessionid","value":session.session_key,"url":BASE,"httpOnly":True,"sameSite":"Strict"}])
 page=ctx.new_page();page.on("request",lambda r:writes.append(r.url) if r.method!="GET" else None)
 page.goto(BASE+"/courses/"+f["course_id"]+"/materials")
 expect(page.locator(".material-row")).to_have_count(3)
 pattern="**/materials?topic_id="+f["topic_ids"][0]+"*"
 page.route(pattern,lambda route:held.append(route))
 nav=page.get_by_role("navigation",name="Material topics")
 nav.get_by_role("button",name="A · Rates of change",exact=False).click()
 page.wait_for_function("location.search.includes('topic=')")
 nav.get_by_role("button",name="B · Accumulation",exact=False).click()
 expect(page.locator(".material-row")).to_have_count(expected)
 assert held,"The old request must have been intercepted"
 for route in held:route.continue_()
 page.wait_for_load_state("networkidle")
 expect(page.locator(".material-row")).to_have_count(expected)
 assert "topic="+f["topic_ids"][1] in page.url
 assert not writes,writes
 b.close()
(ROOT/"var/batch6/late-material-response.json").write_text(json.dumps({"fixture":True,"old_response_cannot_replace_current_topic":True,"writes":writes},indent=2))
print(json.dumps({"fixture":True,"late_response_isolation":"passed","writes":0}))
