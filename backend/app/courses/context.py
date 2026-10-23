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

PROMPT_VERSION = "r1-course-analysis-3"
ANALYSIS_CALL_SECONDS = 300
SCHEMA_VERSION = "r1-course-draft-1"
# 2026-10-24: user added the main L'Hopital and implicit-differentiation teaching pages
# (M34 p34, 46-49; M14 p4; M48 p19, 21, 22) after the first visual re-analysis found them missing.
PAGE_SELECTION = {"M35": list(range(2, 18)), "M34": [14, 28, 29, 30, 31, 32, 33, 34, 41, 46, 47, 48, 49],
    "M48": [19, 20, 21, 22], "M06": [2, 6], "M32": [2], "M46": [3, 4, 6], "M05": [1, 3, 5], "M14": [4, 5], "M33": [22]}
TARGETS = {"K1": "Definition and differentiability", "K2": "Differentiation rules and higher derivatives",
    "K3": "Stationary points and extrema", "K4": "Business applications and optimisation",
    "K5": "Rolle and Mean Value Theorems", "K6": "L'Hopital's Rule", "K7": "Implicit differentiation",
    "K8": "Monotonicity"}


def target_knowledge(course):
    return [{"id": str(uuid.uuid5(course.id, key)), "key": key, "title": title} for key, title in TARGETS.items()]


def statement_list(course):
    # An answer is only meaningful with its question, so the question text travels with it.
    rows = list(course.statements.order_by("created_at", "id").values("id", "text", "kind", "source", "clarification_id", "question"))
    for row in rows:
        row["id"] = str(row["id"])
    if not rows and course.scope_statement and course.scope_provenance == "user_statement":
        rows = [{"id": str(uuid.uuid5(course.id, "initial-scope")), "text": course.scope_statement,
                 "kind": "exam_scope", "source": "User's existing course scope declaration", "clarification_id": "", "question": ""}]
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
    # Material hashes are the reviewed round-one manifest, not untrusted filename matching.
    inventory = json.loads((Path(__file__).parent / "qm_analysis_manifest.json").read_text(encoding="utf-8"))
    known = {m["sha256"]: m for m in inventory}
    versions = list(MaterialVersion.objects.filter(material__course=course, blob__sha256__in=known)
                    .select_related("blob").order_by("id"))
    # Duplicate imports of identical content contribute once, preserving their source version.
    unique = {}
    for v in versions:
        unique.setdefault(v.blob.sha256, v)
    versions = list(unique.values())
    pack = build_evidence_pack(course.owner, [v.id for v in versions])
    v_by_id = {str(v.id): v for v in versions}
    materials = [{**m, "filename": v_by_id[m["material_version_id"]].original_filename,
                  "code": known[m["sha256"]]["id"], "selected_pages": PAGE_SELECTION[known[m["sha256"]]["id"]]}
                 for m in pack["materials"]]
    evidence = []
    for e in pack["evidence"]:
        v = v_by_id[e["material_version_id"]]
        code = known[v.blob.sha256]["id"]
        if e["physical_page"] in PAGE_SELECTION[code]:
            evidence.append({k: value for k, value in {**e, "material_code": code,
                            "roles": v.roles, "blob_sha256": v.blob.sha256}.items() if k != "blocks"})
    attach_visual_evidence(course, evidence)
    targets = target_knowledge(course)
    data = {"course_title": course.title, "target_ids": [t["id"] for t in targets], "target_knowledge": targets,
        "materials": materials, "evidence": evidence, "route_rule_version": RULE_VERSION, "statements": statement_list(course),
        "round1_exclusions": ["software_command_answers", "above_and_beyond_curve_sketching", "other_chapters"]}
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
        "page_count": len(data["evidence"]),
        "review_count": sum(e["visual_status"] == "transcribed" for e in data["evidence"]),
        "visual_pending": [{"evidence_id": e["id"], "material_code": e["material_code"], "physical_page": e["physical_page"],
                            "signals": e["route"]["signals"]} for e in data["evidence"] if e["visual_status"] == "visual_pending"],
        "materials": [{k: m[k] for k in ("code", "filename", "selected_pages", "material_version_id", "sha256")} for m in data["materials"]],
        "statements": data["statements"], "max_calls": 8, "call_timeout_seconds": snapshot["call_timeout_seconds"],
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
