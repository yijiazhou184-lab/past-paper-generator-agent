import time
from django.core.management.base import BaseCommand
from django.db import transaction, close_old_connections, DatabaseError
from django.utils import timezone
from app.core.models import Outbox
from app.core.tasks import recover_stale_tasks
from app.core.queue import run_business_task


def dispatch_once():
    # Queue insertion and marking the outbox share the Django connection/transaction.
    with transaction.atomic():
        for entry in Outbox.objects.select_for_update(skip_locked=True).filter(sent_at=None).order_by("created_at")[:20]:
            if entry.task.state == "queued":
                run_business_task.defer(task_id=str(entry.task_id))
            entry.sent_at = timezone.now()
            entry.save(update_fields=["sent_at"])


class Command(BaseCommand):
    help = "Dispatch durable business tasks and recover expired worker leases."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            try:
                close_old_connections()
                recover_stale_tasks()
                dispatch_once()
            except DatabaseError:
                # Transient outages must not permanently strand committed outbox entries.
                self.stderr.write("DISPATCH_DATABASE_UNAVAILABLE: retrying after reconnect.")
                close_old_connections()
                if options["once"]:
                    raise
            if options["once"]:
                break
            time.sleep(2)
