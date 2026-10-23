import copy
import hashlib
import pytest
from app.ai.contracts import ModelCallResult
from app.ai.visual import PROMPT_VERSION, SCHEMA_VERSION
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import Task, ModelInvocation
from app.core.tasks import submit_task, claim_task
from app.courses import analysis
from app.courses.context import attach_visual_evidence
from app.courses.schemas import AnalysisOutput
from app.materials import transcription
from app.materials.models import VisualTranscription
from test_visual_transcription import parsed_version, fixture_payload
from test_course_analysis import course_payload, analysis_context


def evidence_dicts(version):
    return [{"id": str(e.id), "material_version_id": str(version.id), "physical_page": e.physical_page,
             "material_code": "FX", "roles": ["lecture"], "fidelity_status": e.fidelity_status, "text": e.text,
             "parse_content_hash": e.parse_version.content_hash}
            for e in version.evidence.select_related("parse_version").order_by("physical_page")]


def accept(evidence, payload=None):
    decision = transcription.decide(evidence)
    entry = transcription.page_entry(evidence, decision)
    source = transcription.source_of(entry)
    return VisualTranscription.objects.create(evidence=evidence, **{k: entry[k] for k in transcription.KEY_FIELDS if k != "evidence_id"},
        route=decision, status="transcribed", payload=payload or fixture_payload(source), origin="fixture")


def test_pages_carry_route_and_transcription_or_pending_marker(course):
    version = parsed_version(course, 3)
    accept(version.evidence.get(physical_page=1))
    evidence = evidence_dicts(version)
    attach_visual_evidence(course, evidence)
    status = {e["physical_page"]: e["visual_status"] for e in evidence}
    assert status == {1: "transcribed", 2: "not_needed", 3: "visual_pending"}
    first = evidence[0]["visual"]
    assert first["origin"] == "fixture" and first["verification"] == "model_candidate_not_human_verified"
    assert first["items"][0] == {"kind": "formula", "location": "centre", "legibility": "readable",
                                 "value_origin": "not_applicable", "latex_as_printed": r"\lim_{h\to0}"}


def test_transcribed_page_sends_transcription_instead_of_text(course):
    version = parsed_version(course, 3)
    accept(version.evidence.get(physical_page=1))
    evidence = evidence_dicts(version)
    attach_visual_evidence(course, evidence)
    spec = analysis.make_spec({"input": {"evidence": evidence, "materials": []}, "prompt_version": "p",
                               "schema_version": "s", "context_hash": "h"})
    sent = {e["physical_page"]: e for e in spec.input["evidence"]}
    assert "visual" in sent[1] and "text" not in sent[1]
    assert sent[2]["text"] and sent[3]["text"] and sent[3]["visual_status"] == "visual_pending"


def test_new_transcription_changes_the_analysis_input(course):
    version = parsed_version(course, 1)
    before = evidence_dicts(version)
    attach_visual_evidence(course, before)
    accept(version.evidence.get())
    after = evidence_dicts(version)
    attach_visual_evidence(course, after)
    assert digest(before) != digest(after)


def test_legacy_review_is_used_only_while_page_and_image_are_unchanged(course):
    version = parsed_version(course, 1)
    evidence = version.evidence.select_related("parse_version").get()
    image = transcription.render_page(course.owner, version.id, 1).read_bytes()
    source = {"evidence_id": str(evidence.id), "material_version_id": str(version.id), "parse_version_id": str(evidence.parse_version_id),
              "physical_page": 1, "blob_sha256": version.blob.sha256, "parse_content_hash": evidence.parse_version.content_hash}
    review = {"source": source, "status": "reviewed", "page_title": "Definition", "faithful_transcription": "f'(x)",
              "math_items": [{"as_printed_latex": "f'(x)", "location_on_page": "top", "legibility": "readable"}],
              "findings": [], "teaching_use": "Definition", "unresolved": []}
    task = Task.objects.create(course=course, kind="ai_validation", state="succeeded",
                               snapshot={"pages": [{"source": source, "image_sha256": hashlib.sha256(image).hexdigest()}]})
    ModelInvocation.objects.create(task=task, call_key="M-p1", epoch=1, request_hash="x", state="completed",
                                   result={"status": "parsed", "payload": review})
    evidence_list = evidence_dicts(version)
    attach_visual_evidence(course, evidence_list)
    assert evidence_list[0]["visual"]["origin"] == "legacy_page_review"
    Task.objects.filter(pk=task.pk).update(snapshot={"pages": [{"source": source, "image_sha256": "0" * 64}]})
    evidence_list = evidence_dicts(version)
    attach_visual_evidence(course, evidence_list)
    assert evidence_list[0]["visual_status"] == "visual_pending"


