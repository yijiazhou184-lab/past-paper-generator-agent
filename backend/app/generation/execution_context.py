"""Freeze and authorise the exact inputs for paired generation and its checks."""
import copy
import os
from pathlib import Path
from django.db import transaction
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import digest, intent
from app.core.models import Task
from app.core.tasks import submit_task
from .models import GenerationDraft, GenerationSnapshot, GenerationGrant
from .snapshots import owned_course, require_confirmation, freeze_generation
from .expressions import CHECKER_CONTRACT
from .source_policy import SOURCE_POLICY
from .review_policy import REVIEW_POLICY, PIPELINE_VERSION
from .originality_policy import POLICY as ORIGINALITY_POLICY

PROMPT_DIR = Path(__file__).resolve().parents[1] / "ai/prompts"
PROMPTS = ("question_pairs", "blind_solver", "semantic_review", "repair")
COMPARISON_ROLES = {"past_paper", "practice", "seminar", "revision", "additional_questions", "assessment"}


def source_content(e):
    visual = e.get("visual")
    if visual:
        return {"kind": "visual_transcription", "content": copy.deepcopy(visual)}
    if e.get("visual_status") == "visual_pending":
        raise DomainError("GENERATION_EVIDENCE_PENDING", "A selected mathematical page still needs transcription.")
    return {"kind": "extracted_text", "content": e.get("text", "")}


