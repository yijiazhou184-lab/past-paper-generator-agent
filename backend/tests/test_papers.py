import copy
import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from django.db import connection, transaction, close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from app.core.errors import DomainError
from app.core.tasks import claim_task, cancel_task, recover_stale_tasks, checkpoint
from app.core.models import Task
from app.papers.models import Paper, ContentVersion, PDFArtifact
from app.papers.publication import freeze_content, submit_export, publish_exports
from app.papers.reader import question_view, answer_view, pdf_state
from app.papers.export import run_export, store_artifact
from app.papers.storage import artifact_path
from app.generation.generator import run_generation
from test_generation_execution import start
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


@pytest.fixture
def paper(course, planned):
    task, _, token = start(course, planned)
    run_generation(token)
    task.refresh_from_db()
    assert task.state == "succeeded", task.error
    return Paper.objects.select_related("content", "generation_task", "course").get(generation_task=task)


def pdf():
    from reportlab.pdfgen import canvas
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(50, 700, "Synthetic PDF transport fixture")
    c.save()
    return stream.getvalue(), 1


def test_freeze_once_and_snapshot_does_not_drift(paper):
    original = copy.deepcopy(paper.content.payload)
    task = paper.generation_task
    candidate = paper.content.candidate
    with transaction.atomic():
        assert freeze_content(task, candidate, candidate.check_report).id == paper.id
    paper.course.title = "Changed course"
    paper.course.save()
    paper.content.refresh_from_db()
    assert paper.content.payload == original
    assert Paper.objects.count() == ContentVersion.objects.count() == 1
    with pytest.raises(ValueError):
        paper.content.save()


def test_default_projection_and_owner_isolation(paper, django_user_model):
    client = APIClient()
    client.force_authenticate(paper.course.owner)
    response = client.get(f"/api/v1/papers/{paper.id}")
    assert response.status_code == 200
    candidate = response.json()["candidate"]
    assert "answers" not in str(candidate)
    assert "worked_solution" not in str(candidate)
    assert not candidate["assets"] or all("svg" in a for a in candidate["assets"])
    answer = client.get(f"/api/v1/papers/{paper.id}/answers")
    assert len(answer.json()["answers"]) == len(candidate["pairs"])
    client.force_authenticate(django_user_model.objects.create_user(username="unrelated"))
    for path in (f"papers/{paper.id}", f"papers/{paper.id}/answers", f"papers/{paper.id}/files/questions",
                 f"tasks/{paper.generation_task_id}/paper", f"courses/{paper.course_id}/papers"):
        assert client.get("/api/v1/"+path).status_code == 404
    assert client.post(f"/api/v1/papers/{paper.id}/exports", HTTP_IDEMPOTENCY_KEY="other").status_code == 404


def test_declines_corrupt_or_failed_candidate(paper):
    c = paper.content.candidate
    report = c.check_report
    report.gate = {"allowed": False}
    with pytest.raises(DomainError, match="REQUIRED_CHECKS_BLOCKED"):
        freeze_content(paper.generation_task, c, report)
    report.refresh_from_db()
    c.payload["pairs"][0]["stem"] = []
    with pytest.raises(DomainError, match="CONTENT_INTEGRITY_FAILED"):
        freeze_content(paper.generation_task, c, report)


def test_export_is_opt_in_and_idempotent(paper):
    assert pdf_state(paper)["status"] == "not_generated"
    assert not Task.objects.filter(kind="export").exists()
    _, first = submit_export(paper.course.owner, paper.id, "one")
    _, replay = submit_export(paper.course.owner, paper.id, "one")
    _, double = submit_export(paper.course.owner, paper.id, "another-tab")
    assert first.id == replay.id == double.id
    assert Task.objects.filter(kind="export").count() == 1
    assert first.snapshot["content_version_id"] == str(paper.content_id)
    assert first.model_calls.count() == 0


