from .config_compat import course_projection, mixed_topic_inputs, selected_topics
import copy
import os
from pathlib import Path
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from app.ai.contracts import ModelCallSpec
from app.ai.invocations import run_call
from app.ai.responses import request_body
from app.core.errors import DomainError
from app.core.idempotency import digest, intent
from app.core.models import Task, TaskAttempt, TaskEvent
from app.core.tasks import submit_task, locked_task, checkpoint, finish_task
from app.courses.schemas import TEACHING_ROLES
from app.courses.exam_template import require_current_exam_template
from .models import GenerationDraft, Blueprint, PlanningGrant
from .schemas import PlanningOutput, SCHEMA_VERSION, validate_config, validate_blueprint, materialize_planning_blueprint
from .snapshots import owned_course, require_revision, structure_diff, exam_template_changes


PLANNING_SCHEMA_VERSION = "planning-v3-part-coverage"
PROMPT_VERSION = "r1-planning-3-part-coverage"


def build_context(draft):
    version = draft.course_version
    course = course_projection(version)
    evidence = version.evidence_manifest["evidence"]
    statements = version.statements
    validate_config(draft.config, course, evidence)
    mock = draft.config["mode"] == "mock_exam"
    mixed = draft.config["mode"] == "mixed_topic_practice"
    if mock:
        require_current_exam_template(version)
    else:
        course.pop("exam_template", None)
    analysis_mode = version.evidence_manifest.get("analysis_mode")
    if mixed or mock:
        course, evidence, statements = mixed_topic_inputs(draft.config, course, version.evidence_manifest, statements)
        snapshots = version.evidence_manifest.get("topic_snapshots", {})
        modes = {snapshots.get(tid, {}).get("analysis_mode", analysis_mode) for tid in draft.config["selected_topic_ids"]}
        if len(modes) != 1 or "mixed" in modes:
            raise DomainError("MIXED_TOPIC_ANALYSIS_MODE", "Choose topics with matching analysis provenance.")
        analysis_mode = modes.pop()
    if digest(version.frozen_payload) != version.payload_hash:
        raise DomainError("COURSE_VERSION_HASH_MISMATCH")
    prompt = (Path(__file__).resolve().parents[1] / "ai/prompts/blueprint.md").read_text(encoding="utf-8")
    if mixed:
        prompt += (" For mixed-topic practice, distribute the selected topics and their knowledge across the paper. "
                   "A question may connect topics. Every permitted answer path must cover the chosen topics and knowledge. "
                   "If the requested size cannot support meaningful coverage, return needs_info and identify the conflict.")
    if mock:
        prompt += (" The following mock-exam rules take precedence over the chapter-practice defaults above. "
                   "For a mock exam, use only the selected knowledge; you may leave some selected knowledge untested. "
                   "Put each requested response type somewhere on the printed paper. Follow the confirmed exam template's "
                   "section order, titles, number of questions, marks per question, selection rules and duration when its "
                   "question count matches the requested count. If the requested count changes, propose a revised structure "
                   "and describe the effects on marks, selection and timing. Do not claim official calibration.")
    snapshot = {"prompt_version": PROMPT_VERSION, "schema_version": PLANNING_SCHEMA_VERSION, "prompt": prompt,
        "blueprint_schema_version": SCHEMA_VERSION, "coverage_policy": "part-knowledge-union-v1",
        "schema_hash": digest(PlanningOutput.model_json_schema()), "limits_version": "r1-limits-proposal-1",
        "adapter_version": "official-responses-v1", "model_settings": {"reasoning_effort": "medium", "max_input_tokens": 60000,
            "max_output_tokens": 12000, "sdk_max_retries": 0, "task_deadline_seconds": 180, "call_timeout_seconds": 150},
        "model": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"), "endpoint": "https://api.openai.com/v1/responses", "store": False,
        "mode": "fixture" if analysis_mode == "fixture" else "live",
        "input": {"course_version_id": str(version.id), "course_payload_hash": version.payload_hash,
            "course": course, "config": copy.deepcopy(draft.config),
            "selected_topics": selected_topics(draft.config,version),
            "statements": copy.deepcopy(statements),
            "evidence": [{k: e[k] for k in ("id", "material_version_id", "physical_page", "material_code", "roles", "fidelity_status") if k in e}
                         for e in evidence],
            "capabilities": {"response_types": ["calculation", "explanation_proof", "applied_optimisation"],
                "asset_types": ["function_graph", "data_table"], "software_answers": False, "question_count": [2, 4]}}}
    snapshot["context_hash"] = digest(snapshot)
    # Local routing metadata does not change the exact authorized model input.
    snapshot.update(draft_id=str(draft.id), config_revision=draft.revision, config_hash=draft.config_hash)
    return snapshot