def build_generation_context(snapshot):
    frozen = snapshot.payload
    if digest(frozen) != snapshot.payload_hash or digest(frozen["course"]) != frozen["course_payload_hash"] or digest(frozen["blueprint"]) != frozen["blueprint_hash"]:
        raise DomainError("GENERATION_SNAPSHOT_HASH_MISMATCH")
    evidence = {e["id"]: e for e in frozen["evidence_manifest"]["evidence"]}
    questions = []
    required = set()
    for q in frozen["blueprint"]["questions"]:
        ids = q["evidence_ids"]
        if not set(ids).issubset(evidence):
            raise DomainError("EVIDENCE_REFERENCE_INVALID")
        required.update(ids)
        questions.append({"blueprint": copy.deepcopy(q),
            "knowledge": [copy.deepcopy(n) for n in frozen["course"]["knowledge_nodes"] if n["id"] in q["knowledge_ids"]],
            "methods": copy.deepcopy(frozen["course"]["method_rules"]),
            "issues": copy.deepcopy(frozen["course"]["issues"])})
    comparison_ids = sorted(e["id"] for e in evidence.values() if set(e.get("roles", [])) & COMPARISON_ROLES)
    required.update(comparison_ids)
    sources = []
    for eid in sorted(required):
        e = evidence[eid]
        # Missing fixture text is deliberately synthetic; live missing content is never invented.
        content = source_content(e)
        if snapshot.mode == "live" and not content["content"]:
            raise DomainError("GENERATION_EVIDENCE_EMPTY", "A selected source has no usable frozen content.")
        sources.append({**{k: copy.deepcopy(e[k]) for k in (
            "id", "material_version_id", "parse_version_id", "physical_page", "material_code",
            "parse_content_hash", "blob_sha256", "roles", "fidelity_status") if k in e},
            **content, "content_hash": digest(content)})
    data = {"snapshot_id": str(snapshot.id), "snapshot_hash": snapshot.payload_hash,
        "course_version_id": frozen["course_version_id"], "config": frozen["config"], "blueprint": frozen["blueprint"],
        "course": frozen["course"], "statements": frozen["statements"], "questions": questions,
        "sources": sources,
        "background_source_catalog": [{k: copy.deepcopy(e[k]) for k in
            ("id","material_code","material_version_id","physical_page") if k in e}
            for e in evidence.values()],
        "comparison_source_ids": comparison_ids, "history_content_ids": frozen["history_content_ids"],
        "history_cutoff": frozen["history_cutoff"], "history_status": frozen["history_status"]}
    context = {"pipeline_version": PIPELINE_VERSION, "review_policy": copy.deepcopy(REVIEW_POLICY), "originality_policy": copy.deepcopy(ORIGINALITY_POLICY), "source_policy": copy.deepcopy(SOURCE_POLICY), "mode": snapshot.mode, "input": data,
        "checker_contract": copy.deepcopy(CHECKER_CONTRACT),
        "model": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"), "endpoint": "https://api.openai.com/v1/responses",
        "store": False, "max_calls": frozen["generation_limits"]["calls"], "task_seconds": 600,
        "call_seconds": 240, "max_parallel_calls": 2, "max_input_tokens": 60000, "max_output_tokens": 12000,
        "repair_rounds": 1, "new_page_images": 0, "sdk_max_retries": 0,
        "count_endpoint": "https://api.openai.com/v1/responses/input_tokens",
        "prompts": {name: (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8") for name in PROMPTS}}
    from .content_schemas import schema_hashes
    context["schema_hashes"] = schema_hashes()
    context["context_hash"] = digest(context)
    return context


def inspect_generation_scope(context):
    return {**{k: copy.deepcopy(v) for k, v in context.items() if k != "prompts"},
        "prompt_hashes": {k: digest(v) for k, v in context["prompts"].items()},
        "purpose": "Paired questions and answers, blind solving, semantic and duplicate checks, and at most one repair round",
        "derived_inputs": ["Previously generated question summaries", "Candidate questions and answers",
                           "Blind solutions", "Local check results", "Retrieved excerpts from the listed sources"],
        "count_requests": "One official count before each new model request. Oversized required reviews may add bounded split counts (at most seven tree nodes for four questions, then one paper check). Optional checks can be skipped; no new page images."}


def require_idle(course):
    busy = Task.objects.filter(course=course, kind__in=["analysis", "planning", "generation", "ai_validation"],
                               state__in=["queued", "processing"]).first()
    if busy:
        raise DomainError("COURSE_BUSY", "This course already has a running task.", task_id=busy.id)


@transaction.atomic
def prepare_generation(owner, course_id, confirmation_id, config_revision, config_hash, key):
    course = owned_course(owner, course_id)
    require_idle(course)
    snapshot = freeze_generation(owner, course_id, confirmation_id, config_revision, config_hash, key)
    # Even a repeated freeze key must not bypass current binding checks.
    draft = get_object_or_404(GenerationDraft.objects.select_related("blueprint", "confirmation"), course=course)
    require_confirmation(draft, confirmation_id, config_revision, config_hash)
    return build_generation_context(snapshot)


@transaction.atomic
def submit_generation(owner, course_id, confirmation_id, config_revision, config_hash, context_hash, key, authorize=False):
    course = owned_course(owner, course_id)
    record = intent(owner, f"generation-submit:{course.id}", key, {
        "confirmation_id": str(confirmation_id), "revision": config_revision, "config_hash": config_hash,
        "context_hash": context_hash, "authorize": authorize})
    if record.response:
        return Task.objects.get(pk=record.response["task_id"], course=course)
    context = prepare_generation(owner, course_id, confirmation_id, config_revision, config_hash, f"submit:{key}")
    if context["context_hash"] != context_hash:
        raise DomainError("GENERATION_INPUT_CHANGED", "Review the updated generation inputs before submitting.")
    if context["mode"] == "live":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise DomainError("API_KEY_MISSING", "Set OPENAI_API_KEY in .env.local.")
        if authorize:
            GenerationGrant.objects.get_or_create(course=course, context_hash=context_hash, defaults={
                "scope": inspect_generation_scope(context), "granted_by": owner, "source": "Explicit generation preflight consent"})
        if not GenerationGrant.objects.filter(course=course, context_hash=context_hash).exists():
            raise DomainError("GENERATION_CONSENT_REQUIRED", "Generation needs its own exact-input authorisation.", status=403)
    draft = GenerationDraft.objects.get(course=course)
    previous = Task.objects.filter(course=course, kind="generation").order_by("-created_at").first()
    task = submit_task(course, "generation", context, key, parent=previous)
    draft.latest_task = task
    draft.save(update_fields=["latest_task", "updated_at"])
    record.response = {"task_id": str(task.id)}
    record.save(update_fields=["response"])
    return task
