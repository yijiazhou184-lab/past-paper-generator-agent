import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Task(UUIDModel):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    kind = models.CharField(max_length=32)
    state = models.CharField(max_length=16, default="queued")
    stage = models.CharField(max_length=100, default="Queued")
    snapshot = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    checkpoint = models.JSONField(default=dict)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    execution_epoch = models.PositiveIntegerField(default=0)
    heartbeat_at = models.DateTimeField(null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    deadline_at = models.DateTimeField(null=True)
    cancel_requested_at = models.DateTimeField(null=True)
    call_count = models.PositiveIntegerField(default=0)
    error = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course"],
                condition=Q(kind__in=["analysis", "planning", "generation", "ai_validation"], state__in=["queued", "processing"]),
                name="one_active_course_ai_task",
            ),
        ]


class TaskEvent(UUIDModel):
    task = models.ForeignKey(Task, related_name="events", on_delete=models.CASCADE)
    epoch = models.PositiveIntegerField(default=0)
    stage = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)


class TaskAttempt(UUIDModel):
    task = models.ForeignKey(Task, related_name="attempts", on_delete=models.CASCADE)
    epoch = models.PositiveIntegerField()
    finished_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=30, default="running")
    usage = models.JSONField(null=True)


class IdempotencyRecord(UUIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation = models.CharField(max_length=100)
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    response = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "operation", "key"], name="unique_intent_key")]


class Outbox(UUIDModel):
    task = models.OneToOneField(Task, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(null=True)


class ErrorRecord(UUIDModel):
    task = models.ForeignKey(Task, null=True, on_delete=models.SET_NULL)
    code = models.CharField(max_length=80)
    safe_message = models.TextField()
    stage = models.CharField(max_length=100, blank=True)
    retryable = models.BooleanField(default=False)


class ModelInvocation(UUIDModel):
    task = models.ForeignKey(Task, related_name="model_calls", on_delete=models.PROTECT)
    call_key = models.CharField(max_length=100)
    epoch = models.PositiveIntegerField()
    request_hash = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict)
    state = models.CharField(max_length=30, default="started")
    result = models.JSONField(default=dict)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "call_key"], name="unique_task_model_call")]
