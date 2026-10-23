import copy
import pytest
from app.core.errors import DomainError
from app.generation.schemas import validate_blueprint


@pytest.fixture
def blueprint_inputs():
    config = {"course_version_id": "00000000-0000-0000-0000-000000000001", "mode": "chapter_practice",
              "topic_ids": ["K1", "K2", "K3"], "difficulty": "exam_standard", "main_question_count": 2,
              "question_types": ["calculation", "explanation_proof", "applied_optimisation"]}
    course = {"knowledge_nodes": [{"id": k, "readiness": "supported", "evidence_ids": ["e1"]} for k in config["topic_ids"]],
              "scope_claims": [], "historical_style": []}
    evidence = [{"id": "e1", "roles": ["lecture"]}]
    questions = []
    for n in range(1, 3):
        questions.append({"id": f"q{n}", "number": n, "title": f"Practice question {n}", "objective": "Connect methods and interpretation",
            "knowledge_ids": config["topic_ids"], "evidence_ids": ["e1"],
            "parts": [{"id": f"q{n}{letter}", "label": letter, "response_type": kind, "marks": marks,
                       "knowledge_ids": [kid], "asset_needs": []}
                      for letter, kind, kid, marks in zip("abc", config["question_types"], config["topic_ids"], [3, 2, 4])]})
    payload = {"sections": [{"id": "s1", "title": "Topic 2 practice", "question_ids": ["q1", "q2"],
                            "selection": {"mode": "all", "choose_count": 2}}],
        "questions": questions, "main_question_count": 2, "subquestion_count": 6, "subquestion_count_locked": True,
        "printed_marks": 18, "attempt_marks": 18, "suggested_minutes": 30,
        "coverage": [{"knowledge_id": k, "question_ids": ["q1", "q2"]} for k in config["topic_ids"]],
        "differences": [], "calibration": "uncalibrated"}
    return config, payload, course, evidence


def test_two_main_questions_cover_many_topics_and_mixed_types(blueprint_inputs):
    result = validate_blueprint(*blueprint_inputs)
    assert result["main_question_count"] == 2
    assert result["attempt_marks"] == 18
    assert len(result["coverage"]) == 3


@pytest.mark.parametrize("damage,code", [
    (lambda p: p.update(printed_marks=99), "MARKS_MISMATCH"),
    (lambda p: p["sections"][0]["selection"].update(choose_count=3), "INVALID_SELECTION"),
    (lambda p: p["questions"][0]["parts"][0].update(marks=0.3), "BLUEPRINT_SCHEMA_INVALID"),
    (lambda p: p["questions"][1].update(number=1), "QUESTION_NUMBER_INVALID"),
    (lambda p: p["questions"][1]["parts"][0].update(id="q1a"), "DUPLICATE_IDENTIFIER"),
    (lambda p: p["questions"][0].update(evidence_ids=["foreign-source"]), "EVIDENCE_REFERENCE_INVALID"),
    (lambda p: p["questions"][0]["parts"][0].update(knowledge_ids=["other-topic"]), "KNOWLEDGE_OUTSIDE_SELECTION"),
    (lambda p: p.update(coverage=[]), "COVERAGE_MISMATCH"),
    (lambda p: p.update(calibration="historical_reference"), "CALIBRATION_UNSUPPORTED"),
])
def test_invalid_blueprint_rejected(blueprint_inputs, damage, code):
    config, payload, course, evidence = copy.deepcopy(blueprint_inputs)
    damage(payload)
    with pytest.raises(DomainError, match=code):
        validate_blueprint(config, payload, course, evidence)


def test_missing_selected_type_rejected(blueprint_inputs):
    config, payload, course, evidence = blueprint_inputs
    for q in payload["questions"]:
        q["parts"][2]["response_type"] = "calculation"
    with pytest.raises(DomainError, match="QUESTION_TYPE_MISSING"):
        validate_blueprint(config, payload, course, evidence)


def test_historical_reference_cannot_replace_teaching_evidence(blueprint_inputs):
    config, payload, course, evidence = blueprint_inputs
    evidence.append({"id": "historical", "roles": ["past_paper"]})
    for node in course["knowledge_nodes"]:
        node["evidence_ids"].append("historical")
    payload["questions"][0]["evidence_ids"] = ["historical"]
    with pytest.raises(DomainError, match="KNOWLEDGE_EVIDENCE_MISSING"):
        validate_blueprint(config, payload, course, evidence)
    payload["questions"][0]["evidence_ids"].append("e1")
    assert validate_blueprint(config, payload, course, evidence)["attempt_marks"] == 18


def test_choice_marks_are_computable_and_constraints_hold_for_each_choice(blueprint_inputs):
    config, payload, course, evidence = blueprint_inputs
    payload["sections"][0]["selection"] = {"mode": "choose", "choose_count": 1}
    payload["attempt_marks"] = 9
    assert validate_blueprint(config, payload, course, evidence)["attempt_marks"] == 9
    payload["questions"][0]["parts"][0]["marks"] = 3.5
    payload["printed_marks"] = 18.5
    with pytest.raises(DomainError, match="UNEQUAL_CHOICE_MARKS"):
        validate_blueprint(config, payload, course, evidence)


def test_insufficient_selected_evidence_and_excluded_scope_rejected(blueprint_inputs):
    config, payload, course, evidence = blueprint_inputs
    course["knowledge_nodes"][0]["readiness"] = "partial"
    with pytest.raises(DomainError, match="SELECTED_KNOWLEDGE_NOT_READY"):
        validate_blueprint(config, payload, course, evidence)
    course["knowledge_nodes"][0]["readiness"] = "supported"
    course["scope_claims"] = [{"subject_ids": ["K1"], "disposition": "exclude", "applicability": "current_exam"}]
    with pytest.raises(DomainError, match="SELECTED_KNOWLEDGE_EXCLUDED"):
        validate_blueprint(config, payload, course, evidence)
