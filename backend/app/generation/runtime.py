"""Durable stage artifacts and one-shot official calls for generation."""
import os
from django.db import transaction
from app.ai.contracts import ModelCallSpec
from app.ai.invocations import run_call, count_call
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import Task, ModelInvocation
from app.core.tasks import locked_task, checkpoint
from app.courses.context import verify_sources, compact_transcription
from app.materials.models import VisualTranscription
from app.ai.visual import legacy_to_visual
from .models import GenerationArtifact, GenerationSnapshot, GenerationGrant
from .content_schemas import schema_hashes
from .expressions import CHECKER_CONTRACT


def verify_context(task):
    context=task.snapshot
    if digest({k:v for k,v in context.items() if k!="context_hash"}) != context["context_hash"]:
        raise DomainError("GENERATION_CONTEXT_HASH_MISMATCH")
    if context.get("checker_contract") != CHECKER_CONTRACT:
        raise DomainError("GENERATION_CHECKER_CHANGED", "Start a new preflight using the current mathematical checker contract.")
    if schema_hashes() != context["schema_hashes"]:
        raise DomainError("GENERATION_SCHEMA_CHANGED", "Start a new preflight using the current generation schema.")
    if context["mode"]=="live" and not GenerationGrant.objects.filter(course=task.course,context_hash=context["context_hash"]).exists():
        raise DomainError("GENERATION_CONSENT_REQUIRED")
    original=GenerationSnapshot.objects.get(pk=context["input"]["snapshot_id"],course=task.course)
    if digest(original.payload)!=context["input"]["snapshot_hash"]:
        raise DomainError("GENERATION_SNAPSHOT_HASH_MISMATCH")
    return original


def verify_generation_sources(task):
    original=verify_context(task)
    if task.snapshot["mode"]=="fixture":
        return
    ids={s["id"] for s in task.snapshot["input"]["sources"]}
    evidence=[e for e in original.payload["evidence_manifest"]["evidence"] if e["id"] in ids]
    versions={e["material_version_id"] for e in evidence}
    materials=[m for m in original.payload["evidence_manifest"]["materials"] if m["material_version_id"] in versions]
    verify_sources({"input":{"materials":materials,"evidence":evidence}},task.course)
    for e in evidence:
        visual=e.get("visual")
        if not visual:
            continue
        if visual["origin"]=="legacy_page_review":
            record=ModelInvocation.objects.get(pk=visual["record_id"],task__course=task.course)
            actual=compact_transcription(legacy_to_visual(record.result["payload"]),visual["origin"],visual["record_id"])
        else:
            record=VisualTranscription.objects.get(pk=visual["record_id"],evidence_id=e["id"])
            actual=compact_transcription(record.payload,record.origin,str(record.id))
        if digest(actual)!=digest(visual):
            raise DomainError("TRANSCRIPTION_CONTENT_CHANGED")


@transaction.atomic
def save_artifact(token,key,input_hash,payload,call_ids):
    task=locked_task(token)
    previous=GenerationArtifact.objects.filter(task=task,key=key).first()
    if previous:
        if previous.input_hash!=input_hash or previous.payload_hash!=digest(previous.payload):
            raise DomainError("GENERATION_ARTIFACT_CHANGED")
        return previous.payload
    GenerationArtifact.objects.create(task=task,key=key,input_hash=input_hash,payload=payload,
                                      payload_hash=digest(payload),call_ids=call_ids)
    return payload


def stage_output(token,key,stage,input_data,output_type,fixture):
    task=Task.objects.select_related("course__owner").get(pk=token.task_id)
    context=task.snapshot
    input_hash=digest({"context_hash":context["context_hash"],"stage":stage,"input":input_data})
    with transaction.atomic():
        locked_task(token)
        previous=GenerationArtifact.objects.filter(task=task,key=key).first()
        if previous:
            if previous.input_hash!=input_hash or previous.payload_hash!=digest(previous.payload):
                raise DomainError("GENERATION_ARTIFACT_CHANGED")
            return previous.payload
    if context["mode"]=="fixture":
        payload=output_type.model_validate(fixture()).model_dump(mode="json")
        call_ids=[]
    else:
        verify_generation_sources(task)
        # A reserved but unknown call is never automatically replayed, including after lease recovery.
        existing=ModelInvocation.objects.filter(task=task,call_key=key).first()
        if existing and (existing.state!="completed" or existing.result.get("error_code") in
                         ("PROVIDER_TIMEOUT","PROVIDER_CONNECTION_FAILED")):
            raise DomainError("MODEL_OUTCOME_UNKNOWN", "Review the interrupted model call before another paid request.")
        spec=ModelCallSpec(stage=stage,prompt_version=context["pipeline_version"],schema_version="generation-v1",
                           context_hash=input_hash,input=input_data)
        kwargs={"instructions":context["prompts"][stage],"output_type":output_type,
                "api_key":os.environ.get("OPENAI_API_KEY",""),"model":context["model"]}
        counted=count_call(token,"count:"+key,spec,**kwargs)
        result=run_call(token,key,spec,**kwargs,counted_tokens=counted,call_seconds=context["call_seconds"])
        if result.status!="parsed":
            raise DomainError(result.error_code or "GENERATION_MODEL_FAILED",
                              "The model did not return usable content. The call record is retained.")
        payload=output_type.model_validate(result.payload).model_dump(mode="json")
        call_ids=[str(c.id) for c in ModelInvocation.objects.filter(task=task,call_key__in=[key,"count:"+key])]
    return save_artifact(token,key,input_hash,payload,call_ids)
