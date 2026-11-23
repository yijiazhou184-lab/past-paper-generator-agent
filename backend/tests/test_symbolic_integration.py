"""Capability composition through existing preflight, validation and generation entry points."""
import copy
from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.generation.runtime import verify_context
from app.generation.content_fixtures import fixture_pair
from app.generation.content_validation import validate_group
from app.generation.generator import run_generation
from app.capabilities.symbolic import pack
from test_generation_execution import start
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft
from test_symbolic_extensions import claim, domain, var, op, num


def test_capability_version_and_prompt_changes_invalidate_frozen_preflight(course, planned):
    task, context, _ = start(course, planned)
    assert verify_context(task)
    assert "signed_limit" in context["prompts"]["repair"]
    assert context["checker_contract"]["capability"]["files"]["prompts/verification_specs.md"]
    with patch.object(pack, "PACK_VERSION", "future"):
        with pytest.raises(DomainError, match="GENERATION_CHECKER_CHANGED"):
            verify_context(task)
    changed = copy.deepcopy(context)
    changed["checker_contract"]["capability"]["files"]["prompts/verification_specs.md"] = "different"
    changed["context_hash"] = digest({k: v for k, v in changed.items() if k != "context_hash"})
    task.snapshot = changed
    with pytest.raises(DomainError, match="GENERATION_CHECKER_CHANGED"):
        verify_context(task)


def test_saved_legacy_and_new_specs_parse_and_run_in_same_generation(course, planned):
    task, context, token = start(course, planned)
    def output(question):
        result = fixture_pair(question)
        if question["number"] == 1:
            answer = result["pair"]["answers"][0]
            check = claim("maximal_domain", expression=op("pow", var(), num(2)), expected_intervals=[domain()])
            check.update(id=answer["part_id"]+"-domain", part_id=answer["part_id"])
            answer["checks"].append(check)
        validate_group(question, result, context)
        return result
    with patch("app.generation.generator.fixture_pair", side_effect=output):
        run_generation(token)
    task.refresh_from_db()
    assert task.state == "succeeded", task.result
    assert task.call_count == 0
    candidate = task.candidates.get()
    checks = candidate.payload["pairs"][0]["answers"][0]["checks"]
    assert [check["kind"] for check in checks] == ["derivative", "maximal_domain"]
    assert candidate.check_report.gate["allowed"]
