"""Background page-image transcription for visual-route pages.

One bounded call per page; an accepted result is cached by its full key and never requested again.
Which pages may leave the machine is decided by transcription_policy, not by the task itself.
"""
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, transaction
from PIL import Image
from app.ai.contracts import ModelCallSpec
from app.ai.invocations import run_call
from app.ai.visual import (INSTRUCTIONS, PROMPT_VERSION, SCHEMA_VERSION, VisualTranscriptionOutput,
                           check_transcription)
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import Task, ModelInvocation
from app.core.tasks import submit_task, locked_task, checkpoint, finish_task
from .evidence import render_page
from .models import Evidence, MaterialVersion, VisualTranscription, TranscriptionGrant
from .routing import route_page, RULE_VERSION
from .storage import path_for

# Bounds one task to its deadline; remaining pages are scheduled when it ends.
MAX_PAGES_PER_TASK = 120
# Longest side accepted by the official adapter (portrait A4 renders at 1684 px).
MAX_IMAGE_SIDE = 1600
KEY_FIELDS = ("evidence_id", "parse_content_hash", "image_sha256", "model", "prompt_version", "schema_version")
ACTIVE = ("queued", "processing")


def transcription_model():
    return os.environ.get("OPENAI_MODEL", "gpt-6.1-sol")


def concurrency():
    try:
        value = int(os.environ.get("APP_TRANSCRIPTION_CONCURRENCY", "6"))
    except ValueError:
        value = 6
    return max(1, min(value, 16))


def current_evidence(version):
    """Pages of the newest ready parse of one material version."""
    parse_ids = (version.evidence.filter(parse_version__state="ready")
                 .order_by("-parse_version__created_at").values_list("parse_version_id", flat=True))
    if not parse_ids:
        return []
    return list(version.evidence.filter(parse_version_id=parse_ids[0])
                .select_related("material_version__blob", "parse_version").order_by("physical_page"))


def requested_pages(course):
    """Pages the latest course analysis asked to read from their images."""
    task = (Task.objects.filter(course=course, kind="analysis", state__in=["succeeded", "needs_info"])
            .order_by("-created_at").first())
    return {r["evidence_id"] for r in (task.result.get("visual_review_requests", []) if task else [])}


def signal_pages(course):
    """Evidence ids upgraded beyond the layout rules: by the latest analysis, or manually in a grant."""
    manual = {e["evidence_id"] for grant in TranscriptionGrant.objects.filter(course=course) for e in grant.scope
              if "manual" in e["route"]["signals"]}
    return requested_pages(course), manual


def decide(evidence, requested=frozenset(), manual=frozenset()):
    extra = (["model_requested"] if str(evidence.id) in requested else []) + (["manual"] if str(evidence.id) in manual else [])
    return route_page(evidence.physical_page, evidence.blocks, evidence.text, extra)


def model_image(evidence):
    """The exact PNG sent for a page: the viewer's rendering, shrunk only when it exceeds the adapter bound."""
    path = render_page(evidence.material_version.material.course.owner, evidence.material_version_id, evidence.physical_page)
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as page:
        if max(page.size) <= MAX_IMAGE_SIDE:
            return data
        scale = MAX_IMAGE_SIDE / max(page.size)
        resized = page.resize((round(page.width * scale), round(page.height * scale)), Image.LANCZOS)
        output = io.BytesIO()
        resized.save(output, format="PNG")
        return output.getvalue()


def page_entry(evidence, decision, image_sha=None):
    """The exact unit of consent and caching for one page image."""
    if image_sha is None:
        image_sha = hashlib.sha256(model_image(evidence)).hexdigest()
    return {"evidence_id": str(evidence.id), "material_version_id": str(evidence.material_version_id),
            "parse_version_id": str(evidence.parse_version_id), "physical_page": evidence.physical_page,
            "filename": evidence.material_version.original_filename,
            "blob_sha256": evidence.material_version.blob.sha256,
            "parse_content_hash": evidence.parse_version.content_hash, "image_sha256": image_sha,
            "model": transcription_model(), "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
            "route": decision}


def cache_key(entry):
    return tuple(entry[k] for k in KEY_FIELDS)


def cached(entry):
    return VisualTranscription.objects.filter(**{k: entry[k] for k in KEY_FIELDS}).first()


