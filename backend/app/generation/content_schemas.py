"""Restricted paired-content and review contracts. No model-authored executable code."""
from typing import Literal
from pydantic import Field
from .schemas import Strict, ResponseType

CheckStatus = Literal["pass", "fail", "not_checked", "inconclusive", "not_applicable"]


class Expression(Strict):
    op: Literal["number", "variable", "add", "sub", "mul", "div", "pow", "sin", "cos", "exp", "log", "sqrt", "abs"]
    value: str | None
    args: list["Expression"] = Field(max_length=4)


class Domain(Strict):
    lower: str | None
    upper: str | None
    left_open: bool
    right_open: bool


class MathCheckSpec(Strict):
    id: str = Field(min_length=1, max_length=80)
    part_id: str
    kind: Literal["derivative", "equivalence", "value", "limit", "stationary_points", "bounded_optimum", "lhopital"]
    expression: Expression
    expected: Expression | None
    denominator: Expression | None
    variable: Literal["x", "y", "t", "q"]
    domain: Domain | None
    at: str | None
    direction: Literal["+", "-", "+-"]
    points: list[str] = Field(max_length=20)
    optimum: Literal["min", "max"] | None
    rationale: str = Field(min_length=1, max_length=2000)


class TextBlock(Strict):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=10000)


class MathBlock(Strict):
    type: Literal["math"]
    latex: str = Field(min_length=1, max_length=4000)
    display: bool


class TableBlock(Strict):
    type: Literal["table"]
    columns: list[str] = Field(min_length=1, max_length=12)
    rows: list[list[str]] = Field(min_length=1, max_length=100)
    caption: str


class AssetBlock(Strict):
    type: Literal["asset_ref"]
    asset_id: str


ContentBlock = TextBlock | MathBlock | TableBlock | AssetBlock


class GraphSpec(Strict):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    kind: Literal["function_graph"]
    expression: Expression
    x_min: float = Field(ge=-100000, le=100000)
    x_max: float = Field(ge=-100000, le=100000)
    y_min: float = Field(ge=-100000, le=100000)
    y_max: float = Field(ge=-100000, le=100000)
    samples: int = Field(ge=40, le=600, strict=True)
    x_label: str = Field(max_length=80)
    y_label: str = Field(max_length=80)
    alt: str = Field(min_length=1, max_length=600)


class QuestionPart(Strict):
    part_id: str
    prompt: list[ContentBlock] = Field(min_length=1, max_length=40)
    marks: float = Field(gt=0, le=100, multiple_of=0.5)
    assumptions: list[str] = Field(max_length=20)
    response_type: ResponseType
    knowledge_ids: list[str] = Field(min_length=1, max_length=30)


class MarkingPoint(Strict):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2000)
    marks: float = Field(gt=0, le=100, multiple_of=0.5)
    alternative_group: str | None


class Answer(Strict):
    part_id: str
    worked_solution: list[ContentBlock] = Field(min_length=1, max_length=60)
    final_answer: list[ContentBlock] = Field(min_length=1, max_length=20)
    marking_points: list[MarkingPoint] = Field(min_length=1, max_length=40)
    acceptable_alternatives: list[str] = Field(max_length=20)
    units: str | None
    precision: str | None
    checks: list[MathCheckSpec] = Field(max_length=20)


class BackgroundReference(Strict):
    label: str = Field(min_length=1, max_length=400)
    evidence_id: str | None
    url: str | None = Field(max_length=2000)
    note: str = Field(max_length=2000)


class QuestionPair(Strict):
    question_id: str
    stem: list[ContentBlock] = Field(min_length=1, max_length=30)
    parts: list[QuestionPart] = Field(min_length=1, max_length=12)
    answers: list[Answer] = Field(min_length=1, max_length=12)
    asset_ids: list[str] = Field(max_length=12)
    evidence_ids: list[str] = Field(max_length=40)
    background_references: list[BackgroundReference] = Field(max_length=40)
    originality_notes: str = Field(min_length=1, max_length=3000)
    marking_basis: Literal["suggested", "source_supported"]


class PairOutput(Strict):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=4000)
    pair: QuestionPair | None
    assets: list[GraphSpec] = Field(max_length=12)


class BlindAnswer(Strict):
    part_id: str
    reasoning: list[ContentBlock] = Field(min_length=1, max_length=40)
    final_answer: list[ContentBlock] = Field(min_length=1, max_length=20)


class BlindOutput(Strict):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=4000)
    answers: list[BlindAnswer] = Field(max_length=12)


class ReviewCheck(Strict):
    question_id: str
    category: Literal["clarity", "conditions", "methods", "reasoning", "difficulty", "preferences", "originality", "blind_agreement", "math_relevance", "source_alignment"]
    result: CheckStatus
    rationale: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(max_length=40)


class RepairRequest(Strict):
    target_ids: list[str] = Field(min_length=1, max_length=4)
    issue_codes: list[str] = Field(min_length=1, max_length=30)
    instructions: str = Field(min_length=1, max_length=4000)


class SemanticOutput(Strict):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=4000)
    checks: list[ReviewCheck] = Field(max_length=100)
    repair_requests: list[RepairRequest] = Field(max_length=4)


def schema_hashes():
    from app.core.idempotency import digest
    return {name: digest(schema.model_json_schema()) for name, schema in
            (("pair", PairOutput), ("blind", BlindOutput), ("semantic", SemanticOutput))}
