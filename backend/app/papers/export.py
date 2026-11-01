import hashlib
import io
import os
import uuid
from django.conf import settings
from django.db import transaction
from pypdf import PdfReader
from app.core.errors import DomainError
from app.core.models import Task
from app.core.tasks import checkpoint, locked_task, fail_task
from .models import Paper, PDFArtifact
from .publication import assert_integrity, publish_exports
from .render import render_pdf, RENDERER_VERSION
from .storage import valid_artifact


@transaction.atomic
def store_artifact(token, paper_id, kind, data, pages):
    task = locked_task(token)
    paper = Paper.objects.select_for_update().select_related("content").get(pk=paper_id)
    if paper.latest_export_id != task.id or task.snapshot["content_hash"] != paper.content.payload_hash:
        raise DomainError("STALE_EXECUTION")
    assert_integrity(paper.content)
    # Validate bytes independently of renderer return metadata.
    actual_pages = len(PdfReader(io.BytesIO(data)).pages)
    if not data.startswith(b"%PDF-") or actual_pages < 1 or actual_pages != pages:
        raise DomainError("PDF_INVALID", "The exported file failed validation.")
    hashed = hashlib.sha256(data).hexdigest()
    relative = f"papers/{paper.content_id}/{kind}-{hashed}.pdf"
    target = settings.DATA_DIR / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        with staging.open("xb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    artifact, _ = PDFArtifact.objects.update_or_create(content=paper.content, kind=kind, defaults={
        "path": relative, "sha256": hashed, "pages": pages, "size": len(data),
        "renderer_version": RENDERER_VERSION, "task": task})
    return artifact


def run_export(token):
    task = Task.objects.get(pk=token.task_id)
    paper = Paper.objects.select_related("content").get(pk=task.snapshot["paper_id"])
    try:
        assert_integrity(paper.content)
        for kind, label in (("questions", "question paper"), ("answers", "mark scheme")):
            existing = PDFArtifact.objects.filter(content=paper.content, kind=kind).first()
            if existing and valid_artifact(existing) and (not task.snapshot.get("refresh_layout") or existing.renderer_version == task.snapshot.get("renderer_version")):
                checkpoint(token, f"Reusing saved {label} PDF")
                continue
            # Attempt counts survive worker interruption; never reset the automatic retry budget.
            while True:
                task.refresh_from_db()
                attempts = dict(task.checkpoint.get("pdf_attempts", {}))
                count = attempts.get(kind, 0)
                if count >= 2:
                    raise DomainError("PDF_EXPORT_FAILED", f"The {label} PDF could not be completed. Retry export; saved questions and answers stay the same.", retryable=True)
                attempts[kind] = count + 1
                checkpoint(token, f"Exporting {label} PDF", {"pdf_attempts": attempts})
                try:
                    data, pages = render_pdf(paper.content, kind)
                    store_artifact(token, paper.id, kind, data, pages)
                    break
                except DomainError as exc:
                    if exc.payload["code"] in ("STALE_EXECUTION", "RUN_LIMIT_EXCEEDED", "CONTENT_INTEGRITY_FAILED"):
                        raise
                    if not exc.payload["retryable"]: raise
                except Exception:
                    # Preserve only safe diagnostics; renderer output may contain private content.
                    if count == 1:
                        raise DomainError("PDF_EXPORT_FAILED", f"The {label} PDF could not be completed. Retry export; saved questions and answers stay the same.", retryable=True)
        checkpoint(token, "Finalising PDF files")
        publish_exports(token, paper.id)
    except DomainError as exc:
        if exc.payload["code"] != "STALE_EXECUTION":
            fail_task(token, exc.payload["code"], exc.payload["message"], exc.payload["retryable"])
