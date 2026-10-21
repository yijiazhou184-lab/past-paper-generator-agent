from django.core.management.base import BaseCommand
from app.core.types import ExecutionToken
from app.core.tasks import fail_task
from app.core.errors import DomainError
from app.ai.validation import run_validation


class Command(BaseCommand):
    help = "Worker subprocess for a scoped, already-authorized live validation task."

    def add_arguments(self, parser):
        parser.add_argument("task_id")
        parser.add_argument("epoch", type=int)

    def handle(self, **options):
        token = ExecutionToken(options["task_id"], options["epoch"])
        try:
            run_validation(token)
        except DomainError as exc:
            fail_task(token, exc.payload["code"], exc.payload["message"], False)
        except Exception:
            # SDK/transport exceptions can contain input: only a safe diagnostic code reaches logs/UI.
            fail_task(token, "LIVE_VALIDATION_FAILED", "The validation process failed. Inspect the saved call records.", False)