def transcription_policy(course, entries):
    """Split pages into (allowed, withheld). Development policy: only pages in an explicit grant.

    At launch this is replaced by the consent given at upload; the task code does not change.
    """
    mode = os.environ.get("APP_TRANSCRIPTION_POLICY", "per_page_grant")
    if mode != "per_page_grant":
        raise DomainError("TRANSCRIPTION_POLICY_UNAVAILABLE", "Only per-page consent is implemented in this round.")
    granted = {cache_key(e) for grant in TranscriptionGrant.objects.filter(course=course) for e in grant.scope}
    allowed = [e for e in entries if cache_key(e) in granted]
    withheld = [e for e in entries if cache_key(e) not in granted]
    return allowed, withheld


def running_pages(course):
    return {p["evidence_id"]: str(t.id) for t in Task.objects.filter(course=course, kind="visual_transcription", state__in=ACTIVE)
            for p in t.snapshot.get("pages", [])}


def visual_candidates(course, versions=None):
    """Visual-route pages without an accepted transcription that no active task is handling."""
    versions = versions or MaterialVersion.objects.filter(material__course=course).select_related("blob", "material__course")
    (requested, manual), running = signal_pages(course), running_pages(course)
    entries = []
    for version in versions:
        for evidence in current_evidence(version):
            decision = decide(evidence, requested, manual)
            if decision["route"] != "visual" or str(evidence.id) in running:
                continue
            entry = page_entry(evidence, decision)
            if not cached(entry):
                entries.append(entry)
    return entries


def schedule(course, trigger, versions=None, key=None):
    """Queue allowed pages; withheld pages wait for consent. Returns the task or None."""
    allowed, _ = transcription_policy(course, visual_candidates(course, versions))
    if not allowed:
        return None
    pages = allowed[:MAX_PAGES_PER_TASK]
    snapshot = {"purpose": "visual_transcription", "pages": pages, "policy": "per_page_grant",
                "rule_version": RULE_VERSION, "concurrency": concurrency(), "max_calls": len(pages), "trigger": trigger}
    # The key follows the exact pages, so a repeated trigger never duplicates or silently retries a task.
    return submit_task(course, "visual_transcription", snapshot, key or "transcribe:" + digest(pages))


def page_states(course, versions=None):
    """Per-page status for display. Matching ignores the image hash, which is verified before every call."""
    versions = versions or MaterialVersion.objects.filter(material__course=course).select_related("blob", "material__course")
    (requested, manual), running = signal_pages(course), running_pages(course)
    granted = {(e["evidence_id"], e["parse_content_hash"], e["model"], e["prompt_version"], e["schema_version"])
               for grant in TranscriptionGrant.objects.filter(course=course) for e in grant.scope}
    failures = {}
    for task in Task.objects.filter(course=course, kind="visual_transcription").exclude(state__in=ACTIVE).order_by("created_at"):
        for page in task.result.get("pages", []) + task.checkpoint.get("pages", []):
            if page.get("outcome") == "failed":
                failures[page["evidence_id"]] = {"code": page.get("code"), "task_id": str(task.id)}
    model, states = transcription_model(), []
    for version in versions:
        for evidence in current_evidence(version):
            decision = decide(evidence, requested, manual)
            key = (str(evidence.id), evidence.parse_version.content_hash, model, PROMPT_VERSION, SCHEMA_VERSION)
            done = evidence.transcriptions.filter(parse_content_hash=key[1], model=model, prompt_version=PROMPT_VERSION,
                                                  schema_version=SCHEMA_VERSION).order_by("-created_at").first()
            state = {"evidence_id": str(evidence.id), "material_version_id": str(version.id),
                     "physical_page": evidence.physical_page, "route": decision, "transcription_id": None,
                     "task_id": None, "error_code": None}
            if done:
                state.update(status="done", transcription_id=str(done.id), task_id=str(done.task_id) if done.task_id else None)
            elif decision["route"] != "visual":
                state["status"] = "not_needed"
            elif str(evidence.id) in running:
                state.update(status="running", task_id=running[str(evidence.id)])
            elif str(evidence.id) in failures:
                state.update(status="failed", task_id=failures[str(evidence.id)]["task_id"],
                             error_code=failures[str(evidence.id)]["code"])
            elif key in granted:
                state["status"] = "not_started"
            else:
                state["status"] = "awaiting_consent"
            states.append(state)
    return states


def source_of(entry):
    return {"evidence_id": entry["evidence_id"], "material_version_id": entry["material_version_id"],
            "parse_version_id": entry["parse_version_id"], "physical_page": entry["physical_page"],
            "blob_sha256": entry["blob_sha256"], "parse_content_hash": entry["parse_content_hash"],
            "locator": entry["route"]["locator"]}


