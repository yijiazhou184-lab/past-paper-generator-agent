"""Explicit bounded QM evidence selection; never silently send a whole collection."""
import hashlib
import json
import os
import uuid
from pathlib import Path
from django.conf import settings
from app.core.idempotency import digest
from app.core.errors import DomainError
from app.core.models import ModelInvocation
from app.ai.visual import legacy_to_visual
from app.materials.models import MaterialVersion, Evidence
from app.materials.evidence import build_evidence_pack, render_page
from app.materials.routing import RULE_VERSION
from app.materials.storage import path_for
from app.materials.transcription import cached, decide, page_entry, signal_pages
from .models import UserStatement
from .schemas import AnalysisOutput

PROMPT_VERSION = "r1-course-analysis-5-decisions"
ANALYSIS_CALL_SECONDS = 300
SCHEMA_VERSION = "r1-course-draft-1"
def statement_list(course, topic_ids=None):
    # An answer is only meaningful with its question, so the question text travels with it.
    from .decisions import effective_statements
    rows = effective_statements(course,topic_ids)
    if topic_ids is not None:
        rows = [r for r in rows if not r["topic_ids"] or set(r["topic_ids"]).intersection(topic_ids)]
    for row in rows:
        row["id"] = str(row["id"])
    if not rows and course.scope_statement and course.scope_provenance == "user_statement":
        rows = [{"id": str(uuid.uuid5(course.id, "initial-scope")), "text": course.scope_statement,
                 "kind": "exam_scope", "source": "User's existing course scope declaration", "clarification_id": "", "question": "", "topic_ids": [], "decision": {}}]
    return rows


def ensure_statements(course):
    for row in statement_list(course):
        UserStatement.objects.get_or_create(id=row["id"], defaults={**{k: v for k, v in row.items() if k != "id"},
            "course": course, "submitted_by": course.owner})


def compact_transcription(payload, origin, record_id):
    items = [{k: v for k, v in item.items() if v is not None} for item in payload["items"]]
    return {"origin": origin, "record_id": record_id, "verification": "model_candidate_not_human_verified",
            "status": payload["status"], "page_title": payload["page_title"],
            "faithful_transcription": payload["faithful_transcription"], "items": items,
            "findings": payload["findings"], "unresolved": payload["unresolved"]}


def legacy_reviews(course):
    """Batch-one page reviews whose page, parse and image are unchanged; keyed by evidence id."""
    reviews = {}
    for call in ModelInvocation.objects.filter(task__course=course, task__kind="ai_validation",
                                               state="completed").select_related("task").order_by("created_at"):
        candidate = call.result.get("payload") or {}
        source = candidate.get("source", {})
        if call.result.get("status") != "parsed" or source.get("evidence_id") in reviews:
            continue
        sent = next((p for p in call.task.snapshot.get("pages", []) if p["source"] == source), None)
        if sent:
            reviews[source["evidence_id"]] = (call, candidate, sent["image_sha256"])
    return reviews


def attach_visual_evidence(course, evidence):
    """Give every page its route and, for image-route pages, an accepted transcription or a pending marker."""
    requested, manual = signal_pages(course)
    rows = {str(e.id): e for e in Evidence.objects.filter(pk__in=[e["id"] for e in evidence])
            .select_related("material_version__blob", "material_version__material__course", "parse_version")}
    legacy = legacy_reviews(course)
    for e in evidence:
        row = rows[e["id"]]
        decision = decide(row, requested, manual)
        e["route"] = {"route": decision["route"], "signals": decision["signals"]}
        e["visual"] = None
        if decision["route"] != "visual":
            e["visual_status"] = "not_needed"
            continue
        found = cached(page_entry(row, decision))
        if found:
            e["visual"] = compact_transcription(found.payload, found.origin, str(found.id))
        elif e["id"] in legacy:
            call, review, image_sha = legacy[e["id"]]
            image = render_page(course.owner, row.material_version_id, row.physical_page).read_bytes()
            if (review["source"]["parse_content_hash"] == e["parse_content_hash"]
                    and hashlib.sha256(image).hexdigest() == image_sha):
                e["visual"] = compact_transcription(legacy_to_visual(review), "legacy_page_review", str(call.id))
        e["visual_status"] = "transcribed" if e["visual"] else "visual_pending"


