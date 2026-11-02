import copy
import os
import uuid
from django.db import transaction
from django.utils import timezone
from app.core.errors import DomainError
from app.core.models import Task, TaskAttempt, TaskEvent
from app.core.tasks import submit_task, locked_task, checkpoint, finish_task
from app.core.idempotency import digest
from app.ai.contracts import ModelCallSpec
from app.ai.invocations import run_call, count_call
from app.ai.responses import request_body
from .models import Course, CourseDraft, CourseMachineBase, AnalysisGrant
from .context import build_context, ensure_statements, inspect_scope, verify_sources
from .schemas import AnalysisOutput, validate_payload
from .drafts import merge_manual
from .clarifications import classify_gaps


def sent_transcription(visual):
    """The page as the model needs it. Readable items repeat formulas already inline in the transcription,
    so only items that are not fully readable are sent; the snapshot keeps every item."""
    return {"origin": visual["origin"], "status": visual["status"], "page_title": visual["page_title"],
            "faithful_transcription": visual["faithful_transcription"],
            "unclear_items": [{k: i[k] for k in ("kind", "location", "legibility")} for i in visual["items"]
                              if i["legibility"] != "readable"],
            "findings": [{k: f[k] for k in ("kind", "observation")} for f in visual["findings"]],
            "unresolved": visual["unresolved"]}


def make_spec(snapshot):
    # The immutable local snapshot retains complete hashes and parser identities.
    # The model needs source IDs and content, not the same parser hashes on every page.
    compact = copy.deepcopy(snapshot["input"])
    # A transcribed page is sent as its transcription; its extracted text stays in the local snapshot only.
    compact["evidence"] = [{**{k: e[k] for k in ("id", "material_version_id", "physical_page", "material_code", "roles",
                                                 "fidelity_status", "visual_status")}, "route": e["route"]["route"],
                            **({"visual": sent_transcription(e["visual"])} if e["visual"] else {"text": e["text"]})}
                           for e in compact["evidence"]]
    compact["materials"] = [{k: m[k] for k in ("material_version_id", "filename", "code", "roles", "classification_basis", "selected_pages", "answer_links")}
                            for m in compact["materials"]]
    return ModelCallSpec(stage="course_analysis", prompt_version=snapshot["prompt_version"],
        schema_version=snapshot["schema_version"], context_hash=snapshot["context_hash"], input=compact)


@transaction.atomic
def submit_analysis(course, context_hash, key, *, authorize=False, grant_source="Explicit profile consent", parent=None, target_topic_ids=None, material_selection=None, base_revision=None):
    course = Course.objects.select_for_update().get(pk=course.pk)
    if target_topic_ids is not None:
        from .topic_context import build_topic_analysis_context
        snapshot = build_topic_analysis_context(course,target_topic_ids,material_selection,base_revision)
    else:
        snapshot = build_context(course)
    if snapshot["context_hash"] != context_hash:
        raise DomainError("ANALYSIS_INPUT_CHANGED", "The proposed inputs changed. Review the sending scope again.")
    if not snapshot["input"]["evidence"]:
        raise DomainError("EVIDENCE_NOT_READY", "Select parsed teaching material and explicit physical pages before analysis.")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise DomainError("API_KEY_MISSING", "Set OPENAI_API_KEY in the local .env.local file.")
    try:
        # Size is checked by the official token count after consent, before the analysis request.
        request_body(make_spec(snapshot), snapshot["prompt"], AnalysisOutput, snapshot["model"], byte_admission=False)
    except ValueError as exc:
        raise DomainError(str(exc), "The selected input cannot form a valid request. No data was sent.")
    if authorize:
        AnalysisGrant.objects.get_or_create(course=course, context_hash=context_hash,
            defaults={"granted_by": course.owner, "scope": inspect_scope(snapshot), "source": grant_source})
    if not AnalysisGrant.objects.filter(course=course, context_hash=context_hash).exists():
        raise DomainError("ANALYSIS_CONSENT_REQUIRED", "Review and authorise this exact analysis input before sending course data.", status=403)
    ensure_statements(course)
    if parent is None:
        parent = Task.objects.filter(course=course, kind="analysis", state__in=["succeeded", "failed", "cancelled", "needs_info"]).order_by("-created_at").first()
    return submit_task(course, "analysis", snapshot, key, parent=parent)


def assign_ids(course, payload, target_ids, namespace=None):
    """Local output keys become server-generated persistent identifiers."""
    payload = copy.deepcopy(payload)
    collections = [payload[k] for k in ("knowledge_nodes", "scope_claims", "method_rules", "historical_style", "issues", "clarifications")]
    mapping = {item["id"]: item["id"] if item["id"] in target_ids else str(uuid.uuid5(uuid.UUID(namespace) if namespace else course.id, "analysis:" + item["id"]))
               for items in collections for item in items}
    for items in collections:
        for item in items:
            item["id"] = mapping[item["id"]]
            for field in ("parent_id",):
                if item.get(field):
                    item[field] = mapping.get(item[field], item[field])
            for field in ("prerequisite_ids", "method_ids", "subject_ids", "affected_ids", "resolves_issue_ids"):
                if field in item:
                    item[field] = [mapping.get(value, value) for value in item[field]]
    return payload


