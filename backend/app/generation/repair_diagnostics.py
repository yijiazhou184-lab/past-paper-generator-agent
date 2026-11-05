"""Construct complete failures from program results, independently of model repair suggestions."""
import copy
from app.core.errors import DomainError
from .math_diagnostics import diagnose_spec, diagnostic


def build_repair_failures(pair,checks):
    specs={s["id"]:s for a in pair["answers"] for s in a.get("checks",[])}
    failures=[]
    for c in checks:
        if not c.get("required_for_release") or c["result"]=="pass": continue
        sid=c["check_id"].removeprefix("math:")
        spec=specs.get(sid)
        diagnostics=copy.deepcopy(c.get("diagnostics",[]))
        if not diagnostics and spec: diagnostics=diagnose_spec(spec)
        category=(diagnostics[0]["category"] if diagnostics else
                  "checker_capability" if c.get("method") in ("sympy_subprocess","symbolic") and c["result"]!="fail" else "content_error")
        actionable=any(d.get("actionable") for d in diagnostics) if diagnostics else c["result"]=="fail" and bool(c.get("rationale","").strip()) and category!="checker_capability"
        if not diagnostics:
            diagnostics=[diagnostic("CHECK_FAILED" if c["result"]=="fail" else "CHECK_UNDECIDED","$",None,c.get("rationale",""),
                category=category,actionable=actionable,allowed="The frozen check contract and the stated question conditions.")]
        diagnostics=[{**d,"question_id":pair["question_id"],
            "part_id":spec["part_id"] if spec else next((i for i in c.get("target_ids",[]) if i!=pair["question_id"]),None),
            "check_id":c["check_id"]} for d in diagnostics]
        instructions=c.get("rationale","")
        if any(d.get("code")=="UNSUPPORTED_NUMERIC_LITERAL" for d in diagnostics):
            instructions=("Use only numeric literals in the identified field. Adding parentheses, or spelling the same formula differently, is not a fix. "
                "Preserve the correct answer. If exact values cannot use that field, use a supported equivalent core specification under the frozen contract "
                "with the same final-answer coverage and a justified completeness argument. If no equivalent check exists, report unsupported capability. "
                "Do not remove or demote the required check.")
        failures.append({"check_id":c["check_id"],"question_id":pair["question_id"],
            "part_ids":[i for i in c.get("target_ids",[]) if i!=pair["question_id"]],"result":c["result"],
            "category":category,"rationale":c.get("rationale",""),"diagnostics":diagnostics,
            "specification":copy.deepcopy(spec),"actionable":actionable,"instructions":instructions})
    return failures


def validate_repaired_checks(previous,revised,failures):
    current={s["id"]:s for a in revised["answers"] for s in a.get("checks",[])}
    for f in failures:
        spec=f.get("specification")
        if spec and spec.get("role","core")=="core":
            new=current.get(spec["id"])
            if not new or new.get("role","core")!="core" or new["part_id"]!=spec["part_id"]:
                raise DomainError("REPAIR_REQUIRED_CHECK_REMOVED","A repair cannot remove or demote the blocked core check.")
