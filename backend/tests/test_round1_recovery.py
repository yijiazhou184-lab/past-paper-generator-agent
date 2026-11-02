"""Focused recovery additions; existing lifecycle/snapshot/PDF tests supply the other stages."""
from unittest.mock import Mock
import subprocess
import pytest
from app.generation.math_checks import MathWorker
from app.core.tasks import submit_task,claim_task,checkpoint,finish_task,cancel_task
from app.core.errors import DomainError
from app.core.models import Task,TaskEvent


def test_windows_checker_exit_race_requires_a_confirmed_exit():
    process=Mock();process.poll.return_value=None
    process.kill.side_effect=PermissionError("Synthetic Windows exit race")
    process.wait.return_value=0
    worker=MathWorker();worker.process=process
    worker.close()
    assert worker.process is None
    process.wait.assert_any_call(timeout=0.5)


def test_inaccessible_live_checker_is_not_silently_accepted():
    process=Mock();process.poll.return_value=None
    process.kill.side_effect=PermissionError("Still running")
    process.wait.side_effect=subprocess.TimeoutExpired("synthetic",0.5)
    worker=MathWorker();worker.process=process
    with pytest.raises(PermissionError):worker.close()


def test_unknown_submit_response_reuses_task_and_checkpoint_before_cancel(course):
    task=submit_task(course,"parse",{"source_version":"synthetic"},"stable-intent")
    assert submit_task(course,"parse",{"source_version":"synthetic"},"stable-intent").id==task.id
    token=claim_task(task.id);checkpoint(token,"Saved local parse",{"evidence_hash":"synthetic-hash"})
    assert claim_task(task.id) is None
    cancel_task(course.owner,task.id)
    with pytest.raises(DomainError,match="STALE_EXECUTION"):finish_task(token,{"published":True})
    task.refresh_from_db()
    assert task.state=="cancelled" and task.checkpoint["evidence_hash"]=="synthetic-hash"
    assert Task.objects.filter(course=course).count()==1
    assert TaskEvent.objects.filter(task=task,stage="Saved local parse").exists()
