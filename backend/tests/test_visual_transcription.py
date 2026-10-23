import hashlib
import io
import json
import threading
import time
import pytest
from django.core.management import call_command
from datetime import timedelta
from django.utils import timezone
from reportlab.pdfgen import canvas
from app.ai import invocations
from app.ai.contracts import ModelCallResult, Usage
from app.core.errors import DomainError
from app.core.models import Task, ModelInvocation
from app.core.tasks import claim_task, cancel_task, recover_stale_tasks
from app.courses.models import Course
from app.materials import transcription
from app.materials.ingest import ingest_pdf
from app.materials.models import Evidence, ParseVersion, MaterialVersion, VisualTranscription, TranscriptionGrant
from app.materials.storage import write_bytes, path_for

PROSE = "The derivative measures the instantaneous rate of change of a function at a point in its domain."
FORMULA = [{"kind": "text", "text": "Definition", "bbox": {"l": 0, "t": 10, "r": 10, "b": 0}},
           {"kind": "formula", "text": "", "bbox": {"l": 0, "t": 50, "r": 200, "b": 0}}]


def pdf(pages):
    out = io.BytesIO()
    document = canvas.Canvas(out)
    for number in range(pages):
        document.drawString(60, 700, f"Synthetic teaching page {number + 1}")
        document.showPage()
    document.save()
    return out.getvalue()


def parsed_version(course, pages, name="lecture.pdf", content=b"{}"):
    """A parsed material whose odd pages need the image route and even pages are prose."""
    version = MaterialVersion.objects.get(pk=ingest_pdf(course, pdf(pages), name, "upload:" + name)["version_id"])
    parse = ParseVersion.objects.create(blob=version.blob, parser_version="fixture", config_hash=name + content.decode(),
                                        state="ready", document_key=f"parses/{name}/{len(content)}.json")
    write_bytes(parse.document_key, content)
    parse.content_hash = hashlib.sha256(path_for(parse.document_key).read_bytes()).hexdigest()
    parse.save()
    for number in range(1, pages + 1):
        visual = number % 2 == 1
        Evidence.objects.create(material_version=version, parse_version=parse, physical_page=number,
                                text="Definition" if visual else PROSE,
                                blocks=FORMULA if visual else [{"kind": "text", "text": PROSE, "bbox": None}])
    return version


def grant_all(course):
    entries = transcription.visual_candidates(course)
    TranscriptionGrant.objects.create(course=course, scope_hash=str(len(entries)) + str(TranscriptionGrant.objects.count()),
                                      granted_by=course.owner, scope=entries, source="test")
    return entries


def fixture_payload(source, status="transcribed"):
    item = {k: None for k in ("columns", "rows", "units", "axes", "series", "labelled_values", "elements", "relations", "text")}
    return {"source": source, "status": status, "page_title": "Definition", "faithful_transcription": r"f'(x)=\lim_{h\to0}",
            "items": [{"kind": "formula", "location": "centre", "legibility": "readable", "value_origin": "not_applicable",
                       "latex_as_printed": r"\lim_{h\to0}", **item}],
            "findings": [], "teaching_use": "Definition", "unresolved": []}


@pytest.fixture
def model(monkeypatch):
    """Fixture provider: records calls; never reaches the network."""
    state = {"calls": [], "active": 0, "peak": 0, "fail": set(), "delay": 0, "after_call": None, "raise": False}
    lock = threading.Lock()

    def invoke(spec, **kwargs):
        with lock:
            state["calls"].append(spec.input["source"]["evidence_id"])
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        try:
            time.sleep(state["delay"])
            if state["raise"]:
                raise RuntimeError("connection dropped after sending")
            if state["after_call"]:
                state["after_call"]()
            if spec.input["source"]["physical_page"] in state["fail"]:
                return ModelCallResult(mode="fixture", status="provider_error", error_code="PROVIDER_RATE_LIMIT")
            return ModelCallResult(mode="fixture", status="parsed", payload=fixture_payload(spec.input["source"]),
                                   usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15))
        finally:
            with lock:
                state["active"] -= 1
    monkeypatch.setattr(invocations, "invoke_official", invoke)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-real")
    return state


