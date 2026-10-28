import copy
from concurrent.futures import ThreadPoolExecutor
from django.db import transaction, close_old_connections
from django.utils import timezone
from app.core.tasks import checkpoint, locked_task
from app.core.models import Task, TaskAttempt, TaskEvent
from app.core.idempotency import digest
from app.core.errors import DomainError
from .models import CandidateVersion, GenerationArtifact
from .runtime import stage_output, verify_context, verify_generation_sources, save_artifact
from .content_schemas import PairOutput
from .content_validation import validate_group
from .content_fixtures import fixture_pair
from .source_policy import SOURCE_POLICY


def question_input(context,q,earlier):
    ids=set(q["blueprint"]["evidence_ids"])
    academic={k:copy.deepcopy(v) for k,v in q.items() if k!="issues"}
    return {**academic,"config":context["input"]["config"],
        "statements":context["input"]["statements"],
        "background_context":{"issues":copy.deepcopy(q.get("issues",[])),
                              "scope":context["input"]["course"]["scope_claims"]},
        "academic_source_ids":q["blueprint"]["evidence_ids"],
        "source_policy":context.get("source_policy",SOURCE_POLICY),
        "sources":[s for s in context["input"]["sources"] if s["id"] in ids],
        "earlier_question_summaries":earlier,
        "allowed_assets":["function_graph","data_table"],"software_answers":False,
        "checker_contract":context["checker_contract"]}


def generate_group(token,context,q,earlier,round_number=0,repair_request=None):
    data=question_input(context,q,earlier)
    stage="repair" if round_number else "question_pairs"
    if repair_request is not None:
        data["repair_request"]=repair_request
    key=f"r{round_number}:pair:{q['blueprint']['id']}"
    validated_key="validated:"+key
    input_hash=digest({"context_hash":context["context_hash"],"stage":stage,"input":data})
    task=Task.objects.get(pk=token.task_id)
    for previous_task in (task.id,task.parent_id):
        if previous_task is None:
            continue
        previous=GenerationArtifact.objects.filter(task_id=previous_task,key=validated_key,input_hash=input_hash).first()
        if previous and previous.payload_hash==digest(previous.payload):
            return save_artifact(token,validated_key,input_hash,previous.payload,previous.call_ids)
    output=stage_output(token,key,stage,data,PairOutput,lambda:fixture_pair(q["blueprint"]))
    validated=validate_group(q["blueprint"],output,context)
    raw=GenerationArtifact.objects.get(task_id=token.task_id,key=key)
    return save_artifact(token,validated_key,input_hash,validated,raw.call_ids)


def generate_groups(token,context,questions=None,round_number=0,repair_requests=None):
    questions=questions or context["input"]["questions"]
    groups=[]
    parallel=context["mode"]=="live"
    def work(q,earlier):
        if parallel:
            close_old_connections()
        try:
            return generate_group(token,context,q,earlier,round_number,
                                  (repair_requests or {}).get(q["blueprint"]["id"]))
        finally:
            if parallel:
                close_old_connections()
    for offset in range(0,len(questions),2):
        checkpoint(token,"Repairing questions" if round_number else "Generating questions and answers",
                   {"round":round_number,"completed_questions":[g["pair"]["question_id"] for g in groups]})
        earlier=[{"question_id":g["pair"]["question_id"],"stem":g["pair"]["stem"],
                  "parts":[p["prompt"] for p in g["pair"]["parts"]]} for g in groups]
        batch=questions[offset:offset+2]
        if parallel and len(batch)>1:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(work,q,earlier) for q in batch]
                groups.extend(f.result() for f in futures)
        else:
            groups.extend(work(q,earlier) for q in batch)
    return groups


@transaction.atomic
def persist_candidate(token,context,groups,revision=1,parent=None):
    task=locked_task(token)
    existing=CandidateVersion.objects.filter(task=task,revision=revision).first()
    if existing:
        if existing.payload_hash!=digest(existing.payload):
            raise DomainError("CANDIDATE_CONTENT_CHANGED")
        return existing
    if revision not in (1,2) or (revision==2 and (parent is None or parent.revision!=1 or parent.task_id!=task.id)):
        raise DomainError("REPAIR_ROUND_LIMIT")
    payload={"pairs":[g["pair"] for g in groups],"assets":[a for g in groups for a in g["assets"]]}
    ids=[p["question_id"] for p in payload["pairs"]]
    if ids!=[q["blueprint"]["id"] for q in context["input"]["questions"]]:
        raise DomainError("CANDIDATE_STRUCTURE_INVALID")
    if len({a["id"] for a in payload["assets"]})!=len(payload["assets"]):
        raise DomainError("DUPLICATE_ASSET_ID")
    artifacts=GenerationArtifact.objects.filter(task=task,key__startswith=f"validated:r{revision-1}:pair:")
    return CandidateVersion.objects.create(task=task,snapshot_id=context["input"]["snapshot_id"],parent=parent,
        revision=revision,payload=payload,payload_hash=digest(payload),mode=context["mode"],stage="repair" if parent else "generated",
        call_ids=[cid for a in artifacts for cid in a.call_ids])


@transaction.atomic
def needs_information(token,explanation,candidate=None,report=None):
    task=locked_task(token)
    task.state,task.stage="needs_info","Generation needs information"
    task.result={"mode":task.snapshot["mode"],"explanation":explanation,"allowed":False}
    if candidate is not None and report is not None:
        task.result.update(candidate_id=str(candidate.id),report_id=str(report.id),
                           candidate_revision=candidate.revision,
                           blocking_check_ids=report.gate["blocking_check_ids"])
    task.finished_at=timezone.now()
    task.save()
    TaskAttempt.objects.filter(task=task,epoch=token.epoch).update(outcome="needs_info",finished_at=task.finished_at)
    TaskEvent.objects.create(task=task,epoch=token.epoch,stage=task.stage)


def run_generation(token):
    task=Task.objects.select_related("course__owner").get(pk=token.task_id)
    context=task.snapshot
    checkpoint(token,"Checking inputs")
    verify_context(task)
    verify_generation_sources(task)
    try:
        groups=generate_groups(token,context)
    except DomainError as exc:
        if exc.payload["code"]=="GENERATION_NEEDS_INFO":
            needs_information(token,exc.payload["message"])
            return
        raise
    candidate=persist_candidate(token,context,groups)
    checkpoint(token,"Program checks",{"candidate_id":str(candidate.id),"revision":candidate.revision})
    from .reviewer import check_candidate, finish_candidate
    report=check_candidate(token,context,candidate)
    if not report.gate["allowed"]:
        from .repair import repair_candidate
        try:
            repaired=repair_candidate(token,context,candidate,report)
        except DomainError as exc:
            if exc.payload["code"]=="GENERATION_NEEDS_INFO":
                needs_information(token,exc.payload["message"],candidate,report)
                return
            raise
        if repaired is not None:
            candidate=repaired
            checkpoint(token,"Final checks",{"candidate_id":str(candidate.id),"revision":candidate.revision})
            report=check_candidate(token,context,candidate)
    finish_candidate(token,candidate,report)
