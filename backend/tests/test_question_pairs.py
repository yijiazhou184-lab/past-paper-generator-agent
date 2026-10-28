import copy
import pytest
from app.generation.content_schemas import PairOutput
from app.generation.content_validation import validate_group
from app.generation.content_fixtures import fixture_pair
from app.generation.assets import render_graph
from app.generation.expressions import expression
from app.core.errors import DomainError
from test_generation_preflight import prepare
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def test_pair_contract_and_marking(course, planned):
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]["blueprint"]
    payload = fixture_pair(q)
    PairOutput.model_validate(payload)
    assert validate_group(q, payload, context)["pair"]["question_id"] == q["id"]
    for mutate in ("missing", "duplicate", "marks", "score"):
        bad = copy.deepcopy(payload)
        if mutate == "missing": bad["pair"]["answers"].pop()
        if mutate == "duplicate": bad["pair"]["parts"].append(bad["pair"]["parts"][0])
        if mutate == "marks": bad["pair"]["parts"][0]["marks"] += 1
        if mutate == "score": bad["pair"]["answers"][0]["marking_points"].append(bad["pair"]["answers"][0]["marking_points"][0])
        with pytest.raises(DomainError):
            validate_group(q, bad, context)


def test_alternative_groups_are_not_double_counted(course, planned):
    _, context = prepare(course, planned)
    q = context["input"]["questions"][0]["blueprint"]
    payload = fixture_pair(q)
    points = payload["pair"]["answers"][0]["marking_points"]
    points[0]["alternative_group"] = "same-opportunity"
    points.append({**points[0], "id": "alternative"})
    validate_group(q, payload, context)
    points[1]["alternative_group"] = None
    with pytest.raises(DomainError):
        validate_group(q, payload, context)


def test_unsafe_ast_and_graph_refuse_code():
    with pytest.raises(ValueError):
        expression({"op": "variable", "value": "__import__('os')", "args": []})
    with pytest.raises(ValueError):
        expression({"op": "pow", "value": None, "args": [
            {"op":"variable","value":"x","args":[]}, {"op":"number","value":"9999999","args":[]}]})
    with pytest.raises(ValueError):
        render_graph({"kind":"function_graph","id":"unsafe","expression":{"op":"eval","value":"x","args":[]},
                      "x_min":-2,"x_max":2,"y_min":-2,"y_max":2,"samples":200,"x_label":"x","y_label":"y","alt":"unsafe"})


def test_graph_is_bounded_and_escapes_labels():
    result=render_graph({"kind":"function_graph","id":"g","expression":{"op":"variable","value":"x","args":[]},
        "x_min":-2,"x_max":2,"y_min":-2,"y_max":2,"samples":100,"x_label":"<script>","y_label":"y","alt":"x"})
    assert "<script>" not in result["svg"]
    assert "&lt;script&gt;" in result["svg"]
    assert result["sha256"] and "<path" in result["svg"]


def test_nested_powers_cannot_bypass_complexity_limit():
    def power(base):
        return {"op":"pow","value":None,"args":[base,{"op":"number","value":"12","args":[]}]}
    with pytest.raises(ValueError, match="Combined power"):
        expression(power(power({"op":"variable","value":"x","args":[]})))
    with pytest.raises(ValueError, match="excessive numeric"):
        expression(power(power({"op":"number","value":"99999999","args":[]})))
