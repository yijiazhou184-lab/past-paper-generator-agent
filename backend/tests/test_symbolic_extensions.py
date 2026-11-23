"""Course-independent regressions for the domain, limit and parameter capability gaps."""
import copy
import pytest
from app.capabilities.symbolic.math_worker import evaluate
from app.capabilities.symbolic.math_checks import check_math
from app.capabilities.symbolic.schemas import SymbolicCheck
from app.capabilities.symbolic.projection import compact_pair
from app.capabilities.generation import checker_contract, compose_prompts
from app.generation.checks import mathematical_checks, release_gate
from pydantic import TypeAdapter


def num(value):
    return {"op": "number", "value": str(value), "args": []}


def var(name="x"):
    return {"op": "variable", "value": name, "args": []}


def op(name, *args):
    return {"op": name, "value": None, "args": list(args)}


def domain(lower=None, upper=None, left=True, right=True):
    return {"lower": lower, "upper": upper, "left_open": left, "right_open": right}


def claim(kind, **kwargs):
    return {"id": "check", "part_id": "part", "role": "core", "rationale": "Synthetic regression",
            "kind": kind, "variable": "x", **kwargs}


def parameter_optimum(capacity="3"):
    x, a = var(), var("a")
    root = op("sqrt", a)
    objective = op("sub", op("mul", a, x), op("mul", num("1/3"), op("pow", x, num(3))))
    threshold = str(int(capacity)**2)
    return claim("parameter_optimum", expression=objective, domain=domain("0", capacity, False, False),
        parameter={"name": "a", "domain": domain("0", None)}, optimum="max", unique=True, branches=[
            {"parameter_domain": domain("0", threshold), "point": root,
             "value": op("mul", num("2/3"), a, root)},
            {"parameter_domain": domain(threshold, None, False), "point": num(capacity),
             "value": op("sub", op("mul", num(capacity), a), num(f"{int(capacity)**3}/3"))}])


def test_maximal_domain_is_complete_and_preserves_cancelled_holes():
    x = var()
    radical = op("sqrt", op("mul", x, op("sub", x, num(6))))
    spec = claim("maximal_domain", expression=radical,
                 expected_intervals=[domain(None, "0", True, False), domain("6", None, False, True)])
    assert check_math(spec)["result"] == "pass"
    spec["expected_intervals"] = [domain("6", None, False, True)]
    assert evaluate(spec)["result"] == "fail"
    spec.update(expression=op("div", x, x), expected_intervals=[domain()])
    assert evaluate(spec)["result"] == "fail"
    spec["expected_intervals"] = [domain(None, "0"), domain("0", None)]
    assert evaluate(spec)["result"] == "pass"


def test_domain_excludes_original_logarithm_boundary_even_after_cancellation():
    x = var()
    log = op("log", op("add", x, num(2)))
    spec = claim("maximal_domain", expression=op("sub", log, log), expected_intervals=[domain("-2", None)])
    assert evaluate(spec)["result"] == "pass"
    spec["expected_intervals"][0]["left_open"] = False
    assert evaluate(spec)["result"] == "fail"


def test_real_domain_rejects_complex_subexpressions_and_preserves_power_restrictions():
    imaginary = op("sqrt", num(-1))
    spec = claim("maximal_domain", expression=op("mul", imaginary, imaginary), expected_intervals=[domain()])
    assert evaluate(spec)["result"] == "fail"
    spec["expected_intervals"] = []
    assert evaluate(spec)["result"] == "pass"
    spec.update(expression=op("pow", var(), num("1/3")), expected_intervals=[domain()])
    assert evaluate(spec)["result"] == "fail"
    spec["expected_intervals"] = [domain("0", None, False)]
    assert evaluate(spec)["result"] == "pass"
    spec.update(expression=op("pow", var(), num(-1)),
                expected_intervals=[domain(None, "0"), domain("0", None)])
    assert evaluate(spec)["result"] == "pass"


@pytest.mark.parametrize("side,sign", [("+", "positive_infinity"), ("-", "negative_infinity")])
def test_signed_limits_distinguish_sign_sides_and_remote_intervals(side, sign):
    spec = claim("signed_limit", expression=op("div", num(1), var()), domain=domain("-1", "1"),
                 at="0", direction=side, expected_sign=sign)
    assert check_math(spec)["result"] == "pass"
    spec["direction"] = "+-"
    assert evaluate(spec)["result"] == "fail"
    spec.update(direction=side, domain=domain("2", "3"))
    assert evaluate(spec)["result"] == "fail"


def test_signed_boundary_difference_quotient_and_infinite_approach():
    x = var()
    spec = claim("signed_limit", expression=op("div", op("sqrt", op("mul", x, op("sub", x, num(6)))), x),
                 domain=domain("-1", "0"), at="0", direction="-", expected_sign="negative_infinity")
    assert evaluate(spec)["result"] == "pass"
    spec.update(expression=x, domain=domain("0", None), at="inf", expected_sign="positive_infinity")
    assert evaluate(spec)["result"] == "pass"
    spec["domain"] = domain("0", "10")
    assert evaluate(spec)["result"] == "fail"


