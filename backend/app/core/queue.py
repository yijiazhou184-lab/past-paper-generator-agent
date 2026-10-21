import os
import subprocess
import sys
import time
from pathlib import Path
from django.conf import settings
from procrastinate.contrib.django import app
from .tasks import claim_task, heartbeat, fail_task
from .errors import DomainError
from .models import Task


@app.task(name="run_business_task")
def run_business_task(task_id):
    token = claim_task(task_id)
    if not token:
        return
    task = Task.objects.get(pk=task_id)
    if task.kind != "parse":
        fail_task(token, "NOT_IMPLEMENTED", "This stage is not available in batch 1.", False)
        return
    log_dir = settings.BASE_DIR / "var/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"parser-{task.id}.log").open("ab") as output:
        process = subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / "backend/manage.py"), "parse_one", str(task.id), str(token.epoch)],
            cwd=settings.BASE_DIR / "backend", stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            while process.poll() is None:
                heartbeat(token)
                time.sleep(2)
        except DomainError as exc:
            process.terminate()
            process.wait(timeout=20)
            if exc.payload["code"] == "RUN_LIMIT_EXCEEDED":
                fail_task(token, "RUN_LIMIT_EXCEEDED", "Parsing reached the 15-minute limit. You can retry.")
            return
    task.refresh_from_db()
    if task.state == "processing":
        fail_task(token, "PARSER_PROCESS_FAILED", "The local PDF parser stopped. Retry or inspect the diagnostic record.")
