"""The user's intra-paper repetition rule is applied by code to reported facts (2026-10-29 decision).

These tests check that code applies the rule correctly; they do not evaluate a model's judgement.
"""
import copy
from unittest.mock import patch
from app.generation import semantic_review
from app.generation.generator import run_generation
from app.generation.originality_policy import judge, POLICY
from app.generation.shared_material import overlap_hints
from test_generation_execution import start
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft

PARTS = {"q1d": "q1", "q3d": "q3", "q2a": "q2", "q1a": "q1"}


def fact(a, b, same_stimulus, same_conclusion, ca="Conclusion A", cb="Conclusion B"):
    return {"part_a": a, "part_b": b, "same_stimulus": same_stimulus, "stimulus_basis": "Stated basis.",
            "conclusion_a": ca, "conclusion_b": cb, "same_conclusion": same_conclusion}


def test_same_stimulus_different_conclusion_is_accepted():
    # 7496b3cb: one function in both parts; the final results asked for differ.
    facts = [fact("q1d", "q3d", True, False,
                  "Differentiability at 0 and discontinuity of the derivative",
                  "The value of a limit and the oscillation of a derivative ratio")]
    result, reason, pairs = judge(facts, [{"parts": ["q1d", "q3d"]}], PARTS, reviewed=True)
    assert result == "pass" and pairs == []


def test_same_conclusion_different_stimulus_is_accepted():
    result, _, pairs = judge([fact("q1a", "q2a", False, True)], [], PARTS, reviewed=True)
    assert result == "pass" and pairs == []


def test_same_stimulus_and_same_conclusion_is_a_duplicate():
    result, reason, pairs = judge([fact("q1d", "q3d", True, True)], [], PARTS, reviewed=True)
    assert result == "fail" and pairs == [["q1d", "q3d"]] and "q1d and q3d" in reason


def test_detected_shared_material_without_facts_is_not_a_pass():
    result, reason, _ = judge([], [{"parts": ["q3d", "q1d"]}], PARTS, reviewed=True)
    assert result == "inconclusive" and "q1d and q3d" in reason


def test_missing_review_is_not_checked_and_same_question_pairs_are_ignored():
    assert judge([], [], PARTS, reviewed=False)[0] == "not_checked"
    result, reason, _ = judge([fact("q1d", "q1a", True, True)], [], PARTS, reviewed=True)
    assert result == "pass" and "Ignored invalid pairs" in reason


def test_policy_text_is_generic_and_scoped_to_this_paper():
    text = " ".join(str(v) for v in POLICY.values()).lower()
    assert "same stimulus and the same final conclusion" in text
    assert "course and historical material keep the earlier rule" in text
    # AGENTS.md section 3: no subject or course content in the code-owned rule.
    for word in ("x^2", "sin", "derivative", "limit", "accounting", "qm", "msin"):
        assert word not in text


def num(v): return {"op": "number", "value": str(v), "args": []}
def x(): return {"op": "variable", "value": "x", "args": []}
def op(name, *args): return {"op": name, "value": None, "args": list(args)}


def pair(qid, part_id, expr):
    return {"question_id": qid, "parts": [{"part_id": part_id}],
            "answers": [{"part_id": part_id, "checks": [{"expression": expr, "denominator": None}]}]}


def test_math_hints_find_shared_material_across_questions_only():
    oscillating = op("mul", op("pow", x(), num(2)), op("sin", op("div", num(1), x())))
    ratio = op("mul", x(), op("sin", op("div", num(1), x())))
    hints = overlap_hints([pair("q1", "q1d", oscillating), pair("q3", "q3d", ratio)])
    assert hints and hints[0]["parts"] == ["q1d", "q3d"]
    polynomial = op("add", op("pow", x(), num(2)), num(1))
    assert overlap_hints([pair("q1", "q1a", polynomial), pair("q2", "q2a", polynomial)]) == []


def run_with_facts(course, planned, overlaps):
    task, context, token = start(course, planned)
    actual = semantic_review.stage_output
    def reviewed(token, key, stage, data, output_type, fixture):
        output = actual(token, key, stage, data, output_type, fixture)
        if data["include_paper_check"]:
            output = copy.deepcopy(output)
            output["intra_paper_overlaps"] = overlaps(data)
        return output
    with patch.object(semantic_review, "stage_output", side_effect=reviewed):
        run_generation(token)
    task.refresh_from_db()
    return task


def parts_of(data):
    pairs = data["candidate"]["pairs"]
    return pairs[0]["parts"][0]["part_id"], pairs[-1]["parts"][0]["part_id"]


def test_whole_run_accepts_same_material_with_different_conclusions(course, planned):
    task = run_with_facts(course, planned, lambda d: [fact(*parts_of(d), True, False)])
    report = task.candidates.get().check_report
    item = next(c for c in report.payload["checks"] if c["check_id"] == "paper:intra_duplicates")
    assert item["result"] == "pass" and item["method"] == "intra_paper_rule" and item["required_for_release"]
    assert task.state == "succeeded"


def test_whole_run_blocks_and_repairs_only_the_later_question(course, planned):
    from app.generation import repair
    targeted = []
    original = repair.generate_groups
    def capture(token, context, questions, **kwargs):
        targeted.append(sorted(kwargs["repair_requests"]))
        return original(token, context, questions, **kwargs)
    order = []
    def facts(data):
        order[:] = [p["question_id"] for p in data["candidate"]["pairs"]]
        return [fact(*parts_of(data), True, True)]
    with patch.object(repair, "generate_groups", side_effect=capture):
        task = run_with_facts(course, planned, facts)
    first = task.candidates.get(revision=1).check_report
    item = next(c for c in first.payload["checks"] if c["check_id"] == "paper:intra_duplicates")
    assert item["result"] == "fail" and first.gate["allowed"] is False
    assert targeted == [[order[-1]]]  # only the later question of the duplicate pair is repaired


def test_evaluation_set_is_well_formed_and_covers_the_three_cases():
    import json, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / "backend/tests/fixtures/intra_paper_overlap_eval.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len({c["id"] for c in cases}) == len(cases)
    expected_by_category = {"same_stimulus_different_conclusion": (True, False),
                            "different_stimulus_same_conclusion": (False, True),
                            "same_stimulus_same_conclusion": (True, True)}
    for c in cases:
        assert (c["expected"]["same_stimulus"], c["expected"]["same_conclusion"]) == expected_by_category[c["category"]]
        assert ("part_a" in c and "part_b" in c) or c["source"]["type"] == "local_candidate"
    assert {c["subject"] for c in cases} >= {"mathematics", "accounting", "statistics"}
    local = [c for c in cases if "source" in c]
    assert local and all("part_a" not in c for c in local)  # private course-derived text is not stored
    sys.path.insert(0, str(root / "scripts"))
    from eval_overlap_facts import score
    perfect = [{"id": c["id"], **c["expected"]} for c in cases]
    assert score(data, perfect)["mismatches"] == []
    flipped = [{**p, "same_conclusion": not p["same_conclusion"]} if p["id"] == cases[0]["id"] else p for p in perfect]
    result = score(data, flipped)
    assert result["same_conclusion_agree"] == len(cases) - 1 and result["mismatches"][0]["fields"] == ["same_conclusion"]
