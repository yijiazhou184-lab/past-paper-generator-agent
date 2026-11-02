import json
from unittest.mock import patch
import httpx
from pydantic import BaseModel
from app.ai.contracts import ModelCallSpec
from app.ai.invocations import run_call
from app.ai.responses import invoke_official
from app.core.tasks import submit_task,claim_task,fail_task
from app.core.models import ModelInvocation,ErrorRecord,TaskAttempt
from app.core.api import task_view


class Result(BaseModel):
    message:str


def test_provider_echo_cannot_leak_into_diagnostics_or_usage(course,caplog):
    secret="synthetic-key-DO-NOT-LOG"
    private="SYNTHETIC_FULL_PDF_TEXT_MARKER"
    def respond(request):
        assert request.url.host=="api.openai.com"
        return httpx.Response(400,json={"error":{"message":private+" "+secret,"code":"bad_request","type":"invalid_request_error"}},headers={"x-request-id":"synthetic-request"})
    spec=ModelCallSpec(stage="course_analysis",prompt_version="fixture",schema_version="fixture",context_hash="fixture",input={"text":private})
    task=submit_task(course,"analysis",{},"diagnostic")
    token=claim_task(task.id)
    def call(*args,**kwargs):
        return invoke_official(*args,**kwargs,transport=httpx.MockTransport(respond))
    with patch("app.ai.invocations.invoke_official",side_effect=call):
        result=run_call(token,"one",spec,instructions="Synthetic test",output_type=Result,api_key=secret,model="fixture",counted_tokens=100)
    fail_task(token,result.error_code,"The provider rejected this request.",False)
    task.refresh_from_db()
    diagnostic={"error":task.error,"calls":[{"metadata":c.metadata,"result":c.result} for c in ModelInvocation.objects.filter(task=task)],
        "events":list(task.events.values("stage","detail")),"records":list(ErrorRecord.objects.filter(task=task).values("safe_message","code"))}
    text=json.dumps(diagnostic)+caplog.text
    assert secret not in text and private not in text
    assert result.error_code=="PROVIDER_BAD_REQUEST" and result.request_id=="synthetic-request"
    assert TaskAttempt.objects.get(task=task).usage["input_tokens"] is None
    assert task_view(task,include_calls=True)["model_calls"][0]["usage"]["total_tokens"] is None


def test_database_outage_returns_safe_retryable_json_without_another_database_write(caplog):
    from django.db import OperationalError
    from types import SimpleNamespace
    from app.core.errors import exception_handler
    marker="synthetic-secret-and-full-text"
    response=exception_handler(OperationalError(marker),{"request":SimpleNamespace(method="PATCH")})
    assert response.status_code==503 and response.data["code"]=="DATABASE_UNAVAILABLE"
    assert response.data["retryable"] is True and response.data["diagnostic_id"]
    assert marker not in json.dumps(response.data)+caplog.text
    assert response.data["diagnostic_id"] in caplog.text
