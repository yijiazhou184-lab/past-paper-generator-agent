"""Normal application calls stay disabled; explicit live validation uses responses.py."""
from typing import Callable
from .contracts import ModelCallSpec, ModelCallResult


def call_model(spec: ModelCallSpec, *, fixture_adapter: Callable | None = None) -> ModelCallResult:
    if fixture_adapter is None:
        return ModelCallResult(mode="disabled", status="not_executed", error_code="LIVE_MODEL_DISABLED")
    result = ModelCallResult.model_validate(fixture_adapter(spec))
    if result.mode != "fixture":
        raise ValueError("The injected test adapter must identify its output as fixture.")
    return result
