import copy
import uuid
import pytest
from app.core.errors import DomainError
from app.core.tasks import submit_task, claim_task
from app.courses.topics import create_topic
from app.courses.topic_context import build_topic_analysis_context
from app.courses.topic_state import topic_slice
from app.courses.analysis import publish_analysis
from app.courses.drafts import save_draft
from app.materials.ingest import ingest_pdf
from app.materials.models import MaterialVersion, ParseVersion, Evidence
from app.materials.topic_assignments import set_topic_assignment
from test_course_analysis import course_payload, analysis_context


@pytest.fixture
def topic_sources(course, pdf_bytes):
    topic = create_topic(course.owner, course.id, {"name": "Accumulation and integrals"}, "topic")
    result = ingest_pdf(course, pdf_bytes, "Synthetic lecture.pdf", "upload")
    version = MaterialVersion.objects.get(pk=result["version_id"])
    version.roles = ["lecture"]; version.save()
    parsed = ParseVersion.objects.create(blob=version.blob, parser_name="fixture", parser_version="1", config_hash="fixture", state="succeeded", content_hash="fixture")
    for page in (1, 2):
        Evidence.objects.create(material_version=version, parse_version=parsed, physical_page=page, text="Synthetic teaching evidence about accumulation. " * 10, fidelity_status="text")
    set_topic_assignment(course.owner, version.id, 0, {"scope": "topic", "topic_ids": [str(topic.id)], "page_ranges_by_topic": {str(topic.id): [[1,1]]}})
    return topic, version


def test_dynamic_context_only_contains_explicit_pages_and_no_fixed_targets(course, topic_sources):
    topic, version = topic_sources
    selection = [{"material_version_id": str(version.id), "pages": [1]}]
    a = build_topic_analysis_context(course, [str(topic.id)], selection, 0)
    assert len(a["input"]["evidence"]) == 1
    assert a["input"]["evidence"][0]["physical_page"] == 1
    assert a["input"]["target_ids"] == [] and a["input"]["target_knowledge"] == []
    assert a["input"]["target_topics"][0]["name"] == topic.name
    assert "K1" not in a["prompt"] and "Topic 2" not in a["prompt"]
    b = build_topic_analysis_context(course, [str(topic.id)], [{"material_version_id":str(version.id),"pages":[2]}], 0)
    assert b["context_hash"] != a["context_hash"]
    with pytest.raises(DomainError, match="ANALYSIS_PAGES_REQUIRED"):
        build_topic_analysis_context(course, [str(topic.id)], [{"material_version_id":str(version.id),"pages":[]}], 0)
    with pytest.raises(DomainError, match="DRAFT_REVISION_CONFLICT"):
        build_topic_analysis_context(course, [str(topic.id)], selection, 99)


def test_shared_pages_and_assignment_revision_are_explicit_inputs(course, topic_sources):
    topic, version = topic_sources
    selection=[{"material_version_id":str(version.id),"pages":[1]}]
    before=build_topic_analysis_context(course,[str(topic.id)],selection,0)
    set_topic_assignment(course.owner,version.id,1,{"scope":"shared","topic_ids":[],"shared_page_ranges":[[2,2]]})
    after=build_topic_analysis_context(course,[str(topic.id)],selection,0)
    assert after["context_hash"] != before["context_hash"]
    assert after["input"]["materials"][0]["assignment"]["scope"]=="shared"
    assert [e["physical_page"] for e in after["input"]["evidence"]]==[1]


def scoped_payload(course_payload, analysis_context, topic, node_id):
    payload=copy.deepcopy(course_payload);context=copy.deepcopy(analysis_context)
    payload["knowledge_nodes"][0]["id"]=node_id
    payload["scope_claims"][0]["id"]="scope-"+node_id
    payload["scope_claims"][0]["subject_ids"]=[node_id]
    for e in context["evidence"]:
        e.setdefault("material_version_id",str(uuid.uuid4()));e.setdefault("physical_page",1)
    context.update(target_topic_ids=[str(topic.id)],target_topics=[{"id":str(topic.id),"name":topic.name,"code":topic.code,"revision":topic.revision}],target_ids=[node_id],materials=[],base_revision=0)
    return payload,context


def test_analysis_b_preserves_a_manual_edits_and_rejects_cross_topic_identity(course,course_payload,analysis_context):
    a=create_topic(course.owner,course.id,{"name":"Alpha"},"a")
    b=create_topic(course.owner,course.id,{"name":"Beta"},"b")
    aid,bid=str(uuid.uuid4()),str(uuid.uuid4())
    pa,ca=scoped_payload(course_payload,analysis_context,a,aid)
    da=publish_analysis(claim_task(submit_task(course,"analysis",{},"a-task").id),pa,ca,"fixture")
    save_draft(course.owner,course.id,da.revision,[{"path":["knowledge_nodes",aid,"requirements"],"value":"My reviewed requirement"}],"edit-a")
    pb,cb=scoped_payload(course_payload,analysis_context,b,bid)
    db=publish_analysis(claim_task(submit_task(course,"analysis",{},"b-task").id),pb,cb,"fixture")
    assert topic_slice(db,str(a.id))["knowledge_nodes"][0]["requirements"]=="My reviewed requirement"
    assert [n["id"] for n in topic_slice(db,str(b.id))["knowledge_nodes"]]==[bid]
    pb["knowledge_nodes"][0]["id"]=aid
    with pytest.raises(DomainError,match="ANALYSIS_TOPIC_SCOPE_INVALID"):
        publish_analysis(claim_task(submit_task(course,"analysis",{},"bad-task").id),pb,cb,"fixture")