def build_context(course):
    """Compatibility entrypoint; explicit catalogue links replace subject-specific selection."""
    from .models import CourseDraft
    from .topic_context import build_topic_analysis_context, selection_defaults
    topics=list(course.topics.filter(archived=False))
    if len(topics)==1:
        selection=[s for s in selection_defaults(course,str(topics[0].id)) if s["pages"]]
        if selection:
            draft=CourseDraft.objects.filter(course=course).first()
            return build_topic_analysis_context(course,[str(topics[0].id)],selection,draft.revision if draft else 0)
    return freeze_context({"course_title":course.title,"target_ids":[],"target_knowledge":[],
        "materials":[],"evidence":[],"route_rule_version":RULE_VERSION,"statements":statement_list(course),
        "round1_exclusions":["software_command_answers"]})


def freeze_context(data):
    prompt = (Path(__file__).parents[1] / "ai/prompts/course_analysis.md").read_text(encoding="utf-8")
    schema = AnalysisOutput.model_json_schema()
    frozen = {"input": data, "prompt": prompt, "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
              "projection_version": "r1-compact-evidence-2",
              "admission": {"method": "official_input_tokens_count", "limit_tokens": 60000},
              # User decision 2026-10-24: a 45-page analysis took 142.6 s and the next timed out at 150 s.
              "call_timeout_seconds": ANALYSIS_CALL_SECONDS,
              "schema_hash": digest(schema), "model": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"),
              "endpoint": "https://api.openai.com/v1/responses", "store": False}
    return {**frozen, "context_hash": digest(frozen)}


def inspect_scope(snapshot):
    data = snapshot["input"]
    return {"context_hash": snapshot["context_hash"], "model": snapshot["model"],
        "endpoint": snapshot["endpoint"], "store": False, "new_images": 0,
        "target_topics": data.get("target_topics", []), "base_revision": data.get("base_revision"),
        "page_count": len(data["evidence"]),
        "review_count": sum(e["visual_status"] == "transcribed" for e in data["evidence"]),
        "visual_pending": [{"evidence_id": e["id"], "material_code": e["material_code"], "physical_page": e["physical_page"],
                            "signals": e["route"]["signals"]} for e in data["evidence"] if e["visual_status"] == "visual_pending"],
        "materials": [{k: m[k] for k in ("code", "filename", "selected_pages", "material_version_id", "sha256")} for m in data["materials"]],
        "statements": data["statements"], "prior_decisions":data.get("prior_decisions",[]), "max_calls": 8, "call_timeout_seconds": snapshot["call_timeout_seconds"],
        "admission": {**snapshot["admission"], "local_utf8_bytes": local_bytes(snapshot),
                      "note": "One official token-count request is sent after authorisation; above the limit "
                              "the analysis stops without an analysis request."}}


def local_bytes(snapshot):
    """Size of the request as built locally; shown for orientation, not a token count."""
    from .analysis import make_spec
    spec = make_spec(snapshot)
    return len((snapshot["prompt"] + json.dumps(spec.input, ensure_ascii=False)
                + json.dumps(AnalysisOutput.model_json_schema())).encode("utf-8"))


def verify_sources(snapshot, course):
    for material in snapshot["input"]["materials"]:
        if "assignment" in material:
            from app.materials.topic_assignments import assignment_view
            linked = MaterialVersion.objects.get(pk=material["material_version_id"], material__course=course)
            if assignment_view(linked) != material["assignment"]:
                raise DomainError("MATERIAL_CONTEXT_CHANGED","Topic links changed since this analysis was prepared.")
        version = MaterialVersion.objects.select_related("blob").get(id=material["material_version_id"], material__course=course)
        if hashlib.sha256(path_for(version.blob.storage_key).read_bytes()).hexdigest() != material["sha256"]:
            raise DomainError("SOURCE_CONTENT_CHANGED")
    for e in snapshot["input"]["evidence"]:
        version = MaterialVersion.objects.get(pk=e["material_version_id"], material__course=course)
        source = version.evidence.select_related("parse_version").get(pk=e["id"])
        if (source.text != e["text"] or str(source.parse_version_id) != e["parse_version_id"]
                or source.parse_version.content_hash != e["parse_content_hash"]
                or hashlib.sha256(path_for(source.parse_version.document_key).read_bytes()).hexdigest() != e["parse_content_hash"]):
            raise DomainError("PARSED_CONTENT_CHANGED")
