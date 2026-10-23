import itertools
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.errors import DomainError
from app.courses.schemas import TEACHING_ROLES

ResponseType = Literal["calculation", "explanation_proof", "applied_optimisation"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationConfig(Strict):
    course_version_id: UUID
    mode: Literal["chapter_practice"]
    topic_ids: list[str] = Field(min_length=1, max_length=30)
    difficulty: Literal["foundation", "exam_standard", "challenge"]
    main_question_count: int = Field(ge=2, le=4, strict=True)
    question_types: list[ResponseType] = Field(min_length=1, max_length=3)


class Selection(Strict):
    mode: Literal["all", "choose"]
    choose_count: int = Field(ge=1, le=4, strict=True)


class Section(Strict):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    question_ids: list[str] = Field(min_length=1, max_length=4)
    selection: Selection


SCHEMA_VERSION = "blueprint-v2"
LEGACY_SCHEMA_VERSION = "blueprint-v1"


class Part(Strict):
    """blueprint-v2: label is the part's letter only; focus says what the part assesses."""
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(pattern=r"^[a-z]$")
    focus: str = Field(min_length=1, max_length=200)
    response_type: ResponseType
    marks: float = Field(gt=0, le=100, multiple_of=0.5, strict=True)
    knowledge_ids: list[str] = Field(min_length=1, max_length=30)
    asset_needs: list[Literal["function_graph", "data_table"]] = Field(max_length=2)


class Question(Strict):
    id: str = Field(min_length=1, max_length=80)
    number: int = Field(ge=1, le=4, strict=True)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1500)
    knowledge_ids: list[str] = Field(min_length=1, max_length=30)
    parts: list[Part] = Field(min_length=1, max_length=12)
    evidence_ids: list[str] = Field(min_length=1, max_length=40)


class PartV1(Strict):
    """blueprint-v1, kept so earlier blueprints stay readable, editable and confirmable."""
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=30)
    response_type: ResponseType
    marks: float = Field(gt=0, le=100, multiple_of=0.5, strict=True)
    knowledge_ids: list[str] = Field(min_length=1, max_length=30)
    asset_needs: list[Literal["function_graph", "data_table"]] = Field(max_length=2)


class QuestionV1(Question):
    parts: list[PartV1] = Field(min_length=1, max_length=12)


class Coverage(Strict):
    knowledge_id: str
    question_ids: list[str]


class BlueprintPayload(Strict):
    sections: list[Section] = Field(min_length=1, max_length=4)
    questions: list[Question] = Field(min_length=2, max_length=4)
    main_question_count: int = Field(ge=2, le=4, strict=True)
    subquestion_count: int = Field(ge=2, le=48, strict=True)
    subquestion_count_locked: bool
    printed_marks: float = Field(gt=0, le=4800)
    attempt_marks: float = Field(gt=0, le=4800)
    suggested_minutes: int = Field(ge=5, le=240, strict=True)
    coverage: list[Coverage]
    differences: list[str] = Field(max_length=20)
    calibration: Literal["historical_reference", "uncalibrated"]


class BlueprintPayloadV1(BlueprintPayload):
    questions: list[QuestionV1] = Field(min_length=2, max_length=4)


def schema_version_of(payload):
    """v2 when every part carries focus, v1 when none does; a mixture is invalid."""
    parts = [p for q in (payload.get("questions") or []) if isinstance(q, dict) for p in (q.get("parts") or []) if isinstance(p, dict)]
    with_focus = {"focus" in p for p in parts}
    if with_focus == {False}:
        return LEGACY_SCHEMA_VERSION
    if with_focus == {True} or not parts:
        return SCHEMA_VERSION
    raise DomainError("BLUEPRINT_SCHEMA_INVALID", "Every part needs a focus, or none for an earlier structure.", status=400)


class PlanningOutput(Strict):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=4000)
    blueprint: BlueprintPayload | None


def parse_schema(schema, data, code):
    try:
        return schema.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        error = DomainError(code, "Check the highlighted fields before continuing.", status=400)
        error.payload["field_errors"] = {".".join(map(str, e["loc"])): e["msg"] for e in exc.errors(include_input=False)}
        raise error from None


