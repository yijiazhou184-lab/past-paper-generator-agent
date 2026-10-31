
"""Source comparison decisions are code-owned; all model responses here are synthetic."""
import copy
from unittest.mock import patch
import pytest
from app.generation.source_originality import build_source_targets, source_originality_checks
from app.generation.content_schemas import SourceOverlap, SemanticOutput
from app.generation.duplicates import duplicate_candidates
from app.generation.generator import run_generation
from app.generation import semantic_review
from app.core.errors import DomainError
from test_generation_execution import start
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def pair():
    return {"question_id": "q1", "stem": [{"type": "text", "text": "Compare the observations."}],
            "parts": [{"part_id": "q1a", "prompt": [{"type": "text", "text": "Explain the change in demand."}]}]}


def fact(stimulus=False, conclusion=True, **extra):
    return {"subpart_id": "q1a", "source_id": "s1", "same_stimulus": stimulus,
            "same_conclusion": conclusion, "note": None, **extra}


TARGETS = [{"subpart_id": "q1a", "source_ids": ["s1"]}]


@pytest.mark.parametrize("stimulus,conclusion,result", [
    (True, True, "fail"), (False, True, "pass"), (True, False, "pass"),
    (False, False, "pass"), (None, True, "inconclusive"), (True, None, "inconclusive"),
    (None, None, "inconclusive"), (False, None, "pass"), (None, False, "pass"),
])
def test_rule_uses_only_the_two_required_facts(stimulus, conclusion, result):
    checks = source_originality_checks([pair()], [fact(stimulus, conclusion)], TARGETS, {"s1"}, reviewed=True)
    assert checks[0]["result"] == result
    assert checks[0]["required_for_release"] and checks[0]["method"] == "source_originality_rule"
    assert checks[0]["check_id"] == "semantic:q1:originality"


def test_missing_incomplete_unknown_and_conflicting_facts_never_become_pass():
    assert source_originality_checks([pair()], [], TARGETS, {"s1"}, reviewed=False)[0]["result"] == "not_checked"
    assert source_originality_checks([pair()], [], TARGETS, {"s1"}, reviewed=True)[0]["result"] == "inconclusive"
    assert source_originality_checks([pair()], [fact(source_id="unknown")], TARGETS, {"s1"}, reviewed=True)[0]["result"] == "inconclusive"
    assert source_originality_checks([pair()], [fact(), fact(True, True)], TARGETS, {"s1"}, reviewed=True)[0]["result"] == "inconclusive"
    assert source_originality_checks([pair()], [], [], set(), reviewed=True)[0]["result"] == "inconclusive"


def test_additional_valid_duplicate_blocks_even_when_required_pair_passes():
    checks = source_originality_checks([pair()], [fact(), fact(True, True, source_id="s2")],
                                      TARGETS, {"s1", "s2"}, reviewed=True)
    assert checks[0]["result"] == "fail"
    assert checks[0]["duplicate_sources"] == [{"subpart_id": "q1a", "source_id": "s2"}]
    assert "s2" in checks[0]["evidence_ids"]


def test_targets_are_bounded_deduplicated_and_stable():
    candidates = [
        {"source_id": "s1", "chunk_index": 0, "text": "Explain the change in demand.", "target_ids": ["q1"]},
        {"source_id": "s1", "chunk_index": 1, "text": "Demand changes.", "target_ids": ["q1"]},
        {"source_id": "s2", "chunk_index": 0, "text": "Demand and supply observations.", "target_ids": ["q1"]},
        {"source_id": "s3", "chunk_index": 0, "text": "Unrelated classification.", "target_ids": ["q1"]},
        {"source_id": "outside", "chunk_index": 0, "text": "Explain the change in demand.", "target_ids": ["q2"]},
    ]
    before = copy.deepcopy(candidates)
    targets = build_source_targets([pair()], {"candidates": candidates})
    assert targets == [{"subpart_id": "q1a", "source_ids": ["s1", "s2"]}]
    assert targets == build_source_targets([pair()], {"candidates": list(reversed(candidates))})
    assert candidates == before


def test_minimal_schema_and_number_swap_program_check_are_preserved():
    schema = SourceOverlap.model_json_schema()
    assert set(schema["properties"]) == {"subpart_id", "source_id", "same_stimulus", "same_conclusion", "note"}
    assert set(schema["required"]) == set(schema["properties"])
    assert "source_overlaps" in SemanticOutput.model_json_schema()["required"]
    sample = pair()
    sample["stem"] = [{"type": "text", "text": "A shop sells 12 units at a price of 8 each."}]
    source = {"id": "s1", "content": "A shop sells 99 units at a price of 3 each. Explain the change in demand."}
    result = duplicate_candidates([sample], [source], [])
    assert any(f["code"] == "NUMBER_SWAP_DUPLICATE" for f in result["findings"])


