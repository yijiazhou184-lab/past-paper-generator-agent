from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.core.tasks import cancel_task
from app.generation.generator import generate_groups,persist_candidate,run_generation
from app.generation.check_progress import save_check_stage,progress_report
from app.generation.checks import check
from app.generation import semantic_review
from app.generation.content_schemas import SemanticOutput
from app.generation.review_policy import OPTIONAL_CATEGORIES
from app.core.models import Task
from test_generation_execution import start
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_partial_results_survive_required_review_failure_without_answer_leak(course,planned,client):
    task,_,token=start(course,planned)
    with patch("app.generation.semantic_review.stage_output",side_effect=DomainError("TOKEN_BUDGET_EXCEEDED")):
        with pytest.raises(DomainError,match="TOKEN_BUDGET_EXCEEDED"):
            run_generation(token)
    candidate=task.candidates.get()
    report=progress_report(candidate)
    assert not report["complete"] and not report["gate"]["allowed"]
    assert all("question_ids" in s for s in report["stages"])
    assert any(c["method"]=="sympy_subprocess" and c["result"]=="pass" for c in report["checks"])
    assert any(c["method"]=="semantic_review" and c["result"]=="not_checked" for c in report["checks"])
    assert not hasattr(candidate,"check_report")
    client.force_login(course.owner)
    base=f"/api/v1/tasks/{task.id}/generation-content"
    public=client.get(base).json()["candidates"][0]["report"]
    assert not public["complete"] and public["stages"]
    assert all("rationale" not in c for c in public["checks"])
    assert "blind_comparison" not in public
    assert client.get(base+f"/{candidate.id}/answers").json()["report"]["checks"]


def test_stage_writes_are_idempotent_and_cancelled_worker_cannot_write(course,planned):
    task,context,token=start(course,planned)
    candidate=persist_candidate(token,context,generate_groups(token,context))
    checks=[check("test",[],"program","pass","ANSWER-ONLY-REASON")]
    save_check_stage(token,candidate,"program",checks)
    save_check_stage(token,candidate,"program",checks)
    assert task.generation_artifacts.filter(key="check:r0:program").count()==1
    cancel_task(course.owner,task.id)
    with pytest.raises(DomainError,match="STALE_EXECUTION"):
        save_check_stage(token,candidate,"math",checks)


def test_optional_review_no_longer_judges_background_references(course,planned):
    task,_,token=start(course,planned)
    actual=semantic_review.stage_output
    requested=[]
    def capture(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="optional":
            requested.append(data["optional_categories"])
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=capture):
        run_generation(token)
    report=task.candidates.get().check_report
    assert requested==[["wording","alternative_methods","difficulty_detail"]]
    optional=[c for c in report.payload["checks"] if c["method"]=="optional_review"]
    assert optional and not any(c["check_id"].endswith(":background_references") for c in optional)
    category=SemanticOutput.model_json_schema()["$defs"]["ReviewCheck"]["properties"]["category"]["enum"]
    assert "background_references" not in category


def test_partial_report_keeps_each_task_frozen_optional_categories(course,planned):
    task,_,token=start(course,planned)
    with patch("app.generation.semantic_review.stage_output",side_effect=DomainError("TOKEN_BUDGET_EXCEEDED")):
        with pytest.raises(DomainError,match="TOKEN_BUDGET_EXCEEDED"):
            run_generation(token)
    def optional_ids():
        candidate=Task.objects.get(pk=task.id).candidates.get()
        return {c["check_id"].rsplit(":",1)[1] for c in progress_report(candidate)["checks"]
                if c["method"]=="optional_review"}
    assert optional_ids()==set(OPTIONAL_CATEGORIES)
    # A task frozen under the previous policy still shows its own four optional placeholders.
    snapshot=Task.objects.get(pk=task.id).snapshot
    snapshot["review_policy"]["optional_categories"]=[*OPTIONAL_CATEGORIES,"background_references"]
    Task.objects.filter(pk=task.id).update(snapshot=snapshot)
    assert optional_ids()==set(OPTIONAL_CATEGORIES)|{"background_references"}
