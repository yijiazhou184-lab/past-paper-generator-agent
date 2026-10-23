import copy
import pytest
from django.http import Http404
from app.core.errors import DomainError
from app.core.tasks import submit_task, claim_task, cancel_task
from app.courses.analysis import publish_analysis
from app.courses.models import CourseDraft, UserStatement
from app.courses.drafts import save_draft, answer_clarification, draft_view
from app.courses.confirmation import confirm_course
from test_course_analysis import course_payload, analysis_context


@pytest.fixture
def draft(course, course_payload, analysis_context):
    statement = UserStatement.objects.create(course=course, text="All lecture content", kind="exam_scope", source="User", submitted_by=course.owner)
    course_payload["scope_claims"][0]["statement_ids"] = [str(statement.id)]
    analysis_context["statements"][0]["id"] = str(statement.id)
    analysis_context["materials"] = []
    for e in analysis_context["evidence"]:
        e.update(material_version_id="fixture-version", physical_page=1)
    task = submit_task(course, "analysis", {}, "draft-fixture")
    return publish_analysis(claim_task(task.id), course_payload, analysis_context, "fixture")


def test_save_cas_idempotency_and_immutable_version(course, draft):
    first = confirm_course(course.owner, course.id, draft.id, 1, "confirm-1")
    assert first.evidence_manifest["analysis_mode"] == "fixture"
    patch = [{"path": ["knowledge_nodes", "K1", "requirements"], "value": "My revised study requirement"}]
    changed, rev = save_draft(course.owner, course.id, 1, patch, "save-1")
    assert rev == 2
    assert save_draft(course.owner, course.id, 1, patch, "save-1")[1] == 2
    with pytest.raises(DomainError, match="DRAFT_REVISION_CONFLICT"):
        save_draft(course.owner, course.id, 1, patch, "stale-save")
    with pytest.raises(DomainError, match="DRAFT_REVISION_CONFLICT"):
        confirm_course(course.owner, course.id, draft.id, 1, "new-stale-confirm")
    assert confirm_course(course.owner, course.id, draft.id, 1, "confirm-1").id == first.id
    first.refresh_from_db()
    assert first.frozen_payload["knowledge_nodes"][0]["requirements"] != changed.payload["knowledge_nodes"][0]["requirements"]
    with pytest.raises(ValueError):
        first.save()
    second = confirm_course(course.owner, course.id, draft.id, 2, "confirm-2")
    assert second.number == 2
    assert second.frozen_payload["knowledge_nodes"][0]["requirements"] == patch[0]["value"]


def test_reanalysis_retains_latest_manual_edit_and_reports_diff(course, draft):
    task = submit_task(course, "analysis", {}, "reanalyse")
    token = claim_task(task.id)
    save_draft(course.owner, course.id, 1, [{"path": ["knowledge_nodes", "K1", "title"], "value": "My title"}], "edit-during-call")
    machine = copy.deepcopy(draft.machine_base.payload)
    machine["knowledge_nodes"][0]["title"] = "New machine title"
    updated = publish_analysis(token, machine, draft.machine_base.context, "fixture")
    assert updated.revision == 3
    assert updated.payload["knowledge_nodes"][0]["title"] == "My title"
    assert updated.merge_warnings
    with pytest.raises(DomainError, match="MERGE_REVIEW_REQUIRED"):
        confirm_course(course.owner, course.id, updated.id, 3, "confirm-diff")


def test_answer_is_statement_and_does_not_fill_teaching_gap(course, draft):
    draft.payload["knowledge_nodes"][0]["readiness"] = "unsupported"
    draft.save()
    changed = answer_clarification(course.owner, course.id, "gap-teaching-K1", "I know derivatives", 1, "answer-1")
    assert changed.revision == 2
    q = next(q for q in draft_view(changed)["clarifications"] if q["id"] == "gap-teaching-K1")
    assert q["status"] == "answered" and q["impact"] == "blocks_selected_scope"
    assert course.statements.filter(kind="clarification").count() == 1
    with pytest.raises(DomainError, match="COURSE_GAPS_BLOCK_CONFIRMATION"):
        confirm_course(course.owner, course.id, draft.id, 2, "confirm-gap")


def test_cancelled_analysis_cannot_publish(course, draft):
    task = submit_task(course, "analysis", {}, "cancel-analyse")
    token = claim_task(task.id)
    cancel_task(course.owner, task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        publish_analysis(token, draft.payload, draft.machine_base.context, "fixture")
    assert CourseDraft.objects.get(course=course).revision == 1


def test_provenance_not_editable_but_claim_edit_is_user_statement(course, draft):
    with pytest.raises(DomainError):
        save_draft(course.owner, course.id, 1, [{"path": ["scope_claims", "scope", "authority_status"], "value": "verified"}], "bad")
    changed, _ = save_draft(course.owner, course.id, 1, [{"path": ["scope_claims", "scope", "text"], "value": "My scope note"}], "good")
    assert changed.payload["scope_claims"][0]["provenance"] == "user_statement"
    assert changed.machine_base.payload["scope_claims"][0]["text"] == "All lecture content"
    assert changed.manual_patches[0]["statement_id"]


def test_invalid_template_and_cross_owner_changes_rejected(course, draft, django_user_model):
    other = django_user_model.objects.create_user(username="other")
    with pytest.raises(Http404):
        save_draft(other, course.id, 1, [], "outsider")
    template = {"label": "suggested", "calibration": "not_calibrated_to_current_exam", "question_types": ["calculation"],
        "sections": [{"title": "All", "main_questions": 2, "marks_per_question": 10, "selection": "all", "choose_count": 1}],
        "duration_minutes": 30, "total_marks": 20, "rationale": "Test suggestion"}
    with pytest.raises(DomainError, match="TEMPLATE_SELECTION_INVALID"):
        save_draft(course.owner, course.id, 1, [{"path": ["template_suggestion"], "value": template}], "bad-template")
    draft.refresh_from_db()
    assert draft.revision == 1


def test_answer_keeps_the_question_it_answers(course, draft):
    from app.courses.context import statement_list
    draft.payload["clarifications"] = [{"id": "q-pref", "question": "Which practice treatment for flagged source departures?",
        "reason": "Five printed statements depart from standard usage.", "affected_ids": ["K1"], "impact": "needs_confirmation",
        "suggested_answers": ["Follow the course material as printed", "Use the standard definition and note the difference"],
        "resolves_issue_ids": [], "status": "open"}]
    draft.save()
    answer_clarification(course.owner, course.id, "q-pref", "Use the standard definition and note the difference", 1, "answer-pref")
    statement = course.statements.get(clarification_id="q-pref")
    assert statement.question == "Which practice treatment for flagged source departures?"
    sent = next(s for s in statement_list(course) if s["clarification_id"] == "q-pref")
    assert sent["question"] == statement.question and sent["text"] == "Use the standard definition and note the difference"