def run(task):
    transcription.run_transcription(claim_task(task.id))
    task.refresh_from_db()
    return task


def test_ungranted_visual_pages_wait_for_consent(course):
    parsed_version(course, 2)
    states = {s["physical_page"]: s for s in transcription.page_states(course)}
    assert states[1]["status"] == "awaiting_consent" and "empty_formula_region" in states[1]["route"]["signals"]
    assert states[2]["status"] == "not_needed"
    assert transcription.schedule(course, "parse_complete") is None
    assert not Task.objects.filter(kind="visual_transcription").exists()


def test_granted_pages_transcribe_once_then_reuse_cache(course, model):
    version = parsed_version(course, 2)
    grant_all(course)
    task = transcription.schedule(course, "grant")
    assert [p["physical_page"] for p in task.snapshot["pages"]] == [1] and task.snapshot["max_calls"] == 1
    assert transcription.schedule(course, "grant") is None  # the page is already queued
    assert run(task).state == "succeeded" and task.result["transcribed"] == 1
    row = VisualTranscription.objects.get()
    assert row.origin == "fixture" and row.evidence.fidelity_status == "needs_review"
    assert {s["physical_page"]: s["status"] for s in transcription.page_states(course)} == {1: "done", 2: "not_needed"}
    # An explicit retry of the same pages answers from the cache without a model call.
    again = Task.objects.create(course=course, kind="visual_transcription", snapshot=task.snapshot,
                                deadline_at=timezone.now() + timedelta(minutes=5))
    assert run(again).result["cached"] == 1 and len(model["calls"]) == 1
    assert transcription.schedule(course, "continuation", versions=[version]) is None


def test_changed_parse_invalidates_cache_and_consent(course, model):
    version = parsed_version(course, 1)
    grant_all(course)
    run(transcription.schedule(course, "grant"))
    new_parse = ParseVersion.objects.create(blob=version.blob, parser_version="fixture-2", config_hash="changed",
                                            state="ready", document_key="parses/changed.json")
    write_bytes(new_parse.document_key, b'{"changed": true}')
    new_parse.content_hash = hashlib.sha256(path_for(new_parse.document_key).read_bytes()).hexdigest()
    new_parse.save()
    Evidence.objects.create(material_version=version, parse_version=new_parse, physical_page=1, text="Definition", blocks=FORMULA)
    assert [s["status"] for s in transcription.page_states(course)] == ["awaiting_consent"]
    assert transcription.schedule(course, "parse_complete") is None


def test_page_without_consent_is_never_sent(course, model):
    parsed_version(course, 1)
    entries = transcription.visual_candidates(course)
    task = Task.objects.create(course=course, kind="visual_transcription", deadline_at=timezone.now() + timedelta(minutes=5),
        snapshot={"purpose": "visual_transcription", "pages": entries, "policy": "per_page_grant", "concurrency": 1, "max_calls": 1})
    with pytest.raises(DomainError, match="TRANSCRIPTION_CONSENT_REQUIRED"):
        run(task)
    assert model["calls"] == [] and not ModelInvocation.objects.exists()


def test_other_course_page_is_rejected(course, model, django_user_model):
    other = Course.objects.create(owner=course.owner, title="Other course")
    parsed_version(other, 1, "other.pdf")
    entries = grant_all(other)
    task = Task.objects.create(course=course, kind="visual_transcription", deadline_at=timezone.now() + timedelta(minutes=5),
        snapshot={"purpose": "visual_transcription", "pages": entries, "policy": "per_page_grant", "concurrency": 1, "max_calls": 1})
    with pytest.raises(DomainError, match="EVIDENCE_NOT_FOUND"):
        run(task)
    assert model["calls"] == []


