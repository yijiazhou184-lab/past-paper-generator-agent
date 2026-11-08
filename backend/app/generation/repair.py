"""One bounded targeted repair; never overwrite a candidate or relax a required check."""
from app.core.errors import DomainError
from app.core.models import Task
from app.core.tasks import checkpoint
from .generator import generate_groups, persist_candidate
from .source_policy import source_review_input
from .review_policy import review_call_bound
from .originality_policy import POLICY as ORIGINALITY_POLICY
from .repair_diagnostics import build_repair_failures, validate_repaired_checks


def repair_candidate(token,context,candidate,report):
    if candidate.revision!=1 or candidate.parent_id:
        raise DomainError("REPAIR_ROUND_LIMIT")
    if report.gate["allowed"]:
        return None
    ids={q["blueprint"]["id"] for q in context["input"]["questions"]}
    blocked=[c for c in report.payload["checks"] if c["required_for_release"] and c["result"]!="pass"]
    blocked_ids={qid for c in blocked for qid in c["target_ids"] if qid in ids}
    requests={}
    for r in report.payload["repair_requests"]:
        for qid in r["target_ids"]:
            if qid in blocked_ids:
                requests.setdefault(qid,[]).append({**r,"target_ids":[qid]})
    # Deterministic failures can request a targeted repair even if the review omitted one.
    for c in blocked:
        if (c["method"] in ("sympy_subprocess","program","source_policy","source_originality_rule") and c["result"]=="fail") or c["check_id"].endswith(":source_alignment"):
            for qid in c["target_ids"]:
                if qid in ids:
                    requests.setdefault(qid,[]).append({"target_ids":[qid],"issue_codes":[c["check_id"]],"instructions":c["rationale"]})
    order=[p["question_id"] for p in candidate.payload["pairs"]]
    part_question={part["part_id"]:p["question_id"] for p in candidate.payload["pairs"] for part in p["parts"]}
    for c in blocked:
        if c["check_id"]==ORIGINALITY_POLICY["check_id"] and c["result"]=="fail":
            # Repair only the later question of each pair; the earlier one stays as it is.
            for a,b in c.get("duplicate_pairs",[]):
                qa,qb=part_question.get(a),part_question.get(b)
                if qa in ids and qb in ids:
                    target=max(qa,qb,key=order.index)
                    requests.setdefault(target,[]).append({"target_ids":[target],"issue_codes":[c["check_id"]],
                        "instructions":f"Parts {a} and {b} have the same given material and the same final conclusion. "
                                       "Change this question's given material or the conclusion its part asks for; keep the knowledge targets."})
    for finding in report.payload["duplicate_review"]["findings"]:
        for qid in finding["target_ids"]:
            if qid in ids:
                requests.setdefault(qid,[]).append({"target_ids":[qid],"issue_codes":[finding["code"]],"instructions":finding["explanation"]})
    failures_by_question={p["question_id"]:build_repair_failures(p,[c for c in blocked if p["question_id"] in c["target_ids"]]) for p in candidate.payload["pairs"]}
    # A whole-paper duplicate check targets the paper for reporting, but only the
    # later question of each duplicated pair is a justified repair target.
    duplicate_targets=set()
    for c in blocked:
        if c["check_id"]==ORIGINALITY_POLICY["check_id"]:
            for a,b in c.get("duplicate_pairs",[]):
                qa,qb=part_question.get(a),part_question.get(b)
                if qa in ids and qb in ids:duplicate_targets.add(max(qa,qb,key=order.index))
    # A whole-paper semantic check also targets every question for reporting; the review's
    # repair requests name the questions that must change, and only those are repaired.
    review_targets={qid for r in report.payload["repair_requests"] for qid in r["target_ids"] if qid in ids}
    for qid,failures in failures_by_question.items():
        for failure in failures:
            if failure["check_id"]==ORIGINALITY_POLICY["check_id"] and qid not in duplicate_targets:
                failure["actionable"]=False
                failure["instructions"]="This paper-level finding is repaired in the later question of the identified duplicate pair. Preserve this question."
            elif failure["check_id"].startswith("semantic:paper:") and qid not in review_targets:
                failure["actionable"]=False
                failure["instructions"]="This paper-level finding is repaired in the questions the review named. Preserve this question."
        actions=[f for f in failures if f["actionable"]]
        if actions:
            requests.setdefault(qid,[]).extend({"target_ids":[qid],"issue_codes":[f["check_id"]],"instructions":f["instructions"]} for f in actions)
        elif failures:
            requests.pop(qid,None)
    if not requests:
        checkpoint(token,"No justified repair available",{"candidate_id":str(candidate.id),"reason":"No code-owned actionable diagnosis is available; no repair call was made.","unresolved_check_ids":[c["check_id"] for c in blocked]})
        return None
    task=Task.objects.get(pk=token.task_id)
    # Reserve enough of the frozen ceiling for repairs, independent re-solves and a whole-paper review.
    worst_case=2*len(requests)+review_call_bound(len(ids))
    if context["mode"]=="live" and task.call_count+worst_case>context["max_calls"]:
        checkpoint(token,"Repair budget insufficient",{"required_calls_upper_bound":worst_case,
                    "remaining_calls":context["max_calls"]-task.call_count})
        return None
    pairs={p["question_id"]:p for p in candidate.payload["pairs"]}
    targeted={}
    for qid,issues in requests.items():
        duplicate_review=report.payload["duplicate_review"]
        format_error=any(d.get("code") in ("UNSUPPORTED_NUMERIC_LITERAL", "INVALID_POINT_EXPRESSION")
                         for f in failures_by_question[qid] for d in f["diagnostics"])
        targeted[qid]={"issues":[{"target_ids":[qid],"issue_codes":[f["check_id"]],"instructions":f["instructions"]} for f in failures_by_question[qid] if f["actionable"]],
            "model_suggestions":[] if format_error else issues,"previous_pair":pairs[qid],
            "failures":failures_by_question[qid],
            "protected_check_ids":[f["specification"]["id"] for f in failures_by_question[qid] if f.get("specification") and f["specification"].get("role","core")=="core"],
            "fixed_structure":{"parts":[{k:p[k] for k in ("part_id","marks","knowledge_ids","response_type")} for p in pairs[qid]["parts"]]},
            "local_checks":[c for c in blocked if qid in c["target_ids"]],
            "checker_contract":context["checker_contract"],
            "source_review":source_review_input(context,[pairs[qid]]),
            "duplicate_comparison":{**duplicate_review,
                "candidates":[c for c in duplicate_review["candidates"] if qid in c.get("target_ids",[])],
                "findings":[f for f in duplicate_review["findings"] if qid in f["target_ids"]]},

            "other_question_summaries":[{"question_id":p["question_id"],"stem":p["stem"],
                                         "parts":[part["prompt"] for part in p["parts"]]}
                                        for p in candidate.payload["pairs"] if p["question_id"]!=qid]}
    questions=[q for q in context["input"]["questions"] if q["blueprint"]["id"] in requests]
    repaired=generate_groups(token,context,questions,round_number=1,repair_requests=targeted)
    for group in repaired:
        qid=group["pair"]["question_id"]
        validate_repaired_checks(pairs[qid],group["pair"],failures_by_question[qid])
    replacements={g["pair"]["question_id"]:g for g in repaired}
    groups=[replacements.get(p["question_id"],{"pair":p,"assets":[a for a in candidate.payload["assets"] if a["id"] in p["asset_ids"]]})
            for p in candidate.payload["pairs"]]
    return persist_candidate(token,context,groups,revision=2,parent=candidate)
