"""Generate checks with durable partial progress and bounded model reviews."""
from django.db import transaction
from app.core.idempotency import digest
from app.core.tasks import checkpoint, locked_task, finish_task, fail_task
from app.core.errors import DomainError
from .models import CheckReport
from .runtime import stage_output
from .content_schemas import BlindOutput
from .content_fixtures import fixture_blind, fixture_review
from .checks import check, program_checks, mathematical_checks, release_gate, coverage_summary
from .duplicates import duplicate_candidates
from .check_progress import save_check_stage, progress_report
from .semantic_review import run_semantic_review, run_optional_review


def blind_input(context,pair,assets):
    question_blocks=pair["stem"]+[b for p in pair["parts"] for b in p["prompt"]]
    visible_asset_ids={b["asset_id"] for b in question_blocks if b["type"]=="asset_ref"}
    return {"question":{"question_id":pair["question_id"],"stem":pair["stem"],"parts":pair["parts"]},
        "assets":[{k:v for k,v in a.items() if k!="svg"} for a in assets if a["id"] in visible_asset_ids],
        "course_methods":context["input"]["course"]["method_rules"],
        "scope":context["input"]["course"]["scope_claims"],"user_preferences":context["input"]["statements"]}


@transaction.atomic
def save_report(token,candidate,checks,duplicates,repair_requests,blind):
    locked_task(token)
    existing=CheckReport.objects.filter(candidate=candidate).first()
    if existing:
        return existing
    progress=progress_report(candidate)
    # Include required pending coverage as a final defensive gate.
    values={c["check_id"]:c for c in (progress or {}).get("checks",[])}
    values.update({c["check_id"]:c for c in checks})
    checks=list(values.values())
    payload={"candidate_version_id":str(candidate.id),"complete":True,
             "checks":checks,"duplicate_review":duplicates,"stages":(progress or {}).get("stages",[]),
             "repair_requests":repair_requests,"coverage_summary":coverage_summary(checks),"blind_comparison":blind}
    payload["version"]=digest(payload)
    return CheckReport.objects.create(candidate=candidate,payload=payload,payload_hash=digest(payload),gate=release_gate(checks))


def check_candidate(token,context,candidate):
    try:
        return _check_candidate(token,context,candidate)
    except DomainError as exc:
        if exc.payload["code"] not in ("STALE_EXECUTION","RUN_LIMIT_EXCEEDED"):
            save_check_stage(token,candidate,"interrupted",[],status="blocked",error_code=exc.payload["code"])
            exc.payload["message"]="Questions and answers saved. Required validation could not finish. "+exc.payload["message"]
        raise


def _check_candidate(token,context,candidate):
    existing=CheckReport.objects.filter(candidate=candidate).first()
    if existing:
        if digest(existing.payload)!=existing.payload_hash:
            raise DomainError("CHECK_REPORT_CHANGED")
        return existing
    checkpoint(token,"Program checks",{"candidate_id":str(candidate.id)})
    checks=save_check_stage(token,candidate,"program",program_checks(context,candidate.payload))["checks"]
    checkpoint(token,"Mathematical checks",{"candidate_id":str(candidate.id)})
    checks=checks+save_check_stage(token,candidate,"math",mathematical_checks(candidate.payload["pairs"]))["checks"]
    checkpoint(token,"Blind solving",{"candidate_id":str(candidate.id)})
    blind=[]
    question_map={q["blueprint"]["id"]:q["blueprint"] for q in context["input"]["questions"]}
    for pair in candidate.payload["pairs"]:
        data=blind_input(context,pair,candidate.payload["assets"])
        key="blind:"+digest(data)[:48]
        output=stage_output(token,key,"blind_solver",data,BlindOutput,lambda q=question_map[pair["question_id"]]:fixture_blind(q))
        parts=[p["part_id"] for p in pair["parts"]]
        returned=[a["part_id"] for a in output["answers"]]
        complete=output["status"]=="complete" and sorted(parts)==sorted(returned)
        item=check("blind_available:"+pair["question_id"],[pair["question_id"]],"blind_solver",
                   "pass" if complete else "inconclusive",
                   "Independent solution returned for every part." if complete else output["explanation"] or "Blind solution missing parts.")
        generated={a["part_id"]:a["final_answer"] for a in pair["answers"]}
        comparison=[{"part_id":a["part_id"],"exact_match":digest(a["final_answer"])==digest(generated.get(a["part_id"]))}
                    for a in output["answers"]]
        saved=save_check_stage(token,candidate,"blind-"+pair["question_id"],[item],
                               blind=[{"question_id":pair["question_id"],"output":output,"comparison":comparison}])
        checks+=saved["checks"]
        blind+=saved["blind"]
    checkpoint(token,"Retrieving comparison questions")
    sources=[s for s in context["input"]["sources"] if s["id"] in context["input"]["comparison_source_ids"]]
    duplicates=duplicate_candidates(candidate.payload["pairs"],sources,context["input"]["history_content_ids"])
    retrieval_missing=bool(duplicates["available_source_ids"]) and not duplicates["candidates"]
    duplicate_status="fail" if duplicates["findings"] else "not_checked" if retrieval_missing else "pass"
    duplicate_reason=("Potential substantive duplicates need repair." if duplicates["findings"] else
                      "Supplied comparison pages have no usable excerpts; originality has not been checked." if retrieval_missing else
                      "No exact or number-only match in the supplied comparison and within this candidate; semantic review is still required.")
    item=check("local_duplicates",[p["question_id"] for p in candidate.payload["pairs"]],"normalised_retrieval",
               duplicate_status,duplicate_reason)
    saved=save_check_stage(token,candidate,"retrieval",[item],duplicates=duplicates)
    checks+=saved["checks"]
    duplicates=saved["duplicates"]
    checkpoint(token,"Semantic review",{"candidate_id":str(candidate.id)})
    semantic,repairs=run_semantic_review(token,context,candidate,checks,blind,duplicates,fixture_review)
    checks+=semantic
    checkpoint(token,"Optional checks",{"candidate_id":str(candidate.id)})
    checks+=run_optional_review(token,context,candidate,checks,blind,duplicates,fixture_review,
                                required_passed=release_gate(checks)["allowed"])
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
