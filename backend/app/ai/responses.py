"""Official Responses API only. No implicit retries, tools, file upload or stored state."""
import base64
import io
import json
import re
import time
from typing import Type

import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
from PIL import Image
from pydantic import BaseModel, ValidationError

from .contracts import ModelCallSpec, ModelCallResult, Usage


def request_body(spec: ModelCallSpec, instructions: str, output_type: Type[BaseModel],
                 model: str, image: bytes | None = None, *, byte_admission: bool = True):
    """byte_admission=False leaves the input bound to an official token count made before the call."""
    schema = output_type.model_json_schema()
    content = [{"type": "input_text", "text": json.dumps(spec.input, ensure_ascii=False)}]
    # Conservative local admission bound, not billed token usage. One small page only.
    bound = len((instructions + content[0]["text"] + json.dumps(schema)).encode("utf-8")) + 512
    if image:
        if len(image) > 8 * 1024 * 1024:
            raise ValueError("IMAGE_TOO_LARGE")
        with Image.open(io.BytesIO(image)) as page:
            if page.format != "PNG" or max(page.size) > 1600:
                raise ValueError("IMAGE_DIMENSIONS_UNSUPPORTED")
        bound += 8192
        content.append({"type": "input_image", "image_url": "data:image/png;base64," +
                        base64.b64encode(image).decode("ascii"), "detail": "high"})
    if byte_admission and bound > spec.max_input_tokens:
        raise ValueError("TOKEN_BUDGET_EXCEEDED")
    return {"model": model, "instructions": instructions,
            "input": [{"role": "user", "content": content}], "store": False,
            "max_output_tokens": spec.max_output_tokens, "reasoning": {"effort": "medium"},
            "text": {"format": {"type": "json_schema", "name": output_type.__name__,
                                "strict": True, "schema": schema}}}


def decode_response(response, output_type):
    data = response.model_dump()
    raw_usage = data.get("usage") or {}
    usage = Usage(**{k: raw_usage.get(k) for k in ("input_tokens", "output_tokens", "total_tokens")},
                  cached_input_tokens=(raw_usage.get("input_tokens_details") or {}).get("cached_tokens"),
                  reasoning_tokens=(raw_usage.get("output_tokens_details") or {}).get("reasoning_tokens"))
    result = ModelCallResult(mode="live", status="provider_error", usage=usage,
                             response_id=data.get("id"), request_id=getattr(response, "_request_id", None),
                             model=data.get("model"), service_tier=data.get("service_tier"))
    parts = [p for item in data.get("output", []) if item.get("type") == "message"
             for p in item.get("content", [])]
    if any(p.get("type") == "refusal" for p in parts):
        return result.model_copy(update={"status": "refusal", "error_code": "MODEL_REFUSAL"})
    if data.get("status") == "incomplete":
        return result.model_copy(update={"status": "truncated", "error_code": "MODEL_INCOMPLETE"})
    if data.get("status") != "completed":
        return result.model_copy(update={"error_code": "PROVIDER_RESPONSE_FAILED"})
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "output_text")
    try:
        payload = output_type.model_validate_json(text).model_dump(mode="json")
    except (ValidationError, ValueError):
        return result.model_copy(update={"status": "invalid_output", "error_code": "OUTPUT_SCHEMA_INVALID"})
    return result.model_copy(update={"status": "parsed", "payload": payload})


def invoke_official(spec, *, instructions, output_type, api_key, model, image=None,
                    timeout_seconds=150, transport=None, byte_admission=True):
    body = request_body(spec, instructions, output_type, model, image, byte_admission=byte_admission)
    return call_official(lambda client: decode_response(client.responses.create(**body), output_type),
                         api_key=api_key, timeout_seconds=timeout_seconds, transport=transport)


COUNT_FIELDS = ("model", "instructions", "input", "reasoning", "text")


def count_official(body, *, api_key, timeout_seconds=60, transport=None):
    """Official input-token count for exactly this request body; nothing is generated."""
    def count(client):
        response = client.responses.input_tokens.count(**{k: body[k] for k in COUNT_FIELDS})
        return ModelCallResult(mode="live", status="parsed", payload={"input_tokens": response.input_tokens},
                               request_id=getattr(response, "_request_id", None))
    return call_official(count, api_key=api_key, timeout_seconds=timeout_seconds, transport=transport)


def call_official(action, *, api_key, timeout_seconds, transport):
    if not api_key or not api_key.strip():
        return ModelCallResult(mode="disabled", status="not_executed", error_code="API_KEY_MISSING")
    start = time.monotonic()
    try:
        # Explicit URL prevents ambient OPENAI_BASE_URL from redirecting private material.
        with httpx.Client(transport=transport, follow_redirects=False) as http_client:
            with OpenAI(api_key=api_key, base_url="https://api.openai.com/v1", max_retries=0,
                        timeout=min(timeout_seconds, 150), http_client=http_client) as client:
                result = action(client)
    except APITimeoutError:
        result = ModelCallResult(mode="live", status="provider_error", error_code="PROVIDER_TIMEOUT")
    except APIConnectionError:
        result = ModelCallResult(mode="live", status="provider_error", error_code="PROVIDER_CONNECTION_FAILED")
    except APIStatusError as exc:
        code = {401: "PROVIDER_AUTH_FAILED", 403: "PROVIDER_ACCESS_DENIED", 404: "MODEL_UNAVAILABLE",
                429: "PROVIDER_RATE_LIMIT", 400: "PROVIDER_BAD_REQUEST"}.get(exc.status_code, "PROVIDER_HTTP_ERROR")
        error = exc.body if isinstance(exc.body, dict) else {}
        if isinstance(error.get("error"), dict):
            error = error["error"]
        if error.get("code") in ("insufficient_quota", "billing_hard_limit_reached", "credit_balance_exhausted") or error.get("type") == "insufficient_quota":
            code = "PROVIDER_QUOTA_EXHAUSTED"
        def safe_identifier(value):
            return value if isinstance(value, str) and re.fullmatch(r"[a-z_]{1,80}", value) else None
        retry_after = exc.response.headers.get("retry-after", "")
        # Never persist provider error messages: they can echo submitted input or credentials.
        result = ModelCallResult(mode="live", status="provider_error", error_code=code,
                                 request_id=exc.request_id, http_status=exc.status_code,
                                 provider_error_code=safe_identifier(error.get("code")),
                                 provider_error_type=safe_identifier(error.get("type")),
                                 retry_after_seconds=float(retry_after) if re.fullmatch(r"\d{1,8}(\.\d{1,3})?", retry_after) else None)
    return result.model_copy(update={"elapsed_seconds": round(time.monotonic() - start, 3)})
