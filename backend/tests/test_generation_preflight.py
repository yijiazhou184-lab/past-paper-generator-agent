import copy
import pytest
from app.core.errors import DomainError
from app.core.tasks import claim_task, cancel_task
from app.core.models import Task
from app.generation.execution_context import prepare_generation, submit_generation
from app.generation.models import GenerationGrant, GenerationSnapshot
from app.generation.snapshots import save_config
from test_generation_snapshot import version, config, planned, confirm
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def prepare(course, planned):
    saved = confirm(course, planned)
    return saved, prepare_generation(course.owner, course.id, saved.confirmation_id,
                                     saved.revision, saved.config_hash, "preflight")


def test_preflight_freezes_once_and_contains_exact_scope(course, planned):
    saved, context = prepare(course, planned)
    again = prepare_generation(course.owner, course.id, saved.confirmation_id, saved.revision, saved.config_hash, "another-key")
    assert context == again
    assert GenerationSnapshot.objects.count() == 1
    assert context["mode"] == "fixture"
    assert context["max_calls"] == 16
    assert context["call_seconds"] == 240
    assert context["input"]["history_content_ids"] == []
    assert len(context["input"]["questions"]) == 3
    assert "OPENAI_API_KEY" not in str(context)


def test_submit_idempotent_busy_and_cancel(course, planned):
    saved, context = prepare(course, planned)
    args = (course.owner, course.id, saved.confirmation_id, saved.revision, saved.config_hash, context["context_hash"])
    task = submit_generation(*args, "generate")
    assert task.kind == "generation"
    assert submit_generation(*args, "generate").id == task.id
    with pytest.raises(DomainError, match="COURSE_BUSY") as failure:
        submit_generation(*args, "another")
    assert str(task.id) in str(failure.value.payload)
    cancel_task(course.owner, task.id)
    assert not GenerationGrant.objects.exists()


def test_changed_configuration_rejects_preflight_and_submit(course, planned):
    saved, context = prepare(course, planned)
    save_config(course.owner, course.id, saved.revision, saved.config, "edit")
    with pytest.raises(DomainError, match="CONFIG_REVISION_CONFLICT"):
        submit_generation(course.owner, course.id, saved.confirmation_id, saved.revision,
                          saved.config_hash, context["context_hash"], "stale")
    assert not Task.objects.filter(kind="generation").exists()


def test_context_tampering_and_cross_course_rejected(course, planned, client, django_user_model):
    saved, context = prepare(course, planned)
    with pytest.raises(DomainError, match="GENERATION_INPUT_CHANGED"):
        submit_generation(course.owner, course.id, saved.confirmation_id, saved.revision,
                          saved.config_hash, "0" * 64, "tampered")
    client.force_login(django_user_model.objects.create_user(username="outside"))
    body = {"confirmation_id": str(saved.confirmation_id), "config_revision": saved.revision, "config_hash": saved.config_hash}
    assert client.post(f"/api/v1/courses/{course.id}/generation-preflight", body,
                       content_type="application/json", HTTP_IDEMPOTENCY_KEY="foreign").status_code == 404
