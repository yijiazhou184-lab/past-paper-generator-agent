"""Bounded batch-one validation: a synthetic smoke followed by five named risk pages."""
import hashlib
import json
import os
from django.conf import settings
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import Task
from app.core.tasks import checkpoint, finish_task
from app.materials.models import MaterialVersion, Evidence
from app.materials.evidence import render_page
from app.materials.storage import path_for
from .contracts import ModelCallSpec
from .invocations import run_call
from .page_review import (SmokeResult, PageReview, PAGE_INSTRUCTIONS, PAGE_PROMPT_VERSION, PAGE_SCHEMA_VERSION)

RISK_PAGES = {"M34": [14, 41], "M14": [5], "M33": [22], "M48": [20]}


def source_ref(e):
    return {"evidence_id": str(e.id), "material_version_id": str(e.material_version_id),
            "parse_version_id": str(e.parse_version_id), "physical_page": e.physical_page,
            "blob_sha256": e.material_version.blob.sha256, "parse_content_hash": e.parse_version.content_hash}


def page_input(e):
    return {"source": source_ref(e), "extracted_text": e.text}


def build_snapshot(course, model, *, smoke_only=False):
    manifest = json.loads((settings.BASE_DIR / "backend/tests/fixtures/qm_manifest.json").read_text())
    hashes = {i["id"]: i["sha256"] for i in manifest}
    pages = []
    for material_id, numbers in ({} if smoke_only else RISK_PAGES).items():
        v = MaterialVersion.objects.get(material__course=course, blob__sha256=hashes[material_id], number=1)
        for number in numbers:
            e = v.evidence.select_related("material_version__blob", "parse_version").get(physical_page=number)
            if e.parse_version.state != "ready":
                raise DomainError("EVIDENCE_NOT_READY")
            image = render_page(course.owner, v.id, number).read_bytes()
            pages.append({"material_id": material_id, "filename": v.original_filename, "source": source_ref(e),
                          "input_hash": digest(page_input(e)), "image_sha256": hashlib.sha256(image).hexdigest()})
    return {"purpose": "batch1_live_validation", "model": model, "pages": pages,
            "authorization": "explicit_cli_synthetic_only" if smoke_only else "explicit_cli_scoped_to_these_five_pages", "store": False,
            "prompt_version": PAGE_PROMPT_VERSION, "schema_version": PAGE_SCHEMA_VERSION}


def require_success(result):
    if result.status != "parsed":
        message = ("The API account has no available credit. Check billing and usage limits before retrying."
                   if result.error_code == "PROVIDER_QUOTA_EXHAUSTED" else
                   "The live model check did not complete. Review the saved call metadata before retrying.")
        raise DomainError(result.error_code or "MODEL_CALL_FAILED",
                          message)


def run_validation(token):
    task = Task.objects.select_related("course__owner").get(pk=token.task_id)
    snapshot = task.snapshot
    if task.kind != "ai_validation" or snapshot.get("authorization") not in (
            "explicit_cli_scoped_to_these_five_pages", "explicit_cli_synthetic_only"):
        raise DomainError("LIVE_CALL_NOT_AUTHORIZED")
    if snapshot != build_snapshot(task.course, snapshot["model"],
                                  smoke_only=snapshot["authorization"] == "explicit_cli_synthetic_only"):
        raise DomainError("VALIDATION_SNAPSHOT_CHANGED")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key.strip():
        raise DomainError("API_KEY_MISSING")
    checkpoint(token, "Validating structured output with a synthetic example")
    smoke_spec = ModelCallSpec(stage="semantic_review", prompt_version="r1-smoke-1", schema_version="r1-smoke-1",
        context_hash=digest({"function": "x^2", "x": 3}), input={"function": "x^2", "x": 3}, max_output_tokens=1000)
    smoke = run_call(token, "smoke", smoke_spec, instructions="Return the derivative with respect to x and its integer value at the supplied x.",
                     output_type=SmokeResult, api_key=key, model=snapshot["model"])
    require_success(smoke)
    if smoke.payload["at_x_3"] != 6:
        raise DomainError("SMOKE_ASSERTION_FAILED")
    reviews = []
    for page in snapshot["pages"]:
        ref = page["source"]
        e = Evidence.objects.select_related("material_version__blob", "parse_version").get(
            pk=ref["evidence_id"], material_version__material__course=task.course)
        image = render_page(task.course.owner, e.material_version_id, e.physical_page).read_bytes()
        if (source_ref(e) != ref or digest(page_input(e)) != page["input_hash"] or
                hashlib.sha256(image).hexdigest() != page["image_sha256"] or
                hashlib.sha256(path_for(e.material_version.blob.storage_key).read_bytes()).hexdigest() != ref["blob_sha256"] or
                hashlib.sha256(path_for(e.parse_version.document_key).read_bytes()).hexdigest() != ref["parse_content_hash"]):
            raise DomainError("SOURCE_HASH_MISMATCH")
        spec = ModelCallSpec(stage="semantic_review", prompt_version=PAGE_PROMPT_VERSION,
            schema_version=PAGE_SCHEMA_VERSION, context_hash=digest(page), input=page_input(e), max_output_tokens=5000)
        result = run_call(token, f'{page["material_id"]}-p{e.physical_page}', spec, instructions=PAGE_INSTRUCTIONS,
                          output_type=PageReview, api_key=key, model=snapshot["model"], image=image)
        require_success(result)
        if result.payload["source"] != ref:
            raise DomainError("MODEL_SOURCE_MISMATCH")
        reviews.append({"material_id": page["material_id"], "source": ref, "status": result.payload["status"],
                        "verification": "model_candidate_not_human_verified",
                        "findings": result.payload["findings"]})
    finish_task(token, {"purpose": "batch1_live_validation", "mode": "live", "smoke_passed": True,
                       "pages": reviews, "note": "Original evidence remains unchanged and needs review."})
