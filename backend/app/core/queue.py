import os
import subprocess
import sys
import time
from pathlib import Path
from django.conf import settings
from procrastinate.contrib.django import app
from .tasks import claim_task, heartbeat, fail_task
from .errors import DomainError
from .models import Task, ModelInvocation
from django.utils import timezone


@app.task(name="run_business_task")
def run_business_task(task_id):
    token = claim_task(task_id)
    if not token:
        return
    task = Task.objects.get(pk=task_id)
    command = {"parse": "parse_one", "ai_validation": "validate_ai_one", "analysis": "analyse_course_one"}.get(task.kind)
    if command is None:
        fail_task(token, "NOT_IMPLEMENTED", "This stage is not available in batch 1.", False)
        return
    log_dir = settings.BASE_DIR / "var/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{task.kind}-{task.id}.log").open("ab") as output:
        process = subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / "backend/manage.py"), command, str(task.id), str(token.epoch)],
            cwd=settings.BASE_DIR / "backend", stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            while process.poll() is None:
                heartbeat(token)
                pending = ModelInvocation.objects.filter(task=task, state="started").first() if task.kind in ("ai_validation", "analysis") else None
                if pending and (timezone.now() - pending.created_at).total_seconds() > pending.metadata["timeout_seconds"]:
                    raise DomainError("PROVIDER_TIMEOUT")
                time.sleep(2)
        except DomainError as exc:
            process.terminate()
            process.wait(timeout=20)
            if exc.payload["code"] == "RUN_LIMIT_EXCEEDED":
                fail_task(token, "RUN_LIMIT_EXCEEDED", "The task reached its maximum running time.")
            elif exc.payload["code"] == "PROVIDER_TIMEOUT":
                fail_task(token, "PROVIDER_TIMEOUT", "The model call reached its deadline. Its remote outcome may be unknown.", False)
            return
    task.refresh_from_db()
    if task.state == "processing":
        fail_task(token, "WORKER_PROCESS_FAILED", "The worker process stopped. Inspect the diagnostic record.")
