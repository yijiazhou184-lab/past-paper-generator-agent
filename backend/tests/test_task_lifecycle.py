import pytest
from django.utils import timezone
from app.core.models import Task, Outbox
from app.core.tasks import submit_task, claim_task, checkpoint, cancel_task, finish_task
from app.core.errors import DomainError

pytestmark = pytest.mark.django_db(transaction=True)


def test_idempotency_and_busy(course):
    one = submit_task(course, "analysis", {"v": 1}, "same")
    assert submit_task(course, "analysis", {"v": 1}, "same").id == one.id
    assert Outbox.objects.count() == 1
    with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
        submit_task(course, "analysis", {"v": 2}, "same")
    with pytest.raises(DomainError, match="COURSE_BUSY"):
        submit_task(course, "generation", {"v": 1}, "new")


def test_cancel_fences_late_worker(course):
    task = submit_task(course, "parse", {}, "parse")
    token = claim_task(task.id)
    cancel_task(course.owner, task.id)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        checkpoint(token, "Late result")
    with pytest.raises(DomainError):
        finish_task(token, {"result": 1})
    task.refresh_from_db()
    assert task.state == "cancelled"


def test_success_wins_cancel(course):
    task = submit_task(course, "parse", {}, "parse")
    token = claim_task(task.id)
    finish_task(token, {})
    assert cancel_task(course.owner, task.id).state == "succeeded"


def test_stale_epoch_cannot_write(course):
    task = submit_task(course, "parse", {}, "parse")
    old = claim_task(task.id)
    Task.objects.filter(pk=task.id).update(execution_epoch=old.epoch + 1)
    with pytest.raises(DomainError, match="STALE_EXECUTION"):
        checkpoint(old, "Invalid")
