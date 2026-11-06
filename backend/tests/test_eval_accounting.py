import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from evals.round1.records import RunRecord,summarise_runs,delivery_timing,interval_seconds,write_record


def complete(slot,**kwargs):
    return RunRecord(slot,planned_slot=slot,status="completed",task_ids=["task-"+slot],
        timing={"delivery_complete":True},checks={"required_passed":True},quality_review={"status":"passed"},**kwargs)


def test_failures_and_retests_do_not_replace_six_original_slots():
    rows=[complete("R"+str(i)) for i in range(1,7)]
    rows[2].status="failed"
    rows.append(complete("E1",kind="extension"))
    retry=complete("R3-retest-01",kind="retest",retest_of="R3");retry.planned_slot="R3";rows.append(retry)
    report=summarise_runs(rows)
    assert report["planned_total"]==6 and report["passed"]==5
    assert report["failed_slots"]==["R3"] and len(report["extension_runs"])==1
    assert report["retests"]==["R3-retest-01"] and not report["all_six_passed"]


def test_missing_review_or_pdf_cannot_pass_and_unknown_usage_is_not_zero():
    row=complete("R1");row.timing["delivery_complete"]=False
    report=summarise_runs([row])
    assert report["passed"]==0 and report["usage_unknown_runs"]==1
    row.timing["delivery_complete"]=True;row.quality_review={"status":"not_reviewed"}
    assert summarise_runs([row])["passed"]==0
    assert summarise_runs([])["executed_success_rate"] is None


def test_queue_wall_time_and_user_export_wait_are_separate():
    value=delivery_timing(("2026-11-02T00:00:00+00:00","2026-11-02T00:05:00+00:00"),
        [("2026-11-02T00:07:00+00:00","2026-11-02T00:07:10+00:00")],True)
    assert value=={"generation_seconds":300.0,"export_seconds":10.0,"user_wait_seconds":120.0,"complete_system_seconds":310.0,"delivery_complete":True}
    assert interval_seconds([("2026-11-02T00:00:00Z","2026-11-02T00:00:10Z"),("2026-11-02T00:00:03Z","2026-11-02T00:00:12Z")])==12
    assert delivery_timing((None,None),[],False)["complete_system_seconds"] is None


def test_changed_baselines_and_append_only_records_are_visible(tmp_path):
    rows=[complete("R1",baseline_version="old"),complete("R2",baseline_version="new")]
    assert summarise_runs(rows)["baselines"]==["new","old"]
    path=write_record(tmp_path,rows[0])
    with pytest.raises(FileExistsError):write_record(tmp_path,rows[0])
    assert path.exists()


def test_review_is_bound_to_content_and_all_answer_units():
    from evals.round1.records import apply_quality_review
    row=complete("R1");row.outputs={"content_hash":"original","answer_unit_ids":["a","b"]}
    review={"reviewer":"Development reviewer","content_hash":"original","units":[{"unit_id":"a","status":"correct"},{"unit_id":"b","status":"not_checked"}]}
    assert apply_quality_review(row,review)["quality_review"]["status"]=="failed"
    with pytest.raises(ValueError):apply_quality_review(row,{**review,"content_hash":"another-content"})
    with pytest.raises(ValueError):apply_quality_review(row,{**review,"units":review["units"][:1]})


from test_generation_snapshot import version
from test_course_drafts import draft,course_payload,analysis_context


def test_default_preflight_is_read_only_and_fixture_is_never_a_real_run(course,version,tmp_path,monkeypatch):
    import json
    from evals.round1 import run
    from app.courses.topics import create_topic,register_legacy_mapping
    from app.core.models import Task,ModelInvocation
    from app.generation.models import GenerationDraft
    topic=create_topic(course.owner,course.id,{"name":"Synthetic topic"},"eval-topic")
    ids=[n["id"] for n in version.frozen_payload["knowledge_nodes"]]
    register_legacy_mapping(course.owner,version.id,topic.id,ids,"Reviewed synthetic correspondence")
    manifest={"schema_version":"round1-acceptance-v1","course_id":str(course.id),"topic_id":str(topic.id),
        "knowledge":{"N":ids[0]},"response_types":["calculation"],"rubric":"rubric.yaml",
        "runs":[{"id":"R1","kind":"original","knowledge":["N"],"difficulty":"exam_standard","question_count":2}]}
    path=tmp_path/"manifest.yaml";path.write_text(json.dumps(manifest));(tmp_path/"rubric.yaml").write_text("{}")
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    before=Task.objects.count()
    result=run.run_acceptance(path,"R1")
    assert result["submitted"] is False and Path(result["scope"]).exists()
    assert Task.objects.count()==before and not ModelInvocation.objects.exists() and not GenerationDraft.objects.exists()
    with pytest.raises(ValueError,match="Synthetic runs"):
        run.run_acceptance(path,"R1",execute=True,grant_reference="not-a-grant")


from test_papers import paper,planned,config


def test_collect_reads_actual_saved_candidate_report_and_unknown_usage(paper,tmp_path,monkeypatch):
    from evals.round1 import run
    from evals.round1.collect import collect_run
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    before=copy_payload=paper.content.payload_hash
    record,path=collect_run("fixture-collection",[str(paper.generation_task_id)],kind="fault_fixture")
    assert record.mode=="fixture" and record.status=="incomplete"
    assert record.checks["required_passed"] is True
    assert record.outputs["answer_unit_ids"] and record.usage is None and record.cost_estimate is None
    assert not record.timing["delivery_complete"] and path.exists()
    paper.content.refresh_from_db();assert paper.content.payload_hash==before


