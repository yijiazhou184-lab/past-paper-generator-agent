"""Save checked content once; user-triggered export has its own lifecycle."""
import copy
from django.db import transaction
from django.utils import timezone
from app.core.errors import DomainError
from app.core.idempotency import digest, intent
from app.core.models import Task
from app.core.tasks import locked_task, finish_task, submit_task
from app.courses.models import Course
from app.generation.checks import release_gate
from .models import ContentVersion, Paper


def assert_integrity(content):
    if digest(content.payload) != content.payload_hash:
        raise DomainError("CONTENT_INTEGRITY_FAILED", "Saved content did not pass its integrity check.", retryable=False)


@transaction.atomic
def freeze_content(task, candidate, report):
    if task.state not in ("processing", "succeeded") or task.kind != "generation" or candidate.task_id != task.id:
        raise DomainError("CONTENT_NOT_READY", "Only a successful generation can be saved as a paper.")
    if report.candidate_id != candidate.id or not report.gate.get("allowed") or not release_gate(report.payload["checks"])["allowed"]:
        raise DomainError("REQUIRED_CHECKS_BLOCKED", "All required checks must pass before saving a paper.")
    if digest(candidate.payload) != candidate.payload_hash or digest(report.payload) != report.payload_hash:
        raise DomainError("CONTENT_INTEGRITY_FAILED", "The candidate or report failed its integrity check.")
    snapshot = candidate.snapshot
    if digest(snapshot.payload) != snapshot.payload_hash:
        raise DomainError("CONTENT_INTEGRITY_FAILED", "The frozen generation input failed its integrity check.")
    prior = Paper.objects.filter(generation_task=task).select_related("content").first()
    if prior:
        if prior.content.candidate_id != candidate.id:
            raise DomainError("PAPER_ALREADY_FROZEN", "This generation already has a different saved version.")
        assert_integrity(prior.content)
        return prior
    version = snapshot.confirmation.course_version
    metadata = {
        "course_title": task.course.title, "course_code": task.course.code,
        "course_version_id": str(version.id), "course_version_number": version.number,
        "config": copy.deepcopy(snapshot.payload["config"]),
        "blueprint": copy.deepcopy(snapshot.payload["blueprint"]),
        "mode": candidate.mode, "generated_at": task.created_at.isoformat(),
        "candidate_hash": candidate.payload_hash, "report_hash": report.payload_hash,
        "snapshot_hash": snapshot.payload_hash,
    }
    payload = {"schema_version": "paper-content-v1", "metadata": metadata,
               "content": copy.deepcopy(candidate.payload), "report": copy.deepcopy(report.payload),
               "context": copy.deepcopy(task.snapshot)}
    content = ContentVersion.objects.create(candidate=candidate, payload=payload, payload_hash=digest(payload))
    return Paper.objects.create(course=task.course, generation_task=task, content=content)


@transaction.atomic
def submit_export(owner, paper_id, key, *, refresh_layout=False):
    from django.shortcuts import get_object_or_404
    from .reader import pdf_state
    from .render import RENDERER_VERSION
    initial = get_object_or_404(Paper, pk=paper_id, course__owner=owner)
    course = Course.objects.select_for_update().get(pk=initial.course_id)
    paper = Paper.objects.select_for_update().select_related("content").get(pk=paper_id)
    assert_integrity(paper.content)
    record = intent(owner, f"paper-export:{paper.id}", key, {"content_version_id": str(paper.content_id), "refresh_layout": refresh_layout})
    if record.response:
        return paper, Task.objects.get(pk=record.response["task_id"]) if record.response.get("task_id") else None
    current = paper.latest_export
    if current and current.state in ("queued", "processing"):
        task = current
    elif pdf_state(paper)["status"] == "ready" and not refresh_layout:
        task = current
    else:
        task = submit_task(course, "export", {
            "paper_id": str(paper.id), "content_version_id": str(paper.content_id),
            "content_hash": paper.content.payload_hash, "refresh_layout": refresh_layout, "renderer_version": RENDERER_VERSION,
        }, key, parent=current or paper.generation_task)
        paper.latest_export = task
        paper.exports_ready_at = None
        paper.save(update_fields=["latest_export", "exports_ready_at"])
    record.response = {"task_id": str(task.id) if task else None}
    record.save(update_fields=["response"])
    return paper, task


@transaction.atomic
def publish_exports(token, paper_id):
    from .storage import valid_artifact
    task = locked_task(token)
    paper = Paper.objects.select_for_update().select_related("content").get(pk=paper_id)
    if paper.latest_export_id != task.id or str(paper.content_id) != task.snapshot["content_version_id"]:
        raise DomainError("STALE_EXECUTION")
    assert_integrity(paper.content)
    artifacts = {a.kind: a for a in paper.content.pdfs.all()}
    if not all(k in artifacts and valid_artifact(artifacts[k]) for k in ("questions", "answers")):
        raise DomainError("PDFS_NOT_READY", "Both PDF files must be valid before export is complete.")
    paper.exports_ready_at = paper.exports_ready_at or timezone.now()
    paper.save(update_fields=["exports_ready_at"])
    finish_task(token, {"paper_id": str(paper.id), "content_version_id": str(paper.content_id), "pdf_status": "ready"})
    return paper
