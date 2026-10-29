"""Generation-only output and call limits, and reuse of validated groups across tasks (user decision 2026-10-30)."""
import copy
from unittest.mock import patch
import pytest
from app.ai.contracts import ModelCallResult, ModelCallSpec
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.tasks import claim_task, fail_task
from app.generation.content_fixtures import fixture_pair
from app.generation.content_schemas import PairOutput, SemanticOutput
from app.generation.execution_context import submit_generation
from app.generation.generator import generate_groups, generation_basis
from app.generation.models import GenerationArtifact, GenerationDraft
from app.generation.runtime import stage_output
from test_generation_execution import start
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def limits_for(token, task, stage, output_type):
    task.snapshot["mode"] = "live"
    task.save(update_fields=["snapshot"])
    seen = {}
    def run(token, key, spec, **kwargs):
        seen.update(output=spec.max_output_tokens, seconds=kwargs["call_seconds"])
        return ModelCallResult(mode="fixture", status="refusal")
    with patch("app.generation.runtime.verify_generation_sources"), patch("app.generation.runtime.count_call", return_value=100), \
            patch("app.generation.runtime.run_call", side_effect=run):
        with pytest.raises(DomainError):
            stage_output(token, "limit-" + stage, stage, {}, output_type, lambda: None)
    return seen


def test_only_generation_and_repair_get_the_larger_limits(course, planned):
    task, context, token = start(course, planned)
    assert (context["generation_output_tokens"], context["generation_call_seconds"], context["task_seconds"]) == (20000, 300, 900)
    assert limits_for(token, task, "question_pairs", PairOutput) == {"output": 20000, "seconds": 300}
    assert limits_for(token, task, "repair", PairOutput) == {"output": 20000, "seconds": 300}
    assert limits_for(token, task, "semantic_review", SemanticOutput) == {"output": 12000, "seconds": 240}
    task.refresh_from_db()
    assert (task.deadline_at - task.created_at).total_seconds() == pytest.approx(900, abs=5)


def test_global_output_ceiling_still_applies():
    ModelCallSpec(stage="question_pairs", prompt_version="p", schema_version="s", context_hash="h", input={}, max_output_tokens=20000)
    with pytest.raises(ValueError):
        ModelCallSpec(stage="question_pairs", prompt_version="p", schema_version="s", context_hash="h", input={}, max_output_tokens=32001)


def retry_after_failure(course, planned, context, task, token, key, change=None):
    fail_task(token, "TEST_INTERRUPTION", "Synthetic known failure", True)
    saved = GenerationDraft.objects.get(course=course)
    retry = submit_generation(course.owner, course.id, saved.confirmation_id, saved.revision, saved.config_hash,
                              context["context_hash"], key)
    new_context = copy.deepcopy(retry.snapshot)
    if change:
        change(new_context)
    return retry, new_context, claim_task(retry.id)


def test_validated_groups_are_reused_across_tasks_when_only_limits_change(course, planned):
    task, context, token = start(course, planned)
    first = generate_groups(token, context, context["input"]["questions"][:2])
    def other_limits(c):
        # Limits, timeouts and the context hash differ; the generation inputs do not.
        c.update(generation_output_tokens=16000, generation_call_seconds=280, context_hash="x" * 64)
    retry, new_context, new_token = retry_after_failure(course, planned, context, task, token, "limits-only", other_limits)
    with patch("app.generation.generator.fixture_pair", wraps=fixture_pair) as adapter:
        groups = generate_groups(new_token, new_context)
        assert adapter.call_count == 1  # only the third question is generated
    assert [g["pair"] for g in groups[:2]] == [g["pair"] for g in first]
    notes = GenerationArtifact.objects.filter(task=retry, key__startswith="reused:")
    assert notes.count() == 2 and all(n.payload["from_task"] == str(task.id) for n in notes)
    assert retry.model_calls.count() == 0 and retry.call_count == 0


@pytest.mark.parametrize("change", [
    lambda c: c["prompts"].update(question_pairs=c["prompts"]["question_pairs"] + " Changed."),
    lambda c: c.update(model="another-model"),
    lambda c: c["input"]["config"].update(difficulty="challenge"),
])
def test_any_generation_input_difference_prevents_reuse(course, planned, change):
    task, context, token = start(course, planned)
    generate_groups(token, context, context["input"]["questions"][:1])
    def changed(c):
        change(c)
        c["context_hash"] = "y" * 64
    retry, new_context, new_token = retry_after_failure(course, planned, context, task, token, "changed", changed)
    assert generation_basis(new_context) != generation_basis(context)
    with patch("app.generation.generator.fixture_pair", wraps=fixture_pair) as adapter:
        generate_groups(new_token, new_context)
        assert adapter.call_count == len(new_context["input"]["questions"])
    assert not GenerationArtifact.objects.filter(task=retry, key__startswith="reused:").exists()


def test_changed_earlier_question_summary_prevents_reuse_of_later_groups(course, planned):
    task, context, token = start(course, planned)
    generate_groups(token, context)
    retry, new_context, new_token = retry_after_failure(course, planned, context, task, token, "summary")
    # Remove the first group's saved result: it is regenerated with different text, so later inputs change.
    def altered(q):
        pair = fixture_pair(q)
        if q["id"] == new_context["input"]["questions"][0]["blueprint"]["id"]:
            pair["pair"]["stem"][0]["text"] = "Different synthetic stem."
        return pair
    GenerationArtifact.objects.filter(task=task, key__endswith=new_context["input"]["questions"][0]["blueprint"]["id"]).delete()
    with patch("app.generation.generator.fixture_pair", side_effect=altered) as adapter:
        generate_groups(new_token, new_context)
    # Q1 regenerated; Q2 shares Q1's batch (no earlier summaries) and is reused; Q3 sees a changed summary.
    reused = {a.key for a in GenerationArtifact.objects.filter(task=retry, key__startswith="reused:")}
    q2, q3 = (q["blueprint"]["id"] for q in new_context["input"]["questions"][1:3])
    assert any(k.endswith(q2) for k in reused) and not any(k.endswith(q3) for k in reused)
    assert adapter.call_count == 2


def test_repair_round_is_never_reused_across_tasks(course, planned):
    task, context, token = start(course, planned)
    from app.generation import generator
    with patch.object(generator, "reuse_from_earlier_task") as reuse:
        generate_groups(token, context, context["input"]["questions"][:1], round_number=1,
                        repair_requests={context["input"]["questions"][0]["blueprint"]["id"]: {"issues": []}})
        reuse.assert_not_called()


def test_preview_labels_reused_questions(course, planned):
    from rest_framework.test import APIClient
    from app.generation.generator import persist_candidate
    task, context, token = start(course, planned)
    generate_groups(token, context, context["input"]["questions"][:1])
    retry, new_context, new_token = retry_after_failure(course, planned, context, task, token, "preview")
    persist_candidate(new_token, new_context, generate_groups(new_token, new_context))
    client = APIClient()
    client.force_authenticate(course.owner)
    pairs = client.get(f"/api/v1/tasks/{retry.id}/generation-content").json()["candidates"][0]["pairs"]
    assert pairs[0]["reused_from_task"] == str(task.id) and "reused_from_task" not in pairs[1]
