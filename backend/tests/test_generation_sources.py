import copy
from unittest.mock import patch
import pytest
from app.generation.content_fixtures import fixture_pair, fixture_review
from app.generation.content_validation import validate_group
from app.generation.checks import program_checks, release_gate
from app.generation.generator import question_input, run_generation
from test_generation_execution import start
from test_generation_preflight import prepare
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def test_background_id_does_not_abort_and_is_not_academic_proof(course, planned):
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]
    context["input"]["background_source_catalog"] = [{"id": "background-page", "material_code": "M33", "physical_page": 22}]
    data = fixture_pair(q["blueprint"])
    data["pair"]["evidence_ids"].append("background-page")
    group = validate_group(q["blueprint"], data, context)
    from app.generation.source_policy import source_diagnostics
    diagnostic = source_diagnostics(context, group["pair"])
    assert diagnostic["background_only_ids"] == ["background-page"]
    assert diagnostic["has_academic_basis"]
    assert "background-page" in group["pair"]["evidence_ids"]  # Never silently drop a claim.


def test_external_background_and_unknown_academic_are_retained(course, planned):
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]["blueprint"]
    data = fixture_pair(q)
    data["pair"]["evidence_ids"] += ["unresolved-academic"]
    data["pair"]["background_references"] = [{
        "label": "General business context", "evidence_id": None,
        "url": "https://example.com/context", "note": "Illustrative only; not verified."
    }]
    group = validate_group(q, data, context)
    from app.generation.source_policy import source_diagnostics
    assert source_diagnostics(context, group["pair"])["unresolved_ids"] == ["unresolved-academic"]
    assert group["pair"]["background_references"] == data["pair"]["background_references"]


def test_all_unknown_academic_is_reported_not_structurally_aborted(course, planned):
    _, context = prepare(course, planned)
    groups = []
    for q in context["input"]["questions"]:
        data = fixture_pair(q["blueprint"])
        data["pair"]["evidence_ids"] = ["outside"]
        groups.append(validate_group(q["blueprint"], data, context))
    checks = program_checks(context, {"pairs": [g["pair"] for g in groups], "assets": [a for g in groups for a in g["assets"]]})
    assert all(c["result"] == "pass" for c in checks if c["method"] == "program")
    assert not release_gate(checks)["allowed"]
    assert all(c["result"] == "fail" for c in checks if c["check_id"].startswith("source_basis:"))


def test_generation_input_separates_background_from_academic_allowlist(course, planned):
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]
    q["issues"] = [{"evidence_ids": ["background-page"], "explanation": "Background issue"}]
    data = question_input(context, q, [])
    assert "issues" not in data
    assert data["background_context"]["issues"][0]["evidence_ids"] == ["background-page"]
    assert data["academic_source_ids"] == q["blueprint"]["evidence_ids"]
    assert data["source_policy"]["background_scope"] == "unrestricted"


def test_extra_reference_reaches_candidate_and_semantic_review(course, planned):
    task, context, token = start(course, planned)
    def extra(q):
        data = fixture_pair(q)
        data["pair"]["evidence_ids"] += ["context-only-reference"]
        return data
    with patch("app.generation.generator.fixture_pair", side_effect=extra):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "succeeded"  # Fixture review explicitly accepts supported minor extensions.
    report = task.candidates.get().check_report
    assert any(c["check_id"].startswith("source_notice:") and not c["required_for_release"]
               for c in report.payload["checks"])
    assert any(c["check_id"].endswith(":source_alignment") for c in report.payload["checks"])
    assert task.model_calls.count() == 0


def test_source_failure_targets_one_question_and_keeps_other_groups(course, planned):
    task, context, token = start(course, planned)
    target = context["input"]["questions"][0]["blueprint"]["id"]
    n = [0]
    def review(pairs):
        output = fixture_review(pairs)
        n[0] += 1
        if n[0] == 1:
            c = next(c for c in output["checks"] if c["question_id"] == target and c["category"] == "source_alignment")
            c.update(result="fail", rationale="An advanced method replaces the frozen knowledge target; restore the course method.")
        return output
    with patch("app.generation.reviewer.fixture_review", side_effect=review):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "succeeded"
    first, repaired = list(task.candidates.order_by("revision"))
    assert first.payload["pairs"][1:] == repaired.payload["pairs"][1:]
    assert not first.check_report.gate["allowed"]
    assert repaired.check_report.gate["allowed"]
    assert task.generation_artifacts.filter(key__startswith="r1:pair:").count() == 1


def test_pair_schema_requires_background_and_legacy_validation_is_compatible(course, planned):
    from app.generation.content_schemas import PairOutput
    schema = PairOutput.model_json_schema()["$defs"]["QuestionPair"]
    assert "background_references" in schema["required"]
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]["blueprint"]
    old = fixture_pair(q)
    old["pair"].pop("background_references", None)
    assert validate_group(q, old, context)["pair"]["background_references"] == []
    assert "background_references" not in old["pair"]


def test_reference_policy_is_frozen_and_old_policy_cannot_resume(course, planned):
    from app.core.idempotency import digest
    from app.core.errors import DomainError
    from app.generation.runtime import verify_context
    task, context, _ = start(course, planned)
    assert context["pipeline_version"] == "generation-v5"
    assert context["source_policy"]["background_scope"] == "unrestricted"
    task.snapshot = copy.deepcopy(context)
    task.snapshot["source_policy"]["background_scope"] = "restricted"
    task.snapshot["context_hash"] = digest({k:v for k,v in task.snapshot.items() if k!="context_hash"})
    with pytest.raises(DomainError, match="GENERATION_SOURCE_POLICY_CHANGED"):
        verify_context(task)


def test_bad_review_reference_does_not_invalidate_other_questions(course, planned):
    task, context, token = start(course, planned)
    def review(pairs):
        output = fixture_review(pairs)
        first = next(c for c in output["checks"] if c["category"] == "clarity")
        first["evidence_ids"] = ["unknown-review-context"]
        return output
    with patch("app.generation.reviewer.fixture_review", side_effect=review):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "succeeded"
    checks = task.candidates.get().check_report.payload["checks"]
    assert any(c["check_id"].startswith("review_reference_notice:") for c in checks)
    assert all(c["result"] == "pass" for c in checks if c["required_for_release"])


def test_unrelated_duplicate_review_category_only_invalidates_that_category(course, planned):
    task, context, token = start(course, planned)
    def review(pairs):
        output = fixture_review(pairs)
        output["checks"].append(copy.deepcopy(next(c for c in output["checks"] if c["category"]=="clarity")))
        return output
    with patch("app.generation.reviewer.fixture_review", side_effect=review):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "failed"
    blocked = task.result["blocking_check_ids"]
    assert len(blocked) == 1 and blocked[0].endswith(":clarity")


def test_bounded_source_excerpts_disclose_clipping(course, planned):
    from app.generation.source_policy import source_review_input
    _, context = prepare(course, planned)
    pair = fixture_pair(context["input"]["questions"][0]["blueprint"])["pair"]
    source = next(s for s in context["input"]["sources"] if s["id"] in pair["evidence_ids"])
    source["content"] = "x" * 2000
    result = source_review_input(context, [pair])
    excerpt = next(e for e in result["academic_excerpts"] if e["id"] == source["id"])
    assert len(excerpt["text"]) == 1200 and excerpt["truncated"]
