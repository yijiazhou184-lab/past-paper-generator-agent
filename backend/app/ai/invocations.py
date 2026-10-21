"""Durable call reservation. An ambiguous remote outcome is never automatically replayed."""
from django.db import transaction
from django.utils import timezone
from app.core.budgets import reserve_call
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import ModelInvocation, TaskAttempt
from app.core.tasks import locked_task, checkpoint
from .contracts import ModelCallResult
from .responses import invoke_official, request_body


def run_call(token, call_key, spec, *, instructions, output_type, api_key, model, image=None):
    body = request_body(spec, instructions, output_type, model, image)
    request_hash = digest(body)
    with transaction.atomic():
        task = locked_task(token)
        previous = ModelInvocation.objects.filter(task=task, call_key=call_key).first()
        if previous:
            if previous.request_hash != request_hash:
                raise DomainError("MODEL_CALL_CONTEXT_CHANGED")
            if previous.state != "completed":
                raise DomainError("MODEL_OUTCOME_UNKNOWN", "A previous call was interrupted. Review it before making another paid request.")
            return ModelCallResult.model_validate(previous.result)
        remaining = (task.deadline_at - timezone.now()).total_seconds()
        if remaining < 5:
            raise DomainError("RUN_LIMIT_EXCEEDED")
        reserve_call(token, spec.max_input_tokens, spec.max_output_tokens)
        invocation = ModelInvocation.objects.create(task=task, call_key=call_key, epoch=token.epoch,
            request_hash=request_hash, metadata={"mode": "live", "model": model, "stage": spec.stage,
                "prompt_version": spec.prompt_version, "schema_version": spec.schema_version,
                "context_hash": spec.context_hash, "source": spec.input.get("source"),
                "endpoint": "https://api.openai.com/v1/responses", "store": False,
                "max_input_tokens": spec.max_input_tokens, "max_output_tokens": spec.max_output_tokens,
                "input_admission_method": "utf8_bytes_plus_8192_per_bounded_page_not_billed_usage",
                "timeout_seconds": min(150, remaining), "sdk_max_retries": 0})
    checkpoint(token, f"Calling model: {call_key}", {"call_id": str(invocation.id), "call_key": call_key})
    result = invoke_official(spec, instructions=instructions, output_type=output_type, api_key=api_key,
                             model=model, image=image, timeout_seconds=min(150, remaining))
    # Usage can be retained after cancellation, but the stale attempt cannot publish a task result.
    ModelInvocation.objects.filter(pk=invocation.id).update(
        state="completed", result=result.model_dump(mode="json"), finished_at=timezone.now())
    with transaction.atomic():
        locked_task(token)
        values = [r["usage"] for r in ModelInvocation.objects.filter(task_id=token.task_id, state="completed")
                  .values_list("result", flat=True)]
        usage = {key: sum(v[key] for v in values) if all(v.get(key) is not None for v in values) else None
                 for key in ("input_tokens", "output_tokens", "total_tokens")}
        TaskAttempt.objects.filter(task_id=token.task_id, epoch=token.epoch).update(usage=usage)
    checkpoint(token, f"Model returned: {call_key}", {"call_id": str(invocation.id), "call_key": call_key,
               "status": result.status, "usage": result.usage.model_dump(), "error_code": result.error_code})
    return result
