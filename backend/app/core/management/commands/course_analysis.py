import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from app.courses.models import Course
from app.courses.context import build_context, inspect_scope
from app.courses.analysis import submit_analysis
from app.core.models import Task


class Command(BaseCommand):
    help = "Inspect the exact local analysis scope; explicitly grant and submit only after user authorisation."

    def add_arguments(self, parser):
        parser.add_argument("--submit", action="store_true")
        parser.add_argument("--allow-course-data-upload", action="store_true")
        parser.add_argument("--context-hash")
        parser.add_argument("--key")
        parser.add_argument("--report")

    def handle(self, **options):
        course = Course.objects.get(owner__username="local", code="MSIN0180")
        if options["report"]:
            task = Task.objects.get(pk=options["report"], course=course, kind="analysis")
            report = {"id": str(task.id), "state": task.state, "error": task.error, "snapshot": task.snapshot,
                "result": task.result, "created_at": task.created_at, "finished_at": task.finished_at,
                "wall_seconds": (task.finished_at - task.created_at).total_seconds() if task.finished_at else None,
                "calls": list(task.model_calls.values("id", "metadata", "request_hash", "result", "state"))}
            path = settings.BASE_DIR / "var" / f"batch2-live-{task.id}.json"
            path.write_text(json.dumps(report, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(json.dumps({"task": str(task.id), "state": task.state, "error": task.error, "result": task.result, "report": str(path)}))
            return
        snapshot = build_context(course)
        if not options["submit"]:
            scope = inspect_scope(snapshot)
            path = settings.BASE_DIR / "var/batch2-proposed-scope.json"
            path.write_text(json.dumps(scope, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(json.dumps(scope, ensure_ascii=True))
            return
        if not options["key"] or not options["context_hash"] or not options["allow_course_data_upload"]:
            raise CommandError("Submission requires an inspected context hash, idempotency key and explicit upload authorisation.")
        task = submit_analysis(course, options["context_hash"], options["key"], authorize=True,
            grant_source="User authorised this 36-page text scope in the development chat on 2026-10-23")
        self.stdout.write(json.dumps({"task_id": str(task.id), "state": task.state, "url": f"http://127.0.0.1:5173/tasks/{task.id}"}))
