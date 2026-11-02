"""Bounded acceptance commands. Default is a local preflight; no provider calls here."""
import argparse,json,os,sys,uuid
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evals.round1.records import RunRecord,digest,write_record

def setup():
    sys.path.insert(0,str(ROOT/"backend"));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()

def load_manifest(path):
    # JSON is a YAML 1.2 subset; this deterministic manifest needs no new YAML dependency.
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version")!="round1-acceptance-v1":raise ValueError("Unknown manifest version")
    return value

def definition(manifest,run_id,retest_of=None):
    slot=retest_of or run_id
    value=next((r for r in manifest["runs"] if r["id"]==slot),None)
    if value is None:raise ValueError("Unknown acceptance slot")
    if retest_of and run_id==retest_of:raise ValueError("A retest must use a new run ID")
    return value

def config_for(manifest,run,version,topic_id=None):
    ids=[manifest["knowledge"][k] for k in run["knowledge"]]
    return {"schema_version":"practice-config-v2","course_version_id":str(version.id),"mode":"chapter_practice",
        "selected_topic_ids":[topic_id or manifest["topic_id"]],"knowledge_ids":ids,
        "difficulty":run["difficulty"],"main_question_count":run["question_count"],"question_types":manifest["response_types"]}

def check_matrix(blueprint,run,knowledge=None):
    questions=blueprint["questions"]
    if len(questions)!=run["question_count"] or [len(q["parts"]) for q in questions]!=run["parts"]:
        raise ValueError("The confirmed structure does not match the frozen part counts")
    if [sum(p["marks"] for p in q["parts"]) for q in questions]!=run["marks"] or blueprint["suggested_minutes"]!=run["minutes"]:
        raise ValueError("The confirmed marks/minutes do not match the acceptance matrix")
    if not blueprint["subquestion_count_locked"]:raise ValueError("Lock the part count before acceptance")
    if knowledge is not None and "knowledge" in run:
        expected={knowledge[k] for k in run["knowledge"]}
        actual={kid for q in questions for part in q["parts"] for kid in part["knowledge_ids"]}
        if actual!=expected:
            raise ValueError("The whole-paper knowledge coverage does not match the acceptance selection")

def require_grant(stage,reference,course,context_hash):
    from app.courses.models import AnalysisGrant
    from app.generation.models import PlanningGrant,GenerationGrant
    model={"analysis":AnalysisGrant,"planning":PlanningGrant,"generation":GenerationGrant}[stage]
    try:grant=model.objects.get(pk=reference,course=course,context_hash=context_hash,granted_by=course.owner)
    except (model.DoesNotExist,ValueError):raise ValueError("A matching reviewed grant is required; no task was submitted") from None
    return grant

def bind_task(root,run_id,stage,task):
    directory=Path(root)/run_id;directory.mkdir(parents=True,exist_ok=True)
    path=directory/(stage+"-task.json")
    value={"task_id":str(task.id),"context_hash":task.snapshot.get("context_hash"),"blueprint_hash":digest(task.snapshot["input"]["blueprint"]) if task.snapshot.get("input",{}).get("blueprint") else None}
    if path.exists():
        if json.loads(path.read_text())!=value:raise ValueError("This slot already has a different task. Register a retest instead.")
    else:
        with path.open("x") as stream:json.dump(value,stream)
    return value

