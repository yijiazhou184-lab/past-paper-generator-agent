"""Read-only checks of a saved real response plus fixed, source-derived SymPy calculations.

This is a narrow acceptance sample, not a general semantic verifier or human approval.
"""
import argparse
import json
import uuid
from pathlib import Path
import sympy as s

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task_id", type=uuid.UUID)
args = parser.parse_args()
report = json.loads((ROOT / f"var/batch1-live-{args.task_id}.json").read_text(encoding="utf-8"))
assert report["state"] == "succeeded"
calls = {c["call_key"]: c for c in report["calls"]}
expected = {"smoke", "M34-p14", "M34-p41", "M14-p5", "M33-p22", "M48-p20"}
assert set(calls) == expected
for call in calls.values():
    result = call["result"]
    assert result["mode"] == "live" and result["status"] == "parsed"
    assert result["response_id"] and result["request_id"]
    assert result["usage"]["total_tokens"] == result["usage"]["input_tokens"] + result["usage"]["output_tokens"]
    assert call["metadata"]["store"] is False and call["metadata"]["sdk_max_retries"] == 0

pages = {f'{p["material_id"]}-p{p["source"]["physical_page"]}': p for p in report["snapshot"]["pages"]}
for key, page in pages.items():
    assert calls[key]["result"]["payload"]["source"] == page["source"]


def math_text(key):
    return "".join(item["as_printed_latex"] for item in calls[key]["result"]["payload"]["math_items"]).replace(" ", "")


def has_kind(key, kind):
    return any(f["kind"] == kind for f in calls[key]["result"]["payload"]["findings"])


# Key transcription anchors only; the agent separately compared all five PNGs with the full responses.
assert "=-1" in math_text("M34-p14") and "=1" in math_text("M34-p14")
assert r"2-\sqrt{2},2+\sqrt{2}" in math_text("M34-p41")
assert r"\frac{1}{2\sqrt{x}}" in math_text("M14-p5") and r"x\ne0" in math_text("M14-p5")
assert r"e^{\ln(x)}=1" in math_text("M33-p22") and r"\ln(e^x)=1" in math_text("M33-p22")
assert has_kind("M33-p22", "source_issue")
assert has_kind("M48-p20", "intentional_wrong_example") and r"\frac{4}{2}=2" in math_text("M48-p20")
assert all(has_kind(key, "parser_loss") for key in pages)

# Do not evaluate model-supplied code/expressions. These expressions are fixed from visual source review.
h = s.symbols("h", real=True)
x = s.symbols("x", positive=True)
t = s.symbols("t", real=True)
assert s.limit(s.Abs(h) / h, h, 0, dir="-") == -1
assert s.limit(s.Abs(h) / h, h, 0, dir="+") == 1
profit = -t**3 + 6*t**2 - 6*t
assert set(s.solve(s.diff(profit, t), t)) == {2-s.sqrt(2), 2+s.sqrt(2)}
assert s.diff(profit, t, 2).subs(t, 2+s.sqrt(2)) < 0
assert s.simplify(s.limit((s.sqrt(x+h)-s.sqrt(x))/h, h, 0) - 1/(2*s.sqrt(x))) == 0
assert s.simplify(s.exp(s.log(x))-x) == 0
assert s.simplify(s.log(s.exp(t))-t) == 0
assert s.limit((2*t**2-t-1)/(t**2-t), t, 1) == 3

usage = {k: sum(c["result"]["usage"][k] for c in calls.values())
         for k in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens")}
review = {"task_id": str(args.task_id), "mode": "local_assertions_on_real_responses",
    "checks": {"six_real_structured_responses": True, "five_exact_source_bindings": True,
               "key_transcription_anchors": True, "fixed_source_sympy_checks": True},
    "limitations": "Selected mathematical anchors only. Not a general proof checker, human verification or full course acceptance.",
    "usage": usage, "api_seconds": round(sum(c["result"]["elapsed_seconds"] for c in calls.values()), 3),
    "wall_seconds": report.get("wall_seconds"),
    "estimated_standard_token_cost_usd": round((usage["input_tokens"]*2 + usage["output_tokens"]*10)/1000000, 6),
    "cost_basis": "2026-10-22 official standard input/output rates; no cached input; estimate, not invoice; failed-call costs unknown."}
output = ROOT / f"var/batch1-review-{args.task_id}.json"
output.write_text(json.dumps(review, indent=2), encoding="utf-8")
print(json.dumps(review, indent=2))