def test_invalid_model_source_is_not_cached(course, model, monkeypatch):
    parsed_version(course, 1)
    grant_all(course)
    monkeypatch.setattr(invocations, "invoke_official", lambda spec, **kw: ModelCallResult(
        mode="fixture", status="parsed", payload=fixture_payload({**spec.input["source"], "physical_page": 9})))
    task = transcription.schedule(course, "grant")
    call_command("transcribe_visual_one", str(task.id), str(claim_task(task.id).epoch))
    task.refresh_from_db()
    assert task.state == "failed" and task.error["code"] == "MODEL_SOURCE_MISMATCH"
    assert not VisualTranscription.objects.exists()
    assert [s["status"] for s in transcription.page_states(course) if s["status"] != "not_needed"] == ["failed"]


def test_cancel_stops_dispatch_and_late_result_is_not_published(course, model, monkeypatch):
    monkeypatch.setenv("APP_TRANSCRIPTION_CONCURRENCY", "1")  # threads cannot see this test's open transaction
    parsed_version(course, 3)
    grant_all(course)
    task = transcription.schedule(course, "grant")
    model["after_call"] = lambda: cancel_task(course.owner, task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        run(task)
    assert len(model["calls"]) == 1  # page 3 was never dispatched
    assert ModelInvocation.objects.get().state == "completed" and not VisualTranscription.objects.exists()


def test_unknown_outcome_is_not_replayed_after_recovery(course, model):
    parsed_version(course, 1)
    grant_all(course)
    task = transcription.schedule(course, "grant")
    model["raise"] = True
    with pytest.raises(DomainError):
        run(task)
    Task.objects.filter(pk=task.pk).update(heartbeat_at=timezone.now() - timedelta(minutes=5))
    recover_stale_tasks()
    model["raise"] = False
    with pytest.raises(DomainError, match="MODEL_OUTCOME_UNKNOWN"):
        run(task)
    assert len(model["calls"]) == 1


def test_parse_completion_schedules_granted_pages(course, model):
    from app.core.management.commands.parse_one import schedule_after_parse
    version = parsed_version(course, 1)
    grant_all(course)
    parse_task = Task.objects.create(course=course, kind="parse", snapshot={"material_version_id": str(version.id)})
    schedule_after_parse(parse_task)
    assert Task.objects.filter(kind="visual_transcription", state="queued").count() == 1


@pytest.mark.django_db(transaction=True)
def test_parallel_pages_respect_limit_and_fail_independently(course, model, monkeypatch):
    monkeypatch.setenv("APP_TRANSCRIPTION_CONCURRENCY", "2")
    parsed_version(course, 7)  # pages 1, 3, 5, 7 need images
    grant_all(course)
    task = transcription.schedule(course, "grant")
    model["delay"], model["fail"] = 0.3, {3}
    assert run(task).state == "succeeded"
    assert model["peak"] == 2 and len(model["calls"]) == 4
    outcomes = {p["evidence_id"]: p for p in task.result["pages"]}
    assert task.result["transcribed"] == 3 and task.result["failed"] == 1
    failed = [p for p in outcomes.values() if p["outcome"] == "failed"]
    assert failed[0]["code"] == "PROVIDER_RATE_LIMIT"
    assert VisualTranscription.objects.count() == 3 and task.call_count == 4


def test_portrait_page_is_shrunk_only_for_the_model(course):
    from PIL import Image
    version = parsed_version(course, 1)
    evidence = version.evidence.get()
    shown = Image.open(io.BytesIO(transcription.render_page(course.owner, version.id, 1).read_bytes()))
    sent = Image.open(io.BytesIO(transcription.model_image(evidence)))
    assert max(shown.size) > 1600 and max(sent.size) == 1600  # the viewer keeps its full rendering


def test_frozen_call_limit_stops_extra_pages(course, model, monkeypatch):
    monkeypatch.setenv("APP_TRANSCRIPTION_CONCURRENCY", "1")
    parsed_version(course, 3)
    grant_all(course)
    task = transcription.schedule(course, "grant")
    Task.objects.filter(pk=task.pk).update(snapshot={**task.snapshot, "max_calls": 1})
    task = run(task)
    assert [p.get("code") for p in task.result["pages"]] == [None, "CALL_BUDGET_EXCEEDED"]
    assert len(model["calls"]) == 1
