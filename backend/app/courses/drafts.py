import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from pydantic import ValidationError
from app.core.errors import DomainError
from app.core.idempotency import intent
from .models import Course, CourseDraft, UserStatement
from .schemas import CourseDraftPayload, validate_template
from .clarifications import classify_gaps
from .context import statement_list

EDITABLE = {"knowledge_nodes": {"title", "requirements", "depth"}, "scope_claims": {"text", "disposition"},
            "method_rules": {"text"}, "historical_style": {"text"}}


def get_field(payload, path):
    if len(path) == 1 and path[0] in ("title", "template_suggestion"):
        return payload, path[0]
    if len(path) == 2 and path[0] == "target_exam" and path[1] in ("label", "academic_year"):
        return payload["target_exam"], path[1]
    if len(path) == 3 and path[0] in EDITABLE and path[2] in EDITABLE[path[0]]:
        item = next((item for item in payload[path[0]] if item["id"] == path[1]), None)
        if item is not None:
            return item, path[2]
    raise DomainError("PATCH_PATH_INVALID", "This field is not editable or no longer exists.", status=400)


def apply_patch_value(payload, patch):
    parent, key = get_field(payload, patch["path"])
    parent[key] = copy.deepcopy(patch["value"])
    if patch["path"][0] in ("scope_claims", "method_rules", "historical_style") and patch.get("statement_id"):
        parent.update(provenance="user_statement", authority_status="unverified", status="declared",
                      statement_ids=[patch["statement_id"]])


def merge_manual(machine, previous):
    merged, warnings = copy.deepcopy(machine), []
    for patch in previous.manual_patches if previous else []:
        try:
            parent, key = get_field(merged, patch["path"])
            if parent[key] != patch.get("base_value") and parent[key] != patch["value"]:
                warnings.append({"path": patch["path"], "message": "New analysis differs from your saved edit. Your edit was kept.",
                                 "machine_value": copy.deepcopy(parent[key]), "manual_value": patch["value"]})
            apply_patch_value(merged, patch)
        except DomainError:
            # Retain an orphaned manually edited item, explicitly requiring review.
            path = patch["path"]
            if len(path) == 3 and path[0] in EDITABLE:
                old = next((i for i in previous.payload[path[0]] if i["id"] == path[1]), None)
                if old and not any(i["id"] == old["id"] for i in merged[path[0]]):
                    merged[path[0]].append(copy.deepcopy(old))
            warnings.append({"path": path, "message": "A manually edited item is absent from the new analysis. Review it before confirmation.",
                             "machine_value": None, "manual_value": patch["value"]})
    return merged, warnings


def draft_view(draft):
    if draft is None:
        return None
    questions = classify_gaps(draft.payload, draft.machine_base.context["target_ids"])
    for q in questions:
        answer = draft.clarification_answers.get(q["id"])
        if answer:
            q["status"] = "answered"
            q["answer"] = answer
    latest = draft.course.confirmed_versions.order_by("-number").first()
    statements = statement_list(draft.course)
    analysed_statements = {s["id"] for s in draft.machine_base.context["statements"]}
    pending_answers = any(s["kind"] in ("exam_scope", "clarification") and s["id"] not in analysed_statements for s in statements)
    return {"id": str(draft.id), "revision": draft.revision, "payload": draft.payload,
        "manual_patches": draft.manual_patches, "merge_warnings": draft.merge_warnings,
        "clarifications": questions, "mode": draft.machine_base.mode,
        "analysis_task_id": str(draft.machine_base.task_id), "updated_at": draft.updated_at,
        "target_ids": draft.machine_base.context["target_ids"],
        "evidence": [{k: e[k] for k in ("id", "material_version_id", "physical_page", "material_code")} for e in draft.machine_base.context["evidence"]],
        "statements": statements, "confirmed_revision": latest.draft_revision if latest else None,
        "answers_need_analysis": pending_answers,
        "latest_version_id": str(latest.id) if latest else None,
        "change_summary": "User edits are preserved separately from the machine analysis.",
        "blocking_count": sum(q["impact"] == "blocks_selected_scope" for q in questions) + len(draft.merge_warnings) + int(pending_answers)}


@transaction.atomic
def save_draft(owner, course_id, expected_revision, patches, key, acknowledge_merge=False):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    record = intent(owner, f"draft:{course.id}", key, {"revision": expected_revision, "patches": patches, "ack": acknowledge_merge})
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), course=course)
    if record.response:
        # Return current server state; the committed revision is separately recorded for lost-response recovery.
        return draft, record.response["revision"]
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT", "A newer draft is saved. Compare it with your edits before continuing.")
    if not isinstance(patches, list) or len(patches) > 100:
        raise DomainError("PATCH_INVALID", status=400)
    payload = copy.deepcopy(draft.payload)
    manual = {tuple(p["path"]): p for p in draft.manual_patches}
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {"path", "value"} or not isinstance(patch["path"], list):
            raise DomainError("PATCH_INVALID", status=400)
        path = patch["path"]
        if not all(isinstance(p, str) for p in path):
            raise DomainError("PATCH_INVALID", status=400)
        parent, field = get_field(payload, path)
        entry = {**patch, "base_value": manual.get(tuple(path), {}).get("base_value", copy.deepcopy(parent[field]))}
        if path[0] in ("scope_claims", "method_rules", "historical_style"):
            statement = UserStatement.objects.create(course=course, text=str(patch["value"]), kind="manual_edit",
                source="Direct course profile edit", submitted_by=owner)
            entry["statement_id"] = str(statement.id)
        apply_patch_value(payload, entry)
        manual[tuple(path)] = entry
    try:
        payload = CourseDraftPayload.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        raise DomainError("DRAFT_FIELD_INVALID", "Check the edited field values.", status=400)
    validate_template(payload["template_suggestion"])
    draft.payload = payload
    draft.manual_patches = list(manual.values())
    draft.revision += 1
    if acknowledge_merge:
        draft.merge_warnings = []
    draft.save()
    record.response = {"revision": draft.revision}
    record.save(update_fields=["response"])
    return draft, draft.revision


@transaction.atomic
def answer_clarification(owner, course_id, question_id, text, expected_revision, key):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    record = intent(owner, f"answer:{course.id}", key, {"id": question_id, "text": text, "revision": expected_revision})
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), course=course)
    if record.response:
        return draft
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT")
    questions = classify_gaps(draft.payload, draft.machine_base.context["target_ids"])
    asked = next((q for q in questions if q["id"] == question_id), None)
    if asked is None:
        raise DomainError("CLARIFICATION_NOT_FOUND", status=404)
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 3000:
        raise DomainError("ANSWER_INVALID", status=400)
    statement = UserStatement.objects.create(course=course, text=text.strip(), kind="exam_scope" if question_id == "gap-exam-scope" else "clarification",
        source="Answer to course clarification", clarification_id=question_id, question=asked["question"], submitted_by=owner)
    draft.clarification_answers[question_id] = {"text": text.strip(), "statement_id": str(statement.id),
        "reanalysis_required": question_id != "gap-exam-scope"}
    if question_id == "gap-exam-scope":
        # Do not infer which topics arbitrary free text includes. Explicit structured scope adoption is separate.
        draft.clarification_answers[question_id]["reanalysis_required"] = True
    draft.revision += 1
    draft.save()
    record.response = {"revision": draft.revision, "statement_id": str(statement.id)}
    record.save(update_fields=["response"])
    return draft