def test_empty_facts_block_without_unjustified_repair(course, planned):
    task, _, token = start(course, planned)
    actual = semantic_review.stage_output
    def missing(token, key, stage, data, output_type, fixture):
        output = actual(token, key, stage, data, output_type, fixture)
        if data["review_mode"] == "required":
            output["source_overlaps"] = []
        return output
    with patch.object(semantic_review, "stage_output", side_effect=missing):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "failed" and task.candidates.count() == 1
    checks = task.candidates.get().check_report.payload["checks"]
    assert all(c["result"] == "inconclusive" for c in checks if c["check_id"].endswith(":originality"))
    assert task.call_count == 0


def test_source_duplicate_repairs_only_its_question_and_saves_both_reports(course, planned):
    from app.generation import repair
    task, context, token = start(course, planned)
    target = context["input"]["questions"][0]["blueprint"]["id"]
    actual, generate = semantic_review.stage_output, repair.generate_groups
    repair_targets = []
    def review(token, key, stage, data, output_type, fixture):
        output = actual(token, key, stage, data, output_type, fixture)
        if data["review_mode"] == "required" and key.startswith("r0:"):
            output["source_overlaps"][0].update(same_stimulus=True, same_conclusion=True, note=None)
        return output
    def capture(token, context, questions, **kwargs):
        repair_targets.append([q["blueprint"]["id"] for q in questions])
        return generate(token, context, questions, **kwargs)
    with patch.object(semantic_review, "stage_output", side_effect=review), patch.object(repair, "generate_groups", side_effect=capture):
        run_generation(token)
    task.refresh_from_db()
    first, second = list(task.candidates.order_by("revision"))
    assert task.state == "succeeded" and repair_targets == [[target]]
    assert first.payload["pairs"][1:] == second.payload["pairs"][1:]
    assert first.check_report.payload["source_overlaps"][0]["same_stimulus"] is True
    assert not first.check_report.gate["allowed"] and second.check_report.gate["allowed"]
    assert len(second.check_report.payload["source_overlaps"]) > 0
    assert task.call_count == 0


def test_split_review_persists_every_group_without_paper_rechecking_sources(course, planned):
    task, _, token = start(course, planned)
    actual = semantic_review.stage_output
    observed = []
    def bounded(token, key, stage, data, output_type, fixture):
        if data["review_mode"] == "required" and len(data["question_ids"]) > 1:
            raise DomainError("TOKEN_BUDGET_EXCEEDED")
        if data["review_mode"] in ("paper", "optional"):
            assert data["source_overlap_targets"] == []
        observed.extend(data["source_overlap_targets"])
        return actual(token, key, stage, data, output_type, fixture)
    with patch.object(semantic_review, "stage_output", side_effect=bounded):
        run_generation(token)
    task.refresh_from_db()
    report = task.candidates.get().check_report
    assert task.state == "succeeded"
    assert report.payload["source_overlap_targets"] == observed
    assert {(f["subpart_id"], f["source_id"]) for f in report.payload["source_overlaps"]} == {
        (t["subpart_id"], sid) for t in observed for sid in t["source_ids"]}
    assert task.call_count == 0


def test_changed_originality_policy_requires_new_preflight(course, planned):
    from app.core.idempotency import digest
    from app.generation.runtime import verify_context
    task, context, _ = start(course, planned)
    assert context["pipeline_version"] == "generation-v6"
    assert context["originality_policy"]["version"] == "originality-policy-v2"
    task.snapshot = copy.deepcopy(context)
    task.snapshot["originality_policy"]["max_source_pages_per_part"] = 99
    task.snapshot["context_hash"] = digest({k: v for k, v in task.snapshot.items() if k != "context_hash"})
    with pytest.raises(DomainError, match="GENERATION_ORIGINALITY_POLICY_CHANGED"):
        verify_context(task)


def test_interrupted_split_preserves_completed_source_facts(course, planned):
    from app.generation.check_progress import progress_report
    task, _, token = start(course, planned)
    actual = semantic_review.stage_output
    completed = []
    def interrupted(token, key, stage, data, output_type, fixture):
        if data["review_mode"] == "required" and len(data["question_ids"]) > 1:
            raise DomainError("TOKEN_BUDGET_EXCEEDED")
        if data["review_mode"] == "required":
            if completed:
                raise DomainError("MODEL_OUTCOME_UNKNOWN")
            result = actual(token, key, stage, data, output_type, fixture)
            completed.extend(data["question_ids"])
            return result
        return actual(token, key, stage, data, output_type, fixture)
    with patch.object(semantic_review, "stage_output", side_effect=interrupted):
        with pytest.raises(DomainError, match="MODEL_OUTCOME_UNKNOWN"):
            run_generation(token)
    report = progress_report(task.candidates.get())
    assert report["source_overlaps"] and not report["gate"]["allowed"]
    checked = [c for c in report["checks"] if c["check_id"].endswith(":originality")]
    assert any(c["result"] == "pass" for c in checked)
    assert any(c["result"] == "not_checked" for c in checked)
    assert task.call_count == 0
