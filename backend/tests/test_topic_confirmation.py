import copy
import pytest
from app.core.errors import DomainError
from app.core.tasks import submit_task, claim_task
from app.courses.topics import create_topic
from app.courses.analysis import publish_analysis
from app.courses.drafts import save_draft
from app.courses.confirmation import confirm_topics
from test_topic_analysis import scoped_payload
from test_course_analysis import course_payload, analysis_context


@pytest.fixture
def two_topics(course, course_payload, analysis_context):
    a=create_topic(course.owner,course.id,{"name":"Alpha"},"a")
    b=create_topic(course.owner,course.id,{"name":"Beta"},"b")
    pa,ca=scoped_payload(course_payload,analysis_context,a,"node-a")
    pb,cb=scoped_payload(course_payload,analysis_context,b,"node-b")
    # Use persisted user declaration, as a real preflight does.
    from app.courses.context import ensure_statements, statement_list
    ensure_statements(course)
    for p,c in ((pa,ca),(pb,cb)):
        c["statements"]=statement_list(course)
        p["scope_claims"][0]["statement_ids"]=[c["statements"][0]["id"]]
    publish_analysis(claim_task(submit_task(course,"analysis",{},"ta").id),pa,ca,"fixture")
    draft=publish_analysis(claim_task(submit_task(course,"analysis",{},"tb").id),pb,cb,"fixture")
    return a,b,draft


def test_blocked_b_does_not_block_a_and_same_revision_subsets_are_distinct(course,two_topics):
    a,b,draft=two_topics
    draft.payload["knowledge_nodes"][1]["readiness"]="unsupported";draft.save()
    first=confirm_topics(course.owner,course.id,draft.revision,None,[str(a.id)],"confirm-a")
    assert [n["id"] for n in first.frozen_payload["knowledge_nodes"]]==["node-a"]
    with pytest.raises(DomainError,match="COURSE_GAPS_BLOCK_CONFIRMATION"):
        confirm_topics(course.owner,course.id,draft.revision,str(first.id),[str(b.id)],"blocked-b")
    draft.payload["knowledge_nodes"][1]["readiness"]="supported";draft.save()
    second=confirm_topics(course.owner,course.id,draft.revision,str(first.id),[str(b.id)],"confirm-b")
    assert second.id!=first.id
    assert {n["id"] for n in second.frozen_payload["knowledge_nodes"]}=={"node-a","node-b"}
    assert confirm_topics(course.owner,course.id,draft.revision,str(first.id),[str(b.id)],"confirm-b").id==second.id
    first.refresh_from_db()
    assert len(first.frozen_payload["knowledge_nodes"])==1


def test_confirming_b_keeps_only_the_old_reviewed_a_snapshot(course,two_topics):
    a,b,draft=two_topics
    first=confirm_topics(course.owner,course.id,draft.revision,None,[str(a.id)],"a")
    original=copy.deepcopy(first.frozen_payload)
    draft,_=save_draft(course.owner,course.id,draft.revision,[{"path":["knowledge_nodes","node-a","requirements"],"value":"New unreviewed A edit"}],"edit",topic_id=str(a.id))
    second=confirm_topics(course.owner,course.id,draft.revision,str(first.id),[str(b.id)],"b")
    a_node=next(n for n in second.frozen_payload["knowledge_nodes"] if n["id"]=="node-a")
    assert a_node["requirements"]==original["knowledge_nodes"][0]["requirements"]
    first.refresh_from_db();assert first.frozen_payload==original


def test_shared_edit_requires_explicit_review_and_cannot_leak_other_topic_patch(course,two_topics):
    a,b,draft=two_topics
    first=confirm_topics(course.owner,course.id,draft.revision,None,[str(a.id),str(b.id)],"both")
    with pytest.raises(DomainError,match="PATCH_OUTSIDE_TOPIC"):
        save_draft(course.owner,course.id,draft.revision,[{"path":["knowledge_nodes","node-b","title"],"value":"Bad"}],"bad",topic_id=str(a.id))
    draft,_=save_draft(course.owner,course.id,draft.revision,[{"path":["target_exam","label"],"value":"Updated exam label"}],"common")
    second=confirm_topics(course.owner,course.id,draft.revision,str(first.id),[str(a.id)],"review-a")
    assert [m["topic_id"] for m in second.frozen_payload["topic_manifest"]]==[str(a.id)]
    assert first.frozen_payload["target_exam"]["label"]!="Updated exam label"


def test_manual_scope_statement_is_frozen_and_missing_evidence_is_rejected(course,two_topics):
    a,b,draft=two_topics
    draft,_=save_draft(course.owner,course.id,draft.revision,
        [{"path":["scope_claims","scope-node-a","text"],"value":"My adopted practice scope"}],"manual-claim",topic_id=str(a.id))
    version=confirm_topics(course.owner,course.id,draft.revision,None,[str(a.id)],"manual-confirm")
    claim=version.frozen_payload["scope_claims"][0]
    assert claim["provenance"]=="user_statement" and claim["authority_status"]=="unverified"
    assert set(claim["statement_ids"]) <= {s["id"] for s in version.statements}
    snapshot=version.evidence_manifest["topic_snapshots"][str(a.id)]
    assert snapshot["context"]["analysis_statements"]!=snapshot["context"]["statements"]
    draft.payload["knowledge_nodes"][0]["evidence_ids"]=["absent-source"]
    draft.save()
    with pytest.raises(DomainError,match="EVIDENCE_REFERENCE_INVALID"):
        confirm_topics(course.owner,course.id,draft.revision,str(version.id),[str(a.id)],"bad-source")