def test_second_pdf_failure_retry_preserves_first(paper):
    _, task = submit_export(paper.course.owner, paper.id, "export1")
    token = claim_task(task.id)
    def render(content, kind):
        if kind == "answers": raise RuntimeError("private renderer detail")
        return pdf()
    with patch("app.papers.export.render_pdf", side_effect=render) as adapter:
        run_export(token)
        assert adapter.call_count == 3
    task.refresh_from_db()
    paper.refresh_from_db()
    assert task.state == "failed"
    assert "private renderer detail" not in str(task.error)
    assert paper.exports_ready_at is None
    assert paper.generation_task.state == "succeeded"
    first = PDFArtifact.objects.get(content=paper.content, kind="questions")
    original_hash = first.sha256
    _, retry = submit_export(paper.course.owner, paper.id, "export2")
    assert retry.parent_id == task.id
    with patch("app.papers.export.render_pdf", return_value=pdf()) as adapter:
        run_export(claim_task(retry.id))
        assert adapter.call_count == 1
        assert adapter.call_args.args[1] == "answers"
    retry.refresh_from_db()
    paper.refresh_from_db()
    first.refresh_from_db()
    assert retry.state == "succeeded"
    assert pdf_state(paper)["status"] == "ready"
    assert first.sha256 == original_hash
    assert first.task_id == task.id
    assert retry.model_calls.count() == 0
    assert Paper.objects.count() == 1