def make_spec(snapshot):
    return ModelCallSpec(stage="blueprint", prompt_version=snapshot["prompt_version"], schema_version=snapshot["schema_version"],
        context_hash=snapshot["context_hash"], input=snapshot["input"])


def inspect_scope(snapshot):
    return {"context_hash": snapshot["context_hash"], "model": snapshot["model"], "mode": snapshot["mode"],
        "endpoint": snapshot["endpoint"], "store": False, "course_version_id": snapshot["input"]["course_version_id"],
        "config_revision": snapshot["config_revision"], "evidence": snapshot["input"]["evidence"],
        "input": snapshot["input"], "new_page_images": 0, "raw_page_texts": 0,
        "purpose": "Practice blueprint planning only", "max_calls": 2, "task_seconds": 180, "call_seconds": 150}


@transaction.atomic
def submit_plan(owner, course_id, expected_revision, context_hash, key, authorize=False):
    course = owned_course(owner, course_id)
    record = intent(owner, f"plan-submit:{course.id}", key, {"revision": expected_revision, "context_hash": context_hash, "authorize": authorize})
    if record.response:
        return Task.objects.get(pk=record.response["task_id"], course=course)
    draft = get_object_or_404(GenerationDraft.objects.select_related("course_version"), course=course)
    require_revision(draft, expected_revision)
    snapshot = build_context(draft)
    if snapshot["context_hash"] != context_hash:
        raise DomainError("PLANNING_INPUT_CHANGED", "Review the updated sending scope before planning.")
    if snapshot["mode"] == "live":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise DomainError("API_KEY_MISSING", "Set OPENAI_API_KEY in .env.local before live planning.")
        try:
            request_body(make_spec(snapshot), snapshot["prompt"], PlanningOutput, snapshot["model"])
        except ValueError:
            raise DomainError("PLANNING_INPUT_BUDGET_EXCEEDED", "The frozen input exceeds the call budget. No data was sent.") from None
        if authorize:
            PlanningGrant.objects.get_or_create(course=course, context_hash=context_hash, defaults={
                "scope": inspect_scope(snapshot), "granted_by": owner, "source": "Explicit Generate planning consent"})
        if not PlanningGrant.objects.filter(course=course, context_hash=context_hash).exists():
            raise DomainError("PLANNING_CONSENT_REQUIRED", "Authorise this planning input. Analysis consent does not cover planning.", status=403)
    previous = draft.latest_task
    task = submit_task(course, "planning", snapshot, key, parent=previous)
    draft.latest_task = task
    draft.confirmation = None
    draft.save()
    record.response = {"task_id": str(task.id)}
    record.save(update_fields=["response"])
    return task


@transaction.atomic
def publish_plan(token, payload):
    task = locked_task(token)
    course = owned_course(task.course.owner, task.course_id)
    snapshot = task.snapshot
    draft = get_object_or_404(GenerationDraft.objects.select_related("blueprint"), pk=snapshot["draft_id"], course=course)
    frozen = snapshot["input"]
    payload = validate_blueprint(frozen["config"], payload, frozen["course"], frozen["evidence"],
                                 schema_version=snapshot.get("blueprint_schema_version", snapshot.get("schema_version")))
    existing = Blueprint.objects.filter(task=task).first()
    if existing:
        raise DomainError("BLUEPRINT_ALREADY_PUBLISHED")
    previous = draft.blueprint
    origin = Blueprint.objects.filter(family=previous.family, task__isnull=False).select_related("task").first() if previous else None
    old_config = origin.task.snapshot["input"]["config"] if origin else None
    differences = structure_diff(previous.payload if previous else None, payload, old_config, frozen["config"])
    if frozen["config"]["mode"] == "mock_exam":
        template = frozen["course"]["exam_template"]
        changes = exam_template_changes(template, payload)
        template_count = sum(len(section["question_marks"]) for section in template["sections"])
        if changes and template_count == frozen["config"]["main_question_count"]:
            raise DomainError("EXAM_TEMPLATE_STRUCTURE_MISMATCH", " ".join(changes), status=400)
        differences = [*(changes or ["Uses the confirmed exam template."]), *differences]
    blueprint = Blueprint.objects.create(draft=draft, course_version_id=frozen["course_version_id"],
        config_revision=snapshot["config_revision"], config_hash=snapshot["config_hash"], task=task,
        payload=payload, payload_hash=digest(payload), context_hash=snapshot["context_hash"], mode=snapshot["mode"],
        differences=differences)
    current = (draft.revision == snapshot["config_revision"] and draft.config_hash == snapshot["config_hash"]
               and draft.latest_task_id == task.id and str(draft.course_version_id) == frozen["course_version_id"])
    if current:
        draft.blueprint, draft.confirmation = blueprint, None
        draft.save()
    finish_task(token, {"blueprint_id": str(blueprint.id), "revision": blueprint.revision, "config_revision": snapshot["config_revision"],
        "config_hash": snapshot["config_hash"], "mode": snapshot["mode"], "superseded": not current,
        "generate_url": f"/courses/{course.id}/generate", "message": "Review the structure before confirming." if current else "Configuration changed. This saved result did not replace the current structure."})
    return blueprint


