import uuid
from django.conf import settings
from django.db import models
from app.core.models import UUIDModel


class Immutable(UUIDModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Frozen generation records are immutable.")
        return super().save(*args, **kwargs)


class GenerationDraft(UUIDModel):
    course = models.OneToOneField("courses.Course", on_delete=models.PROTECT)
    course_version = models.ForeignKey("courses.CourseVersion", on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)
    config = models.JSONField()
    config_hash = models.CharField(max_length=64)
    blueprint = models.ForeignKey("Blueprint", null=True, on_delete=models.PROTECT, related_name="current_drafts")
    confirmation = models.ForeignKey("StructureConfirmation", null=True, on_delete=models.PROTECT, related_name="current_drafts")
    latest_task = models.ForeignKey("core.Task", null=True, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class Blueprint(Immutable):
    draft = models.ForeignKey(GenerationDraft, on_delete=models.PROTECT, related_name="blueprints")
    course_version = models.ForeignKey("courses.CourseVersion", on_delete=models.PROTECT)
    config_revision = models.PositiveIntegerField()
    config_hash = models.CharField(max_length=64)
    family = models.UUIDField(default=uuid.uuid4)
    revision = models.PositiveIntegerField(default=1)
    task = models.OneToOneField("core.Task", null=True, on_delete=models.PROTECT)
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    differences = models.JSONField(default=list)
    mode = models.CharField(max_length=16)
    context_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["family", "revision"], name="unique_blueprint_revision")]


class StructureConfirmation(Immutable):
    blueprint = models.ForeignKey(Blueprint, on_delete=models.PROTECT)
    draft = models.ForeignKey(GenerationDraft, on_delete=models.PROTECT)
    config_revision = models.PositiveIntegerField()
    config_hash = models.CharField(max_length=64)
    blueprint_hash = models.CharField(max_length=64)
    course_version = models.ForeignKey("courses.CourseVersion", on_delete=models.PROTECT)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class GenerationSnapshot(Immutable):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    confirmation = models.OneToOneField(StructureConfirmation, on_delete=models.PROTECT)
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    mode = models.CharField(max_length=16)


class PlanningGrant(Immutable):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    context_hash = models.CharField(max_length=64)
    scope = models.JSONField()
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "context_hash"], name="unique_planning_grant")]
