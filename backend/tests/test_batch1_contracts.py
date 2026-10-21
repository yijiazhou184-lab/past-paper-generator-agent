import io
import json
import importlib.metadata
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from django.db import close_old_connections, connection
from django.utils import timezone
from rest_framework.test import APIClient
from app.core.tasks import submit_task, claim_task, checkpoint, recover_stale_tasks
from app.core.models import Task, Outbox
from app.core.errors import DomainError
from app.core.budgets import reserve_call
from app.materials.ingest import ingest_pdf, validate_pdf
from app.materials.models import MaterialVersion, ParseVersion, Evidence
from app.materials.parser import CONFIG, parse_material
from app.materials.storage import write_bytes, path_for
from app.core.idempotency import digest

pytestmark = pytest.mark.django_db(transaction=True)


def imported(course, pdf_bytes, key="one", replace=None):
    return MaterialVersion.objects.get(pk=ingest_pdf(course, pdf_bytes, "lecture.pdf", key,
        replace_id=replace)["version_id"])


def cached_parse(version):
    parse = ParseVersion.objects.create(blob=version.blob, parser_name="docling",
        parser_version=importlib.metadata.version("docling"), config_hash=digest(CONFIG),
        state="ready", document_key=f"fixture/{version.id}.json")
    payload = {"pages": [{"physical_page": n, "text": f"Fixture page {n}", "blocks": []}
                         for n in range(1, version.blob.pages + 1)]}
    write_bytes(parse.document_key, json.dumps(payload).encode())
    parse_material(claim_task(version.task_id), version.id)
    return parse


def test_concurrent_submission_and_duplicate_claim(course):
    def submit(_):
        close_old_connections()
        try:
            return submit_task(course, "analysis", {"revision": 1}, "parallel").id
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    assert Task.objects.count() == Outbox.objects.count() == 1
    assert claim_task(ids[0]) is not None
    assert claim_task(ids[0]) is None


def test_outbox_resend_and_lease_recovery(course):
    from app.core.management.commands.dispatch_outbox import dispatch_once
    task = submit_task(course, "parse", {}, "outbox")
    dispatch_once()
    Outbox.objects.filter(task=task).update(sent_at=None)
    dispatch_once()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM procrastinate_jobs WHERE args->>'task_id' = %s", [str(task.id)])
        assert cursor.fetchone()[0] == 2
    old = claim_task(task.id)
    Task.objects.filter(pk=task.id).update(heartbeat_at=timezone.now()-timedelta(seconds=100))
    recover_stale_tasks()
    new = claim_task(task.id)
    assert new.epoch > old.epoch
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        checkpoint(old, "Late write")
    assert task.attempts.get(epoch=old.epoch).outcome == "interrupted"
    assert Outbox.objects.get(task=task).sent_at is None


def test_deadline_and_call_limits(course):
    task = submit_task(course, "planning", {}, "budget")
    token = claim_task(task.id)
    assert task.attempts.first().usage is None
    with pytest.raises(DomainError, match="TOKEN_BUDGET_EXCEEDED"):
        reserve_call(token, 60001, 1)
    assert reserve_call(token, 100, 100) == 1
    assert reserve_call(token, 100, 100) == 2
    with pytest.raises(DomainError, match="CALL_BUDGET_EXCEEDED"):
        reserve_call(token, 100, 100)
    Task.objects.filter(pk=task.id).update(deadline_at=timezone.now()-timedelta(seconds=1))
    with pytest.raises(DomainError, match="RUN_LIMIT_EXCEEDED"):
        checkpoint(token, "Too late")


def test_old_source_survives_replacement_and_cache_reuse(course, pdf_bytes):
    old = imported(course, pdf_bytes)
    parse = cached_parse(old)
    evidence_id = old.evidence.get(physical_page=2).id
    replacement = imported(course, pdf_bytes, "replace", str(old.material_id))
    parse_material(claim_task(replacement.task_id), replacement.id)
    assert ParseVersion.objects.count() == 1
    assert replacement.number == 2
    assert replacement.evidence.get(physical_page=2).parse_version_id == parse.id
    client = APIClient()
    client.force_authenticate(course.owner)
    source = client.get(f"/api/v1/sources/{evidence_id}").json()
    assert source["material_version_id"] == str(old.id)
    assert source["physical_page"] == 2
    assert source["fidelity_status"] == "needs_review"
    image = client.get(source["image_url"])
    assert image.status_code == 200
    assert b"".join(image.streaming_content).startswith(b"\x89PNG")
    assert client.get(f"/api/v1/material-versions/{old.id}/pages/3").status_code == 404
    assert client.get(f"/api/v1/material-versions/{old.id}/original").status_code == 200


def test_same_name_new_content_is_not_duplicate(course, pdf_bytes):
    first = imported(course, pdf_bytes)
    second = imported(course, pdf_bytes+b"\n%additional revision\n", "different")
    assert first.blob_id != second.blob_id
    assert first.material_id != second.material_id


