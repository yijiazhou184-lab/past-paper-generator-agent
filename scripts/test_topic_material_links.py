"""Exercise duplicate upload linking and CAS conflict with an isolated fixture."""
import json,os,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from app.materials.models import MaterialVersion
from app.materials.storage import path_for
from app.core.models import ModelInvocation
from round1_fixture import create_fixture
f=create_fixture()
owner=get_user_model().objects.get(pk=f["owner_id"])
version=MaterialVersion.objects.select_related("blob").get(pk=f["material_ids"][0])
before_blob_id=version.blob_id;content=path_for(version.blob.storage_key).read_bytes()
session=SessionStore();session["_auth_user_id"]=str(owner.id);session["_auth_user_backend"]="django.contrib.auth.backends.ModelBackend";session["_auth_user_hash"]=owner.get_session_auth_hash();session.save()
BASE="http://127.0.0.1:5173";checks=[];before_calls=ModelInvocation.objects.count()
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport={"width":1440,"height":1000})
 context.add_cookies([{"name":"sessionid","value":session.session_key,"url":BASE,"httpOnly":True,"sameSite":"Strict"}])
 page=context.new_page();page.goto(BASE+"/courses/"+f["course_id"]+"/materials?topic="+f["topic_ids"][1])
 expect(page.locator(".material-row")).to_have_count(1)
 page.locator('input[type=file]').set_input_files({"name":"Alpha duplicate.pdf","mimeType":"application/pdf","buffer":content})
 expect(page.get_by_role("heading",name="Upload 1 PDF")).to_be_visible()
 page.get_by_role("button",name="Upload files",exact=True).click()
 page.get_by_role("button",name="Link existing material",exact=True).click()
 expect(page.get_by_role("checkbox",name="A · Rates of change")).to_be_checked()
 expect(page.get_by_role("checkbox",name="B · Accumulation")).to_be_checked()
 page.get_by_role("button",name="Save topic links").click()
 expect(page.locator(".material-row")).to_have_count(2)
 checks.append("Duplicate upload explicitly appends B, retains A, and reuses the same file/version.")
 row=page.locator(".material-row").filter(has=page.locator(".file-title",has_text="Alpha lecture"))
 row.get_by_role("button",name="Manage topics").click()
 note=page.get_by_label("Classification note");note.fill("Local draft retained after conflict")
 # Another tab changes only the saved note, after this editor has loaded its revision.
 current=page.request.get(BASE+"/api/v1/courses/"+f["course_id"]+"/materials").json()
 item=next(m for m in current["materials"] if m["id"]==str(version.id))
 csrf=page.request.get(BASE+"/api/v1/session").json()["csrf_token"]
 assignment={**item["topic_assignment"],"expected_revision":item["topic_assignment"]["revision"],"note":"Another tab saved this note"}
 response=page.request.patch(BASE+"/api/v1/material-versions/"+str(version.id)+"/topic-assignment",data=assignment,headers={"X-CSRFToken":csrf})
 assert response.status==200
 page.get_by_role("button",name="Save topic links").click()
 expect(page.get_by_role("alert")).to_contain_text("Topic links changed")
 expect(note).to_have_value("Local draft retained after conflict")
 page.get_by_role("button",name="Compare saved links").click()
 expect(page.get_by_text("Another tab saved this note",exact=False)).to_be_visible()
 page.get_by_role("button",name="Use this revision for my next save").click()
 page.get_by_role("button",name="Save topic links").click()
 expect(page.get_by_text("Topic links saved.",exact=True)).to_be_visible()
 checks.append("Stale link save shows conflict, retains local input, compares server state, and only retries after explicit revision adoption.")
 browser.close()
version.refresh_from_db();assert version.blob_id==before_blob_id and path_for(version.blob.storage_key).read_bytes()==content
assert ModelInvocation.objects.count()==before_calls
(ROOT/"var/batch6/material-links-browser.json").write_text(json.dumps({"fixture":True,"checks":checks},indent=2))
print(json.dumps({"fixture":True,"checks":checks}))
