import copy
from django.db import transaction
from app.core.models import Task
from app.core.idempotency import digest
from app.core.tasks import checkpoint, locked_task, finish_task, fail_task
from app.core.errors import DomainError
from .models import CheckReport
from .runtime import stage_output
from .content_schemas import BlindOutput, SemanticOutput
from .content_fixtures import fixture_blind, fixture_review, CATEGORIES
from .checks import check, program_checks, mathematical_checks, release_gate, coverage_summary
from .duplicates import duplicate_candidates


def blind_input(context,pair,assets):
    question_blocks=pair["stem"]+[b for p in pair["parts"] for b in p["prompt"]]
    visible_asset_ids={b["asset_id"] for b in question_blocks if b["type"]=="asset_ref"}
    return {"question":{"question_id":pair["question_id"],"stem":pair["stem"],"parts":pair["parts"]},
        "assets":[{k:v for k,v in a.items() if k!="svg"} for a in assets if a["id"] in visible_asset_ids],
        "course_methods":context["input"]["course"]["method_rules"],
        "scope":context["input"]["course"]["scope_claims"],"user_preferences":context["input"]["statements"]}


def review_semantics(token,context,candidate,local,blind,duplicates):
    data={"candidate":candidate.payload,"blueprint":context["input"]["blueprint"],
          "course":context["input"]["course"],"user_preferences":context["input"]["statements"],
          "config":context["input"]["config"],"local_checks":local,"blind_solutions":blind,
          "duplicate_comparison":duplicates}
    output=stage_output(token,f"r{candidate.revision-1}:semantic","semantic_review",data,SemanticOutput,
                        lambda:fixture_review(candidate.payload["pairs"]))
    return output


@transaction.atomic
def save_report(token,candidate,checks,duplicates,repair_requests,blind):
    locked_task(token)
    existing=CheckReport.objects.filter(candidate=candidate).first()
    if existing:
        return existing
    payload={"candidate_version_id":str(candidate.id),"checks":checks,"duplicate_review":duplicates,
             "repair_requests":repair_requests,"coverage_summary":coverage_summary(checks),"blind_comparison":blind}
    return CheckReport.objects.create(candidate=candidate,payload=payload,payload_hash=digest(payload),gate=release_gate(checks))


def check_candidate(token,context,candidate):
    existing=CheckReport.objects.filter(candidate=candidate).first()
    if existing:
        if digest(existing.payload)!=existing.payload_hash:
            raise DomainError("CHECK_REPORT_CHANGED")
        return existing
    checkpoint(token,"Program checks",{"candidate_id":str(candidate.id)})
    checks=program_checks(context,candidate.payload)
    checkpoint(token,"Mathematical checks",{"candidate_id":str(candidate.id)})
    checks.extend(mathematical_checks(candidate.payload["pairs"]))
    checkpoint(token,"Blind solving",{"candidate_id":str(candidate.id)})
    blind=[]
    question_map={q["blueprint"]["id"]:q["blueprint"] for q in context["input"]["questions"]}
    for pair in candidate.payload["pairs"]:
        data=blind_input(context,pair,candidate.payload["assets"])
        # Unchanged questions across repair rounds reuse the same blind solve by input identity.
        key="blind:"+digest(data)[:48]
        output=stage_output(token,key,"blind_solver",data,BlindOutput,lambda q=question_map[pair["question_id"]]:fixture_blind(q))
        parts=[p["part_id"] for p in pair["parts"]]
        returned=[a["part_id"] for a in output["answers"]]
        complete=output["status"]=="complete" and sorted(parts)==sorted(returned)
        checks.append(check("blind_available:"+pair["question_id"],[pair["question_id"]],"blind_solver",
                            "pass" if complete else "inconclusive",
                            "Independent solution returned for every part." if complete else output["explanation"] or "Blind solution missing parts."))
        generated={a["part_id"]:a["final_answer"] for a in pair["answers"]}
        comparison=[{"part_id":a["part_id"],"exact_match":digest(a["final_answer"])==digest(generated.get(a["part_id"]))}
                    for a in output["answers"]]
        blind.append({"question_id":pair["question_id"],"output":output,"comparison":comparison})
    checkpoint(token,"Retrieving comparison questions")
    sources=[s for s in context["input"]["sources"] if s["id"] in context["input"]["comparison_source_ids"]]
    duplicates=duplicate_candidates(candidate.payload["pairs"],sources,context["input"]["history_content_ids"])
    retrieval_missing=bool(duplicates["available_source_ids"]) and not duplicates["candidates"]
    duplicate_status="fail" if duplicates["findings"] else "not_checked" if retrieval_missing else "pass"
    duplicate_reason=("Potential substantive duplicates need repair." if duplicates["findings"] else
                      "Supplied comparison pages have no usable excerpts; originality has not been checked." if retrieval_missing else
                      "No exact or number-only match in the supplied comparison and within this candidate; semantic review is still required.")
    checks.append(check("local_duplicates",[p["question_id"] for p in candidate.payload["pairs"]],"normalised_retrieval",
                        duplicate_status,duplicate_reason))
    checkpoint(token,"Semantic review",{"candidate_id":str(candidate.id)})
    semantic=review_semantics(token,context,candidate,checks,blind,duplicates)
    ids={p["question_id"] for p in candidate.payload["pairs"]}
    evidence_ids={s["id"] for s in context["input"]["sources"]}
    returned={}
    invalid=False
    for c in semantic["checks"]:
        key=(c["question_id"],c["category"])
        if key in returned or c["question_id"] not in ids or not set(c["evidence_ids"])<=evidence_ids:
            invalid=True
        returned[key]=c
    for qid in sorted(ids):
        for category in CATEGORIES:
            item=returned.get((qid,category))
            if semantic["status"]!="complete" or invalid or item is None:
                checks.append(check(f"semantic:{qid}:{category}",[qid],"semantic_review","not_checked",
                                    semantic["explanation"] or "Required semantic judgement missing or invalid."))
            else:
                # Requiredness and coverage are code-owned, never chosen by the model.
                checks.append(check(f"semantic:{qid}:{category}",[qid],"semantic_review",item["result"],
                                    item["rationale"],item["evidence_ids"]))
    repairs=[r for r in semantic["repair_requests"] if set(r["target_ids"])<=ids]
    return save_report(token,candidate,checks,duplicates,repairs,blind)


@transaction.atomic
def finish_candidate(token,candidate,report):
    task=locked_task(token)
    result={"mode":candidate.mode,"candidate_id":str(candidate.id),"report_id":str(report.id),
            "candidate_revision":candidate.revision,**report.gate,
            "message":"Checks passed for this candidate · publication arrives in batch 5" if report.gate["allowed"] else
                      "Required checks did not pass. The candidate and reports are retained; nothing was published."}
    task.result=result
    task.save(update_fields=["result"])
    if report.gate["allowed"]:
        finish_task(token,result)
    else:
        fail_task(token,"REQUIRED_CHECKS_BLOCKED",result["message"],False)
