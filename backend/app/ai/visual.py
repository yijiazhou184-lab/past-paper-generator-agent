"""Subject-neutral page-image transcription contract. Results are model candidates, never verification."""
from pathlib import Path
from typing import Literal
from pydantic import ValidationError
from app.core.errors import DomainError
from .page_review import StrictModel, Finding

PROMPT_VERSION = "r1-visual-transcription-1"
SCHEMA_VERSION = "r1-visual-transcription-1"
LEGACY_SCHEMA_VERSION = "legacy:r1-page-review-1"
INSTRUCTIONS = (Path(__file__).parent / "prompts/visual_transcription.md").read_text(encoding="utf-8")


class Locator(StrictModel):
    kind: Literal["pdf_page", "slide", "section"]
    value: str
    bbox: list[float] | None


class VisualSource(StrictModel):
    evidence_id: str
    material_version_id: str
    parse_version_id: str
    physical_page: int
    blob_sha256: str
    parse_content_hash: str
    locator: Locator


class TableRow(StrictModel):
    cells: list[str]


class Axis(StrictModel):
    name: str
    label_as_printed: str
    scale_or_range: str | None


class Series(StrictModel):
    name: str
    description: str


class LabelledValue(StrictModel):
    label: str
    value_as_printed: str


class Relation(StrictModel):
    subject: str
    relation: str
    object: str


class VisualItem(StrictModel):
    kind: Literal["formula", "table", "chart", "diagram", "image_text", "other"]
    location: str
    legibility: Literal["readable", "uncertain", "unreadable"]
    value_origin: Literal["native_data", "read_from_image", "not_applicable"]
    latex_as_printed: str | None
    columns: list[str] | None
    rows: list[TableRow] | None
    units: str | None
    axes: list[Axis] | None
    series: list[Series] | None
    labelled_values: list[LabelledValue] | None
    elements: list[str] | None
    relations: list[Relation] | None
    text: str | None


class VisualTranscriptionOutput(StrictModel):
    source: VisualSource
    status: Literal["transcribed", "partially_readable", "unsupported_input", "unable_to_determine"]
    page_title: str
    faithful_transcription: str
    items: list[VisualItem]
    findings: list[Finding]
    teaching_use: str
    unresolved: list[str]


# The fields that carry the content of each kind; an item without them transcribes nothing.
REQUIRED_CONTENT = {"formula": ("latex_as_printed",), "table": ("rows",), "chart": ("axes",),
                    "diagram": ("elements",), "image_text": ("text",), "other": ("text",)}


def check_transcription(payload, expected_source):
    """Business rules the JSON schema cannot express. Violations reject the page, never repair it."""
    try:
        output = VisualTranscriptionOutput.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        raise DomainError("VISUAL_SCHEMA_INVALID", "The page transcription does not match its schema.")
    if output["source"] != expected_source:
        raise DomainError("MODEL_SOURCE_MISMATCH", "The transcription names a different source.")
    for item in output["items"]:
        # Only an image was supplied; no value in this route can come from native document data.
        if item["value_origin"] == "native_data":
            raise DomainError("VISUAL_VALUE_ORIGIN_INVALID", "Values read from a page image must be marked read_from_image.")
        if item["legibility"] != "unreadable" and not all(item[f] for f in REQUIRED_CONTENT[item["kind"]]):
            raise DomainError("VISUAL_ITEM_EMPTY", f"A readable {item['kind']} item has no transcribed content.")
    return output


def legacy_to_visual(review):
    """Read-only view of a batch-one PageReview in the transcription shape; the original stays unchanged."""
    status = {"reviewed": "transcribed", "insufficient_information": "partially_readable",
              "unable_to_determine": "unable_to_determine"}[review["status"]]
    source = {**review["source"], "locator": {"kind": "pdf_page", "value": str(review["source"]["physical_page"]), "bbox": None}}
    items = [{"kind": "formula", "location": m["location_on_page"], "legibility": m["legibility"],
              "value_origin": "not_applicable", "latex_as_printed": m["as_printed_latex"], "columns": None,
              "rows": None, "units": None, "axes": None, "series": None, "labelled_values": None,
              "elements": None, "relations": None, "text": None} for m in review["math_items"]]
    return VisualTranscriptionOutput.model_validate({
        "source": source, "status": status, "page_title": review["page_title"],
        "faithful_transcription": review["faithful_transcription"], "items": items,
        "findings": review["findings"], "teaching_use": review["teaching_use"],
        "unresolved": review["unresolved"]}).model_dump(mode="json")
