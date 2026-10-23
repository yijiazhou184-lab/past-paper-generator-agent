from django.core.management.base import BaseCommand
from app.core.types import ExecutionToken
from app.core.models import Task
from app.core.tasks import fail_task
from app.core.errors import DomainError
from app.materials.parser import parse_material
from uuid import UUID
import sys


def schedule_after_parse(task):
    """Queue page transcription for the parsed version; a scheduling problem never fails the parse."""
    from app.materials.models import MaterialVersion
    from app.materials.transcription import schedule
    try:
        version = MaterialVersion.objects.select_related("blob", "material__course").get(pk=task.snapshot["material_version_id"])
        schedule(task.course, "parse_complete", versions=[version])
    except Exception as exc:
        sys.stderr.write(f"Transcription scheduling skipped: {type(exc).__name__}\n")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("task_id")
        parser.add_argument("epoch", type=int)

    def handle(self, *args, **options):
        token = ExecutionToken(UUID(options["task_id"]), options["epoch"])
        task = Task.objects.get(pk=token.task_id)
        try:
            parse_material(token, task.snapshot["material_version_id"])
            schedule_after_parse(task)
        except DomainError as exc:
            fail_task(token, exc.payload["code"], exc.payload["message"], exc.payload["retryable"])
        except Exception as exc:
            # Keep exception type for diagnosis; do not log document text or credentials.
            fail_task(token, "PDF_PARSE_FAILED",
                      f"Local parsing failed ({type(exc).__name__}). Check parser setup or retry.")
            self.stderr.write(f"Parser failure type: {type(exc).__name__}")
