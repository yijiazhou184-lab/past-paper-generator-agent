"""One bounded targeted repair; never overwrite a candidate or relax a required check."""
from app.core.errors import DomainError
from app.core.models import Task
from app.core.tasks import checkpoint
from .generator import generate_groups, persist_candidate
from .source_policy import source_review_input
from .review_policy import review_call_bound


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
        if (c["method"] in ("sympy_subprocess","program","source_policy") and c["result"]=="fail") or c["check_id"].endswith(":source_alignment"):
            for qid in c["target_ids"]:
                if qid in ids:
                    requests.setdefault(qid,[]).append({"target_ids":[qid],"issue_codes":[c["check_id"]],"instructions":c["rationale"]})
    for finding in report.payload["duplicate_review"]["findings"]:
        for qid in finding["target_ids"]:
            if qid in ids:
                requests.setdefault(qid,[]).append({"target_ids":[qid],"issue_codes":[finding["code"]],"instructions":finding["explanation"]})
    if not requests:
        checkpoint(token,"No justified repair available",{"candidate_id":str(candidate.id)})
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
        targeted[qid]={"issues":issues,"previous_pair":pairs[qid],
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
    replacements={g["pair"]["question_id"]:g for g in repaired}
    groups=[replacements.get(p["question_id"],{"pair":p,"assets":[a for a in candidate.payload["assets"] if a["id"] in p["asset_ids"]]})
            for p in candidate.payload["pairs"]]
    return persist_candidate(token,context,groups,revision=2,parent=candidate)