def output_with(requests):
    return AnalysisOutput.model_validate({"status": "needs_info", "explanation": "x", "draft": None,
                                          "visual_review_requests": requests})


def test_model_request_upgrades_page_for_next_preflight(course, course_payload, analysis_context):
    version = parsed_version(course, 2)
    prose = version.evidence.get(physical_page=2)
    context = {"evidence": [{"id": str(prose.id)}]}
    with pytest.raises(DomainError, match="EVIDENCE_REFERENCE_INVALID"):
        analysis.visual_requests(output_with([{"evidence_id": "elsewhere", "reason": "x"}]), context)
    requests = analysis.visual_requests(output_with([{"evidence_id": str(prose.id), "reason": "Refers to Figure 2"}]), context)
    for e in analysis_context["evidence"]:
        e.update(material_version_id="fixture-version", physical_page=1)
    analysis_context["materials"] = []
    task = submit_task(course, "analysis", {}, "visual-request")
    analysis.publish_analysis(claim_task(task.id), course_payload, analysis_context, "fixture", requests)
    task.refresh_from_db()
    assert task.result["visual_review_requests"] == requests
    state = next(s for s in transcription.page_states(course) if s["physical_page"] == 2)
    assert state["route"]["signals"] == ["model_requested"] and state["status"] == "awaiting_consent"


def test_analysis_schema_keeps_requests_strict():
    schema = AnalysisOutput.model_json_schema()
    assert "visual_review_requests" in schema["required"]
    assert schema["$defs"]["VisualReviewRequest"]["additionalProperties"] is False


def test_materials_and_source_api_show_transcription_state(course):
    from rest_framework.test import APIClient
    version = parsed_version(course, 3)
    row = accept(version.evidence.get(physical_page=1))
    client = APIClient()
    client.force_authenticate(course.owner)
    summary = client.get(f"/api/v1/courses/{course.id}/materials").json()["materials"][0]["transcription"]
    assert summary == {"visual_pages": 2, "done": 1, "running": 0, "not_started": 0, "awaiting_consent": 1,
                       "failed": 0, "task_id": None}
    first = client.get(f"/api/v1/sources/{row.evidence_id}").json()
    assert first["transcription_status"] == "done" and first["transcription"]["origin"] == "fixture"
    assert first["route"]["route"] == "visual" and "empty_formula_region" in first["route"]["signals"]
    prose = client.get(f"/api/v1/sources/{version.evidence.get(physical_page=2).id}").json()
    assert prose["transcription_status"] == "not_needed" and prose["transcription"] is None


