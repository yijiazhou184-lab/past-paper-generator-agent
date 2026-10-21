import json
from django.conf import settings
from django.core.management.base import BaseCommand
from app.core.models import Task


class Command(BaseCommand):
    help = "Assert a real task recovered after worker interruption and kept its retry ancestors."

    def add_arguments(self, parser):
        parser.add_argument("task_id")

    def handle(self, task_id, **options):
        task = Task.objects.select_related("parent__parent").get(pk=task_id)
        attempts = list(task.attempts.order_by("created_at").values("epoch", "outcome", "created_at", "finished_at"))
        assert task.state == "succeeded", task.state
        assert any(a["outcome"] == "interrupted" for a in attempts)
        assert attempts[-1]["outcome"] == "succeeded"
        assert task.parent.state == "cancelled"
        assert task.parent.parent.state == "failed"
        report = {"mode": "real_local_no_models", "task_id": str(task.id), "state": task.state,
                  "attempts": attempts, "cancelled_parent": str(task.parent_id),
                  "failed_ancestor": str(task.parent.parent_id), "final_epoch": task.execution_epoch,
                  "driver_note": "The live fault-injection driver stopped during an unrelated API restart (HTTP 500). This follow-up asserts the persisted recovery outcome."}
        output = settings.BASE_DIR / "var/recovery-check.json"
        output.write_text(json.dumps(report, indent=2, default=str))
        self.stdout.write(json.dumps(report, default=str))