def test_cancelled_and_stale_workers_cannot_save_or_publish(paper):
    _, task = submit_export(paper.course.owner, paper.id, "export")
    token = claim_task(task.id)
    cancel_task(paper.course.owner, task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        store_artifact(token, paper.id, "questions", *pdf())
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        publish_exports(token, paper.id)
    assert PDFArtifact.objects.count() == 0


def test_incomplete_exports_cannot_publish(paper):
    _, task = submit_export(paper.course.owner, paper.id, "export")
    token = claim_task(task.id)
    store_artifact(token, paper.id, "questions", *pdf())
    with pytest.raises(DomainError, match="PDFS_NOT_READY"):
        publish_exports(token, paper.id)
    paper.refresh_from_db()
    assert paper.exports_ready_at is None


def test_completed_export_survives_late_cancel_and_downloads(paper):
    _, task = submit_export(paper.course.owner, paper.id, "export")
    with patch("app.papers.export.render_pdf", return_value=pdf()):
        run_export(claim_task(task.id))
    assert cancel_task(paper.course.owner, task.id).state == "succeeded"
    client = APIClient()
    client.force_authenticate(paper.course.owner)
    response = client.get(f"/api/v1/papers/{paper.id}/files/questions")
    assert response.status_code == 200
    assert b"".join(response.streaming_content).startswith(b"%PDF-")
    response.close()
    assert "question-paper" in response["Content-Disposition"]


def test_missing_file_can_be_restored_without_new_content(paper):
    _, task = submit_export(paper.course.owner, paper.id, "export")
    with patch("app.papers.export.render_pdf", return_value=pdf()):
        run_export(claim_task(task.id))
    question = PDFArtifact.objects.get(content=paper.content, kind="questions")
    artifact_path(question).unlink()
    paper.refresh_from_db()
    assert pdf_state(paper)["status"] == "failed"
    _, retry = submit_export(paper.course.owner, paper.id, "restore")
    with patch("app.papers.export.render_pdf", return_value=pdf()) as adapter:
        run_export(claim_task(retry.id))
        assert adapter.call_count == 1
    assert Paper.objects.count() == 1


def test_worker_recovery_reuses_completed_file_and_fences_old_epoch(paper):
    from datetime import timedelta
    _, task = submit_export(paper.course.owner, paper.id, "export")
    old = claim_task(task.id)
    store_artifact(old, paper.id, "questions", *pdf())
    checkpoint(old, "Exporting mark scheme PDF", {"pdf_attempts": {"questions": 1, "answers": 1}})
    Task.objects.filter(pk=task.id).update(heartbeat_at=timezone.now()-timedelta(seconds=100))
    recover_stale_tasks()
    new = claim_task(task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        publish_exports(old, paper.id)
    with patch("app.papers.export.render_pdf", return_value=pdf()) as adapter:
        run_export(new)
        assert adapter.call_count == 1
    task.refresh_from_db()
    assert task.state == "succeeded"


def test_expired_task_cannot_publish(paper):
    from datetime import timedelta
    _, task = submit_export(paper.course.owner, paper.id, "export")
    token = claim_task(task.id)
    Task.objects.filter(pk=task.id).update(deadline_at=timezone.now()-timedelta(seconds=1))
    with pytest.raises(DomainError, match="RUN_LIMIT_EXCEEDED"):
        publish_exports(token, paper.id)


@pytest.mark.django_db(transaction=True)
def test_two_submissions_share_one_export(paper):
    from threading import Barrier
    barrier = Barrier(2)
    def submit(key):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return str(submit_export(paper.course.owner, paper.id, key)[1].id)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(submit, ["tab1", "tab2"]))
    assert ids[0] == ids[1]
    assert Task.objects.filter(kind="export").count() == 1


def test_immutable_database_trigger_and_history_reference(paper):
    from django.db import DatabaseError
    from app.generation.execution_context import build_generation_context
    from app.generation.generator import question_input
    from app.generation.duplicates import duplicate_candidates
    with pytest.raises(DatabaseError), transaction.atomic():
        ContentVersion.objects.filter(pk=paper.content_id).update(payload_hash="changed")
    context=build_generation_context(paper.content.candidate.snapshot)
    assert str(paper.content_id) in context["input"]["history_content_ids"]
    data=question_input(context,context["input"]["questions"][0],[])
    assert data["previous_practice_examples_to_avoid"]
    result=duplicate_candidates(paper.content.payload["content"]["pairs"],[],context["input"]["history_content_ids"],context["input"]["history_papers"])
    assert any(f["code"]=="SAVED_PAPER_DUPLICATE" for f in result["findings"])
    assert result["compared_paper_ids"] == [str(paper.id)]


def test_history_cursor_paginates_equal_timestamps_without_duplicates(paper):
    from django.core import signing
    from app.generation.models import CandidateVersion
    base = paper.content.candidate
    for index in range(20):
        task = Task.objects.create(course=paper.course, kind="generation", state="succeeded")
        candidate = CandidateVersion.objects.create(snapshot=base.snapshot, task=task, revision=1,
            payload=base.payload, payload_hash=base.payload_hash, mode="fixture", stage="saved")
        content = ContentVersion.objects.create(candidate=candidate, payload=paper.content.payload,
            payload_hash=paper.content.payload_hash)
        Paper.objects.create(course=paper.course, generation_task=task, content=content)
    # Timestamp ties must use the UUID tie-breaker consistently on both pages.
    Paper.objects.update(created_at=paper.created_at)
    client = APIClient()
    client.force_authenticate(paper.course.owner)
    path = f"/api/v1/courses/{paper.course_id}/papers"
    first = client.get(path).json()
    assert len(first["papers"]) == 20
    assert first["next_cursor"]
    second = client.get(path, {"cursor": first["next_cursor"]}).json()
    assert len(second["papers"]) == 1
    assert second["next_cursor"] is None
    ids = [p["id"] for p in first["papers"] + second["papers"]]
    assert len(set(ids)) == 21
    assert ids == sorted(ids, reverse=True)
    assert client.get(path, {"cursor": first["next_cursor"]+"tampered"}).status_code == 400
    data = signing.loads(first["next_cursor"], salt="paper-list")
    data["course"] = "another-course"
    assert client.get(path, {"cursor": signing.dumps(data, salt="paper-list")}).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_concurrent_finalisers_publish_once(paper):
    from threading import Barrier
    _, task = submit_export(paper.course.owner, paper.id, "export")
    token = claim_task(task.id)
    for kind in ("questions", "answers"):
        store_artifact(token, paper.id, kind, *pdf())
    barrier = Barrier(2)
    def finish(_):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            try:
                publish_exports(token, paper.id)
                return "published"
            except DomainError as exc:
                return exc.payload["code"]
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finish, range(2)))
    assert sorted(outcomes) == ["STALE_EXECUTION", "published"]
    task.refresh_from_db()
    assert task.state == "succeeded"
    assert task.events.filter(stage="Complete").count() == 1
    assert Paper.objects.count() == 1