@transaction.atomic
def publish_analysis(token, payload, context, mode, visual_review_requests=()):
    task = locked_task(token)
    # Serialize with all editing and confirmation. Late edits are merged from the current draft.
    course = Course.objects.select_for_update().get(pk=task.course_id)
    if CourseMachineBase.objects.filter(task=task).exists():
        raise DomainError("ANALYSIS_ALREADY_PUBLISHED")
    base = CourseMachineBase.objects.create(course=course, task=task, payload=payload, context=context, mode=mode)
    previous = CourseDraft.objects.select_for_update().filter(course=course).first()
    if context.get("target_topic_ids"):
        from .topic_state import scoped_merge
        merged,warnings,states = scoped_merge(payload,previous,context,base)
    else:
        merged,warnings = merge_manual(payload,previous)
        states = previous.topic_state if previous else {}
    draft = previous or CourseDraft(course=course)
    draft.topic_state = states
    draft.machine_base = base
    draft.payload = merged
    draft.merge_warnings = warnings
    if previous:
        draft.revision += 1
    draft.save()
    questions = classify_gaps(payload if context.get("target_topic_ids") else merged, context["target_ids"])
    blocked = any(q["impact"] == "blocks_selected_scope" for q in questions)
    result = {"draft_id": str(draft.id), "revision": draft.revision, "mode": mode,
              "profile_url": f"/courses/{course.id}/profile" + ("?topic="+context["target_topic_ids"][0] if context.get("target_topic_ids") else ""), "blocking_gaps": sum(q["impact"] == "blocks_selected_scope" for q in questions),
              "visual_review_requests": list(visual_review_requests)}
    if blocked:
        task.state, task.stage, task.result = "needs_info", "Course draft needs information", result
        task.finished_at = timezone.now()
        task.save()
        TaskAttempt.objects.filter(task=task, epoch=token.epoch).update(outcome="needs_info", finished_at=task.finished_at)
        TaskEvent.objects.create(task=task, epoch=token.epoch, stage=task.stage)
    else:
        finish_task(token, result)
    return draft


def run_analysis(token):
    task = Task.objects.select_related("course").get(pk=token.task_id)
    snapshot = task.snapshot
    if not AnalysisGrant.objects.filter(course=task.course, context_hash=snapshot["context_hash"]).exists():
        raise DomainError("ANALYSIS_CONSENT_REQUIRED")
    if digest(AnalysisOutput.model_json_schema()) != snapshot["schema_hash"]:
        raise DomainError("ANALYSIS_SCHEMA_CHANGED", "Restart analysis with the current schema; the old task was not altered.")
    checkpoint(token, "Checking frozen evidence")
    verify_sources(snapshot, task.course)
    spec, key = make_spec(snapshot), os.environ.get("OPENAI_API_KEY", "")
    counted = count_call(token, "course-analysis:count", spec, instructions=snapshot["prompt"],
                         output_type=AnalysisOutput, api_key=key, model=snapshot["model"])
    result = run_call(token, "course-analysis", spec, instructions=snapshot["prompt"],
        output_type=AnalysisOutput, api_key=key, model=snapshot["model"], counted_tokens=counted,
        call_seconds=snapshot.get("call_timeout_seconds", 150))
    if result.status != "parsed":
        raise DomainError(result.error_code or "COURSE_ANALYSIS_FAILED", "The model did not return a usable course draft. Saved call details explain the failure.")
    output = AnalysisOutput.model_validate(result.payload)
    if output.draft is None or output.status in ("unable_to_determine", "not_checked"):
        raise DomainError("COURSE_ANALYSIS_UNDETERMINED", output.explanation)
    if snapshot["input"].get("target_topic_ids") and not output.draft.knowledge_nodes:
        raise DomainError("COURSE_KNOWLEDGE_UNDETERMINED","No supported knowledge could be identified. Review the saved analysis and material selection.")
    checkpoint(token, "Checking course references and provenance")
    payload = validate_payload(output.draft.model_dump(mode="json"), snapshot["input"])
    review_ids=snapshot["input"]["target_ids"] or [n["id"] for n in payload["knowledge_nodes"]]
    if output.status == "needs_info" and not any(q["impact"] == "blocks_selected_scope" for q in classify_gaps(payload, review_ids)):
        payload["issues"].append({"id": "model-needs-info", "code": "model_needs_info", "severity": "blocking",
            "affected_ids": review_ids, "explanation": output.explanation, "evidence_ids": [],
            "suggested_action": "Review the information needed by the analysis."})
    target_topics=snapshot["input"].get("target_topic_ids",[])
    if target_topics:
        from .topic_state import state_map,COLLECTIONS
        previous=CourseDraft.objects.filter(course=task.course).first()
        foreign={i for tid,state in state_map(previous).items() if tid not in target_topics for ids in state["item_ids"].values() for i in ids}
        if any(row["id"] in foreign or foreign.intersection(row.get("subject_ids",row.get("affected_ids",[]))) for key in COLLECTIONS for row in payload[key]):
            raise DomainError("ANALYSIS_TOPIC_SCOPE_INVALID")
    payload = assign_ids(task.course, payload, snapshot["input"]["target_ids"], target_topics[0] if target_topics else None)
    if target_topics:
        snapshot["input"]["target_ids"]=[n["id"] for n in payload["knowledge_nodes"]]
    publish_analysis(token, payload, snapshot["input"], "live", visual_requests(output, snapshot["input"]))


def visual_requests(output, context):
    """Pages the model wants read from their image; they become model_requested route signals."""
    known = {e["id"] for e in context["evidence"]}
    requests = [r.model_dump() for r in output.visual_review_requests]
    if {r["evidence_id"] for r in requests} - known:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "A page-image request names a page outside this analysis.")
    return requests