def counted_task(course, monkeypatch, tokens):
    from app.ai import invocations
    from app.courses.models import AnalysisGrant
    from app.core.idempotency import digest as d
    calls = {"count": 0, "generate": 0}
    def count(body, **kw):
        calls["count"] += 1
        return ModelCallResult(mode="fixture", status="parsed", payload={"input_tokens": tokens})
    def generate(spec, **kw):
        calls["generate"] += 1
        assert kw["byte_admission"] is False
        return ModelCallResult(mode="fixture", status="refusal", error_code="MODEL_REFUSAL")
    monkeypatch.setattr(invocations, "count_official", count)
    monkeypatch.setattr(invocations, "invoke_official", generate)
    monkeypatch.setattr(analysis, "verify_sources", lambda *a: None)
    # Larger than the old 60,000-byte bound, which must no longer decide admission.
    evidence = [{"id": "e", "material_version_id": "v", "physical_page": 1, "material_code": "FX", "roles": ["lecture"],
                 "fidelity_status": "needs_review", "text": "x" * 70000, "route": {"route": "text", "signals": []},
                 "visual_status": "not_needed", "visual": None}]
    snapshot = {"input": {"evidence": evidence, "materials": []}, "prompt": "fixture", "prompt_version": "fixture",
                "schema_version": "fixture", "schema_hash": d(AnalysisOutput.model_json_schema()), "model": "fixture",
                "context_hash": "counted-" + str(tokens)}
    AnalysisGrant.objects.create(course=course, context_hash=snapshot["context_hash"], scope={}, source="test", granted_by=course.owner)
    return submit_task(course, "analysis", snapshot, "counted-" + str(tokens)), calls


def test_over_limit_count_stops_before_any_analysis_request(course, monkeypatch):
    task, calls = counted_task(course, monkeypatch, 60001)
    with pytest.raises(DomainError, match="TOKEN_BUDGET_EXCEEDED"):
        analysis.run_analysis(claim_task(task.id))
    assert calls == {"count": 1, "generate": 0}
    count = ModelInvocation.objects.get(task=task)
    assert count.metadata["purpose"] == "input_token_count" and count.result["payload"] == {"input_tokens": 60001}
    task.refresh_from_db()
    assert task.call_count == 0


def test_counted_input_within_limit_proceeds_with_count_recorded(course, monkeypatch):
    task, calls = counted_task(course, monkeypatch, 19500)
    with pytest.raises(DomainError, match="MODEL_REFUSAL"):
        analysis.run_analysis(claim_task(task.id))
    assert calls == {"count": 1, "generate": 1}
    generation = ModelInvocation.objects.get(task=task, call_key="course-analysis")
    assert generation.metadata["input_admission_method"] == "official_input_tokens_count"
    assert generation.metadata["counted_input_tokens"] == 19500


def test_preflight_states_the_token_admission(course):
    from app.courses.context import build_context, inspect_scope
    scope = inspect_scope(build_context(course))
    assert scope["admission"]["method"] == "official_input_tokens_count" and scope["admission"]["limit_tokens"] == 60000
    assert scope["admission"]["local_utf8_bytes"] > 0


def test_analysis_call_limit_comes_from_its_snapshot_and_other_stages_keep_150(course, monkeypatch):
    from app.core.models import Task as T
    task, calls = counted_task(course, monkeypatch, 19500)
    T.objects.filter(pk=task.pk).update(snapshot={**task.snapshot, "call_timeout_seconds": 300})
    seen = {}
    from app.ai import invocations
    def generate(spec, **kw):
        seen["timeout"] = kw["timeout_seconds"]
        return ModelCallResult(mode="fixture", status="refusal", error_code="MODEL_REFUSAL")
    monkeypatch.setattr(invocations, "invoke_official", generate)
    with pytest.raises(DomainError, match="MODEL_REFUSAL"):
        analysis.run_analysis(claim_task(task.id))
    assert 295 < seen["timeout"] <= 300
    assert ModelInvocation.objects.get(task=task, call_key="course-analysis").metadata["timeout_seconds"] > 295
    # Another stage without its own setting keeps the 150-second default.
    import inspect
    assert inspect.signature(invocations.run_call).parameters["call_seconds"].default == 150


def test_preflight_shows_the_300_second_analysis_limit(course):
    from app.courses.context import build_context, inspect_scope
    snapshot = build_context(course)
    assert snapshot["call_timeout_seconds"] == 300 and inspect_scope(snapshot)["call_timeout_seconds"] == 300
