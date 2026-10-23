import copy
import pytest
from django.db import DatabaseError, transaction
from django.http import Http404
from app.core.errors import DomainError
from app.core.tasks import claim_task, cancel_task
from app.courses.confirmation import confirm_course
from app.courses.drafts import save_draft
from app.generation.models import GenerationDraft, GenerationSnapshot, Blueprint
from app.generation.planning import build_context, submit_plan, run_planning, publish_plan
from app.generation.fixtures import fixture_blueprint
from app.generation.snapshots import save_config, confirm_structure, freeze_generation, edit_blueprint, binding_valid
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


@pytest.fixture
def version(course, draft):
    return confirm_course(course.owner, course.id, draft.id, draft.revision, "batch3-course")


@pytest.fixture
def config(version):
    return {"course_version_id": str(version.id), "mode": "chapter_practice", "topic_ids": ["K1"],
            "difficulty": "exam_standard", "main_question_count": 3,
            "question_types": ["calculation", "explanation_proof", "applied_optimisation"]}


@pytest.fixture
def planned(course, config):
    saved, _ = save_config(course.owner, course.id, 0, config, "config-1")
    task = submit_plan(course.owner, course.id, saved.revision, build_context(saved)["context_hash"], "plan-1")
    run_planning(claim_task(task.id))
    saved.refresh_from_db()
    return saved


def confirm(course, planned, key="confirm-structure"):
    return confirm_structure(course.owner, course.id, planned.blueprint_id, planned.revision,
                             planned.blueprint.revision, planned.config_hash, key)


def freeze(course, saved, key="freeze"):
    return freeze_generation(course.owner, course.id, saved.confirmation_id, saved.revision, saved.config_hash, key)


def test_three_four_three_invalidates_confirmation_even_same_hash(course, planned):
    confirmed = confirm(course, planned)
    original_hash, confirmation_id = confirmed.config_hash, confirmed.confirmation_id
    changed = {**planned.config, "main_question_count": 4}
    four, _ = save_config(course.owner, course.id, 1, changed, "four")
    three, _ = save_config(course.owner, course.id, 2, planned.config, "back-to-three")
    assert three.revision == 3 and three.config_hash == original_hash
    assert not binding_valid(three)
    with pytest.raises(DomainError):
        freeze_generation(course.owner, course.id, confirmation_id, 3, original_hash, "expired")
    with pytest.raises(DomainError):
        confirm_structure(course.owner, course.id, planned.blueprint_id, 3, 1, original_hash, "expired-confirm")


def test_config_cas_idempotency_and_course_defaults_unchanged(course, version, planned):
    original = copy.deepcopy(version.frozen_payload)
    saved, revision = save_config(course.owner, course.id, 1, {**planned.config, "difficulty": "challenge"}, "same-key")
    assert revision == 2
    assert save_config(course.owner, course.id, 1, {**planned.config, "difficulty": "challenge"}, "same-key")[1] == 2
    with pytest.raises(DomainError, match="CONFIG_REVISION_CONFLICT"):
        save_config(course.owner, course.id, 1, planned.config, "other-tab")
    version.refresh_from_db()
    assert version.frozen_payload == original


def test_snapshot_is_immutable_idempotent_and_keeps_course_version(course, draft, version, planned):
    saved = confirm(course, planned)
    snapshot = freeze(course, saved)
    assert freeze(course, saved).id == snapshot.id
    assert freeze(course, saved, "new-freeze-key").id == snapshot.id
    assert snapshot.mode == "fixture"
    assert snapshot.payload["course_version_id"] == str(version.id)
    assert snapshot.payload["history_cutoff"] and snapshot.payload["history_content_ids"] == []
    before = copy.deepcopy(snapshot.payload)
    save_draft(course.owner, course.id, draft.revision, [{"path": ["title"], "value": "New draft title"}], "change-course")
    snapshot.refresh_from_db()
    assert snapshot.payload == before
    with pytest.raises(ValueError):
        snapshot.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        GenerationSnapshot.objects.filter(pk=snapshot.pk).update(payload={})
    assert GenerationSnapshot.objects.count() == 1