def test_owner_scope_and_revision_conflict(course, pdf_bytes, django_user_model):
    version = imported(course, pdf_bytes)
    cached_parse(version)
    evidence = version.evidence.first()
    client = APIClient()
    assert client.get(f"/api/v1/sources/{evidence.id}").status_code == 403
    client.force_authenticate(django_user_model.objects.create_user(username="other"))
    for endpoint in [f"sources/{evidence.id}", f"material-versions/{version.id}/pages/1",
                     f"material-versions/{version.id}/original", f"tasks/{version.task_id}",
                     f"courses/{course.id}/materials"]:
        assert client.get(f"/api/v1/{endpoint}").status_code == 404
    assert client.patch(f"/api/v1/material-versions/{version.id}/classification",
        {"roles": ["lecture"], "expected_revision": 1}, format="json").status_code == 404
    client.force_authenticate(course.owner)
    endpoint = f"/api/v1/material-versions/{version.id}/classification"
    assert client.patch(endpoint, {"roles": ["lecture"], "expected_revision": 1}, format="json").status_code == 200
    assert client.patch(endpoint, {"roles": ["answer"], "expected_revision": 1}, format="json").status_code == 409
    version.refresh_from_db()
    assert version.roles == ["lecture"]


def test_login_requires_csrf_and_loopback(django_user_model, settings):
    settings.LOCAL_ACCESS = True
    django_user_model.objects.create_user(username="local")
    client = APIClient(enforce_csrf_checks=True)
    assert client.post("/api/v1/session").status_code == 403
    token = client.get("/api/v1/session").json()["csrf_token"]
    assert client.post("/api/v1/session", HTTP_X_CSRFTOKEN=token, REMOTE_ADDR="192.168.1.1").status_code == 403
    assert client.post("/api/v1/session", HTTP_X_CSRFTOKEN=token).status_code == 200


def test_validation_and_cumulative_page_limit(course, pdf_bytes):
    with pytest.raises(DomainError, match="INVALID_PDF"):
        validate_pdf(pdf_bytes, "renamed.txt")
    with pytest.raises(DomainError, match="FILE_TOO_LARGE"):
        validate_pdf(b"%PDF-"+b"x"*(20*1024*1024), "large.pdf")
    version = imported(course, pdf_bytes)
    version.blob.pages = 300
    version.blob.save()
    with pytest.raises(DomainError, match="COURSE_PAGE_LIMIT"):
        imported(course, pdf_bytes+b"\n%new\n", "overlimit")
    assert MaterialVersion.objects.count() == 1


def test_private_storage_rejects_escape():
    with pytest.raises(ValueError):
        path_for("../outside.pdf")


def test_evidence_pack_freezes_revision_and_preserves_provenance(course, pdf_bytes):
    from app.materials.evidence import build_evidence_pack
    version = imported(course, pdf_bytes)
    with pytest.raises(DomainError, match="EVIDENCE_NOT_READY"):
        build_evidence_pack(course.owner, [version.id])
    cached_parse(version)
    before = build_evidence_pack(course.owner, [version.id])
    version.roles = ["personal_notes"]
    version.classification_basis = "user_corrected"
    version.classification_revision += 1
    version.save()
    after = build_evidence_pack(course.owner, [version.id])
    assert before["manifest_hash"] != after["manifest_hash"]
    assert before["materials"][0]["roles"] != ["personal_notes"]
    assert after["materials"][0]["classification_basis"] == "user_corrected"
    assert after["evidence"][0]["fidelity_status"] == "needs_review"


def test_answer_associations_scope_and_revision(course, pdf_bytes, django_user_model):
    from app.courses.models import Course
    from app.materials.models import MaterialRelation
    answer = imported(course, pdf_bytes)
    question = imported(course, pdf_bytes+b"\n%questions", "questions")
    other = Course.objects.create(owner=django_user_model.objects.create_user(username="other"), title="Other")
    foreign = imported(other, pdf_bytes, "foreign")
    client = APIClient()
    client.force_authenticate(course.owner)
    endpoint = f"/api/v1/material-versions/{answer.id}/relations"
    assert client.post(endpoint, {"target_version_id": str(foreign.id), "coverage": "Q1"}, format="json").status_code == 404
    for coverage in ("Q1", "Q1–2"):
        assert client.post(endpoint, {"target_version_id": str(question.id), "coverage": coverage}, format="json").status_code == 201
    relation = MaterialRelation.objects.get(source=answer)
    assert relation.coverage == "Q1–2" and relation.revision == 2
    assert client.post(f"/api/v1/relations/{relation.id}/remove").status_code == 200
    relation.refresh_from_db()
    assert not relation.active and relation.revision == 3


def test_parser_rejects_different_task_input(course, pdf_bytes):
    first = imported(course, pdf_bytes)
    second = imported(course, pdf_bytes+b"\n%second", "second")
    with pytest.raises(DomainError, match="TASK_INPUT_MISMATCH"):
        parse_material(claim_task(first.task_id), second.id)
    assert not Evidence.objects.exists()
