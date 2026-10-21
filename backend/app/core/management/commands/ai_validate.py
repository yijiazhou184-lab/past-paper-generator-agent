import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from app.courses.models import Course
from app.core.models import Task
from app.core.tasks import submit_task
from app.ai.validation import build_snapshot


class Command(BaseCommand):
    help = "Explicitly submit the bounded batch-one live check, or export its local evidence. No automatic retries."

    def add_arguments(self, parser):
        parser.add_argument("--submit", action="store_true")
        parser.add_argument("--allow-course-data-upload", action="store_true")
        parser.add_argument("--smoke-only", action="store_true")
        parser.add_argument("--key")
        parser.add_argument("--parent", metavar="TASK_ID")
        parser.add_argument("--report", metavar="TASK_ID")

    def handle(self, **options):
        if options["report"]:
            task = Task.objects.get(pk=options["report"], kind="ai_validation", course__owner__username="local")
            calls = list(task.model_calls.order_by("created_at").values(
                "id", "call_key", "epoch", "created_at", "finished_at", "metadata", "request_hash", "state", "result"))
            report = {"task_id": str(task.id), "state": task.state, "error": task.error, "snapshot": task.snapshot,
                      "result": task.result, "calls": calls, "created_at": task.created_at,
                      "started_at": task.started_at, "finished_at": task.finished_at,
                      "wall_seconds": (task.finished_at - task.created_at).total_seconds() if task.finished_at else None,
                      "processing_seconds": (task.finished_at - task.started_at).total_seconds()
                          if task.finished_at and task.started_at else None}
            output = settings.BASE_DIR / "var" / f"batch1-live-{task.id}.json"
            output.write_text(json.dumps(report, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(json.dumps({"task_id": str(task.id), "state": task.state, "call_count": len(calls),
                "calls": [{"key": c["call_key"], "state": c["state"], "status": c["result"].get("status"),
                           "error": c["result"].get("error_code")} for c in calls], "report": str(output)}))
            return
        if not (options["submit"] and options["key"] and (options["allow_course_data_upload"] or options["smoke_only"])):
            raise CommandError("Use --submit --key <unique-run-key> with --smoke-only or --allow-course-data-upload; or --report <task-id>.")
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise CommandError("API_KEY_MISSING: set it locally in .env.local; never send it in chat.")
        course = Course.objects.get(owner__username="local")
        model = os.environ.get("OPENAI_MODEL", "gpt-6.1-sol")
        parent = Task.objects.get(pk=options["parent"], course=course, kind="ai_validation",
                                  state__in=["failed", "cancelled"]) if options["parent"] else None
        task = submit_task(course, "ai_validation", build_snapshot(course, model, smoke_only=options["smoke_only"]),
                           options["key"], parent=parent)
        self.stdout.write(json.dumps({"task_id": str(task.id), "state": task.state, "model": model,
            "max_calls": 1 if options["smoke_only"] else 6, "page_count": 0 if options["smoke_only"] else 5, "store": False,
            "url": f"http://127.0.0.1:5173/tasks/{task.id}"}))
