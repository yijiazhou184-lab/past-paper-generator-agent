import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import intent, digest
from .models import Course, CourseDraft, CourseVersion
from .clarifications import classify_gaps
from .context import statement_list
from .schemas import validate_template


@transaction.atomic
def confirm_course(owner, course_id, draft_id, expected_revision, key):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    record = intent(owner, f"confirm:{course.id}", key, {"draft_id": str(draft_id), "revision": expected_revision})
    if record.response:
        return CourseVersion.objects.get(pk=record.response["version_id"], course=course)
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), pk=draft_id, course=course)
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT", "Save and review the latest draft before confirming.")
    if draft.merge_warnings:
        raise DomainError("MERGE_REVIEW_REQUIRED", "Review the preserved edits before confirmation.")
    questions = classify_gaps(draft.payload, draft.machine_base.context["target_ids"])
    if any(q["impact"] == "blocks_selected_scope" for q in questions):
        raise DomainError("COURSE_GAPS_BLOCK_CONFIRMATION", "Resolve the selected-topic evidence or scope gaps first.")
    from app.materials.models import MaterialVersion
    for material in draft.machine_base.context.get("materials", []):
        version = MaterialVersion.objects.get(pk=material["material_version_id"], material__course=course)
        if version.classification_revision != material["classification_revision"]:
            raise DomainError("MATERIAL_CONTEXT_CHANGED", "Material classification changed. Analyse the updated sources first.")
        links = [{"target_version_id": str(a.target_id), "coverage": a.coverage, "revision": a.revision}
                 for a in version.answer_links.filter(active=True).order_by("id")]
        if links != material["answer_links"]:
            raise DomainError("MATERIAL_CONTEXT_CHANGED", "Answer links changed. Analyse the updated sources first.")
    used_statements = {s["id"] for s in draft.machine_base.context["statements"]}
    unanswered_analysis = [s for s in statement_list(course) if s["kind"] in ("exam_scope", "clarification") and s["id"] not in used_statements]
    if unanswered_analysis:
        raise DomainError("ANSWER_REANALYSIS_REQUIRED", "Analyse your new clarification answer before confirming this course.")
    validate_template(draft.payload["template_suggestion"])
    existing = CourseVersion.objects.filter(draft=draft, draft_revision=draft.revision).first()
    if existing:
        version = existing
    else:
        version = CourseVersion.objects.create(course=course, number=course.confirmed_versions.count() + 1,
            draft=draft, draft_revision=draft.revision, payload_hash=digest(draft.payload),
            frozen_payload=copy.deepcopy(draft.payload), evidence_manifest={**copy.deepcopy(draft.machine_base.context), "analysis_mode": draft.machine_base.mode},
            statements=statement_list(course), manual_patches=copy.deepcopy(draft.manual_patches), confirmed_by=owner)
    record.response = {"version_id": str(version.id)}
    record.save(update_fields=["response"])
    return version
