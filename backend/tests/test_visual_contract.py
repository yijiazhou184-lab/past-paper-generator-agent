import copy
import pytest
from django.db import DatabaseError, transaction
from app.ai.visual import VisualTranscriptionOutput, check_transcription, legacy_to_visual
from app.core.errors import DomainError
from app.materials.routing import route_page, RULE_VERSION


def block(kind, text="", l=0, t=100, r=100, b=0):
    return {"kind": kind, "text": text, "bbox": {"l": l, "t": t, "r": r, "b": b, "coord_origin": "BOTTOMLEFT"}}


PROSE = "The derivative measures the instantaneous rate of change of a function at a point in its domain."


def test_plain_prose_stays_on_text_route():
    decision = route_page(3, [block("text", PROSE), block("section_header", "Derivatives")], PROSE)
    assert decision == {"locator": {"kind": "pdf_page", "value": "3", "bbox": None}, "route": "text",
                        "signals": [], "rule_version": RULE_VERSION}


@pytest.mark.parametrize("blocks,text,signal", [
    ([block("text", PROSE), block("formula")], PROSE, "empty_formula_region"),
    ([block("text", PROSE), block("picture", r=300, t=300)], PROSE, "large_figure"),
    ([block("text", PROSE), block("table", "a | b")], PROSE, "table_region"),
    ([block("section_header", "Lecture 2")], "Lecture 2", "low_text_density"),
    ([block("picture", r=595, t=842)], "", "full_page_image"),
])
def test_layout_signals_send_page_to_visual_route(blocks, text, signal):
    decision = route_page(1, blocks, text)
    assert decision["route"] == "visual" and signal in decision["signals"]


def test_small_logo_and_transcribed_formula_do_not_trigger():
    blocks = [block("text", PROSE), block("picture", r=60, t=60), block("formula", "f'(x) = 2x")]
    assert route_page(1, blocks, PROSE)["route"] == "text"


def test_figure_without_box_is_treated_as_large():
    assert "large_figure" in route_page(1, [block("text", PROSE), {"kind": "picture", "text": ""}], PROSE)["signals"]


def test_model_request_upgrades_text_page_and_unknown_signal_is_rejected():
    decision = route_page(1, [block("text", PROSE)], PROSE, extra_signals=["model_requested"])
    assert decision["route"] == "visual" and decision["signals"] == ["model_requested"]
    with pytest.raises(ValueError):
        route_page(1, [], PROSE, extra_signals=["subject_is_maths"])


def strict_objects(schema):
    for definition in [schema, *schema.get("$defs", {}).values()]:
        if definition.get("type") == "object":
            yield definition


def test_schema_is_strict_for_structured_outputs():
    schema = VisualTranscriptionOutput.model_json_schema()
    for obj in strict_objects(schema):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


SOURCE = {"evidence_id": "e1", "material_version_id": "v1", "parse_version_id": "p1", "physical_page": 4,
          "blob_sha256": "b" * 64, "parse_content_hash": "c" * 64,
          "locator": {"kind": "pdf_page", "value": "4", "bbox": None}}
EMPTY = {k: None for k in ("latex_as_printed", "columns", "rows", "units", "axes", "series",
                           "labelled_values", "elements", "relations", "text")}


def transcription(**items):
    return {"source": copy.deepcopy(SOURCE), "status": "transcribed", "page_title": "Definition of the derivative",
            "faithful_transcription": r"f'(x) = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h}",
            "items": [{"kind": "formula", "location": "centre", "legibility": "readable",
                       "value_origin": "not_applicable", **EMPTY, "latex_as_printed": r"\lim_{h \to 0}", **items}],
            "findings": [], "teaching_use": "Definition", "unresolved": []}


def test_valid_transcription_passes_unchanged():
    assert check_transcription(transcription(), SOURCE) == transcription()


@pytest.mark.parametrize("mutate,code", [
    (lambda p: p["source"].update(physical_page=5), "MODEL_SOURCE_MISMATCH"),
    (lambda p: p["items"][0].update(value_origin="native_data"), "VISUAL_VALUE_ORIGIN_INVALID"),
    (lambda p: p["items"][0].update(latex_as_printed=None), "VISUAL_ITEM_EMPTY"),
    (lambda p: p["items"][0].pop("value_origin"), "VISUAL_SCHEMA_INVALID"),
    (lambda p: p.update(verified=True), "VISUAL_SCHEMA_INVALID"),
])
def test_invalid_transcriptions_are_rejected_not_repaired(mutate, code):
    payload = transcription()
    mutate(payload)
    with pytest.raises(DomainError, match=code):
        check_transcription(payload, SOURCE)


def test_unreadable_item_may_be_empty():
    payload = transcription(latex_as_printed=None, legibility="unreadable")
    assert check_transcription(payload, SOURCE)["items"][0]["latex_as_printed"] is None


def test_legacy_page_review_maps_to_formula_items():
    review = {"source": {k: v for k, v in SOURCE.items() if k != "locator"}, "status": "reviewed",
              "page_title": "Kinks", "faithful_transcription": "f(x)=|x|",
              "math_items": [{"as_printed_latex": "|x|", "location_on_page": "top", "legibility": "readable"}],
              "findings": [{"kind": "parser_loss", "observation": "Formula missing", "evidence_on_page": "top",
                            "suggested_interpretation": None}], "teaching_use": "Example", "unresolved": []}
    mapped = legacy_to_visual(review)
    assert mapped["source"] == SOURCE and mapped["status"] == "transcribed"
    assert mapped["items"][0]["kind"] == "formula" and mapped["items"][0]["latex_as_printed"] == "|x|"
    assert mapped["findings"] == review["findings"]


def test_database_rejects_update_of_transcription(course, pdf_bytes):
    from app.materials.models import Evidence, ParseVersion, MaterialBlob, Material, MaterialVersion, VisualTranscription
    blob = MaterialBlob.objects.create(owner=course.owner, sha256="b" * 64, bytes=1, pages=1, storage_key="x")
    version = MaterialVersion.objects.create(material=Material.objects.create(course=course), blob=blob, original_filename="x.pdf")
    parse = ParseVersion.objects.create(blob=blob, parser_version="t", config_hash="h", state="ready", content_hash="c" * 64)
    evidence = Evidence.objects.create(material_version=version, parse_version=parse, physical_page=1, text="")
    row = VisualTranscription.objects.create(evidence=evidence, parse_content_hash="c" * 64, image_sha256="i" * 64,
        model="fixture", prompt_version="p", schema_version="s", route={}, status="transcribed",
        payload=transcription(), origin="fixture")
    with pytest.raises(DatabaseError), transaction.atomic():
        VisualTranscription.objects.filter(pk=row.pk).update(status="tampered")
