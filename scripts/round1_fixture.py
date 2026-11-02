"""Private synthetic two-topic workspace for browser tests; no real AI calls."""
import os,sys,uuid,io,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()


def create_fixture():
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.backends.db import SessionStore
    from django.utils import timezone
    from reportlab.pdfgen import canvas
    from app.courses.models import Course,CourseDraft,CourseMachineBase,UserStatement
    from app.courses.topics import create_topic
    from app.courses.topic_confirmation import confirm_topics
    from app.courses.context import statement_list
    from app.core.models import Task
    from app.core.idempotency import digest
    from app.materials.models import Material,MaterialVersion,MaterialBlob,ParseVersion,Evidence
    from app.materials.storage import write_bytes
    from app.materials.topic_assignments import set_topic_assignment,assignment_view
    from app.materials.evidence import build_evidence_pack
    owner=get_user_model().objects.create_user(username="batch6-fixture-"+uuid.uuid4().hex[:12])
    course=Course.objects.create(owner=owner,title="Synthetic topic workspace · FIXTURE",code="TEST",scope_statement="All supplied lecture knowledge")
    UserStatement.objects.create(course=course,text=course.scope_statement,kind="exam_scope",source="Synthetic fixture statement",submitted_by=owner)
    topics=[create_topic(owner,course.id,{"name":name,"code":code,"order":i},"topic-"+code) for i,(name,code) in enumerate([("Rates of change","A"),("Accumulation","B"),("Unanalysed topic","C")])]
    versions=[]
    for i,title in enumerate(["Alpha lecture · FIXTURE.pdf","Beta lecture · FIXTURE.pdf","Shared reference · FIXTURE.pdf"]):
        out=io.BytesIO();pdf=canvas.Canvas(out)
        for page in (1,2):
            pdf.drawString(45,740,"SYNTHETIC FIXTURE: "+title);pdf.drawString(45,710,"Physical page "+str(page));pdf.showPage()
        pdf.save();data=out.getvalue();hashed=hashlib.sha256(data).hexdigest()
        key=f"browser-fixtures/{owner.id}/{hashed}.pdf";write_bytes(key,data)
        blob=MaterialBlob.objects.create(owner=owner,sha256=hashed,bytes=len(data),pages=2,storage_key=key)
        parsekey=f"browser-fixtures/{owner.id}/{hashed}.json";document=b'{"fixture":true}';write_bytes(parsekey,document)
        parsed=ParseVersion.objects.create(blob=blob,parser_name="fixture",parser_version="synthetic-1",config_hash=digest({"fixture":True}),state="succeeded",content_hash=hashlib.sha256(document).hexdigest(),document_key=parsekey)
        task=Task.objects.create(course=course,kind="parse",state="succeeded",stage="Complete",finished_at=timezone.now())
        version=MaterialVersion.objects.create(material=Material.objects.create(course=course),blob=blob,original_filename=title,path_aliases=["synthetic/"+title],roles=["lecture"],classification_basis="fixture",task=task)
        for page in (1,2):
            Evidence.objects.create(material_version=version,parse_version=parsed,physical_page=page,text="Synthetic lecture evidence; this is a browser fixture, never an academic result. "*4,fidelity_status="text")
        specific=i<2
        set_topic_assignment(owner,version.id,0,{"scope":"topic" if specific else "shared","topic_ids":[str(topics[i].id)] if specific else [],"page_ranges_by_topic":{str(topics[i].id):[[1,2]]} if specific else {},"shared_page_ranges":[[1,1]] if not specific else []})
        versions.append(version)
    all_payload={"title":course.title,"target_exam":{"label":"Synthetic exam","academic_year":None},"template_suggestion":None,
        "knowledge_nodes":[],"scope_claims":[],"method_rules":[],"historical_style":[],"issues":[],"clarifications":[]}
    states={};lastbase=None
    for i,topic in enumerate(topics[:2]):
        kid=str(uuid.uuid4());claimid=str(uuid.uuid4());evidence=list(versions[i].evidence.order_by("physical_page"))
        payload={**all_payload,"knowledge_nodes":[{"id":kid,"title":"Rates" if i==0 else "Accumulation","parent_id":None,"depth":1,
            "prerequisite_ids":[],"method_ids":[],"evidence_ids":[str(evidence[0].id)],"readiness":"supported","requirements":"Synthetic learning requirement "+topic.code}],
            "scope_claims":[{"id":claimid,"text":course.scope_statement,"subject_ids":[kid],"applicability":"current_exam","provenance":"user_statement","authority_status":"unverified","evidence_ids":[],"statement_ids":[statement_list(course)[0]["id"]],"status":"declared","disposition":"include"}]}
        pack=build_evidence_pack(owner,[versions[i].id])
        for e in pack["evidence"]:
            e.update(material_code="fixture-"+topic.code,roles=["lecture"],route={"route":"text","signals":[]},visual=None,visual_status="not_needed",blob_sha256=versions[i].blob.sha256)
        for m in pack["materials"]:
            m.update(filename=versions[i].original_filename,code="fixture-"+topic.code,selected_pages=[1,2],assignment=assignment_view(versions[i]))
        context={"target_topic_ids":[str(topic.id)],"target_topics":[{"id":str(topic.id),"name":topic.name,"code":topic.code}],"target_ids":[kid],
            "statements":statement_list(course),"materials":pack["materials"],"evidence":pack["evidence"],"round1_exclusions":["software_command_answers"]}
        task=Task.objects.create(course=course,kind="analysis",state="succeeded",stage="Complete",snapshot={"input":context},finished_at=timezone.now())
        base=CourseMachineBase.objects.create(course=course,task=task,payload=payload,context=context,mode="fixture");lastbase=base
        states[str(topic.id)]={"item_ids":{key:[row["id"] for row in payload[key]] for key in ("knowledge_nodes","scope_claims","method_rules","historical_style","issues","clarifications")},
            "knowledge_ids":[kid],"machine_base_id":str(base.id),"template_suggestion":None,"name":topic.name,"code":topic.code,"revision":1}
        for key in ("knowledge_nodes","scope_claims"):all_payload[key]=all_payload[key]+payload[key]
    draft=CourseDraft.objects.create(course=course,machine_base=lastbase,payload=all_payload,topic_state=states)
    confirmed=confirm_topics(owner,course.id,1,None,[str(t.id) for t in topics[:2]],"initial")
    session=SessionStore();session["_auth_user_id"]=str(owner.pk);session["_auth_user_backend"]="django.contrib.auth.backends.ModelBackend";session["_auth_user_hash"]=owner.get_session_auth_hash();session.save()
    return {"course_id":str(course.id),"owner_id":str(owner.id),"topic_ids":[str(t.id) for t in topics],"material_ids":[str(v.id) for v in versions],"session_key":session.session_key,"course_version_id":str(confirmed.id)}