def test_edit_recalculates_marks_and_creates_preserved_revision(course, planned):
    confirmed = confirm(course, planned)
    old = confirmed.blueprint
    changed = copy.deepcopy(old.payload)
    changed["questions"][0]["parts"][0]["marks"] += 1.5
    changed["suggested_minutes"] = 45
    edited = edit_blueprint(course.owner, course.id, old.id, planned.revision, old.revision, changed, "structure-edit")
    assert edited.blueprint.revision == 2
    assert edited.blueprint.payload["printed_marks"] == old.payload["printed_marks"] + 1.5
    assert edited.confirmation is None and not binding_valid(edited)
    assert Blueprint.objects.get(pk=old.id).payload == old.payload
    with pytest.raises(DomainError, match="BLUEPRINT_REVISION_CONFLICT"):
        edit_blueprint(course.owner, course.id, old.id, planned.revision, old.revision, changed, "stale-edit")


def test_late_plan_retained_but_cannot_replace_current_config(course, config):
    draft, _ = save_config(course.owner, course.id, 0, config, "initial")
    task = submit_plan(course.owner, course.id, 1, build_context(draft)["context_hash"], "slow")
    token = claim_task(task.id)
    changed, _ = save_config(course.owner, course.id, 1, {**config, "main_question_count": 4}, "change-while-planning")
    blueprint = publish_plan(token, fixture_blueprint(config, task.snapshot["input"]["course"]))
    changed.refresh_from_db()
    task.refresh_from_db()
    assert changed.blueprint_id is None
    assert task.result["superseded"] and blueprint.config_revision == 1


def test_cancelled_plan_and_cross_owner_cannot_publish_or_freeze(course, config, django_user_model):
    draft, _ = save_config(course.owner, course.id, 0, config, "initial")
    task = submit_plan(course.owner, course.id, 1, build_context(draft)["context_hash"], "cancel")
    token = claim_task(task.id)
    cancel_task(course.owner, task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        publish_plan(token, fixture_blueprint(config, task.snapshot["input"]["course"]))
    outsider = django_user_model.objects.create_user(username="outsider")
    with pytest.raises(Http404):
        save_config(outsider, course.id, 1, config, "foreign")
    assert not Blueprint.objects.exists()


def test_api_refresh_and_expired_generation_submission(course, planned, client):
    client.force_login(course.owner)
    saved = confirm(course, planned)
    url = f"/api/v1/courses/{course.id}"
    body = {"confirmation_id": str(saved.confirmation_id), "config_revision": saved.revision, "config_hash": saved.config_hash}
    assert client.get(url + "/generation-workspace").json()["draft"]["confirmed"]
    assert client.post(url + "/generations", body, content_type="application/json").status_code == 501
    save_config(course.owner, course.id, 1, saved.config, "new-revision")
    assert client.post(url + "/generations", body, content_type="application/json").status_code == 409


def test_foreign_version_and_unknown_topic_rejected(course, config, django_user_model):
    bad = {**config, "course_version_id": "00000000-0000-0000-0000-000000000001"}
    with pytest.raises(Http404):
        save_config(course.owner, course.id, 0, bad, "unknown-version")
    with pytest.raises(DomainError, match="KNOWLEDGE_OUTSIDE_SELECTION"):
        save_config(course.owner, course.id, 0, {**config, "topic_ids": ["outside"]}, "outside")


@pytest.mark.parametrize("payload", [[], {"course_version_id": "not-a-uuid"}])
def test_invalid_config_shape_is_readable_400(course, payload):
    with pytest.raises(DomainError, match="CONFIG_SCHEMA_INVALID") as failure:
        save_config(course.owner, course.id, 0, payload, "bad-shape")
    assert failure.value.status_code == 400
    assert failure.value.payload["field_errors"]


def test_replanning_blocks_old_confirmation_and_editing(course, planned):
    confirm(course, planned)
    task = submit_plan(course.owner, course.id, planned.revision, build_context(planned)["context_hash"], "new-plan")
    with pytest.raises(DomainError, match="PLANNING_IN_PROGRESS"):
        confirm(course, planned, "confirm-during-plan")
    with pytest.raises(DomainError, match="PLANNING_IN_PROGRESS"):
        edit_blueprint(course.owner, course.id, planned.blueprint_id, planned.revision, planned.blueprint.revision, planned.blueprint.payload, "edit-during-plan")
    cancel_task(course.owner, task.id)
