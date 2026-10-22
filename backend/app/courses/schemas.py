"""AI 1 output schema and independent provenance/reference checks."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.errors import DomainError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetExam(StrictModel):
    label: str | None = Field(max_length=200)
    academic_year: str | None = Field(max_length=40)


class KnowledgeNode(StrictModel):
    id: str = Field(max_length=100)
    title: str = Field(min_length=1, max_length=200)
    parent_id: str | None
    depth: int = Field(ge=1, le=5)
    prerequisite_ids: list[str] = Field(max_length=30)
    method_ids: list[str] = Field(max_length=30)
    evidence_ids: list[str] = Field(max_length=36)
    readiness: Literal["supported", "partial", "unsupported"]
    requirements: str = Field(max_length=2000)


class Claim(StrictModel):
    id: str = Field(max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    subject_ids: list[str] = Field(max_length=40)
    applicability: Literal["teaching", "current_exam", "coursework_1", "historical_mock", "round1_practice"]
    provenance: Literal["course_material", "assessment_document", "historical_paper", "user_statement", "personal_note", "inference", "external_source"]
    authority_status: Literal["attributed", "unverified", "verified"]
    evidence_ids: list[str] = Field(max_length=36)
    statement_ids: list[str] = Field(max_length=30)
    status: Literal["supported", "declared", "inferred", "disputed", "unknown"]
    disposition: Literal["include", "exclude", "context", "unknown"]


class TemplateSection(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    main_questions: int = Field(ge=1, le=4)
    marks_per_question: int = Field(ge=1, le=100)
    selection: Literal["all", "choose"]
    choose_count: int = Field(ge=1, le=4)


class TemplateSummary(StrictModel):
    label: Literal["suggested"]
    calibration: Literal["not_calibrated_to_current_exam"]
    question_types: list[Literal["calculation", "explanation_proof", "applied_optimisation"]] = Field(min_length=1, max_length=3)
    sections: list[TemplateSection] = Field(min_length=1, max_length=4)
    duration_minutes: int = Field(ge=5, le=240)
    total_marks: int = Field(ge=1, le=200)
    rationale: str = Field(max_length=2000)


class Issue(StrictModel):
    id: str = Field(max_length=100)
    code: str = Field(max_length=80)
    severity: Literal["info", "warning", "blocking"]
    affected_ids: list[str] = Field(max_length=40)
    explanation: str = Field(max_length=2000)
    evidence_ids: list[str] = Field(max_length=36)
    suggested_action: str | None = Field(max_length=1000)


class Clarification(StrictModel):
    id: str = Field(max_length=100)
    question: str = Field(max_length=1000)
    reason: str = Field(max_length=2000)
    affected_ids: list[str] = Field(max_length=40)
    impact: Literal["informational", "needs_confirmation", "blocks_selected_scope"]
    suggested_answers: list[str] = Field(max_length=4)
    resolves_issue_ids: list[str] = Field(max_length=30)
    status: Literal["open", "answered", "superseded"]


class CourseDraftPayload(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    target_exam: TargetExam
    knowledge_nodes: list[KnowledgeNode] = Field(max_length=40)
    scope_claims: list[Claim] = Field(max_length=40)
    method_rules: list[Claim] = Field(max_length=40)
    historical_style: list[Claim] = Field(max_length=20)
    template_suggestion: TemplateSummary | None
    issues: list[Issue] = Field(max_length=40)
    clarifications: list[Clarification] = Field(max_length=30)


class AnalysisOutput(StrictModel):
    status: Literal["complete", "needs_info", "unable_to_determine", "not_checked"]
    explanation: str = Field(max_length=2000)
    draft: CourseDraftPayload | None


TEACHING_ROLES = {"lecture", "summary", "seminar", "revision", "teaching"}


def validate_template(template):
    if template is None:
        return
    total = 0
    for section in template["sections"]:
        if section["choose_count"] > section["main_questions"] or (section["selection"] == "all" and section["choose_count"] != section["main_questions"]):
            raise DomainError("TEMPLATE_SELECTION_INVALID", "Check how many questions must be answered.", status=400)
        total += section["marks_per_question"] * section["choose_count"]
    if total != template["total_marks"]:
        raise DomainError("TEMPLATE_MARKS_INVALID", "Section marks do not add up to the total.", status=400)
    if not 2 <= sum(s["main_questions"] for s in template["sections"]) <= 4:
        raise DomainError("TEMPLATE_QUESTION_COUNT_INVALID", "Round 1 supports 2–4 main questions.", status=400)


def validate_payload(raw, context):
    try:
        payload = CourseDraftPayload.model_validate(raw).model_dump(mode="json")
    except ValidationError:
        raise DomainError("COURSE_SCHEMA_INVALID", "The course draft does not match its schema.", status=400)
    evidence = {e["id"]: e for e in context["evidence"]}
    statements = {s["id"] for s in context["statements"]}
    nodes = {n["id"] for n in payload["knowledge_nodes"]}
    claims = payload["scope_claims"] + payload["method_rules"] + payload["historical_style"]
    methods = {n["id"] for n in payload["method_rules"]}
    all_items = payload["knowledge_nodes"] + claims + payload["issues"] + payload["clarifications"]
    ids = [item["id"] for item in all_items]
    if len(ids) != len(set(ids)):
        raise DomainError("DUPLICATE_OUTPUT_ID")
    for item in all_items:
        if set(item.get("evidence_ids", [])) - evidence.keys():
            raise DomainError("EVIDENCE_REFERENCE_INVALID")
    for node in payload["knowledge_nodes"]:
        if (set(node["prerequisite_ids"]) - nodes or set(node["method_ids"]) - methods
                or (node["parent_id"] and node["parent_id"] not in nodes)):
            raise DomainError("KNOWLEDGE_REFERENCE_INVALID")
        if not any(TEACHING_ROLES.intersection(evidence[e]["roles"]) for e in node["evidence_ids"]):
            node["readiness"] = "unsupported"
        seen, parent = {node["id"]}, node["parent_id"]
        by_id = {n["id"]: n for n in payload["knowledge_nodes"]}
        while parent:
            if parent in seen:
                raise DomainError("KNOWLEDGE_CYCLE")
            seen.add(parent)
            parent = by_id[parent]["parent_id"]
    for claim in claims:
        if set(claim["statement_ids"]) - statements or set(claim["subject_ids"]) - nodes:
            raise DomainError("CLAIM_REFERENCE_INVALID")
        if claim["authority_status"] == "verified":
            raise DomainError("AUTHORITY_PROMOTION_FORBIDDEN")
        provenance = claim["provenance"]
        if provenance == "user_statement":
            if not claim["statement_ids"] or claim["status"] not in ("declared", "unknown", "disputed"):
                raise DomainError("USER_PROVENANCE_INVALID")
        elif claim["statement_ids"]:
            raise DomainError("STATEMENT_AUTHORITY_PROMOTION_FORBIDDEN")
        if provenance not in ("user_statement", "inference") and not claim["evidence_ids"]:
            raise DomainError("CLAIM_SOURCE_REQUIRED")
        if provenance == "inference" and claim["status"] not in ("inferred", "unknown", "disputed"):
            raise DomainError("INFERENCE_STATUS_INVALID")
        codes = {evidence[e].get("material_code") for e in claim["evidence_ids"]}
        roles = {r for e in claim["evidence_ids"] for r in evidence[e].get("roles", [])}
        allowed_roles = {"course_material": TEACHING_ROLES | {"additional_questions", "other"},
            "assessment_document": {"assessment_brief", "assessment", "exam_scope"},
            "historical_paper": {"past_paper", "mark_scheme"}, "personal_note": {"personal_note", "notes"},
            "external_source": {"external_source"}}
        if provenance in allowed_roles and not roles.intersection(allowed_roles[provenance]):
            raise DomainError("SOURCE_PROVENANCE_MISMATCH")
        if "M46" in codes and claim["applicability"] == "current_exam":
            raise DomainError("ASSESSMENT_APPLICABILITY_INVALID")
        if provenance == "historical_paper" and claim["applicability"] != "historical_mock":
            raise DomainError("HISTORICAL_APPLICABILITY_INVALID")
        if codes.intersection({"M04", "M05"}) and provenance not in ("historical_paper", "inference"):
            raise DomainError("HISTORICAL_PROVENANCE_INVALID")
        if provenance == "course_material" and claim["applicability"] == "current_exam":
            raise DomainError("TEACHING_IS_NOT_EXAM_SCOPE")
    validate_template(payload["template_suggestion"])
    return payload
