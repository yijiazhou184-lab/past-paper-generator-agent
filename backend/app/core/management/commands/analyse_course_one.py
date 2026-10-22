from django.core.management.base import BaseCommand
from app.core.types import ExecutionToken
from app.core.tasks import fail_task
from app.core.errors import DomainError
from app.courses.analysis import run_analysis


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("task_id")
        parser.add_argument("epoch", type=int)

    def handle(self, task_id, epoch, **options):
        token = ExecutionToken(task_id, epoch)
        try:
            run_analysis(token)
        except DomainError as exc:
            fail_task(token, exc.payload["code"], exc.payload["message"], exc.payload["retryable"])
        except Exception:
            fail_task(token, "COURSE_ANALYSIS_INTERNAL_ERROR", "Course analysis stopped unexpectedly. No incomplete draft was published.")