def transcribe_one(token, course, entry):
    with transaction.atomic():
        locked_task(token)  # A cancelled task dispatches no further page.
    evidence = Evidence.objects.select_related("material_version__blob", "material_version__material__course",
                                               "parse_version").filter(pk=entry["evidence_id"], material_version__material__course=course).first()
    if evidence is None:
        raise DomainError("EVIDENCE_NOT_FOUND", "The page does not belong to this course.")
    image = model_image(evidence)
    if (str(evidence.parse_version_id) != entry["parse_version_id"]
            or evidence.parse_version.content_hash != entry["parse_content_hash"]
            or hashlib.sha256(path_for(evidence.parse_version.document_key).read_bytes()).hexdigest() != entry["parse_content_hash"]
            or hashlib.sha256(path_for(evidence.material_version.blob.storage_key).read_bytes()).hexdigest() != entry["blob_sha256"]
            or hashlib.sha256(image).hexdigest() != entry["image_sha256"]):
        raise DomainError("SOURCE_HASH_MISMATCH", "The page changed after it was queued.")
    if not transcription_policy(course, [entry])[0]:
        raise DomainError("TRANSCRIPTION_CONSENT_REQUIRED", "This page image is not authorised for sending.")
    existing = cached(entry)
    if existing:
        return {"evidence_id": entry["evidence_id"], "outcome": "cached", "transcription_id": str(existing.id)}
    source = source_of(entry)
    call_key = "page:" + entry["evidence_id"]
    spec = ModelCallSpec(stage="visual_transcription", prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION,
                         context_hash=digest(entry), input={"source": source, "extracted_text": evidence.text},
                         max_output_tokens=5000)
    result = run_call(token, call_key, spec, instructions=INSTRUCTIONS, output_type=VisualTranscriptionOutput,
                      api_key=os.environ.get("OPENAI_API_KEY", ""), model=entry["model"], image=image)
    if result.status != "parsed":
        raise DomainError(result.error_code or "VISUAL_TRANSCRIPTION_FAILED", "The model returned no usable transcription.")
    payload = check_transcription(result.payload, source)
    with transaction.atomic():
        task = locked_task(token)  # A late result after cancellation stays only as its call record.
        row, _ = VisualTranscription.objects.get_or_create(
            evidence=evidence, **{k: entry[k] for k in KEY_FIELDS if k != "evidence_id"},
            defaults={"route": entry["route"], "status": payload["status"], "payload": payload, "origin": result.mode,
                      "task": task, "invocation": ModelInvocation.objects.filter(task=task, call_key=call_key).first()})
    return {"evidence_id": entry["evidence_id"], "outcome": "transcribed", "transcription_id": str(row.id),
            "status": payload["status"]}


def run_transcription(token):
    task = Task.objects.select_related("course__owner").get(pk=token.task_id)
    snapshot = task.snapshot
    if task.kind != "visual_transcription" or snapshot.get("policy") != "per_page_grant":
        raise DomainError("TRANSCRIPTION_POLICY_UNAVAILABLE")
    pages = snapshot["pages"]
    checkpoint(token, "Transcribing page images", {"pages_total": len(pages), "concurrency": snapshot["concurrency"]})
    threaded = snapshot["concurrency"] > 1 and len(pages) > 1

    def work(entry):
        try:
            return transcribe_one(token, task.course, entry)
        except DomainError as exc:
            return {"evidence_id": entry["evidence_id"], "outcome": "failed", "code": exc.payload["code"]}
        except Exception as exc:
            return {"evidence_id": entry["evidence_id"], "outcome": "failed", "code": "VISUAL_PAGE_INTERNAL_ERROR",
                    "error_type": type(exc).__name__}
        finally:
            if threaded:
                connection.close()

    if threaded:
        with ThreadPoolExecutor(max_workers=snapshot["concurrency"]) as pool:
            outcomes = list(pool.map(work, pages))
    else:
        outcomes = [work(entry) for entry in pages]
    failed = [o for o in outcomes if o["outcome"] == "failed"]
    summary = {"purpose": "visual_transcription", "pages": outcomes, "failed": len(failed),
               "transcribed": sum(o["outcome"] == "transcribed" for o in outcomes),
               "cached": sum(o["outcome"] == "cached" for o in outcomes),
               "note": "Transcriptions are model candidates. Original evidence remains needs_review."}
    if failed and len(failed) == len(outcomes):
        checkpoint(token, "No page was transcribed", summary)
        raise DomainError(failed[0]["code"], f"All {len(failed)} pages failed. Each page's reason is saved.")
    finish_task(token, summary)
