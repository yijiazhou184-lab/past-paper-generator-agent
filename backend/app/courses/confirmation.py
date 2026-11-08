import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import intent, digest
from .models import Course, CourseDraft, CourseVersion
from .clarifications import classify_gaps
from .context import statement_list
from .schemas import validate_template
from .exam_template import current_exam_template


@transaction.atomic
def confirm_course(owner, course_id, draft_id, expected_revision, key, *, include_exam_template=False):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    request = {"draft_id": str(draft_id), "revision": expected_revision}
    if include_exam_template:
        request["include_exam_template"] = True
    record = intent(owner, f"confirm:{course.id}", key, request)
    if record.response:
        return CourseVersion.objects.get(pk=record.response["version_id"], course=course)
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), pk=draft_id, course=course)
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT", "Save and review the latest draft before confirming.")
    if draft.merge_warnings:
        raise DomainError("MERGE_REVIEW_REQUIRED", "Review the preserved edits before confirmation.")
    from .drafts import draft_view
    view=draft_view(draft);payload=copy.deepcopy(view["payload"]);questions=view["clarifications"]
    payload.pop("exam_template", None)
    if not view["eligibility"]["allowed"] or any(q["impact"]=="blocks_selected_scope" or
            q["impact"]=="needs_confirmation" and q["status"]!="answered" for q in questions):
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
    from .decisions import needs_analysis
    unanswered_analysis = [s for s in statement_list(course) if needs_analysis(s,used_statements)]
    if unanswered_analysis:
        raise DomainError("ANSWER_REANALYSIS_REQUIRED", "Analyse your new clarification answer before confirming this course.")
    validate_template(payload["template_suggestion"])
    latest = course.confirmed_versions.order_by("-number").first()
    template = current_exam_template(draft, latest, include=include_exam_template)
    if template:
        payload["exam_template"] = template
    fingerprint = digest(template) if template else ""
    existing = CourseVersion.objects.filter(draft=draft, draft_revision=draft.revision, confirmation_fingerprint=fingerprint).first()
    if existing:
        version = existing
    else:
        version = CourseVersion.objects.create(course=course, number=course.confirmed_versions.count() + 1,
            draft=draft, draft_revision=draft.revision, confirmation_fingerprint=fingerprint, payload_hash=digest(payload),
            frozen_payload=copy.deepcopy(payload), evidence_manifest={**copy.deepcopy(draft.machine_base.context), "analysis_statements":copy.deepcopy(draft.machine_base.context["statements"]), "statements":statement_list(course), "analysis_mode": draft.machine_base.mode},
            statements=statement_list(course), manual_patches=copy.deepcopy(draft.manual_patches), confirmed_by=owner)
    record.response = {"version_id": str(version.id)}
    record.save(update_fields=["response"])
    return version


from .topic_confirmation import confirm_topics
