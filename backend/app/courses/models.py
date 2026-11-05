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
    decision = models.JSONField(default=dict)
    topic_ids = models.JSONField(default=list)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="statements")
    text = models.TextField()
    kind = models.CharField(max_length=40)
    source = models.CharField(max_length=200)
    clarification_id = models.CharField(max_length=120, blank=True)
    # The question as it was asked; a later analysis may re-word or re-number it.
    question = models.TextField(blank=True, default="")
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
    topic_state = models.JSONField(default=dict)
    course = models.OneToOneField(Course, on_delete=models.PROTECT, related_name="draft")
    revision = models.PositiveIntegerField(default=1)
    machine_base = models.ForeignKey(CourseMachineBase, on_delete=models.PROTECT)
    payload = models.JSONField()
    manual_patches = models.JSONField(default=list)
    merge_warnings = models.JSONField(default=list)
    clarification_answers = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class CourseVersion(UUIDModel):
    confirmation_fingerprint = models.CharField(max_length=64, default="")
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
                       models.UniqueConstraint(fields=["draft", "draft_revision", "confirmation_fingerprint"], name="unique_scoped_confirmed_revision")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Confirmed course versions are immutable.")
        return super().save(*args, **kwargs)


class Topic(UUIDModel):
    course = models.ForeignKey(Course, related_name="topics", on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40, blank=True)
    order = models.PositiveIntegerField(default=0)
    revision = models.PositiveIntegerField(default=1)
    archived = models.BooleanField(default=False)
    provenance = models.CharField(max_length=40, default="user_declared")
    source_refs = models.JSONField(default=list)


class LegacyTopicMapping(UUIDModel):
    course_version = models.ForeignKey(CourseVersion, on_delete=models.PROTECT)
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT)
    topic_name = models.CharField(max_length=200)
    topic_code = models.CharField(max_length=40, blank=True)
    knowledge_ids = models.JSONField()
    source = models.CharField(max_length=300)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course_version", "topic"], name="unique_legacy_topic_mapping")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Legacy mappings are immutable; old results must not drift.")
        return super().save(*args, **kwargs)
