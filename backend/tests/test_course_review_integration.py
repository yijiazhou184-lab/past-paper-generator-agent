import copy
import pytest
from app.core.errors import DomainError
from app.core.models import ModelInvocation
from app.core.tasks import submit_task,claim_task
from app.courses.analysis import publish_analysis
from app.courses.drafts import draft_view,answer_clarification
from app.courses.eligibility import save_review_selection
from app.courses.context import statement_list,ensure_statements
from app.courses.topics import create_topic
from app.courses.topic_confirmation import confirm_topics,assert_topic_generation_current
from test_topic_analysis import scoped_payload
from test_course_analysis import course_payload,analysis_context


@pytest.fixture
def review_draft(course,course_payload,analysis_context):
    topic=create_topic(course.owner,course.id,{"name":"Historical source analysis"},"topic")
    p,c=scoped_payload(course_payload,analysis_context,topic,"ready")
    ready=p["knowledge_nodes"][0]
    ready["node_kind"]="objective";ready["parent_id"]="group"
    missing={**copy.deepcopy(ready),"id":"missing","title":"Compare an additional source","readiness":"partial"}
    group={**copy.deepcopy(ready),"id":"group","title":"Historical enquiry","node_kind":"group","parent_id":None,"method_ids":[],"readiness":"partial"}
    p["knowledge_nodes"]=[group,ready,missing]
    for claim in p["scope_claims"]:claim["subject_ids"]=["group","ready","missing"]
    p["clarifications"]=[{"id":"convention","kind":"preference","decision_key":"practice-convention","question":"Which convention should practice use?",
        "reason":"Choose the practice convention.","affected_ids":["ready"],"impact":"needs_confirmation",
        "suggested_answers":["Course convention","Reference convention"],"resolves_issue_ids":[],"status":"open"}]
    ensure_statements(course);c["statements"]=statement_list(course)
    p["scope_claims"][0]["statement_ids"]=[c["statements"][0]["id"]]
    c["target_ids"]=["group","ready","missing"]
    draft=publish_analysis(claim_task(submit_task(course,"analysis",{},"analyse").id),p,c,"fixture")
    return topic,draft


def choose(course,topic,draft):
    q=next(q for q in draft_view(draft,str(topic.id))["clarifications"] if q["id"]=="convention")
    return answer_clarification(course.owner,course.id,q["id"],"",draft.revision,"choose",
        topic_id=str(topic.id),option_ids=[q["options"][0]["id"]],definition_hash=q["definition_hash"])


def test_fixed_choice_applies_without_model_and_partial_range_can_confirm(course,review_draft):
    topic,d=review_draft;d=choose(course,topic,d)
    view=draft_view(d,str(topic.id));q=next(q for q in view["clarifications"] if q["id"]=="convention")
    assert q["answer"]["application_status"]=="applied" and not view["answers_need_analysis"]
    assert not ModelInvocation.objects.exists()
    d=save_review_selection(course.owner,course.id,str(topic.id),d.revision,["ready"],"select")
    assert draft_view(d,str(topic.id))["blocking_count"]==0
    version=confirm_topics(course.owner,course.id,d.revision,None,[str(topic.id)],"confirm")
    assert version.frozen_payload["topic_manifest"][0]["knowledge_ids"]==["ready"]
    assert "missing" not in {n["id"] for n in version.frozen_payload["knowledge_nodes"]}
    assert version.statements[-1]["decision"]["requires_analysis"] is False
    assert_topic_generation_current(version,{"schema_version":"practice-config-v2","selected_topic_ids":[str(topic.id)],"knowledge_ids":["ready"]})


def test_partial_prerequisite_blocks_even_when_target_supported(course,review_draft):
    topic,d=review_draft;d=choose(course,topic,d)
    next(n for n in d.payload["knowledge_nodes"] if n["id"]=="ready")["prerequisite_ids"]=["missing"];d.save()
    d=save_review_selection(course.owner,course.id,str(topic.id),d.revision,["ready"],"select")
    assert not draft_view(d,str(topic.id))["eligibility"]["allowed"]
    with pytest.raises(DomainError,match="COURSE_GAPS_BLOCK_CONFIRMATION"):
        confirm_topics(course.owner,course.id,d.revision,None,[str(topic.id)],"confirm")


def test_changed_choice_definition_and_wrong_action_are_rejected(course,review_draft):
    topic,d=review_draft
    with pytest.raises(DomainError,match="DECISION_DEFINITION_CHANGED"):
        answer_clarification(course.owner,course.id,"convention","",d.revision,"bad",topic_id=str(topic.id),option_ids=["unknown"],definition_hash="old")
    d.refresh_from_db();assert d.revision==1
    gap=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["id"]=="gap-teaching-missing")
    with pytest.raises(DomainError,match="ANSWER_ACTION_REQUIRED"):
        answer_clarification(course.owner,course.id,gap["id"],"I know it",d.revision,"fake-evidence",topic_id=str(topic.id))


def test_stable_saved_choice_survives_question_id_and_wording_change(course,review_draft):
    topic,d=review_draft;d=choose(course,topic,d)
    q=d.payload["clarifications"][0];q["id"]="new-question-id";q["question"]="Select the convention for this practice";d.topic_state[str(topic.id)]["item_ids"]["clarifications"]=["new-question-id"];d.save()
    current=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["id"]=="new-question-id")
    assert current["answer"]["application_status"]=="applied"
    d.payload["clarifications"][0]["suggested_answers"]=["New definition","Another choice"];d.save()
    current=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["id"]=="new-question-id")
    assert current["decision_status"]=="needs_review" and "answer" not in current


