from django.core.management.base import BaseCommand
from app.core.types import ExecutionToken
from app.core.models import Task
from app.core.tasks import fail_task
from app.core.errors import DomainError
from app.materials.transcription import run_transcription, schedule


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("task_id")
        parser.add_argument("epoch", type=int)

    def handle(self, task_id, epoch, **options):
        token = ExecutionToken(task_id, epoch)
        try:
            run_transcription(token)
        except DomainError as exc:
            fail_task(token, exc.payload["code"], exc.payload["message"], exc.payload["retryable"])
        except Exception as exc:
            fail_task(token, "VISUAL_TRANSCRIPTION_INTERNAL_ERROR", "Page transcription stopped unexpectedly. Completed pages are kept.")
            self.stderr.write(f"Transcription failure type: {type(exc).__name__}")
        task = Task.objects.select_related("course").get(pk=token.task_id)
        if task.state == "succeeded":
            # Pages beyond one task's bound, or granted meanwhile, continue in a new task.
            schedule(task.course, "continuation")
