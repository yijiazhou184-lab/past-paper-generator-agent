"""Import reviewed E1 sources locally. This creates no analysis/model task."""
import json,hashlib
from pathlib import Path
from evals.round1.run import setup,ROOT
def main():
    setup()
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from app.courses.models import Course
    from app.courses.topics import create_topic
    from app.materials.models import MaterialBlob,MaterialVersion,ParseVersion
    from app.materials.topic_assignments import set_topic_assignment,assignment_view
    from app.core.models import ModelInvocation
    before=ModelInvocation.objects.count()
    plan=json.loads((ROOT/"evals/round1/e1-materials.json").read_text(encoding="utf-8"))
    owner=get_user_model().objects.get(username="local")
    course,_=Course.objects.get_or_create(owner=owner,title=plan["course_title"],defaults={"code":plan["course_code"],"scope_statement":"All lecture content","scope_provenance":"user_statement"})
    if hasattr(course,"draft"):raise ValueError("E1 already has a draft; do not reset a real experiment")
    client=APIClient();client.force_authenticate(owner)
    imports=[]
    for i,row in enumerate(plan["files"]):
        path=ROOT/row["path"];data=path.read_bytes();hashed=hashlib.sha256(data).hexdigest()
        blob=MaterialBlob.objects.filter(owner=owner,sha256=hashed).first()
        cached=bool(blob and ParseVersion.objects.filter(blob=blob,state="succeeded").exists())
        response=client.post(f"/api/v1/courses/{course.id}/materials",{"file":SimpleUploadedFile(path.name,data,content_type="application/pdf")},format="multipart",HTTP_IDEMPOTENCY_KEY=f"e1-import-{i}")
        if response.status_code!=201:raise ValueError(response.json())
        result=response.json();version=MaterialVersion.objects.get(pk=result["version_id"])
        if version.roles!=row["roles"]:
            response=client.patch(f"/api/v1/material-versions/{version.id}/classification",{"expected_revision":version.classification_revision,"roles":row["roles"]},format="json")
            if response.status_code!=200:raise ValueError(response.json())
        imports.append({**row,**result,"sha256":hashed,"parse_cache_available_at_import":cached})
    topic=create_topic(owner,course.id,{"name":plan["topic_name"],"code":plan["topic_code"],"order":1,"provenance":"reviewed_material","source_refs":[{"material_version_id":imports[0]["version_id"],"physical_page":1}]},"e1-topic")
    for row in imports:
        version=MaterialVersion.objects.get(pk=row["version_id"])
        old=assignment_view(version)
        if old["revision"]==0:
            set_topic_assignment(owner,version.id,0,{"scope":"topic","topic_ids":[str(topic.id)],"page_ranges_by_topic":{str(topic.id):[[p,p] for p in row["pages"]]},"shared_page_ranges":[],"note":"E1 reviewed local selection. No API consent is implied."})
        elif old["topic_ids"]!=[str(topic.id)]:raise ValueError("Existing links differ; manual review required")
    out=ROOT/"var/evals/round1/E1";out.mkdir(parents=True,exist_ok=True)
    selection={"course_id":str(course.id),"target_topic_ids":[str(topic.id)],"base_revision":0,"material_selection":[{"material_version_id":r["version_id"],"pages":r["pages"]} for r in imports]}
    (out/"selection.json").write_text(json.dumps(selection,indent=2))
    (out/"local-import.json").write_text(json.dumps({"mode":"local_only","course_id":str(course.id),"topic_id":str(topic.id),"imports":imports,"user_statement":"All lecture content","provenance":"user_statement","focus":plan["focus"]},indent=2),encoding="utf-8")
    assert ModelInvocation.objects.count()==before
    print(json.dumps({"course_id":str(course.id),"topic_id":str(topic.id),"selection":str(out/"selection.json"),"parse_task_ids":[r["task_id"] for r in imports],"selected_pages":sum(len(r["pages"]) for r in imports),"model_calls_added":0}))
if __name__=="__main__":main()
