import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from app.core.errors import DomainError
from app.core.idempotency import digest, intent
from app.courses.models import Course, CourseVersion
from .models import GenerationDraft, Blueprint, StructureConfirmation, GenerationSnapshot
from .schemas import GenerationConfig, parse_schema, validate_config, validate_blueprint, schema_version_of


def owned_course(owner, course_id):
    return get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)


def require_revision(draft, revision):
    if (draft.revision if draft else 0) != revision:
        raise DomainError("CONFIG_REVISION_CONFLICT", "Another tab saved a newer configuration. Compare it with your edits before saving.")


def blueprint_view(blueprint):
    if blueprint is None:
        return None
    return {"id": str(blueprint.id), "revision": blueprint.revision, "config_revision": blueprint.config_revision,
        "config_hash": blueprint.config_hash, "course_version_id": str(blueprint.course_version_id),
        "payload": blueprint.payload, "payload_hash": blueprint.payload_hash, "differences": blueprint.differences,
        "mode": blueprint.mode, "task_id": str(blueprint.task_id) if blueprint.task_id else None}


def binding_valid(draft):
    b, c = draft.blueprint, draft.confirmation
    return bool(b and c and c.blueprint_id == b.id and c.config_revision == draft.revision == b.config_revision
        and c.config_hash == draft.config_hash == b.config_hash and c.blueprint_hash == b.payload_hash
        and c.course_version_id == draft.course_version_id == b.course_version_id)


def draft_view(draft):
    if draft is None:
        return None
    return {"id": str(draft.id), "revision": draft.revision, "config": draft.config, "config_hash": draft.config_hash,
        "blueprint": blueprint_view(draft.blueprint), "confirmation_id": str(draft.confirmation_id) if draft.confirmation_id else None,
        "confirmed": binding_valid(draft), "latest_task_id": str(draft.latest_task_id) if draft.latest_task_id else None}


def snapshot_view(snapshot):
    return {"id": str(snapshot.id), "mode": snapshot.mode, "payload_hash": snapshot.payload_hash,
        "confirmation_id": str(snapshot.confirmation_id), "created_at": snapshot.created_at,
        "payload": snapshot.payload, "generation_available": True}


@transaction.atomic
def save_config(owner, course_id, expected_revision, payload, key):
    course = owned_course(owner, course_id)
    record = intent(owner, f"config:{course.id}", key, {"revision": expected_revision, "config": payload})
    draft = GenerationDraft.objects.select_related("blueprint", "confirmation").filter(course=course).first()
    if record.response:
        return draft, record.response["revision"]
    require_revision(draft, expected_revision)
    parsed = parse_schema(GenerationConfig, payload, "CONFIG_SCHEMA_INVALID")
    version = get_object_or_404(CourseVersion, pk=parsed["course_version_id"], course=course)
    config = validate_config(payload, version.frozen_payload, version.evidence_manifest["evidence"])
    if draft is None:
        draft = GenerationDraft(course=course)
    else:
        draft.revision += 1
    draft.course_version = version
    draft.config, draft.config_hash, draft.confirmation = config, digest(config), None
    draft.save()
    record.response = {"revision": draft.revision}
    record.save(update_fields=["response"])
    return draft, draft.revision


def structure_diff(previous, payload, old_config=None, new_config=None):
    if previous is None:
        return ["New suggested structure. Marks and time are practice estimates, not official exam rules."]
    labels = {"main_question_count": "Main questions", "subquestion_count": "Parts", "printed_marks": "Printed marks",
              "attempt_marks": "Attempt marks", "suggested_minutes": "Suggested minutes", "subquestion_count_locked": "Part count locked"}
    changes = [f"{label}: {previous[key]} → {payload[key]}" for key, label in labels.items() if previous[key] != payload[key]]
    for key, label in (("difficulty", "Difficulty"), ("question_types", "Question types"), ("topic_ids", "Knowledge selection")):
        if old_config and new_config and old_config[key] != new_config[key]:
            changes.append(f"{label} changed for this practice.")
    for key, label in (("questions", "Question objectives, parts, marks or coverage"), ("sections", "Section or answer-selection rules")):
        if previous[key] != payload[key]:
            changes.append(f"{label} updated. Review each question below.")
    return changes or ["The suggested structure is unchanged. Confirm it for this configuration revision."]


@transaction.atomic
def edit_blueprint(owner, course_id, blueprint_id, config_revision, expected_revision, payload, key):
    course = owned_course(owner, course_id)
    record = intent(owner, f"blueprint-edit:{course.id}", key,
        {"blueprint": str(blueprint_id), "config_revision": config_revision, "revision": expected_revision, "payload": payload})
    draft = get_object_or_404(GenerationDraft.objects.select_related("blueprint", "course_version"), course=course)
    if record.response:
        return draft
    require_revision(draft, config_revision)
    if draft.latest_task_id and draft.latest_task.state in ("queued", "processing"):
        raise DomainError("PLANNING_IN_PROGRESS", "Wait for the current plan or cancel it before editing the structure.")
    previous = get_object_or_404(Blueprint, pk=blueprint_id, draft=draft)
    if draft.blueprint_id != previous.id or previous.revision != expected_revision or previous.config_revision != draft.revision:
        raise DomainError("BLUEPRINT_REVISION_CONFLICT", "This structure is no longer current. Review the saved configuration and structure.")
    version = draft.course_version
    validated = validate_blueprint(draft.config, payload, version.frozen_payload, version.evidence_manifest["evidence"],
                                   recalculate=True, schema_version=schema_version_of(previous.payload))
    # Provider explanations are not used as a programmatic diff, even on edited plans.
    validated["differences"] = previous.payload["differences"]
    draft.blueprint = Blueprint.objects.create(draft=draft, course_version=version, config_revision=draft.revision,
        config_hash=draft.config_hash, family=previous.family, revision=previous.revision + 1,
        payload=validated, payload_hash=digest(validated), differences=structure_diff(previous.payload, validated),
        mode=previous.mode, context_hash=previous.context_hash)
    draft.confirmation = None
    draft.save()
    record.response = {"blueprint_id": str(draft.blueprint_id)}
    record.save(update_fields=["response"])
    return draft


