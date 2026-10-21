from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelCallSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["course_analysis", "blueprint", "question_pairs", "semantic_review", "repair"]
    prompt_version: str
    schema_version: str
    context_hash: str
    input: dict[str, Any]
    max_input_tokens: int = Field(default=60000, gt=0, le=60000)
    max_output_tokens: int = Field(default=12000, gt=0, le=12000)


class ModelCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["disabled", "fixture", "live"]
    status: Literal["parsed", "refusal", "truncated", "provider_error", "not_executed"]
    payload: dict[str, Any] | None = None
    usage: Usage = Field(default_factory=Usage)
    error_code: str | None = None
