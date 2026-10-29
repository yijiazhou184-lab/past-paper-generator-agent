from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.core.tasks import cancel_task
from app.generation.generator import generate_groups,persist_candidate,run_generation
from app.generation.check_progress import save_check_stage,progress_report
from app.generation.checks import check
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
