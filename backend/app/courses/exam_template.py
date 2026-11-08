"""Editable, course-wide exam structure with versioned material references."""
import copy
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import DomainError
from app.materials.models import MaterialVersion
from .models import CourseDraft
from .schemas import ResponseType


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExamSelection(Strict):
    mode: Literal["all", "choose"]
    choose_count: int = Field(ge=1, strict=True)


class ExamSection(Strict):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    question_marks: list[float] = Field(min_length=1, max_length=40)
    selection: ExamSelection


class ExamSource(Strict):
    material_version_id: UUID
    physical_page: int = Field(ge=1, strict=True)
    classification_revision: int | None = None


class ExamTemplate(Strict):
    sections: list[ExamSection] = Field(min_length=1, max_length=16)
    duration_minutes: int = Field(ge=5, le=240, strict=True)
    question_types: list[ResponseType] = Field(min_length=1, max_length=3)
    permitted_aids: str | None = Field(default=None, max_length=500)
    origin: Literal["current_instruction", "historical_reference", "user_entry"]
    sources: list[ExamSource] = Field(default_factory=list, max_length=12)


def invalid(code, message, field):
    error = DomainError(code, message, status=400)
    error.payload["field_errors"] = {field: message}
    return error


def validate_exam_template(template, course, *, for_confirmation=False):
    try:
        value = ExamTemplate.model_validate(template).model_dump(mode="json")
    except ValidationError as exc:
        error = DomainError("EXAM_TEMPLATE_INVALID", "Review the highlighted template fields.", status=400)
        error.payload["field_errors"] = {".".join(map(str, e["loc"])): e["msg"] for e in exc.errors(include_input=False)}
        raise error from None
    if len({s["id"] for s in value["sections"]}) != len(value["sections"]):
        raise invalid("EXAM_TEMPLATE_INVALID", "Section identifiers must be unique.", "sections")
    if len(set(value["question_types"])) != len(value["question_types"]):
        raise invalid("EXAM_TEMPLATE_INVALID", "Each question type must be selected once.", "question_types")
    for i, section in enumerate(value["sections"]):
        marks, selection = section["question_marks"], section["selection"]
        path = f"sections.{i}"
        count = selection["choose_count"]
        if count > len(marks) or (selection["mode"] == "all") != (count == len(marks)):
            raise invalid("EXAM_TEMPLATE_SELECTION_INVALID", "Choose a valid number of questions for this section.", path + ".selection")
        if any(not (0 < mark <= 1200 and mark * 2 == int(mark * 2)) for mark in marks):
            raise invalid("EXAM_TEMPLATE_MARKS_INVALID", "Use positive whole or half marks for every question.", path + ".question_marks")
        if selection["mode"] == "choose" and len(set(marks)) != 1:
            raise invalid("EXAM_TEMPLATE_MARKS_INVALID", "All choices in this section must give the same attempt marks.", path + ".question_marks")
    roles, seen = set(), set()
    for i, source in enumerate(value["sources"]):
        ref = (source["material_version_id"], source["physical_page"])
        version = MaterialVersion.objects.select_related("blob").filter(pk=ref[0], material__course=course).first()
        current = version and not MaterialVersion.objects.filter(material_id=version.material_id, number__gt=version.number).exists()
        if ref in seen or not current or ref[1] > version.blob.pages:
            raise invalid("EXAM_TEMPLATE_SOURCE_INVALID", "Select a unique page in a current material version for this course.", f"sources.{i}")
        if for_confirmation and source["classification_revision"] != version.classification_revision:
            raise invalid("EXAM_TEMPLATE_SOURCE_CHANGED", "Review the source's updated classification and save the template again.", f"sources.{i}")
        source["classification_revision"] = version.classification_revision
        roles.update(version.roles)
        seen.add(ref)
    if value["origin"] == "historical_reference" and "past_paper" not in roles:
        raise invalid("EXAM_TEMPLATE_SOURCE_INVALID", "A historical reference requires a past paper source.", "sources")
    if value["origin"] == "current_instruction":
        ids = [s["material_version_id"] for s in value["sources"]]
        if not any("exam_scope" in version.roles and "past_paper" not in version.roles
                   for version in MaterialVersion.objects.filter(pk__in=ids, material__course=course)):
            raise invalid("EXAM_TEMPLATE_SOURCE_INVALID", "Link a current exam instruction to use this source category.", "sources")
    return value


def current_exam_template(draft, latest, *, include=False):
    record = draft.exam_template
    if not record:
        if include:
            raise invalid("EXAM_TEMPLATE_REQUIRED", "Save an exam template before confirming it.", "exam_template")
        return None
    prior = latest.frozen_payload.get("exam_template") if latest else None
    if not include and (not prior or prior["template_revision"] != record["revision"]
                        or latest.frozen_payload.get("target_exam") != draft.payload.get("target_exam")):
        return None
    try:
        value = validate_exam_template(record["value"], draft.course, for_confirmation=True)
    except DomainError:
        if include:
            raise
        return None
    return {**value, "template_revision": record["revision"],
            "calibration": "current_reference" if value["origin"] == "current_instruction" else "uncalibrated"}


def exam_template_view(draft, latest):
    if not draft.exam_template:
        return None, "not_configured"
    value = copy.deepcopy(draft.exam_template["value"])
    return value, "confirmed" if current_exam_template(draft, latest) else "changes_pending"


def exam_template_blocker(version, draft):
    template = version.frozen_payload.get("exam_template")
    if not template:
        return "Confirm an exam template in Course profile."
    if not draft or current_exam_template(draft, version) != template:
        return "Review and confirm the changed exam template in Course profile."
    count = sum(len(s["question_marks"]) for s in template["sections"])
    if not 2 <= count <= 4 or len(template["sections"]) > 4:
        return "The template is saved. Mock exams currently support 2 to 4 main questions in up to 4 sections."
    return ""


def require_current_exam_template(version):
    draft = CourseDraft.objects.filter(course_id=version.course_id).select_related("course").first()
    blocker = exam_template_blocker(version, draft)
    if blocker:
        raise DomainError("EXAM_TEMPLATE_NOT_READY", blocker)
