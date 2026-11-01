from django.db import models
from app.core.models import UUIDModel
from app.generation.models import Immutable


class ContentVersion(Immutable):
    candidate = models.OneToOneField("generation.CandidateVersion", on_delete=models.PROTECT)
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=64)


class Paper(UUIDModel):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    generation_task = models.OneToOneField("core.Task", on_delete=models.PROTECT, related_name="paper")
    content = models.OneToOneField(ContentVersion, on_delete=models.PROTECT)
    latest_export = models.ForeignKey("core.Task", null=True, on_delete=models.PROTECT, related_name="export_papers")
    exports_ready_at = models.DateTimeField(null=True)


class PDFArtifact(UUIDModel):
    content = models.ForeignKey(ContentVersion, on_delete=models.PROTECT, related_name="pdfs")
    kind = models.CharField(max_length=20, choices=[("questions", "Question paper"), ("answers", "Mark scheme")])
    path = models.CharField(max_length=300)
    sha256 = models.CharField(max_length=64)
    pages = models.PositiveIntegerField()
    size = models.PositiveIntegerField()
    renderer_version = models.CharField(max_length=60)
    task = models.ForeignKey("core.Task", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["content", "kind"], name="unique_pdf_content_kind")]
