from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from app.courses.models import Course
from .models import Task, TaskEvent, TaskAttempt, Outbox, ErrorRecord
from .idempotency import intent
from .types import ExecutionToken
from .errors import DomainError

LIMITS = {"parse": 900, "analysis": 900, "planning": 180, "generation": 900, "export": 120,
          "ai_validation": 900, "visual_transcription": 900}


@transaction.atomic
def submit_task(course, kind, snapshot, key, parent=None):
    course = Course.objects.select_for_update().get(pk=course.pk)
    record = intent(course.owner, f"task:{course.id}:{kind}", key, snapshot)
    if record.response:
        return Task.objects.get(pk=record.response["task_id"])
    if kind in ("analysis", "planning", "generation", "ai_validation"):
        busy = Task.objects.filter(course=course, kind__in=["analysis", "planning", "generation", "ai_validation"],
                                   state__in=["queued", "processing"]).first()
        if busy:
            raise DomainError("COURSE_BUSY", "This course already has a running task.", task_id=busy.id)
    task = Task.objects.create(course=course, kind=kind, snapshot=snapshot, parent=parent,
                               deadline_at=timezone.now() + timedelta(seconds=LIMITS[kind]))
    Outbox.objects.create(task=task)
    TaskEvent.objects.create(task=task, stage="Queued")
    record.response = {"task_id": str(task.id)}
    record.save(update_fields=["response"])
    return task


@transaction.atomic
def claim_task(task_id):
    task = Task.objects.select_for_update().get(pk=task_id)
    if task.state != "queued":
        return None
    task.execution_epoch += 1
    task.state = "processing"
    task.started_at = task.started_at or timezone.now()
    task.heartbeat_at = timezone.now()
    task.stage = "Starting"
    task.save()
    TaskAttempt.objects.create(task=task, epoch=task.execution_epoch)
    return ExecutionToken(task.id, task.execution_epoch)


def locked_task(token):
    task = Task.objects.select_for_update().get(pk=token.task_id)
    if task.state != "processing" or task.execution_epoch != token.epoch or task.cancel_requested_at:
        raise DomainError("STALE_EXECUTION")
    if task.deadline_at and timezone.now() >= task.deadline_at:
        raise DomainError("RUN_LIMIT_EXCEEDED", "The task reached its maximum running time.", retryable=True)
    return task


@transaction.atomic
def checkpoint(token, stage, detail=None):
    task = locked_task(token)
    task.stage = stage
    task.heartbeat_at = timezone.now()
    task.checkpoint = detail or task.checkpoint
    task.save(update_fields=["stage", "heartbeat_at", "checkpoint"])
    TaskEvent.objects.create(task=task, epoch=token.epoch, stage=stage, detail=detail or {})


@transaction.atomic
def heartbeat(token):
    task = locked_task(token)
    task.heartbeat_at = timezone.now()
    task.save(update_fields=["heartbeat_at"])


@transaction.atomic
def finish_task(token, result):
    task = locked_task(token)
    task.state, task.stage, task.result = "succeeded", "Complete", result
    task.finished_at = timezone.now()
    task.save()
    TaskAttempt.objects.filter(task=task, epoch=token.epoch).update(outcome="succeeded", finished_at=task.finished_at)
    TaskEvent.objects.create(task=task, epoch=token.epoch, stage="Complete")


@transaction.atomic
def fail_task(token, code, message, retryable=True):
    task = Task.objects.select_for_update().get(pk=token.task_id)
    if task.state != "processing" or task.execution_epoch != token.epoch:
        return
    error = ErrorRecord.objects.create(task=task, code=code, safe_message=message, stage=task.stage, retryable=retryable)
    task.state = "failed"
    task.stage = "Failed"
    task.finished_at = timezone.now()
    task.error = {"code": code, "message": message, "retryable": retryable, "diagnostic_id": str(error.id)}
    task.save()
    TaskAttempt.objects.filter(task=task, epoch=token.epoch).update(outcome="failed", finished_at=task.finished_at)
    TaskEvent.objects.create(task=task, epoch=token.epoch, stage="Failed", detail=task.error)


@transaction.atomic
def cancel_task(owner, task_id):
    task = get_object_or_404(Task.objects.select_for_update(), pk=task_id, course__owner=owner)
    if task.state in ("queued", "processing"):
        task.state = "cancelled"
        task.cancel_requested_at = task.finished_at = timezone.now()
        task.execution_epoch += 1
        task.stage = "Cancelled"
        task.save()
        TaskAttempt.objects.filter(task=task, finished_at=None).update(outcome="cancelled", finished_at=task.finished_at)
        TaskEvent.objects.create(task=task, epoch=task.execution_epoch, stage="Cancelled")
    return task


@transaction.atomic
def recover_stale_tasks():
    cutoff = timezone.now() - timedelta(seconds=90)
    for task in Task.objects.select_for_update(skip_locked=True).filter(state="processing", heartbeat_at__lt=cutoff):
        task.execution_epoch += 1
        task.state = "queued"
        task.stage = "Recovering after worker interruption"
        task.save()
        TaskAttempt.objects.filter(task=task, finished_at=None).update(outcome="interrupted", finished_at=timezone.now())
        Outbox.objects.filter(task=task).update(sent_at=None)
        TaskEvent.objects.create(task=task, epoch=task.execution_epoch, stage=task.stage)
