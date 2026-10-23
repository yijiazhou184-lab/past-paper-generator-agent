from django.conf import settings
from django.db import models
from app.core.models import UUIDModel


class MaterialBlob(UUIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sha256 = models.CharField(max_length=64)
    bytes = models.PositiveBigIntegerField()
    pages = models.PositiveIntegerField()
    storage_key = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "sha256"], name="unique_owner_blob")]


class Material(UUIDModel):
    course = models.ForeignKey("courses.Course", related_name="materials", on_delete=models.PROTECT)


class MaterialVersion(UUIDModel):
    material = models.ForeignKey(Material, related_name="versions", on_delete=models.PROTECT)
    blob = models.ForeignKey(MaterialBlob, on_delete=models.PROTECT)
    number = models.PositiveIntegerField(default=1)
    original_filename = models.CharField(max_length=255)
    path_aliases = models.JSONField(default=list)
    roles = models.JSONField(default=list)
    classification_basis = models.CharField(max_length=30, default="unclassified")
    classification_revision = models.PositiveIntegerField(default=1)
    content_metadata = models.JSONField(default=dict)
    task = models.ForeignKey("core.Task", null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["material", "number"], name="unique_material_revision")]


class ParseVersion(UUIDModel):
    blob = models.ForeignKey(MaterialBlob, on_delete=models.PROTECT)
    parser_name = models.CharField(max_length=40, default="docling")
    parser_version = models.CharField(max_length=40)
    config_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=30, default="processing")
    document_key = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    issues = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["blob", "parser_name", "parser_version", "config_hash"], name="unique_parse_config")]


class Evidence(UUIDModel):
    material_version = models.ForeignKey(MaterialVersion, related_name="evidence", on_delete=models.PROTECT)
    parse_version = models.ForeignKey(ParseVersion, on_delete=models.PROTECT)
    physical_page = models.PositiveIntegerField()
    printed_label = models.CharField(max_length=50, blank=True)
    text = models.TextField()
    blocks = models.JSONField(default=list)
    fidelity_status = models.CharField(max_length=40, default="needs_review")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["material_version", "parse_version", "physical_page"], name="unique_page_evidence")]


class MaterialRelation(UUIDModel):
    source = models.ForeignKey(MaterialVersion, related_name="answer_links", on_delete=models.PROTECT)
    target = models.ForeignKey(MaterialVersion, related_name="question_links", on_delete=models.PROTECT)
    coverage = models.CharField(max_length=500)
    revision = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "target"], name="unique_material_relation")]


class VisualTranscription(UUIDModel):
    """One accepted page-image transcription; a cache entry that is never updated in place."""
    evidence = models.ForeignKey(Evidence, related_name="transcriptions", on_delete=models.PROTECT)
    parse_content_hash = models.CharField(max_length=64)
    image_sha256 = models.CharField(max_length=64)
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=60)
    schema_version = models.CharField(max_length=60)
    route = models.JSONField()
    status = models.CharField(max_length=30)
    payload = models.JSONField()
    origin = models.CharField(max_length=20)
    task = models.ForeignKey("core.Task", null=True, on_delete=models.PROTECT)
    invocation = models.ForeignKey("core.ModelInvocation", null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["evidence", "parse_content_hash", "image_sha256", "model", "prompt_version", "schema_version"],
            name="unique_visual_transcription_key")]


class TranscriptionGrant(UUIDModel):
    """Development consent for sending an exact list of page images; scope entries carry their full cache keys."""
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    scope_hash = models.CharField(max_length=64)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.JSONField()
    source = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["course", "scope_hash"], name="unique_transcription_grant")]