@transaction.atomic
def needs_information(token, status, explanation):
    task = locked_task(token)
    task.state, task.stage = "needs_info", "Planning needs information"
    task.result = {"status": status, "explanation": explanation, "mode": task.snapshot["mode"],
                   "generate_url": f"/courses/{task.course_id}/generate"}
    task.finished_at = timezone.now()
    task.save()
    TaskAttempt.objects.filter(task=task, epoch=token.epoch).update(outcome="needs_info", finished_at=task.finished_at)
    TaskEvent.objects.create(task=task, epoch=token.epoch, stage=task.stage, detail={"status": status})


def run_planning(token):
    task = Task.objects.select_related("course").get(pk=token.task_id)
    snapshot = task.snapshot
    if digest(PlanningOutput.model_json_schema()) != snapshot["schema_hash"]:
        raise DomainError("PLANNING_SCHEMA_CHANGED", "Start a new plan using the current schema; the original task is preserved.")
    checkpoint(token, "Checking frozen planning inputs")
    # Skip obsolete requests before spending tokens. In-flight late results are retained but never attached.
    draft = GenerationDraft.objects.get(pk=snapshot["draft_id"], course=task.course)
    if draft.revision != snapshot["config_revision"] or draft.latest_task_id != task.id:
        finish_task(token, {"superseded": True, "mode": snapshot["mode"], "generate_url": f"/courses/{task.course_id}/generate",
                            "message": "Configuration changed before planning started. No model call was made."})
        return
    if snapshot["mode"] == "fixture":
        from .fixtures import fixture_blueprint, apply_fixture_exam_template
        config, course = snapshot["input"]["config"], snapshot["input"]["course"]
        payload = fixture_blueprint(config, course)
        if config["mode"] == "mock_exam":
            payload = apply_fixture_exam_template(payload, course["exam_template"])
        checkpoint(token, "Building synthetic fixture structure (no model call)")
    else:
        if not PlanningGrant.objects.filter(course=task.course, context_hash=snapshot["context_hash"]).exists():
            raise DomainError("PLANNING_CONSENT_REQUIRED")
        result = run_call(token, "practice-blueprint", make_spec(snapshot), instructions=snapshot["prompt"], output_type=PlanningOutput,
                          api_key=os.environ.get("OPENAI_API_KEY", ""), model=snapshot["model"])
        if result.status != "parsed":
            raise DomainError(result.error_code or "BLUEPRINT_MODEL_FAILED", "The model did not return a usable blueprint. Inspect the saved call record.")
        output = PlanningOutput.model_validate(result.payload)
        if output.status != "complete" or output.blueprint is None:
            needs_information(token, output.status, output.explanation)
            return
        payload = materialize_planning_blueprint(output.blueprint.model_dump(mode="json"))
        frozen = snapshot["input"]
        teaching_sources = {e["id"] for e in frozen["evidence"] if set(e.get("roles", [])) & TEACHING_ROLES}
        evidence_by_target = {
            node["id"]: [eid for eid in node["evidence_ids"] if eid in teaching_sources]
            for node in frozen["course"]["knowledge_nodes"]
        }
        for question in payload["questions"]:
            cited = set(question["evidence_ids"])
            for target in question["knowledge_ids"]:
                eligible = evidence_by_target.get(target, [])
                if eligible and not cited.intersection(eligible):
                    source_id = eligible[0]
                    question["evidence_ids"].append(source_id)
                    cited.add(source_id)
    checkpoint(token, "Checking marks, coverage, sources and answer selection")
    publish_plan(token, payload)