def test_parameter_derivatives_hold_as_identities_and_reject_hidden_poles():
    source = parameter_optimum()
    spec = claim("parameter_derivative", expression=source["expression"],
        domain=source["domain"], parameter=source["parameter"], differentiate_by="x", order=1,
        expected=op("sub", var("a"), op("pow", var(), num(2))))
    assert check_math(spec)["result"] == "pass"
    spec.update(differentiate_by="a", expected=var())
    assert evaluate(spec)["result"] == "pass"
    spec["expected"] = num(1)
    assert evaluate(spec)["result"] == "fail"
    spec["expression"] = op("div", var("a"), var("a"))
    result = evaluate(spec)
    assert result["result"] == "not_checked"
    assert result["diagnostics"][0]["category"] == "checker_capability"


@pytest.mark.parametrize("capacity", ["2", "3", "5"])
def test_parameter_optimum_proves_all_values_and_thresholds(capacity):
    spec = parameter_optimum(capacity)
    assert check_math(spec)["result"] == "pass"
    spec["branches"][1]["value"] = num(0)
    assert evaluate(spec)["result"] == "fail"


@pytest.mark.parametrize("mutation", ["gap", "overlap", "missing", "outside", "wrong_point"])
def test_parameter_optimum_rejects_incomplete_or_false_branches(mutation):
    spec = parameter_optimum()
    if mutation == "gap":
        spec["branches"][1]["parameter_domain"]["left_open"] = True
    elif mutation == "overlap":
        spec["branches"][0]["parameter_domain"]["right_open"] = False
    elif mutation == "missing":
        spec["branches"].pop()
    elif mutation == "outside":
        spec["branches"][0]["point"] = num(4)
    else:
        spec["branches"][0].update(point=num(0), value=num(0))
    assert evaluate(spec)["result"] == "fail"


def test_parameter_minimum_and_undecidable_curvature():
    spec = parameter_optimum()
    spec["optimum"] = "min"
    spec["expression"] = op("mul", num(-1), spec["expression"])
    for branch in spec["branches"]:
        branch["value"] = op("mul", num(-1), branch["value"])
    assert evaluate(spec)["result"] == "pass"
    spec["optimum"] = "max"
    result = evaluate(spec)
    assert result["result"] == "not_checked"
    assert result["diagnostics"][0]["code"] == "SYMBOLIC_CAPABILITY_UNSUPPORTED"


def test_parameter_identity_and_full_capacity_value():
    source = parameter_optimum()
    spec = claim("parameter_identity", expression=source["expression"], domain=source["domain"],
                 parameter=source["parameter"], at="3", expected=op("sub", op("mul", num(3), var("a")), num(9)))
    assert evaluate(spec)["result"] == "pass"
    spec["at"] = "4"
    assert evaluate(spec)["result"] == "fail"
    spec.update(at=None, expected=copy.deepcopy(spec["expression"]))
    assert evaluate(spec)["result"] == "pass"


def test_uniqueness_is_never_inferred_from_optimality_alone():
    spec = parameter_optimum()
    spec.update(expression=var("a"), branches=[{"parameter_domain": domain("0", None), "point": num(0), "value": var("a")}])
    assert evaluate(spec)["result"] == "not_checked"
    spec["unique"] = False
    assert evaluate(spec)["result"] == "pass"


def test_new_claims_use_normal_answer_checks_and_release_gate():
    spec = parameter_optimum()
    TypeAdapter(SymbolicCheck).validate_python(spec)
    pair = {"question_id": "q", "parts": [{"part_id": "part", "response_type": "applied_optimisation"}],
            "answers": [{"part_id": "part", "checks": [spec]}]}
    checks = mathematical_checks([pair])
    assert release_gate(checks)["allowed"]
    projected = compact_pair(pair)
    assert projected["answers"][0]["checks"][0]["branches"][0]["point"] == "sqrt(a)"
    assert pair["answers"][0]["checks"][0] == spec
    spec["branches"].pop()
    assert not release_gate(mathematical_checks([pair]))["allowed"]


def test_contract_and_shared_fragments_are_versioned_without_course_data():
    contract = checker_contract()
    assert contract["capability"]["id"] == "quantitative_symbolic"
    assert "extended.py" in contract["capability"]["files"]
    prompts = compose_prompts({name: "Core instructions" for name in ("question_pairs", "repair", "semantic_review", "blind_solver")})
    assert prompts["question_pairs"] == prompts["repair"]
    assert "parameter_optimum" in prompts["question_pairs"]
    assert prompts["blind_solver"] == "Core instructions"


def test_all_output_schema_objects_require_every_field():
    from app.generation.content_schemas import PairOutput
    schema = PairOutput.model_json_schema()
    for item in schema["$defs"].values():
        if item.get("type") == "object":
            assert set(item["required"]) == set(item["properties"])
            assert item["additionalProperties"] is False
