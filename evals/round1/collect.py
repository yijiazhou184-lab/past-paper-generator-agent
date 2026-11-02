"""Read existing tasks and artifacts; no model calls, no writes to business records."""
import json
from pathlib import Path
from .records import RunRecord,digest,delivery_timing,write_record


def collect_run(run_id,task_ids,*,planned_slot=None,kind="original",retest_of=None):
    from .run import setup,ROOT,bind_task
    setup()
    from app.core.models import Task
    from app.papers.models import Paper
    from app.papers.reader import pdf_state
    tasks=list(Task.objects.filter(pk__in=task_ids).order_by("created_at"))
    if len(tasks)!=len(set(task_ids)):raise ValueError("Some tasks do not exist")
    if len({t.course_id for t in tasks})>1:raise ValueError("A run cannot silently mix courses")
    generations=[t for t in tasks if t.kind=="generation"]
    if len(generations)>1:raise ValueError("Register a second generation as a retest")
    record=RunRecord(run_id,planned_slot=planned_slot or retest_of or run_id,kind=kind,retest_of=retest_of)
    record.task_ids=[str(t.id) for t in tasks]
    root=ROOT/"var/evals/round1"
    baselines=[];usage_rows=[]
    for task in tasks:
        if task.kind in ("analysis","planning","generation"):bind_task(root,run_id,task.kind,task)
        snapshot=task.snapshot;data=snapshot.get("input",{})
        baselines.append({k:snapshot[k] for k in ("model","model_settings","prompt_version","schema_hash","schema_hashes","prompts","prompt","pipeline_version","max_calls","task_seconds","max_input_tokens","generation_output_tokens") if k in snapshot})
        record.bindings[str(task.id)]={"kind":task.kind,"state":task.state,"result":task.result,"error":task.error,
            "checkpoint":task.checkpoint,"snapshot_hash":digest(snapshot),"context_hash":snapshot.get("context_hash"),
            "submitted_at":task.created_at,"started_at":task.started_at,"finished_at":task.finished_at,
            "events":list(task.events.order_by("created_at").values("stage","created_at","detail")),
            "course_id":str(task.course_id),"course_version_id":data.get("course_version_id"),"config":data.get("config"),
            "blueprint_hash":digest(data["blueprint"]) if data.get("blueprint") else None,
            "history_hash":digest(data["history_papers"]) if "history_papers" in data else None,
            "history_content_ids":data.get("history_content_ids"),"schema_hashes":snapshot.get("schema_hashes"),
            "sources":[{k:s[k] for k in ("id","material_version_id","parse_version_id","physical_page","parse_content_hash","blob_sha256","content_hash") if k in s} for s in data.get("sources",data.get("evidence",[]))]}
        if task.error:
            record.notes.append({"task_id":str(task.id),"kind":task.kind,"state":task.state,"error":task.error})
        if task.kind=="visual_transcription":
            failed_pages=[p for p in task.result.get("pages",task.checkpoint.get("pages",[])) if p.get("outcome")=="failed"]
            if failed_pages:
                record.notes.append({"task_id":str(task.id),"kind":task.kind,"state":task.state,
                    "partial_failure":True,"failed_pages":failed_pages})
        record.attempts.extend([{"task_id":str(task.id),**a} for a in task.attempts.values("epoch","outcome","usage","created_at","finished_at")])
        for call in task.model_calls.order_by("created_at"):
            result=call.result
            record.calls.append({"id":str(call.id),"task_id":str(task.id),"key":call.call_key,"epoch":call.epoch,"state":call.state,
                "request_hash":call.request_hash,"created_at":call.created_at,"finished_at":call.finished_at,"metadata":call.metadata,
                "status":result.get("status"),"error_code":result.get("error_code"),"elapsed_seconds":result.get("elapsed_seconds"),
                "usage":result.get("usage"),"counted_input_tokens":call.metadata.get("counted_input_tokens"),
                "input_token_count":(result.get("payload") or {}).get("input_tokens") if call.metadata.get("purpose")=="input_token_count" else None})
            if call.metadata.get("purpose")!="input_token_count":usage_rows.append(result.get("usage"))
        if snapshot.get("mode")=="fixture":record.mode="fixture"
    record.baseline_version=digest(baselines[-1] if baselines else {})
    if usage_rows and all(v and all(v.get(k) is not None for k in ("input_tokens","output_tokens","total_tokens")) for v in usage_rows):
        record.usage={k:sum(v[k] for v in usage_rows) for k in ("input_tokens","output_tokens","total_tokens")}
    from .records import interval_seconds
    stage_timing={}
    for kind_name in ("analysis","planning","visual_transcription"):
        intervals=[(t.created_at,t.finished_at) for t in tasks if t.kind==kind_name]
        stage_timing[kind_name+"_system_seconds"]=interval_seconds(intervals) if intervals and all(b for a,b in intervals) else None
    analysis_tasks=[t for t in tasks if t.kind=="analysis"]
    analysis_calls=[c for c in record.calls if c["task_id"] in {str(t.id) for t in analysis_tasks} and c["metadata"].get("purpose")!="input_token_count" and c["finished_at"]]
    stage_timing["analysis_first_response_seconds"]=(min(c["finished_at"] for c in analysis_calls)-analysis_tasks[0].created_at).total_seconds() if analysis_calls else None
    stage_timing["analysis_user_wait_seconds"]=None
    record.timing=stage_timing
    if generations:
        generation=generations[0]
        paper=Paper.objects.filter(generation_task=generation).select_related("content").first()
        export_tasks=list(Task.objects.filter(kind="export",snapshot__paper_id=str(paper.id)).order_by("created_at")) if paper else []
        for export in export_tasks:
            if str(export.id) not in record.task_ids:
                record.task_ids.append(str(export.id))
                record.attempts.extend([{"task_id":str(export.id),**a} for a in export.attempts.values("epoch","outcome","usage","created_at","finished_at")])
        ready=bool(paper and pdf_state(paper)["status"]=="ready")
        record.timing={**stage_timing,**delivery_timing((generation.created_at,generation.finished_at),[(t.created_at,t.finished_at) for t in export_tasks],ready)}
        if paper:
            record.outputs={"paper_id":str(paper.id),"content_version_id":str(paper.content_id),"content_hash":paper.content.payload_hash,
                "answer_unit_ids":[part["part_id"] for pair in paper.content.payload["content"]["pairs"] for part in pair["parts"]],
                "pdfs":[{"kind":a.kind,"sha256":a.sha256,"path":a.path,"pages":a.pages,"bytes":a.size} for a in paper.content.pdfs.all()]}
            from app.generation.checks import release_gate
            record.checks={"required_passed":release_gate(paper.content.payload["report"]["checks"])["allowed"],"report":paper.content.payload["report"]}
        else:
            candidate=generation.candidates.order_by("-revision").first()
            if candidate:
                from app.generation.check_progress import progress_report
                record.outputs={"candidate_version_id":str(candidate.id),"candidate_hash":candidate.payload_hash,
                    "answer_unit_ids":[p["part_id"] for pair in candidate.payload["pairs"] for p in pair["parts"]]}
                record.checks={"required_passed":False,"report":candidate.check_report.payload if hasattr(candidate,"check_report") else progress_report(candidate)}
        failed=any(t.state in ("failed","cancelled","needs_info") for t in tasks+export_tasks)
        record.status="failed" if failed else "completed" if ready else "incomplete" if generation.finished_at else "running"
        record.notes.extend([{"task_id":str(t.id),"state":t.state,"error":t.error} for t in export_tasks if t.error])
    else:
        record.status="failed" if any(t.state in ("failed","cancelled","needs_info") for t in tasks) else "awaiting_generation"
    path=write_record(root,record)
    return record,path


def main():
    import argparse
    from .records import apply_quality_review
    from .run import ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",required=True);parser.add_argument("--task-id",action="append",required=True)
    parser.add_argument("--planned-slot");parser.add_argument("--kind",choices=["original","extension","retest","fault_fixture"],default="original")
    parser.add_argument("--retest-of");parser.add_argument("--review-file")
    args=parser.parse_args()
    record,path=collect_run(args.run,args.task_id,planned_slot=args.planned_slot,kind=args.kind,retest_of=args.retest_of)
    if args.review_file:
        reviewed=apply_quality_review(record,json.loads(Path(args.review_file).read_text()))
        path=write_record(ROOT/"var/evals/round1",reviewed)
    print(json.dumps({"record":str(path),"status":record.status,"mode":record.mode}))
if __name__=="__main__":main()
