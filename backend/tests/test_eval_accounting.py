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
