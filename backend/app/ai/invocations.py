"""Durable call reservation. An ambiguous remote outcome is never automatically replayed."""
from django.db import transaction
from django.utils import timezone
from app.core.budgets import reserve_call
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import ModelInvocation, TaskAttempt
from app.core.tasks import locked_task, checkpoint
from .contracts import ModelCallResult
from .responses import invoke_official, request_body, count_official

TOKEN_LIMIT = 60000


def run_call(token, call_key, spec, *, instructions, output_type, api_key, model, image=None, counted_tokens=None,
             call_seconds=150):
    """counted_tokens: an official input-token count of this exact request, replacing the byte bound.
    call_seconds: this stage's per-call limit (150 unless a stage sets otherwise)."""
    body = request_body(spec, instructions, output_type, model, image, byte_admission=counted_tokens is None)
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
        reserve_call(token, counted_tokens or spec.max_input_tokens, spec.max_output_tokens)
        invocation = ModelInvocation.objects.create(task=task, call_key=call_key, epoch=token.epoch,
            request_hash=request_hash, metadata={"mode": "live", "model": model, "stage": spec.stage,
                "prompt_version": spec.prompt_version, "schema_version": spec.schema_version,
                "context_hash": spec.context_hash, "source": spec.input.get("source"),
                "endpoint": "https://api.openai.com/v1/responses", "store": False,
                "max_input_tokens": spec.max_input_tokens, "max_output_tokens": spec.max_output_tokens,
                "input_admission_method": ("official_input_tokens_count" if counted_tokens is not None else
                                           "utf8_bytes_plus_8192_per_bounded_page_not_billed_usage"),
                "counted_input_tokens": counted_tokens,
                "timeout_seconds": min(call_seconds, remaining), "sdk_max_retries": 0})
    checkpoint(token, f"Calling model: {call_key}", {"call_id": str(invocation.id), "call_key": call_key})
    result = invoke_official(spec, instructions=instructions, output_type=output_type, api_key=api_key,
                             model=model, image=image, timeout_seconds=min(call_seconds, remaining),
                             byte_admission=counted_tokens is None)
    # Usage can be retained after cancellation, but the stale attempt cannot publish a task result.
    ModelInvocation.objects.filter(pk=invocation.id).update(
        state="completed", result=result.model_dump(mode="json"), finished_at=timezone.now())
    with transaction.atomic():
        locked_task(token)
        # Input-token counts report request size, not billed generation usage.
        # Filter in Python: SQL JSON-key exclusion also drops records whose purpose key is absent.
        values = [r.get("usage",{}) for metadata,r in ModelInvocation.objects.filter(task_id=token.task_id, state="completed")
                  .values_list("metadata","result") if metadata.get("purpose")!="input_token_count"]
        usage = {key: sum(v[key] for v in values) if all(v.get(key) is not None for v in values) else None
                 for key in ("input_tokens", "output_tokens", "total_tokens")}
        TaskAttempt.objects.filter(task_id=token.task_id, epoch=token.epoch).update(usage=usage)
    checkpoint(token, f"Model returned: {call_key}", {"call_id": str(invocation.id), "call_key": call_key,
               "status": result.status, "usage": result.usage.model_dump(), "error_code": result.error_code})
    return result


def count_call(token, call_key, spec, *, instructions, output_type, api_key, model, timeout_seconds=60):
    """Count the exact request's input tokens with the official endpoint before any generation request.

    The count generates nothing, so an interrupted count may be repeated. The generation call must be
    started with the returned count; above TOKEN_LIMIT no generation request is made.
    """
    body = request_body(spec, instructions, output_type, model, byte_admission=False)
    limit = min(TOKEN_LIMIT, spec.max_input_tokens)
    request_hash = digest(body)
    with transaction.atomic():
        task = locked_task(token)
        remaining = max(0, (task.deadline_at - timezone.now()).total_seconds() - 5)
        if remaining < 1:
            raise DomainError("RUN_LIMIT_EXCEEDED")
        timeout_seconds = min(timeout_seconds, remaining)
        previous = ModelInvocation.objects.filter(task=task, call_key=call_key).first()
        if previous and previous.request_hash != request_hash:
            raise DomainError("MODEL_CALL_CONTEXT_CHANGED")
        if previous and previous.state == "completed":
            result = ModelCallResult.model_validate(previous.result)
        else:
            invocation = previous or ModelInvocation.objects.create(task=task, call_key=call_key, epoch=token.epoch,
                request_hash=request_hash, metadata={"mode": "live", "model": model, "stage": spec.stage,
                    "purpose": "input_token_count", "prompt_version": spec.prompt_version,
                    "schema_version": spec.schema_version, "context_hash": spec.context_hash,
                    "endpoint": "https://api.openai.com/v1/responses/input_tokens", "store": None,
                    "token_limit": limit, "timeout_seconds": timeout_seconds, "sdk_max_retries": 0})
            result = None
    if result is None:
        checkpoint(token, f"Counting input tokens: {call_key}", {"call_id": str(invocation.id)})
        result = count_official(body, api_key=api_key, timeout_seconds=timeout_seconds)
        ModelInvocation.objects.filter(pk=invocation.id).update(
            state="completed", result=result.model_dump(mode="json"), finished_at=timezone.now())
    if result.status != "parsed":
        raise DomainError(result.error_code or "TOKEN_COUNT_FAILED",
                          "The official token count did not complete. No analysis request was sent.")
    counted = result.payload["input_tokens"]
    checkpoint(token, f"Input tokens counted: {call_key}", {"input_tokens": counted, "limit": limit})
    if counted > limit:
        raise DomainError("TOKEN_BUDGET_EXCEEDED",
                          f"The input is {counted} tokens, above the {limit} limit. No analysis request was sent.",
                          retryable=False)
    return counted