def run_acceptance(manifest_path,run_id,grant_reference=None,*,execute=False,stage="planning",selection_path=None,retest_of=None):
    setup()
    from app.courses.models import Course,CourseVersion
    from app.generation.models import GenerationDraft
    from app.generation.config_compat import course_projection
    from app.generation.schemas import validate_config
    from app.courses.topic_confirmation import assert_topic_generation_current
    from app.generation import planning
    from app.generation.execution_context import prepare_generation,submit_generation
    from app.generation.snapshots import save_config
    manifest=load_manifest(manifest_path);run=definition(manifest,run_id,retest_of)
    binding=json.loads(Path(selection_path).read_text()) if selection_path else {}
    course=Course.objects.get(pk=binding.get("course_id",manifest["course_id"]))
    record=RunRecord(run_id,planned_slot=run["id"],kind="retest" if retest_of else run["kind"],retest_of=retest_of)
    evidence_root=ROOT/"var/evals/round1";key="acceptance:"+run_id+":"+stage
    if execute and (evidence_root/run_id/(stage+"-task.json")).exists():
        # Replaying a command returns the original task binding, even if live history has grown.
        return json.loads((evidence_root/run_id/(stage+"-task.json")).read_text())
    current=GenerationDraft.objects.filter(course=course).select_related("course_version","confirmation","blueprint").first()
    if stage=="analysis":
        from app.courses.topic_context import build_topic_analysis_context
        from app.courses.analysis import submit_analysis
        if not binding:raise ValueError("Analysis requires an explicit private selection file")
        snapshot=build_topic_analysis_context(course,binding["target_topic_ids"],binding["material_selection"],binding["base_revision"])
        if execute:
            if snapshot.get("mode","live")!="live":raise ValueError("Synthetic runs cannot fill real acceptance slots")
            require_grant(stage,grant_reference,course,snapshot["context_hash"])
            task=submit_analysis(course,snapshot["context_hash"],key,authorize=False,target_topic_ids=binding["target_topic_ids"],material_selection=binding["material_selection"],base_revision=binding["base_revision"])
    elif stage=="planning":
        if run["id"]=="E1" and not binding.get("config"):raise ValueError("E1 needs its new confirmed course and explicit configuration")
        if execute and run["id"] in ("R2","R3"):raise ValueError("R2/R3 reuse R1's confirmed blueprint. Use the generation stage.")
        version=CourseVersion.objects.get(pk=binding["course_version_id"],course=course) if binding.get("course_version_id") else course.confirmed_versions.order_by("-number").first()
        if version is None:raise ValueError("Confirm the selected topic first")
        config=binding.get("config") or config_for(manifest,run,version)
        validate_config(config,course_projection(version),version.evidence_manifest["evidence"])
        assert_topic_generation_current(version,config)
        revision=(current.revision if current else 0)+1
        proposal=SimpleNamespace(course_version=version,config=config,id=current.id if current else uuid.uuid5(course.id,"acceptance-config"),revision=revision,config_hash=digest(config))
        snapshot=planning.build_context(proposal)
        if execute:
            if snapshot.get("mode","live")!="live":raise ValueError("Synthetic runs cannot fill real acceptance slots")
            require_grant(stage,grant_reference,course,snapshot["context_hash"])
            saved,_=save_config(course.owner,course.id,current.revision if current else 0,config,key+":config")
            if planning.build_context(saved)["context_hash"]!=snapshot["context_hash"]:raise ValueError("Planning inputs changed")
            task=planning.submit_plan(course.owner,course.id,saved.revision,snapshot["context_hash"],key,authorize=False)
    elif stage=="generation":
        if not current or not current.confirmation_id:raise ValueError("Review and confirm the acceptance structure first")
        config=binding.get("config") or config_for(manifest,run,current.course_version)
        if current.config!=config:raise ValueError("Saved configuration does not match this acceptance slot")
        if "parts" in run:check_matrix(current.blueprint.payload,run,manifest["knowledge"])
        snapshot=prepare_generation(course.owner,course.id,current.confirmation_id,current.revision,current.config_hash,key+":preflight")
        if run["id"] in ("R2","R3"):
            from app.core.models import Task
            for predecessor in (["R1"] if run["id"]=="R2" else ["R1","R2"]):
                previous_path=evidence_root/predecessor/"generation-task.json"
                if not previous_path.exists():raise ValueError("Complete and record preceding history runs first")
                previous=json.loads(previous_path.read_text())
                original=Task.objects.get(pk=previous["task_id"],course=course)
                if original.state!="succeeded" or not hasattr(original,"paper"):
                    raise ValueError("The preceding run did not save a successful paper; do not silently replace its failed slot")
                if previous["blueprint_hash"]!=digest(current.blueprint.payload):
                    raise ValueError("R1-R3 must use the same confirmed blueprint")
        if execute:
            if snapshot.get("mode","live")!="live":raise ValueError("Synthetic runs cannot fill real acceptance slots")
            require_grant(stage,grant_reference,course,snapshot["context_hash"])
            task=submit_generation(course.owner,course.id,current.confirmation_id,current.revision,current.config_hash,snapshot["context_hash"],key,authorize=False)
    else:raise ValueError("Unknown model stage")
    record.mode=snapshot.get("mode","live")
    if execute and record.mode!="live":raise ValueError("Synthetic runs cannot fill real acceptance slots")
    if execute:record.task_ids=[str(task.id)]
    record.bindings={"rubric_hash":digest(json.loads((Path(manifest_path).parent/manifest["rubric"]).read_text())), "manifest_hash":digest(manifest),"course_id":str(course.id),"stage":stage,"context_hash":snapshot["context_hash"]}
    record.baseline_version=digest({k:v for k,v in snapshot.items() if k in ("model","model_settings","prompt_version","schema_version","schema_hash","schema_hashes","prompts","prompt","pipeline_version","max_calls","task_seconds","max_input_tokens","max_output_tokens","generation_output_tokens","generation_call_seconds")})
    record.status="running" if execute else "preflight_ready"
    path=write_record(evidence_root,record)
    (path.parent/"preflight.json").write_text(json.dumps(snapshot,indent=2,default=str),encoding="utf-8")
    if execute:
        record.task_ids=[str(task.id)];bind_task(evidence_root,run_id,stage,task)
        (path.parent/"submission.json").write_text(json.dumps({"task_id":str(task.id),"grant_reference":str(grant_reference)},indent=2))
    return {"record":str(path),"scope":str(path.parent/"preflight.json"),"context_hash":snapshot["context_hash"],"submitted":execute,"task_id":str(task.id) if execute else None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",default=str(ROOT/"evals/round1/manifest.yaml"));parser.add_argument("--run",required=True)
    parser.add_argument("--stage",choices=["analysis","planning","generation"],default="planning")
    parser.add_argument("--preflight",action="store_true");parser.add_argument("--execute",action="store_true")
    parser.add_argument("--grant-ref");parser.add_argument("--selection-file");parser.add_argument("--retest-of")
    args=parser.parse_args()
    if args.execute and args.preflight:parser.error("Choose execute or preflight")
    if args.execute and not args.grant_ref:parser.error("--execute requires a matching reviewed --grant-ref")
    value=run_acceptance(args.manifest,args.run,args.grant_ref,execute=args.execute,stage=args.stage,selection_path=args.selection_file,retest_of=args.retest_of)
    print(json.dumps(value))
if __name__=="__main__":main()