def unique(values):
    if len(values) != len(set(values)):
        raise DomainError("DUPLICATE_IDENTIFIER", "Each identifier or selection must appear once.", status=400)


def validate_config(data, course_payload, evidence):
    config = parse_schema(GenerationConfig, data, "CONFIG_SCHEMA_INVALID")
    unique(config["topic_ids"])
    unique(config["question_types"])
    nodes = {n["id"]: n for n in course_payload["knowledge_nodes"]}
    sources = {e["id"]: e for e in evidence}
    for kid in config["topic_ids"]:
        node = nodes.get(kid)
        if node is None:
            raise DomainError("KNOWLEDGE_OUTSIDE_SELECTION", "Choose knowledge from this confirmed course version.", status=400)
        if node["readiness"] != "supported" or not any(
            set(sources.get(eid, {}).get("roles", [])) & TEACHING_ROLES for eid in node["evidence_ids"]
        ):
            raise DomainError("SELECTED_KNOWLEDGE_NOT_READY", "Selected knowledge needs teaching evidence. Return to Course profile.")
    for claim in course_payload.get("scope_claims", []):
        if claim["applicability"] in ("current_exam", "round1_practice") and claim["disposition"] in ("exclude", "needs_review"):
            if not claim["subject_ids"] or set(claim["subject_ids"]) & set(config["topic_ids"]):
                raise DomainError("SELECTED_KNOWLEDGE_EXCLUDED", "This selection conflicts with the confirmed course scope.")
    return config


def summarize(payload):
    """Computed totals, including choice feasibility. Never trust model arithmetic."""
    questions = payload["questions"]
    by_id = {q["id"]: q for q in questions}
    marks = {qid: sum(p["marks"] for p in q["parts"]) for qid, q in by_id.items()}
    assigned = [qid for s in payload["sections"] for qid in s["question_ids"]]
    unique(assigned)
    if set(assigned) != set(by_id):
        raise DomainError("SECTION_MEMBERSHIP_INVALID", "Each question must belong to exactly one section.", status=400)
    attempt_marks = 0
    for section in payload["sections"]:
        rule = section["selection"]
        count = len(section["question_ids"])
        if rule["choose_count"] > count or rule["mode"] == "all" and rule["choose_count"] != count:
            raise DomainError("INVALID_SELECTION", "Answer-all must include every question; choose counts cannot exceed the section size.", status=400)
        totals = {sum(marks[qid] for qid in choice) for choice in itertools.combinations(section["question_ids"], rule["choose_count"])}
        if len(totals) != 1:
            raise DomainError("UNEQUAL_CHOICE_MARKS", "Every permitted choice must have the same total marks.", status=400)
        attempt_marks += totals.pop()
    coverage = {}
    for q in questions:
        for kid in {k for p in q["parts"] for k in p["knowledge_ids"]}:
            coverage.setdefault(kid, []).append(q["id"])
    return {"main_question_count": len(questions), "subquestion_count": sum(len(q["parts"]) for q in questions),
        "printed_marks": sum(marks.values()), "attempt_marks": attempt_marks,
        "coverage": [{"knowledge_id": k, "question_ids": v} for k, v in sorted(coverage.items())]}


