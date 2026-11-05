import copy
from app.courses.clarifications import classify_gaps
from app.courses.eligibility import eligible_targets
from app.courses.decisions import decision_identity


def payload():
    return {"knowledge_nodes":[
        {"id":"chapter","title":"A chapter","node_kind":"group","readiness":"partial","parent_id":None,"prerequisite_ids":[],"evidence_ids":[]},
        {"id":"ready","title":"Source interpretation","node_kind":"objective","readiness":"supported","parent_id":"chapter","prerequisite_ids":[],"evidence_ids":["page"]},
        {"id":"missing","title":"Evidence-based argument","node_kind":"objective","readiness":"partial","parent_id":"chapter","prerequisite_ids":[],"evidence_ids":["page"]}],
        "scope_claims":[{"applicability":"current_exam","status":"declared","disposition":"include","subject_ids":["chapter","ready","missing"]}],
        "issues":[],"clarifications":[]}


def test_reading_gap_is_an_action_not_an_empty_text_question():
    q=next(q for q in classify_gaps(payload(),["ready","missing"]) if "missing" in q["affected_ids"])
    assert q["action_kind"]=="review_existing_sources"
    assert q["evidence_ids"]==["page"] and not q["allows_free_text"]
    assert "missing" in q["affected_ids"]


def test_unknown_question_without_options_requires_review():
    p=payload();p["clarifications"]=[{"id":"q","question":"An unresolved question","reason":"Unknown","affected_ids":["ready"],"impact":"needs_confirmation","suggested_answers":[],"resolves_issue_ids":[],"status":"open"}]
    q=next(q for q in classify_gaps(p,["ready"]) if q["id"]=="q")
    assert q["action_kind"]=="review_required" and not q["allows_free_text"]


def test_group_does_not_independently_require_teaching_evidence():
    report=eligible_targets(payload(),["ready"])
    assert report["allowed"] and report["objective_ids"]==["ready"]
    assert not any("chapter" in q["affected_ids"] for q in report["blockers"])


def test_selected_missing_target_and_missing_prerequisite_still_block():
    p=payload();p["knowledge_nodes"][1]["prerequisite_ids"]=["missing"]
    report=eligible_targets(p,["ready"])
    assert not report["allowed"] and set(report["objective_ids"])=={"ready","missing"}
    assert report["blockers"]
    assert not eligible_targets(payload(),["missing"])["allowed"]


def test_empty_unknown_or_group_only_selection_cannot_confirm():
    from app.core.errors import DomainError
    import pytest
    for selected in ([],["unknown"],["chapter"]):
        with pytest.raises(DomainError):eligible_targets(payload(),selected)


def test_decision_identity_survives_question_id_change_but_checks_option_definition():
    q={"id":"one","decision_key":"practice-policy","kind":"preference","question":"Choose a convention","affected_ids":["ready"],"suggested_answers":["First","Second"]}
    k,h=decision_identity(q,["topic"]);q2={**q,"id":"two","question":"Which convention should practice use?"}
    assert decision_identity(q2,["topic"])==(k,h)
    assert decision_identity({**q2,"suggested_answers":["First","Changed"]},["topic"])[1]!=h
    assert decision_identity(q,["other-topic"])[0]!=k


def test_unselected_gap_remains_visible_without_blocking_supported_objectives():
    questions=classify_gaps(payload(),["ready"])
    gap=next(q for q in questions if q["id"]=="gap-teaching-missing")
    assert gap["impact"]=="informational" and gap["action_kind"]=="evidence_note"
    assert gap["evidence_ids"]==["page"]


def test_local_example_with_alternate_support_is_not_a_definition_gap():
    p=payload();p["knowledge_nodes"][1]["evidence_ids"]=["unreadable-example","other-teaching"]
    p["issues"]=[{"id":"reading","code":"READING_GAP","kind":"processing_gap","coverage_role":"supporting_example",
        "affected_ids":["ready"],"evidence_ids":["unreadable-example"],"severity":"blocking",
        "explanation":"A local example is unreadable.","suggested_action":None}]
    assert eligible_targets(p,["ready"])["allowed"]
    p["issues"][0]["coverage_role"]="required_content"
    assert not eligible_targets(p,["ready"])["allowed"]
    p["issues"][0]["coverage_role"]="supporting_example"
    p["knowledge_nodes"][1]["evidence_ids"]=["unreadable-example"]
    assert not eligible_targets(p,["ready"])["allowed"]


def test_group_scoped_required_issue_blocks_its_selected_objective():
    p=payload();p["issues"]=[{"id":"required","code":"GAP","kind":"source_gap","coverage_role":"required_content",
        "affected_ids":["chapter"],"evidence_ids":["page"],"severity":"blocking",
        "explanation":"A required chapter condition is absent.","suggested_action":None}]
    assert not eligible_targets(p,["ready"])["allowed"]


def test_unknown_issue_is_not_promoted_to_a_preference_by_having_options():
    from app.courses.issue_actions import decorate_action
    q=decorate_action({"kind":"review_required","action_kind":"clarification","suggested_answers":["First","Second"]})
    assert q["action_kind"]=="review_required" and not q["allows_free_text"]


def test_reanalysis_input_retains_model_decision_key_and_definition():
    from app.courses.decisions import prior_decisions
    q={"id":"old-id","kind":"preference","decision_key":"course-convention","question":"Choose the convention",
       "affected_ids":["ready"],"suggested_answers":["First","Second"],"option_actions":["practice_preference","practice_preference"],
       "selection_mode":"single","reason":"An explanation that need not be repeated"}
    frozen=prior_decisions({"clarifications":[q]})[0]
    assert frozen["decision_key"]=="course-convention" and frozen["suggested_answers"]==["First","Second"]
    assert "reason" not in frozen
