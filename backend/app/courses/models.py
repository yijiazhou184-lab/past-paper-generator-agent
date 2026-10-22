from django.conf import settings
from django.db import models
from app.core.models import UUIDModel


class Course(UUIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    code = models.CharField(max_length=40, default="MSIN0180")
    scope_statement = models.TextField(default="All lecture content")
    scope_provenance = models.CharField(max_length=32, default="user_statement")


class UserStatement(UUIDModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="statements")
    text = models.TextField()
    kind = models.CharField(max_length=40)
    source = models.CharField(max_length=200)
    clarification_id = models.CharField(max_length=120, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class AnalysisGrant(UUIDModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    context_hash = models.CharField(max_length=64)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.JSONField()
    source = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "context_hash"], name="unique_analysis_grant")]


class CourseMachineBase(UUIDModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    task = models.OneToOneField("core.Task", on_delete=models.PROTECT)
    payload = models.JSONField()
    context = models.JSONField()
    mode = models.CharField(max_length=16)


class CourseDraft(UUIDModel):
    course = models.OneToOneField(Course, on_delete=models.PROTECT, related_name="draft")
    revision = models.PositiveIntegerField(default=1)
    machine_base = models.ForeignKey(CourseMachineBase, on_delete=models.PROTECT)
    payload = models.JSONField()
    manual_patches = models.JSONField(default=list)
    merge_warnings = models.JSONField(default=list)
    clarification_answers = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class CourseVersion(UUIDModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="confirmed_versions")
    number = models.PositiveIntegerField()
    draft = models.ForeignKey(CourseDraft, on_delete=models.PROTECT)
    draft_revision = models.PositiveIntegerField()
    payload_hash = models.CharField(max_length=64)
    frozen_payload = models.JSONField()
    evidence_manifest = models.JSONField()
    statements = models.JSONField()
    manual_patches = models.JSONField()
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "number"], name="unique_course_version"),
                       models.UniqueConstraint(fields=["draft", "draft_revision"], name="unique_confirmed_revision")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Confirmed course versions are immutable.")
        return super().save(*args, **kwargs)