def current_blueprint(draft, blueprint_id, revision, config_hash):
    require_revision(draft, revision)
    if draft.latest_task_id and draft.latest_task.state in ("queued", "processing"):
        raise DomainError("PLANNING_IN_PROGRESS", "Wait for the current planning task or cancel it before confirming.")
    b = draft.blueprint
    if not b or str(b.id) != str(blueprint_id) or b.config_revision != draft.revision or config_hash != draft.config_hash or b.config_hash != config_hash:
        raise DomainError("STRUCTURE_BINDING_EXPIRED", "Configuration changed — review the updated structure.")
    if b.course_version_id != draft.course_version_id:
        raise DomainError("STRUCTURE_BINDING_EXPIRED")
    validate_blueprint(draft.config, b.payload, draft.course_version.frozen_payload, draft.course_version.evidence_manifest["evidence"])
    return b


@transaction.atomic
def confirm_structure(owner, course_id, blueprint_id, config_revision, blueprint_revision, config_hash, key):
    course = owned_course(owner, course_id)
    record = intent(owner, f"structure-confirm:{course.id}", key, {"blueprint_id": str(blueprint_id),
        "revision": config_revision, "blueprint_revision": blueprint_revision, "config_hash": config_hash})
    draft = get_object_or_404(GenerationDraft.objects.select_related("blueprint", "confirmation", "course_version"), course=course)
    if record.response:
        return draft
    blueprint = current_blueprint(draft, blueprint_id, config_revision, config_hash)
    if blueprint.revision != blueprint_revision:
        raise DomainError("BLUEPRINT_REVISION_CONFLICT")
    if not binding_valid(draft):
        draft.confirmation = StructureConfirmation.objects.create(blueprint=blueprint, draft=draft, config_revision=draft.revision,
            config_hash=draft.config_hash, blueprint_hash=blueprint.payload_hash, course_version=draft.course_version, confirmed_by=owner)
        draft.save()
    record.response = {"confirmation_id": str(draft.confirmation_id)}
    record.save(update_fields=["response"])
    return draft


def require_confirmation(draft, confirmation_id, revision, config_hash):
    require_revision(draft, revision)
    if draft.latest_task_id and draft.latest_task.state in ("queued", "processing"):
        raise DomainError("PLANNING_IN_PROGRESS", "Wait for the current plan before preparing generation.")
    if str(draft.confirmation_id) != str(confirmation_id) or not binding_valid(draft) or draft.config_hash != config_hash:
        raise DomainError("STRUCTURE_BINDING_EXPIRED", "Confirm the current structure before preparing generation.")


@transaction.atomic
def freeze_generation(owner, course_id, confirmation_id, config_revision, config_hash, key):
    course = owned_course(owner, course_id)
    record = intent(owner, f"generation-freeze:{course.id}", key,
        {"confirmation_id": str(confirmation_id), "revision": config_revision, "config_hash": config_hash})
    if record.response:
        return GenerationSnapshot.objects.get(pk=record.response["snapshot_id"], course=course)
    draft = get_object_or_404(GenerationDraft.objects.select_related("course_version", "blueprint", "confirmation"), course=course)
    require_confirmation(draft, confirmation_id, config_revision, config_hash)
    snapshot = GenerationSnapshot.objects.filter(confirmation=draft.confirmation).first()
    if snapshot is None:
        version = draft.course_version
        payload = {"schema_version": "generation-input-v1", "course_version_id": str(version.id), "course_payload_hash": version.payload_hash,
            "course": copy.deepcopy(version.frozen_payload), "evidence_manifest": copy.deepcopy(version.evidence_manifest),
            "statements": copy.deepcopy(version.statements), "config": copy.deepcopy(draft.config),
            "config_revision": draft.revision, "config_hash": draft.config_hash, "blueprint_id": str(draft.blueprint_id),
            "blueprint_revision": draft.blueprint.revision, "blueprint_hash": draft.blueprint.payload_hash,
            "blueprint": copy.deepcopy(draft.blueprint.payload), "confirmation_id": str(draft.confirmation_id),
            "history_cutoff": timezone.now().isoformat(), "history_content_ids": [],
            "history_status": "not_available_before_paper_storage", "limits_version": "r1-limits-proposal-1",
            "generation_limits": {"calls": 16, "deadline_seconds": 600, "repair_rounds": 1},
            "analysis_mode": version.evidence_manifest.get("analysis_mode", "unknown"), "planning_mode": draft.blueprint.mode}
        snapshot = GenerationSnapshot.objects.create(course=course, confirmation=draft.confirmation, payload=payload,
            payload_hash=digest(payload), mode=draft.blueprint.mode)
    record.response = {"snapshot_id": str(snapshot.id)}
    record.save(update_fields=["response"])
    return snapshot
