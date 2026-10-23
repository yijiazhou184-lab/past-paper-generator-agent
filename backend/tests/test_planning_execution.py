import pytest
from unittest.mock import patch
from app.ai.contracts import ModelCallResult
from app.core.errors import DomainError
from app.core.tasks import claim_task
from app.core.models import ModelInvocation
from app.generation.planning import submit_plan, build_context, run_planning
from app.generation.snapshots import save_config
from app.generation.models import Blueprint, PlanningGrant
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft
from test_generation_snapshot import version, config, planned


def test_fixture_planning_is_explicit_and_never_calls_model(course, config):
    saved, _ = save_config(course.owner, course.id, 0, config, "save")
    context = build_context(saved)
    with patch("app.generation.planning.run_call", side_effect=AssertionError("Fixture cannot call API")):
        task = submit_plan(course.owner, course.id, 1, context["context_hash"], "plan")
        assert submit_plan(course.owner, course.id, 1, context["context_hash"], "plan").id == task.id
        run_planning(claim_task(task.id))
    task.refresh_from_db()
    assert task.state == "succeeded" and task.result["mode"] == "fixture"
    assert task.call_count == 0 and not ModelInvocation.objects.exists()


def live_snapshot(saved):
    snapshot = build_context(saved)
    snapshot["mode"] = "live"
    # Isolated transport fixtures only, never update the immutable confirmed version.
    return snapshot


def test_live_plan_requires_separate_authorization(course, config, monkeypatch):
    saved, _ = save_config(course.owner, course.id, 0, config, "save")
    context = live_snapshot(saved)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key-not-real")
    with patch("app.generation.planning.build_context", return_value=context):
        with pytest.raises(DomainError, match="PLANNING_CONSENT_REQUIRED"):
            submit_plan(course.owner, course.id, 1, context["context_hash"], "no-consent")
        task = submit_plan(course.owner, course.id, 1, context["context_hash"], "consent", authorize=True)
    assert PlanningGrant.objects.filter(course=course).count() == 1
    assert task.snapshot["input"]["course"]["scope_claims"][0]["provenance"] == "user_statement"


@pytest.mark.parametrize("status", ["refusal", "truncated", "provider_error", "invalid_output"])
def test_bad_model_output_never_publishes(course, config, monkeypatch, status):
    saved, _ = save_config(course.owner, course.id, 0, config, "save")
    context = live_snapshot(saved)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key-not-real")
    with patch("app.generation.planning.build_context", return_value=context):
        task = submit_plan(course.owner, course.id, 1, context["context_hash"], "plan", authorize=True)
    with patch("app.generation.planning.run_call", return_value=ModelCallResult(mode="fixture", status=status)):
        with pytest.raises(DomainError, match="BLUEPRINT_MODEL_FAILED"):
            run_planning(claim_task(task.id))
    assert not Blueprint.objects.exists()


@pytest.mark.parametrize("status", ["needs_info", "unable_to_determine", "not_checked"])
def test_incomplete_judgment_retains_explanation_without_blueprint(course, config, monkeypatch, status):
    saved, _ = save_config(course.owner, course.id, 0, config, "save")
    context = live_snapshot(saved)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key-not-real")
    with patch("app.generation.planning.build_context", return_value=context):
        task = submit_plan(course.owner, course.id, 1, context["context_hash"], "plan", authorize=True)
    output = ModelCallResult(mode="fixture", status="parsed", payload={"status": status, "explanation": "Conflicting constraints", "blueprint": None})
    with patch("app.generation.planning.run_call", return_value=output):
        run_planning(claim_task(task.id))
    task.refresh_from_db()
    assert task.state == "needs_info" and task.result["status"] == status
    assert not Blueprint.objects.exists()


def test_stale_queued_plan_skips_call(course, config):
    saved, _ = save_config(course.owner, course.id, 0, config, "save")
    task = submit_plan(course.owner, course.id, 1, build_context(saved)["context_hash"], "plan")
    save_config(course.owner, course.id, 1, {**config, "main_question_count": 4}, "changed")
    with patch("app.generation.planning.run_call", side_effect=AssertionError("Stale task cannot call")):
        run_planning(claim_task(task.id))
    task.refresh_from_db()
    assert task.result["superseded"] and not Blueprint.objects.exists()