def test_collect_preserves_page_failure_inside_completed_transcription(course,tmp_path,monkeypatch):
    from django.utils import timezone
    from app.core.models import Task
    from evals.round1 import run
    from evals.round1.collect import collect_run
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    outcome={"pages":[{"evidence_id":"page-a","outcome":"transcribed"},
        {"evidence_id":"page-b","outcome":"failed","code":"MODEL_SOURCE_MISMATCH"}],"transcribed":1,"failed":1}
    task=Task.objects.create(course=course,kind="visual_transcription",state="succeeded",result=outcome)
    task.finished_at=task.created_at;task.save(update_fields=["finished_at"])
    record,path=collect_run("E1",[str(task.id)],kind="extension")
    assert record.status=="awaiting_generation" and record.quality_review["status"]=="not_reviewed"
    assert record.bindings[str(task.id)]["result"]==outcome
    assert record.notes[0]["partial_failure"] is True
    assert record.notes[0]["failed_pages"]==[outcome["pages"][1]]
    task.refresh_from_db();assert task.result==outcome and task.state=="succeeded"


def test_collect_keeps_planning_error_without_a_generation_task(course,tmp_path,monkeypatch):
    from django.utils import timezone
    from app.core.models import Task
    from evals.round1 import run
    from evals.round1.collect import collect_run
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    error={"code":"QUESTION_COVERAGE_MISMATCH","message":"Question knowledge must match its parts.","retryable":False}
    task=Task.objects.create(course=course,kind="planning",state="failed",error=error)
    task.finished_at=task.created_at;task.save(update_fields=["finished_at"])
    record,path=collect_run("R1",[str(task.id)])
    assert record.status=="failed" and record.bindings[str(task.id)]["error"]==error
    assert record.notes==[{"task_id":str(task.id),"kind":"planning","state":"failed","error":error}]
    assert record.usage is None and record.cost_estimate is None


def test_explicit_skip_is_separate_from_failure_or_unexecuted():
    failed=complete("R1");failed.status="failed"
    skipped=RunRecord("R2",planned_slot="R2",status="skipped")
    report=summarise_runs([failed,skipped])
    assert report["planned_total"]==6 and report["active_planned_total"]==5
    assert report["skipped_slots"]==["R2"]
    assert report["failed_slots"]==["R1"] and report["attempted"]==1
    assert report["not_executed_slots"]==["R3","R4","R5","R6"]
    assert report["passed"]==0 and report["planned_success_fraction"]==0
    assert report["all_six_passed"] is False


def test_analysis_followup_keeps_original_task_binding(course,tmp_path,monkeypatch):
    import json
    from app.core.models import Task
    from evals.round1 import run
    from evals.round1.collect import collect_run
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    first=Task.objects.create(course=course,kind="analysis",state="succeeded",snapshot={"context_hash":"first"})
    first.finished_at=first.created_at;first.save(update_fields=["finished_at"])
    collect_run("E1",[str(first.id)],kind="extension")
    binding=tmp_path/"var/evals/round1/E1/analysis-task.json"
    original=binding.read_bytes()
    second=Task.objects.create(course=course,kind="analysis",state="succeeded",snapshot={"context_hash":"followup"})
    second.finished_at=second.created_at;second.save(update_fields=["finished_at"])
    record,path=collect_run("E1",[str(first.id),str(second.id)],kind="extension")
    assert binding.read_bytes()==original
    assert set(record.bindings)=={str(first.id),str(second.id)}
    extra=binding.parent/("analysis-followup-"+str(second.id)+"-task.json")
    assert json.loads(extra.read_text())["task_id"]==str(second.id)
    assert Task.objects.count()==2 and record.status=="awaiting_generation"


@pytest.mark.parametrize("confirmed",[True,False])
def test_analysis_needs_info_is_resolved_only_by_the_papers_actual_confirmed_version(paper,tmp_path,monkeypatch,confirmed):
    from types import SimpleNamespace
    from unittest.mock import patch
    from django.utils import timezone
    from app.core.models import Task
    from evals.round1 import run
    from evals.round1.collect import collect_run
    monkeypatch.setattr(run,"ROOT",tmp_path);monkeypatch.setattr(run,"setup",lambda:None)
    analysis=Task.objects.create(course=paper.course,kind="analysis",state="needs_info",finished_at=timezone.now())
    version=SimpleNamespace(id=paper.content.payload["metadata"]["course_version_id"],evidence_manifest={"topic_snapshots":{
        "topic":{"context":{"analysis_task_id":str(analysis.id) if confirmed else "different-analysis"}}}})
    with patch("app.courses.models.CourseVersion.objects.get",return_value=version) as lookup:
        record,path=collect_run("analysis-resolved",[str(analysis.id),str(paper.generation_task_id)],kind="fault_fixture")
    lookup.assert_called_once_with(pk=version.id,course=paper.course)
    assert record.status==("incomplete" if confirmed else "failed")  # PDFs are absent in this fixture.
    assert bool([n for n in record.notes if n.get("resolved_by_course_version")])==confirmed
    analysis.refresh_from_db();assert analysis.state=="needs_info"  # Never rewrite the actual task outcome.
