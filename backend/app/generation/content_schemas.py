"""Restricted paired-content and review contracts. No model-authored executable code."""
from typing import Literal
from pydantic import Field
from .schemas import Strict, ResponseType
from app.capabilities.symbolic.schemas import Expression, Domain, MathCheckSpec, SymbolicCheck

CheckStatus = Literal["pass", "fail", "not_checked", "inconclusive", "not_applicable"]


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
    checks: list[SymbolicCheck] = Field(max_length=20)


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
    category: Literal["clarity", "conditions", "methods", "reasoning", "difficulty", "preferences", "blind_agreement", "math_relevance", "source_alignment", "paper_consistency", "wording", "alternative_methods", "difficulty_detail"]
    result: CheckStatus
    rationale: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(max_length=40)


class RepairRequest(Strict):
    target_ids: list[str] = Field(min_length=1, max_length=4)
    issue_codes: list[str] = Field(min_length=1, max_length=30)
    instructions: str = Field(min_length=1, max_length=4000)


class PartOverlap(Strict):
    """Facts about two parts from different questions; deliberately no duplicate or pass field."""
    part_a: str = Field(min_length=1, max_length=80)
    part_b: str = Field(min_length=1, max_length=80)
    same_stimulus: bool
    stimulus_basis: str = Field(min_length=1, max_length=1000)
    conclusion_a: str = Field(min_length=1, max_length=600)
    conclusion_b: str = Field(min_length=1, max_length=600)
    same_conclusion: bool



class SourceOverlap(Strict):
    """Compact observations; application code decides whether a source was copied."""
    subpart_id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    same_stimulus: bool | None
    same_conclusion: bool | None
    note: str | None = Field(max_length=300)


class SemanticOutput(Strict):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=4000)
    checks: list[ReviewCheck] = Field(max_length=100)
    intra_paper_overlaps: list[PartOverlap] = Field(max_length=30)
    source_overlaps: list[SourceOverlap] = Field(max_length=100)
    repair_requests: list[RepairRequest] = Field(max_length=4)


def schema_hashes():
    from app.core.idempotency import digest
    return {name: digest(schema.model_json_schema()) for name, schema in
            (("pair", PairOutput), ("blind", BlindOutput), ("semantic", SemanticOutput))}
