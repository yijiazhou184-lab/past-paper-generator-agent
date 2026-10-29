"""Mathematical capability: interval domain proofs, absolute-value kinks, and core/auxiliary gate rules."""
import sympy as sp
from app.generation.math_bounds import prove
from app.generation.math_worker import evaluate
from app.generation.checks import math_check, release_gate, coverage_summary

X = sp.Symbol("x", real=True)


def num(v): return {"op": "number", "value": str(v), "args": []}
def x(): return {"op": "variable", "value": "x", "args": []}
def op(name, *args): return {"op": name, "value": None, "args": list(args)}


def spec(kind, expression, expected, *, lower, upper, left_open=False, right_open=False, at=None,
         direction="+-", denominator=None, points=(), optimum=None, role="core"):
    return {"id": "s", "part_id": "p", "kind": kind, "expression": expression, "expected": expected,
            "denominator": denominator, "variable": "x",
            "domain": {"lower": lower, "upper": upper, "left_open": left_open, "right_open": right_open},
            "at": at, "direction": direction, "points": list(points), "optimum": optimum, "role": role,
            "rationale": "Test specification."}


ONE_PLUS_XSINX = op("add", num(1), op("mul", x(), op("sin", x())))


def test_interval_proof_decides_signs_on_intervals_and_punctured_unions():
    assert prove(1 + X * sp.sin(X), X, sp.Interval(-sp.Rational(1, 2), sp.Rational(1, 2)), "pos") is True
    punctured = sp.Interval.open(-sp.Rational(1, 2), sp.Rational(1, 2)) - sp.FiniteSet(0)
    assert prove(1 + X * sp.sin(X), X, punctured, "pos") is True
    assert prove(sp.cos(X) - 2, X, sp.Interval(0, 1), "pos") is False          # refuted everywhere
    assert prove(X, X, sp.Interval.open(0, 1), "pos") is None                   # open endpoint: not forced
    assert prove(sp.log(X), X, sp.Interval(0, sp.oo), "pos") is None            # unbounded: no interval claim


def test_logarithmic_limit_is_decided_once_the_domain_is_proven():
    power = op("exp", op("div", op("log", ONE_PLUS_XSINX), op("pow", x(), num(2))))
    result = evaluate(spec("limit", power, op("exp", num(1)), lower="-0.5", upper="0.5",
                           left_open=True, right_open=True, at="0"))
    assert result["result"] == "pass"
    step = evaluate(spec("lhopital", op("log", ONE_PLUS_XSINX), num(1), lower="0", upper="0.5",
                         left_open=True, right_open=True, at="0", direction="+",
                         denominator=op("pow", x(), num(2))))
    assert step["result"] == "pass"


def test_undefined_logarithm_is_refuted_not_passed():
    shifted = op("log", op("sub", op("cos", x()), num(2)))
    assert evaluate(spec("value", shifted, num(0), lower="0", upper="1", at="0.5"))["result"] == "fail"


def test_absolute_value_kink_is_a_candidate_for_core_but_not_for_auxiliary():
    tent = op("sub", num(1), op("abs", x()))
    core = spec("bounded_optimum", tent, num("1/2"), lower="-0.5", upper="0.5",
                points=["-0.5", "0.5"], optimum="min")
    assert evaluate(core)["result"] == "fail"  # the kink at 0 was not listed
    assert evaluate({**core, "points": ["-0.5", "0", "0.5"]})["result"] == "pass"
    assert evaluate({**core, "points": ["-0.5", "0", "0.5"], "optimum": "max", "expected": num(1)})["result"] == "pass"
    assert evaluate({**core, "role": "auxiliary"})["result"] == "pass"  # value only


def test_kink_inside_the_domain_means_no_derivative_and_none_outside():
    tent = op("abs", x())
    assert evaluate(spec("derivative", tent, num(1), lower="-1", upper="1"))["result"] == "fail"
    assert evaluate(spec("derivative", tent, num(1), lower="0", upper="1", left_open=True))["result"] == "pass"


def test_stationary_points_exclude_kinks():
    shape = op("add", op("abs", x()), op("pow", op("sub", x(), num(2)), num(2)))
    # |x| + (x-2)^2 on [-1, 3]: derivative 1 + 2(x-2) = 0 at x = 3/2 on the right piece; none on the left piece.
    result = evaluate(spec("stationary_points", shape, None, lower="-1", upper="3", points=["3/2"]))
    assert result["result"] == "pass"


def outcome(result): return {"result": result, "rationale": "Test."}


def test_gate_rules_for_core_and_auxiliary():
    core_bad = [math_check("c", ["q1", "p"], "core", outcome(r)) for r in ("fail", "inconclusive", "not_checked")]
    assert all(c["required_for_release"] for c in core_bad)
    aux = {r: math_check("a", ["q1", "p"], "auxiliary", outcome(r)) for r in ("pass", "fail", "inconclusive", "not_checked")}
    assert aux["fail"]["required_for_release"] is True
    assert not aux["inconclusive"]["required_for_release"] and not aux["not_checked"]["required_for_release"]
    assert aux["inconclusive"]["limitation"] and aux["inconclusive"]["result"] == "inconclusive"  # never rewritten as pass
    assert release_gate([math_check("c", ["q1"], "core", outcome("pass")), aux["inconclusive"]])["allowed"] is True
    assert release_gate([math_check("c", ["q1"], "core", outcome("pass")), aux["fail"]])["allowed"] is False
    assert coverage_summary([aux["inconclusive"], aux["not_checked"], aux["pass"]])["auxiliary_unresolved"] == 2


def test_quantitative_part_without_a_core_check_is_blocked():
    from app.generation.checks import mathematical_checks
    aux_only = spec("value", op("pow", x(), num(2)), num(1), lower="-2", upper="2", at="1", role="auxiliary")
    pair = {"question_id": "q1", "parts": [{"part_id": "p", "response_type": "calculation"}],
            "answers": [{"part_id": "p", "checks": [aux_only]}]}
    checks = mathematical_checks([pair])
    missing = [c for c in checks if c["check_id"] == "math:p:core_missing"]
    assert missing and missing[0]["required_for_release"] and missing[0]["result"] == "not_checked"
    legacy = {k: v for k, v in aux_only.items() if k != "role"}
    pair["answers"][0]["checks"] = [legacy]
    checks = mathematical_checks([pair])
    assert [c["math_role"] for c in checks] == ["core"]  # saved specifications without a role are not relaxed
