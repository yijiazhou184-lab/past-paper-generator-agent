"""Offline protocol fixtures only: no API key or network is needed by these tests."""
import json
import httpx
import pytest
from app.ai.contracts import ModelCallSpec
from app.ai.page_review import SmokeResult
from app.ai.responses import invoke_official


def spec():
    return ModelCallSpec(stage="semantic_review", prompt_version="fixture", schema_version="fixture",
                         context_hash="fixture", input={"function": "x^2", "x": 3}, max_output_tokens=1000)


def response_body(status="completed", content=None):
    return {"id": "resp_fixture", "object": "response", "created_at": 0, "status": status,
            "model": "gpt-6.1-sol", "service_tier": "default", "parallel_tool_calls": False,
            "tool_choice": "none", "tools": [],
            "output": [{"id": "msg_fixture", "type": "message", "role": "assistant", "status": "completed",
                        "content": content if content is not None else [{"type": "output_text", "annotations": [],
                            "text": json.dumps({"derivative": "2x", "at_x_3": 6})}]}],
            "usage": {"input_tokens": 12, "output_tokens": 18, "total_tokens": 30,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 5}}}


def invoke(handler, **kwargs):
    return invoke_official(spec(), instructions="Synthetic fixture", output_type=SmokeResult,
                           api_key="test-not-a-real-key", model="gpt-6.1-sol",
                           transport=httpx.MockTransport(handler), **kwargs)


def test_actual_sdk_request_contract(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid/v1")
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["store"] is False and "tools" not in body
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        assert body["max_output_tokens"] == 1000
        return httpx.Response(200, json=response_body(), headers={"x-request-id": "fixture-request"})
    result = invoke(handler)
    assert result.status == "parsed" and result.payload["at_x_3"] == 6
    assert result.request_id == "fixture-request" and result.usage.total_tokens == 30
    assert result.usage.reasoning_tokens == 5


@pytest.mark.parametrize("body,status,code", [
    (response_body("incomplete"), "truncated", "MODEL_INCOMPLETE"),
    (response_body(content=[{"type": "refusal", "refusal": "fixture refusal"}]), "refusal", "MODEL_REFUSAL"),
    (response_body(content=[{"type": "output_text", "text": "{}", "annotations": []}]), "invalid_output", "OUTPUT_SCHEMA_INVALID"),
    (response_body("failed"), "provider_error", "PROVIDER_RESPONSE_FAILED"),
])
def test_non_success_keeps_usage_without_publishing_payload(body, status, code):
    result = invoke(lambda _: httpx.Response(200, json=body))
    assert result.status == status and result.error_code == code
    assert result.payload is None and result.usage.total_tokens == 30


@pytest.mark.parametrize("status,provider_code,expected", [
    (401, "invalid_api_key", "PROVIDER_AUTH_FAILED"), (403, "unsupported_country", "PROVIDER_ACCESS_DENIED"),
    (404, "model_not_found", "MODEL_UNAVAILABLE"), (429, "insufficient_quota", "PROVIDER_QUOTA_EXHAUSTED"),
    (429, "credit_balance_exhausted", "PROVIDER_QUOTA_EXHAUSTED"),
    (429, "rate_limit_exceeded", "PROVIDER_RATE_LIMIT"), (500, "server_error", "PROVIDER_HTTP_ERROR"),
])
def test_no_hidden_retry_no_secret_in_error(status, provider_code, expected):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={"error": {"code": provider_code, "message": "PRIVATE SECRET ECHO"}},
                              headers={"x-request-id": "fixture-error"})
    result = invoke(handler)
    assert len(seen) == 1 and result.error_code == expected
    assert result.usage.total_tokens is None and "PRIVATE" not in result.model_dump_json()
    assert result.http_status == status and result.provider_error_code == provider_code


def test_timeout_and_missing_key_never_claim_zero_usage():
    def timeout(request):
        raise httpx.ReadTimeout("fixture timeout", request=request)
    assert invoke(timeout).error_code == "PROVIDER_TIMEOUT"
    result = invoke_official(spec(), instructions="", output_type=SmokeResult, api_key="", model="unused")
    assert result.status == "not_executed" and result.usage.total_tokens is None


def test_overlarge_text_stopped_before_transport():
    from app.ai.responses import request_body
    oversized = spec().model_copy(update={"input": {"text": "x" * 60001}})
    with pytest.raises(ValueError, match="TOKEN_BUDGET_EXCEEDED"):
        request_body(oversized, "", SmokeResult, "gpt-6.1-sol")


def test_image_payload_and_size_are_bounded():
    import io
    from PIL import Image
    from app.ai.responses import request_body
    output = io.BytesIO()
    Image.new("RGB", (800, 600)).save(output, format="PNG")
    body = request_body(spec(), "", SmokeResult, "gpt-6.1-sol", output.getvalue())
    image = body["input"][0]["content"][1]
    assert image["detail"] == "high" and image["image_url"].startswith("data:image/png;base64,")
    output = io.BytesIO()
    Image.new("RGB", (1601, 600)).save(output, format="PNG")
    with pytest.raises(ValueError, match="IMAGE_DIMENSIONS_UNSUPPORTED"):
        request_body(spec(), "", SmokeResult, "gpt-6.1-sol", output.getvalue())
