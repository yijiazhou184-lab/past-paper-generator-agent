import pytest
from app.ai.client import call_model
from app.ai.contracts import ModelCallSpec, ModelCallResult


def test_no_adapter_means_no_model_call_and_unknown_usage():
    spec = ModelCallSpec(stage="course_analysis", prompt_version="test", schema_version="test", context_hash="test", input={})
    result = call_model(spec)
    assert result.mode == "disabled" and result.status == "not_executed"
    assert result.usage.total_tokens is None
    with pytest.raises(ValueError, match="fixture"):
        call_model(spec, fixture_adapter=lambda _: ModelCallResult(mode="live", status="parsed", payload={}))
    assert call_model(spec, fixture_adapter=lambda _: ModelCallResult(mode="fixture", status="parsed", payload={})).mode == "fixture"
