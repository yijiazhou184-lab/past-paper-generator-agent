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
from app.materials.models import MaterialVersion
from app.materials.evidence import build_evidence_pack
from app.materials.storage import path_for
from .models import UserStatement
from .schemas import AnalysisOutput

PROMPT_VERSION = "r1-course-analysis-1"
SCHEMA_VERSION = "r1-course-draft-1"
PAGE_SELECTION = {"M35": list(range(2, 18)), "M34": [14, 28, 29, 30, 31, 32, 33, 41],
    "M48": [20], "M06": [2, 6], "M32": [2], "M46": [3, 4, 6], "M05": [1, 3, 5], "M14": [5], "M33": [22]}
TARGETS = {"K1": "Definition and differentiability", "K2": "Differentiation rules and higher derivatives",
    "K3": "Stationary points and extrema", "K4": "Business applications and optimisation",
    "K5": "Rolle and Mean Value Theorems", "K6": "L'Hopital's Rule", "K7": "Implicit differentiation",
    "K8": "Monotonicity"}


def target_knowledge(course):
    return [{"id": str(uuid.uuid5(course.id, key)), "key": key, "title": title} for key, title in TARGETS.items()]


def statement_list(course):
    rows = list(course.statements.order_by("created_at", "id").values("id", "text", "kind", "source", "clarification_id"))
    for row in rows:
        row["id"] = str(row["id"])
    if not rows and course.scope_statement and course.scope_provenance == "user_statement":
        rows = [{"id": str(uuid.uuid5(course.id, "initial-scope")), "text": course.scope_statement,
                 "kind": "exam_scope", "source": "User's existing course scope declaration", "clarification_id": ""}]
    return rows


def ensure_statements(course):
    for row in statement_list(course):
        UserStatement.objects.get_or_create(id=row["id"], defaults={**{k: v for k, v in row.items() if k != "id"},
            "course": course, "submitted_by": course.owner})


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
    evidence_ids = {e["id"] for e in evidence}
    reviews = []
    seen = set()
    for call in ModelInvocation.objects.filter(task__course=course, task__kind="ai_validation",
                                               state="completed").order_by("created_at"):
        candidate = call.result.get("payload") or {}
        source = candidate.get("source", {})
        source_id = source.get("evidence_id")
        if source_id in evidence_ids and source_id not in seen and call.result.get("status") == "parsed":
            original = next(e for e in evidence if e["id"] == source_id)
            if source.get("parse_content_hash") != original["parse_content_hash"]:
                continue
            seen.add(source_id)
            reviews.append({"call_id": str(call.id), "verification": "model_candidate_not_human_verified", "review": candidate})
    targets = target_knowledge(course)
    data = {"course_title": course.title, "target_ids": [t["id"] for t in targets], "target_knowledge": targets,
        "materials": materials, "evidence": evidence, "page_review_candidates": reviews, "statements": statement_list(course),
        "round1_exclusions": ["software_command_answers", "above_and_beyond_curve_sketching", "other_chapters"]}
    prompt = (Path(__file__).parents[1] / "ai/prompts/course_analysis.md").read_text(encoding="utf-8")
    schema = AnalysisOutput.model_json_schema()
    frozen = {"input": data, "prompt": prompt, "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
              "projection_version": "r1-compact-evidence-1",
              "schema_hash": digest(schema), "model": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"),
              "endpoint": "https://api.openai.com/v1/responses", "store": False}
    return {**frozen, "context_hash": digest(frozen)}


def inspect_scope(snapshot):
    data = snapshot["input"]
    return {"context_hash": snapshot["context_hash"], "model": snapshot["model"],
        "endpoint": snapshot["endpoint"], "store": False, "new_images": 0,
        "page_count": len(data["evidence"]), "review_count": len(data["page_review_candidates"]),
        "materials": [{k: m[k] for k in ("code", "filename", "selected_pages", "material_version_id", "sha256")} for m in data["materials"]],
        "statements": data["statements"], "max_calls": 8, "call_timeout_seconds": 150}


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
