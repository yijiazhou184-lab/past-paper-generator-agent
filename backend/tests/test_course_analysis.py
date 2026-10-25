import copy
import pytest
from app.core.errors import DomainError
from app.courses.schemas import validate_payload
from app.courses.clarifications import classify_gaps


@pytest.fixture
def analysis_context():
    return {"target_ids": ["K1"], "statements": [{"id": "s1", "text": "All lecture content", "kind": "exam_scope"}],
            "evidence": [{"id": "e1", "roles": ["lecture"], "material_code": "M35", "text": "Synthetic teaching: derivatives and their domains."},
                         {"id": "e2", "roles": ["assessment"], "material_code": "M46", "text": "Synthetic assessment instructions: justify all conclusions."},
                         {"id": "e3", "roles": ["past_paper"], "material_code": "M05", "text": "Synthetic historical example: interpret a decreasing marginal rate."}]}


@pytest.fixture
def course_payload():
    return {"title": "Quantitative Methods", "target_exam": {"label": "Final exam", "academic_year": None},
        "knowledge_nodes": [{"id": "K1", "title": "Derivatives", "parent_id": None, "depth": 1,
            "prerequisite_ids": [], "method_ids": [], "evidence_ids": ["e1"], "readiness": "supported",
            "requirements": "Use the limit definition and check one-sided derivatives."}],
        "scope_claims": [{"id": "scope", "text": "All lecture content", "subject_ids": ["K1"],
            "applicability": "current_exam", "provenance": "user_statement", "authority_status": "unverified",
            "evidence_ids": [], "statement_ids": ["s1"], "status": "declared", "disposition": "include"}],
        "method_rules": [], "historical_style": [], "template_suggestion": None,
        "issues": [], "clarifications": []}


def test_user_scope_is_declared_not_official(course_payload, analysis_context):
    result = validate_payload(course_payload, analysis_context)
    assert result["scope_claims"][0]["provenance"] == "user_statement"
    assert not [q for q in classify_gaps(result, ["K1"]) if q["impact"] == "blocks_selected_scope"]
    bad = copy.deepcopy(course_payload)
    bad["scope_claims"][0]["authority_status"] = "verified"
    with pytest.raises(DomainError):
        validate_payload(bad, analysis_context)


def test_fake_source_rejected(course_payload, analysis_context):
    course_payload["knowledge_nodes"][0]["evidence_ids"] = ["another-course-source"]
    with pytest.raises(DomainError, match="EVIDENCE_REFERENCE_INVALID"):
        validate_payload(course_payload, analysis_context)


def test_paper_cannot_replace_teaching(course_payload, analysis_context):
    course_payload["knowledge_nodes"][0]["evidence_ids"] = ["e3"]
    payload = validate_payload(course_payload, analysis_context)
    assert payload["knowledge_nodes"][0]["readiness"] == "unsupported"
    assert any(q["impact"] == "blocks_selected_scope" for q in classify_gaps(payload, ["K1"]))


def test_missing_current_scope_blocks_but_no_current_paper_does_not(course_payload, analysis_context):
    assert not any(q["impact"] == "blocks_selected_scope" for q in classify_gaps(course_payload, ["K1"]))
    course_payload["scope_claims"][0]["applicability"] = "historical_mock"
    assert any(q["id"] == "gap-exam-scope" for q in classify_gaps(course_payload, ["K1"]))


def test_coursework_cannot_be_current_exam(course_payload, analysis_context):
    claim = course_payload["scope_claims"][0]
    claim.update(provenance="assessment_document", evidence_ids=["e2"], statement_ids=[], status="supported")
    with pytest.raises(DomainError, match="ASSESSMENT_APPLICABILITY_INVALID"):
        validate_payload(course_payload, analysis_context)
    claim["applicability"] = "coursework_1"
    assert validate_payload(course_payload, analysis_context)["scope_claims"][0]["applicability"] == "coursework_1"


def test_unrelated_conflict_is_informational(course_payload):
    course_payload["issues"] = [{"id": "lu-conflict", "code": "scope_conflict", "severity": "blocking",
        "affected_ids": ["Topic10"], "explanation": "LU scope requires clarification.", "evidence_ids": [],
        "suggested_action": "Check the Topic 10 scope."}]
    assert classify_gaps(course_payload, ["K1"])[0]["impact"] == "informational"


def test_existing_pdf_gap_is_grouped_not_repeated_as_upload_questions(course_payload):
    course_payload["knowledge_nodes"][0]["readiness"] = "partial"
    course_payload["issues"] = [{"id": "missing", "code": "MISSING_FORMULA", "severity": "blocking",
        "affected_ids": ["K1"], "explanation": "The extracted text omitted the formula.", "evidence_ids": ["e1"], "suggested_action": None}]
    course_payload["clarifications"] = [{"id": "q1", "question": "Upload a readable page?", "reason": "Formula absent from extraction",
        "affected_ids": ["K1"], "impact": "blocks_selected_scope", "suggested_answers": [], "resolves_issue_ids": ["missing"], "status": "open"}]
    questions = classify_gaps(course_payload, ["K1"])
    assert len(questions) == 1
    assert questions[0]["action_kind"] == "review_existing_sources"
    assert questions[0]["evidence_ids"] == ["e1"]


def test_teaching_cannot_be_relabelled_as_official_scope(course_payload, analysis_context):
    claim = course_payload["scope_claims"][0]
    claim.update(provenance="assessment_document", evidence_ids=["e1"], statement_ids=[], status="supported")
    with pytest.raises(DomainError, match="SOURCE_PROVENANCE_MISMATCH"):
        validate_payload(course_payload, analysis_context)
