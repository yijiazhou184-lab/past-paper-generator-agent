"""Explicit synthetic course-review browser checks; never calls a real model."""
import argparse,copy,json,uuid
from pathlib import Path
from round1_fixture import create_fixture
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:5173"


def prepare(title,ready_title):
    from app.courses.models import Course,CourseDraft,CourseMachineBase
    from app.courses.topic_state import topic_slice
    from app.courses.models import Topic
    from app.core.models import Task
    from django.utils import timezone
    f=create_fixture();c=Course.objects.get(pk=f["course_id"]);c.title=title+" · SYNTHETIC FIXTURE";c.save()
    tid=f["topic_ids"][0];topic=Topic.objects.get(pk=tid);topic.name=title;topic.save()
    d=CourseDraft.objects.get(course=c);state=d.topic_state[tid]
    ready=next(n for n in d.payload["knowledge_nodes"] if n["id"] in state["knowledge_ids"])
    ready.update(title=ready_title,node_kind="objective")
    group={**copy.deepcopy(ready),"id":str(uuid.uuid4()),"title":"Sample learning objectives","parent_id":None,"node_kind":"group","readiness":"partial","evidence_ids":[],"method_ids":[]}
    ready["parent_id"]=group["id"]
    missing={**copy.deepcopy(ready),"id":str(uuid.uuid4()),"title":"Additional source comparison","readiness":"partial"}
    d.payload["knowledge_nodes"]+=[group,missing];d.payload["title"]=c.title
    for claim in d.payload["scope_claims"]:
        if ready["id"] in claim["subject_ids"]:claim["subject_ids"]+=[group["id"],missing["id"]]
    q={"id":str(uuid.uuid4()),"kind":"preference","decision_key":"source-use-policy","question":"How should this practice use the supplied sources?",
       "reason":"Synthetic preference; this does not certify source accuracy.","affected_ids":[ready["id"]],"impact":"needs_confirmation",
       "suggested_answers":["Use the course framing","Use the reference framing and note differences"],"selection_mode":"single","resolves_issue_ids":[],"status":"open"}
    d.payload["clarifications"].append(q)
    state["item_ids"]["knowledge_nodes"]+=[group["id"],missing["id"]];state["knowledge_ids"]+=[group["id"],missing["id"]];state["item_ids"]["clarifications"]=[q["id"]]
    payload=topic_slice(d,tid)
    old=CourseMachineBase.objects.get(pk=state["machine_base_id"]);context=copy.deepcopy(old.context);context["target_ids"]=state["knowledge_ids"]
    task=Task.objects.create(course=c,kind="analysis",state="succeeded",stage="Complete",snapshot={"input":context},finished_at=timezone.now())
    base=CourseMachineBase.objects.create(course=c,task=task,payload=payload,context=context,mode="fixture")
    state["machine_base_id"]=str(base.id);d.machine_base=base;d.save()
    f.update(ready_id=ready["id"],missing_id=missing["id"],topic_id=tid,title=c.title)
    return f


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--fixture",action="store_true");args=parser.parse_args()
    if not args.fixture:parser.error("--fixture is required")
    from app.core.models import ModelInvocation
    before=ModelInvocation.objects.count();fixtures=[prepare("History seminar","Evaluate source provenance"),prepare("Life sciences seminar","Interpret experimental observations")]
    out=ROOT/"var/confirmation-flow-2026-11-06";out.mkdir(exist_ok=True);checks=[];errors=[]
    with __import__("playwright.sync_api",fromlist=["sync_playwright"]).sync_playwright() as pw:
        from playwright.sync_api import expect
        browser=pw.chromium.launch(headless=True)
        for i,f in enumerate(fixtures):
            context=browser.new_context(viewport={"width":1440,"height":1000})
            context.add_cookies([{"name":"sessionid","value":f["session_key"],"url":BASE,"httpOnly":True,"sameSite":"Strict"}])
            page=context.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
            url=BASE+"/courses/"+f["course_id"]+"/profile?topic="+f["topic_id"]
            page.goto(url);page.wait_for_load_state("networkidle")
            expect(page.locator(".clarification textarea")).to_have_count(0)
            card=page.locator(".clarification").filter(has=page.get_by_role("heading",name="How should this practice use the supplied sources?"))
            card.get_by_role("radio",name="Use the course framing",exact=True).click();card.get_by_role("button",name="Save choice",exact=True).click()
            expect(card.get_by_text("Choice saved and applied",exact=True)).to_be_visible()
            page.reload();page.wait_for_load_state("networkidle");expect(page.get_by_text("Choice saved and applied",exact=True)).to_be_visible()
            checks.append(f["title"]+": fixed choice persists without reanalysis")
            page.locator(".clarification").filter(has_text="Additional source comparison").get_by_role("button",name="fixture-A · p1",exact=True).click()
            expect(page.get_by_role("dialog")).to_be_visible();expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("1")
            page.get_by_role("button",name="Close source").click();checks.append(f["title"]+": source version/page action works")
            scope=page.locator("#review-objectives");scope.get_by_role("button",name="Select supported objectives").click()
            expect(page.get_by_role("button",name="Review & confirm",exact=False)).to_be_disabled()
            scope.get_by_role("button",name="Save objective selection").click()
            expect(page.get_by_role("button",name="Review & confirm",exact=False)).to_be_enabled()
            page.reload();page.wait_for_load_state("networkidle");expect(page.get_by_role("button",name="Review & confirm",exact=False)).to_be_enabled()
            page.screenshot(path=str(out/("course-"+str(i)+"-review.png")),full_page=True)
            for width in (1024,768,390):
                page.set_viewport_size({"width":width,"height":1000});page.wait_for_timeout(100)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
            page.set_viewport_size({"width":1440,"height":1000})
            page.get_by_role("button",name="Review & confirm",exact=False).click();page.get_by_role("button",name="Confirm topic",exact=True).click()
            expect(page.get_by_role("heading",name="Plan a focused practice.")).to_be_visible()
            checks.append(f["title"]+": partial range confirms, missing objective excluded; four widths")
            context.close()
        browser.close()
    assert not errors,errors
    assert ModelInvocation.objects.count()==before
    (out/"browser-flow.json").write_text(json.dumps({"fixture":True,"checks":checks,"js_errors":errors,"model_calls_unchanged":before,
        "fixtures":[{k:v for k,v in f.items() if k!="session_key"} for f in fixtures]},indent=2),encoding="utf-8")
    print(json.dumps({"checks":checks,"errors":errors,"model_calls_unchanged":before}))


if __name__=="__main__":main()