def validate_blueprint(config, payload, course_payload, evidence, *, recalculate=False, schema_version=None):
    """schema_version pins the expected version: a model plan must be v2, an edit keeps its predecessor's."""
    config = validate_config(config, course_payload, evidence)
    version = schema_version_of(payload)
    if schema_version and version != schema_version:
        raise DomainError("BLUEPRINT_SCHEMA_VERSION_MISMATCH", "The structure format does not match its saved version.", status=400)
    plan = parse_schema(BlueprintPayload if version == SCHEMA_VERSION else BlueprintPayloadV1, payload, "BLUEPRINT_SCHEMA_INVALID")
    if version == SCHEMA_VERSION:
        for q in plan["questions"]:
            if [p["label"] for p in q["parts"]] != [chr(97 + i) for i in range(len(q["parts"]))]:
                raise DomainError("PART_LABELS_INVALID", "Label each question's parts a, b, c … in order.", status=400)
            if any(not p["focus"].strip() for p in q["parts"]):
                raise DomainError("PART_FOCUS_REQUIRED", "Describe what each part assesses.", status=400)
    questions = plan["questions"]
    if len(questions) != config["main_question_count"]:
        raise DomainError("MAIN_QUESTION_COUNT_MISMATCH", "The plan must match the requested main-question count.", status=400)
    if [q["number"] for q in questions] != list(range(1, len(questions) + 1)):
        raise DomainError("QUESTION_NUMBER_INVALID", "Question numbers must run consecutively from 1.", status=400)
    unique([s["id"] for s in plan["sections"]] + [q["id"] for q in questions] + [p["id"] for q in questions for p in q["parts"]])
    sources = {e["id"] for e in evidence}
    teaching_sources = {e["id"] for e in evidence if set(e.get("roles", [])) & TEACHING_ROLES}
    nodes = {n["id"]: n for n in course_payload["knowledge_nodes"]}
    for q in questions:
        unique([p["label"] for p in q["parts"]])
        unique(q["evidence_ids"])
        if not set(q["evidence_ids"]) <= sources:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "A blueprint source is outside the frozen course evidence.", status=400)
        part_knowledge = {kid for p in q["parts"] for kid in p["knowledge_ids"]}
        if not (set(q["knowledge_ids"]) | part_knowledge) <= set(config["topic_ids"]):
            raise DomainError("KNOWLEDGE_OUTSIDE_SELECTION", "The plan uses knowledge outside this practice selection.", status=400)
        if set(q["knowledge_ids"]) != part_knowledge:
            raise DomainError("QUESTION_COVERAGE_MISMATCH", "Question knowledge must match its parts.", status=400)
        if any(not (set(nodes[k]["evidence_ids"]) & set(q["evidence_ids"]) & teaching_sources) for k in part_knowledge):
            raise DomainError("KNOWLEDGE_EVIDENCE_MISSING", "Each target needs an associated frozen teaching source.", status=400)
        if any(p["response_type"] not in config["question_types"] for p in q["parts"]):
            raise DomainError("QUESTION_TYPE_OUTSIDE_SELECTION", "The plan includes an unselected response type.", status=400)
    totals = summarize(plan)
    if not recalculate:
        if any(plan[k] != totals[k] for k in ("printed_marks", "attempt_marks")):
            raise DomainError("MARKS_MISMATCH", "Printed and attempt marks do not match the sum of parts.", status=400)
        if any(plan[k] != totals[k] for k in ("main_question_count", "subquestion_count")):
            raise DomainError("QUESTION_COUNT_MISMATCH", "Declared question counts do not match the plan.", status=400)
        canonical = lambda items: sorted((i["knowledge_id"], sorted(i["question_ids"])) for i in items)
        if canonical(plan["coverage"]) != canonical(totals["coverage"]):
            raise DomainError("COVERAGE_MISMATCH", "Declared coverage does not match the planned parts.", status=400)
    plan.update(totals)
    by_id = {q["id"]: q for q in questions}
    choices = [list(itertools.combinations(s["question_ids"], s["selection"]["choose_count"])) for s in plan["sections"]]
    for attempt in itertools.product(*choices):
        parts = [p for group in attempt for qid in group for p in by_id[qid]["parts"]]
        if {p["response_type"] for p in parts} != set(config["question_types"]):
            raise DomainError("QUESTION_TYPE_MISSING", "Every permitted attempt must cover all selected question types.", status=400)
        if {k for p in parts for k in p["knowledge_ids"]} != set(config["topic_ids"]):
            raise DomainError("SELECTED_KNOWLEDGE_MISSING", "Every permitted attempt must cover the selected knowledge.", status=400)
    if plan["calibration"] == "historical_reference" and not course_payload.get("historical_style"):
        raise DomainError("CALIBRATION_UNSUPPORTED", "This course version has no historical exam reference.", status=400)
    return plan
