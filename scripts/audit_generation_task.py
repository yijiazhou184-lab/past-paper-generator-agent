"""Read-only audit of a retained generation task; replay local checks without any model calls.

Writes only ignored var/ audit files. Does not update the task, candidates, reports or grants.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from app.core.models import Task
from app.core.idempotency import digest
from app.generation.checks import mathematical_checks, program_checks, coverage_summary
from app.generation.duplicates import duplicate_candidates
from app.generation.shared_material import overlap_hints


def audit(task_id,candidate_id=None):
    task=Task.objects.get(pk=task_id,kind="generation")
    if task.state in ("queued","processing"):
        raise ValueError("Wait for the original task to reach a terminal state before offline replay.")
    candidates=task.candidates.order_by("-revision")
    candidate=candidates.get(pk=candidate_id) if candidate_id else candidates.first()
    if candidate is None:
        raise ValueError("This task has no complete candidate to replay.")
    report=candidate.check_report
    assert candidate.payload_hash==digest(candidate.payload)
    assert report.payload_hash==digest(report.payload)
    calls=list(task.model_calls.order_by("created_at"))
    model_calls=[c for c in calls if c.metadata.get("purpose")!="input_token_count"]
    def sum_usage(key):
        values=[c.result.get("usage",{}).get(key) for c in model_calls]
        return sum(values) if values and all(v is not None for v in values) else None
    local=program_checks(task.snapshot,candidate.payload)+mathematical_checks(candidate.payload["pairs"])
    sources=[s for s in task.snapshot["input"]["sources"] if s["id"] in task.snapshot["input"]["comparison_source_ids"]]
    duplicates=duplicate_candidates(candidate.payload["pairs"],sources,task.snapshot["input"]["history_content_ids"])
    summary={
        "audit_mode":"offline_replay_only_no_model_calls_no_original_record_changes",
        "audited_at":datetime.now(timezone.utc).isoformat(),
        "task_id":str(task.id),"original_state":task.state,"original_error_code":task.error.get("code"),
        "original_context_hash":task.snapshot["context_hash"],
        "candidate_id":str(candidate.id),"candidate_revision":candidate.revision,"report_id":str(report.id),
        "original_gate":report.gate,"original_coverage":report.payload["coverage_summary"],
        "elapsed_submission_seconds":(task.finished_at-task.created_at).total_seconds(),
        "elapsed_execution_seconds":(task.finished_at-task.started_at).total_seconds(),
        "model_calls":len(model_calls),"count_requests":len(calls)-len(model_calls),
        "call_states":dict(Counter(c.state for c in calls)),
        "model_response_statuses":dict(Counter(c.result.get("status","unknown") for c in model_calls)),
        "usage":{k:sum_usage(k) for k in ("input_tokens","output_tokens","total_tokens","cached_input_tokens","reasoning_tokens")},
        "billing_cost":None,"billing_note":"Provider billing was not queried.",
        "offline_local_coverage":coverage_summary(local),
        "offline_blocking_checks":[c for c in local if c["required_for_release"] and c["result"]!="pass"],
        "offline_retrieval":{"available_pages":len(sources),"selected_excerpts":len(duplicates["candidates"]),
            "compared_pages":len(duplicates["compared_source_ids"]),"retrieval_status":duplicates["retrieval_status"],
            "per_question":{p["question_id"]:sum(p["question_id"] in c["target_ids"] for c in duplicates["candidates"]) for p in candidate.payload["pairs"]},
            "exact_duplicate_findings":duplicates["findings"]},
        # Facts about intra-paper overlaps come only from a new review; offline replay records the program hints.
        "offline_intra_paper_hints":overlap_hints(candidate.payload["pairs"]),
        "offline_auxiliary_unresolved":[c["check_id"] for c in local if c.get("limitation")],
        "reused_groups":{a.key:a.payload for a in task.generation_artifacts.filter(key__startswith="reused:")},
        "new_model_calls":0,"new_semantic_review":False,"publication_allowed":False,
    }
    output={"summary":summary,"calls":[{"id":str(c.id),"key":c.call_key,"state":c.state,
        "created_at":c.created_at.isoformat(),"finished_at":c.finished_at.isoformat() if c.finished_at else None,
        "elapsed_seconds":(c.finished_at-c.created_at).total_seconds() if c.finished_at else None,
        "status":c.result.get("status"),"error_code":c.result.get("error_code"),"usage":c.result.get("usage"),
        "request_hash":c.request_hash} for c in calls],
        "offline_local_checks":local,"offline_duplicate_comparison":duplicates}
    task.refresh_from_db();candidate.refresh_from_db();report.refresh_from_db()
    assert task.model_calls.count()==len(calls)
    assert candidate.payload_hash==digest(candidate.payload) and report.payload_hash==digest(report.payload)
    path=ROOT/"var"/(f"generation-audit-{task.id}.json" if not candidate_id else f"generation-audit-{task.id}-{candidate.id}.json")
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"path":str(path),**summary},indent=2,ensure_ascii=True))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("--candidate",help="Replay this saved candidate instead of the latest revision")
    args=parser.parse_args()
    audit(args.task_id,args.candidate)