def test_multi_choice_exam_scope_is_unverified_and_does_not_promote_teaching(course,review_draft):
    topic,d=review_draft;d=choose(course,topic,d)
    d.payload["scope_claims"]=[];d.topic_state[str(topic.id)]["item_ids"]["scope_claims"]=[];d.save()
    q=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["kind"]=="exam_scope")
    assert q["selection_mode"]=="multiple" and {o["id"] for o in q["options"]}=={"ready","missing"}
    d=answer_clarification(course.owner,course.id,q["id"],"",d.revision,"scope",
        topic_id=str(topic.id),option_ids=["ready","missing"],definition_hash=q["definition_hash"])
    view=draft_view(d,str(topic.id));claim=next(c for c in view["payload"]["scope_claims"] if c["provenance"]=="user_statement")
    assert claim["authority_status"]=="unverified" and claim["status"]=="declared"
    assert next(n for n in view["payload"]["knowledge_nodes"] if n["id"]=="missing")["readiness"]=="partial"
    d=save_review_selection(course.owner,course.id,str(topic.id),d.revision,["ready"],"select")
    assert draft_view(d,str(topic.id))["blocking_count"]==0
    assert confirm_topics(course.owner,course.id,d.revision,None,[str(topic.id)],"confirm")


def test_conflict_choice_adopts_practice_convention_and_retains_uncertainty(course,review_draft):
    topic,d=review_draft
    q=d.payload["clarifications"][0];q.update(kind="source_conflict",impact="blocks_selected_scope",resolves_issue_ids=["conflict"],option_actions=["practice_preference","practice_preference"])
    d.payload["issues"]=[{"id":"conflict","kind":"source_conflict","code":"CONFLICT","severity":"blocking",
        "affected_ids":["ready"],"explanation":"The two sources disagree.","evidence_ids":[],"suggested_action":None}]
    d.topic_state[str(topic.id)]["item_ids"]["issues"]=["conflict"];d.save()
    d=choose(course,topic,d)
    view=draft_view(d,str(topic.id));issue=view["payload"]["issues"][0]
    assert issue["severity"]=="warning" and "uncertainty is retained" in issue["explanation"]
    d=save_review_selection(course.owner,course.id,str(topic.id),d.revision,["ready"],"select")
    assert draft_view(d,str(topic.id))["blocking_count"]==0
    # A changed definition must not silently reuse that convention to unblock a conflict.
    d.payload["clarifications"][0]["suggested_answers"]=["Different choice","Another interpretation"];d.save()
    view=draft_view(d,str(topic.id))
    assert view["payload"]["issues"][0]["severity"]=="blocking"
    assert next(q for q in view["clarifications"] if q["id"]=="convention")["decision_status"]=="needs_review"


def test_choice_note_waits_for_interpretation_and_invalid_free_text_is_rejected(course,review_draft):
    topic,d=review_draft;q=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["id"]=="convention")
    with pytest.raises(DomainError,match="ANSWER_ACTION_REQUIRED"):
        answer_clarification(course.owner,course.id,q["id"],"Arbitrary substitute",d.revision,"text",topic_id=str(topic.id))
    d=answer_clarification(course.owner,course.id,q["id"],"",d.revision,"note",topic_id=str(topic.id),
        option_ids=[q["options"][0]["id"]],definition_hash=q["definition_hash"],note="A new course fact to interpret.")
    view=draft_view(d,str(topic.id));q=next(q for q in view["clarifications"] if q["id"]=="convention")
    assert q["answer"]["application_status"]=="needs_analysis" and view["answers_need_analysis"]
    assert not ModelInvocation.objects.exists()


def test_review_selection_api_enforces_owner_revision_and_idempotency(course,review_draft,django_user_model):
    from rest_framework.test import APIClient
    topic,d=review_draft;client=APIClient();url=f"/api/v1/courses/{course.id}/review-selection"
    body={"topic_id":str(topic.id),"expected_revision":d.revision,"knowledge_ids":["ready"]}
    client.force_authenticate(django_user_model.objects.create_user(username="outsider"))
    assert client.post(url,body,format="json",HTTP_IDEMPOTENCY_KEY="select").status_code==404
    client.force_authenticate(course.owner)
    assert client.post(url,body,format="json",HTTP_IDEMPOTENCY_KEY="select").status_code==200
    assert client.post(url,body,format="json",HTTP_IDEMPOTENCY_KEY="select").status_code==200
    assert client.post(url,body,format="json",HTTP_IDEMPOTENCY_KEY="stale").status_code==409
    d.refresh_from_db();assert d.revision==2


def test_changed_fixed_choice_requires_new_confirmation_before_generation(course,review_draft):
    topic,d=review_draft;d=choose(course,topic,d)
    d=save_review_selection(course.owner,course.id,str(topic.id),d.revision,["ready"],"select")
    version=confirm_topics(course.owner,course.id,d.revision,None,[str(topic.id)],"confirm")
    q=next(q for q in draft_view(d,str(topic.id))["clarifications"] if q["id"]=="convention")
    answer_clarification(course.owner,course.id,q["id"],"",d.revision,"change-choice",topic_id=str(topic.id),
        option_ids=[q["options"][1]["id"]],definition_hash=q["definition_hash"])
    with pytest.raises(DomainError,match="TOPIC_REVIEW_REQUIRED"):
        assert_topic_generation_current(version,{"schema_version":"practice-config-v2","selected_topic_ids":[str(topic.id)],"knowledge_ids":["ready"]})
