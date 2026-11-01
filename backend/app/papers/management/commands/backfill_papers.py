from django.core.management.base import BaseCommand
from django.db import transaction
from app.core.models import Task
from app.generation.models import CandidateVersion, CheckReport
from app.papers.publication import freeze_content


class Command(BaseCommand):
    help = "Save existing successful checked candidates as papers; no model calls or exports."

    def handle(self, *args, **options):
        count = 0
        for task_id in Task.objects.filter(kind="generation", state="succeeded", paper__isnull=True).values_list("id", flat=True):
            with transaction.atomic():
                task = Task.objects.select_for_update().get(pk=task_id)
                if not task.result.get("allowed") or not task.result.get("candidate_id"):
                    continue
                candidate = CandidateVersion.objects.get(pk=task.result["candidate_id"], task=task)
                report = CheckReport.objects.get(candidate=candidate)
                freeze_content(task, candidate, report)
                count += 1
        self.stdout.write(f"Saved {count} existing successful papers. No model calls.")
