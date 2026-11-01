from uuid import UUID
from django.core.management.base import BaseCommand
from app.core.types import ExecutionToken
from app.papers.export import run_export


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("task_id", type=UUID)
        parser.add_argument("epoch", type=int)

    def handle(self, task_id, epoch, **options):
        run_export(ExecutionToken(task_id, epoch))
