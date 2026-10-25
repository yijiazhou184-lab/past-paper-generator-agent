import pytest
from app.ai import invocations
from app.ai.contracts import ModelCallResult, Usage
from app.ai.page_review import SmokeResult
from app.core.errors import DomainError
from app.core.models import ModelInvocation
from app.core.tasks import submit_task, claim_task, cancel_task
from app.core.budgets import reserve_call
from test_responses_adapter import spec

pytestmark = pytest.mark.django_db


def run(token, key="smoke"):
    return invocations.run_call(token, key, spec(), instructions="fixture", output_type=SmokeResult,
                                api_key="test-not-a-real-key", model="gpt-6.1-sol")


def fixture_result():
    return ModelCallResult(mode="fixture", status="parsed", payload={"derivative": "2x", "at_x_3": 6},
                            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30))


def test_completed_call_reused_unknown_call_never_replayed(course, monkeypatch):
    task = submit_task(course, "ai_validation", {}, "test")
    token = claim_task(task.id)
    seen = []
    monkeypatch.setattr(invocations, "invoke_official", lambda *a, **k: seen.append(1) or fixture_result())
    assert run(token).status == "parsed"
    assert run(token).status == "parsed" and len(seen) == 1
    record = ModelInvocation.objects.get(task=task)
    assert record.result["usage"]["total_tokens"] == 30
    record.state = "started"
    record.save()
    with pytest.raises(DomainError) as exc:
        run(token)
    assert exc.value.payload["code"] == "MODEL_OUTCOME_UNKNOWN" and len(seen) == 1


def test_cancel_during_call_preserves_usage_but_blocks_publication(course, monkeypatch):
    task = submit_task(course, "ai_validation", {}, "test")
    token = claim_task(task.id)
    def cancelled(*args, **kwargs):
        cancel_task(course.owner, task.id)
        return fixture_result()
    monkeypatch.setattr(invocations, "invoke_official", cancelled)
    with pytest.raises(DomainError) as exc:
        run(token)
    assert exc.value.payload["code"] == "STALE_EXECUTION"
    task.refresh_from_db()
    assert task.state == "cancelled" and task.result == {}
    assert ModelInvocation.objects.get(task=task).result["usage"]["total_tokens"] == 30


def test_live_scope_has_six_call_limit_and_blocks_other_ai_task(course):
    task = submit_task(course, "ai_validation", {}, "test")
    token = claim_task(task.id)
    for _ in range(6):
        reserve_call(token, 1000, 1000)
    with pytest.raises(DomainError) as exc:
        reserve_call(token, 1000, 1000)
    assert exc.value.payload["code"] == "CALL_BUDGET_EXCEEDED"
    with pytest.raises(DomainError) as exc:
        submit_task(course, "analysis", {}, "other")
    assert exc.value.payload["code"] == "COURSE_BUSY"


def test_call_records_are_owner_scoped_and_web_cannot_repeat_paid_task(course, django_user_model, monkeypatch):
    from rest_framework.test import APIClient
    from app.core.tasks import fail_task
    task = submit_task(course, "ai_validation", {}, "test")
    token = claim_task(task.id)
    monkeypatch.setattr(invocations, "invoke_official", lambda *a, **k: fixture_result())
    run(token)
    fail_task(token, "FIXTURE_FAILURE", "Synthetic test failure", False)
    client = APIClient()
    client.force_authenticate(course.owner)
    data = client.get(f"/api/v1/tasks/{task.id}").json()
    assert data["model_calls"][0]["mode"] == "fixture"
    assert data["model_calls"][0]["payload"]["at_x_3"] == 6
    assert client.get(f"/api/v1/courses/{course.id}/tasks").json()["tasks"][0]["model_calls"] == []
    retry = client.post(f"/api/v1/tasks/{task.id}/retries", HTTP_IDEMPOTENCY_KEY="web-retry")
    assert retry.status_code == 409 and retry.json()["code"] == "LIVE_VALIDATION_COMMAND_REQUIRED"
    client.force_authenticate(django_user_model.objects.create_user(username="other"))
    assert client.get(f"/api/v1/tasks/{task.id}").status_code == 404


def test_synthetic_snapshot_has_no_course_text_or_page_images(course, monkeypatch):
    from app.ai import validation
    monkeypatch.setattr(validation.MaterialVersion.objects, "get", lambda **kw: pytest.fail("Material read in synthetic scope"))
    snapshot = validation.build_snapshot(course, "gpt-6.1-sol", smoke_only=True)
    assert snapshot["pages"] == [] and snapshot["authorization"] == "explicit_cli_synthetic_only"


@pytest.mark.parametrize("unknown_model_usage",[False,True])
def test_count_requests_do_not_erase_model_usage_but_unknown_usage_does(course,monkeypatch,unknown_model_usage):
    task=submit_task(course,"ai_validation",{},"usage")
    token=claim_task(task.id)
    ModelInvocation.objects.create(task=task,call_key="count:smoke",epoch=token.epoch,
        request_hash="a"*64,state="completed",metadata={"purpose":"input_token_count"},
        result=ModelCallResult(mode="fixture",status="parsed",payload={"input_tokens":10}).model_dump(mode="json"))
    if unknown_model_usage:
        ModelInvocation.objects.create(task=task,call_key="unknown-usage",epoch=token.epoch,
            request_hash="b"*64,state="completed",metadata={},
            result=ModelCallResult(mode="fixture",status="provider_error").model_dump(mode="json"))
    monkeypatch.setattr(invocations,"invoke_official",lambda *a,**k:fixture_result())
    run(token)
    usage=task.attempts.get(epoch=token.epoch).usage
    assert usage==({"input_tokens":None,"output_tokens":None,"total_tokens":None} if unknown_model_usage else
                   {"input_tokens":10,"output_tokens":20,"total_tokens":30})
