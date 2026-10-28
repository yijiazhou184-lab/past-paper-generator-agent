"""Read-only replay of saved pair outputs under the current reference policy. No provider calls."""
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from app.core.models import Task
from app.core.idempotency import digest
from app.generation.models import GenerationSnapshot
from app.generation.execution_context import build_generation_context
from app.generation.content_validation import validate_group
from app.generation.checks import program_checks
from app.generation.source_policy import source_diagnostics


def fingerprint(task):
    task.refresh_from_db()
    return digest(json.loads(json.dumps({"state": task.state, "snapshot": task.snapshot, "result": task.result, "error": task.error,
                   "calls": list(task.model_calls.order_by("id").values()),
                   "artifacts": list(task.generation_artifacts.order_by("id").values()),
                   "candidates": list(task.candidates.order_by("id").values())}, default=str)))


def audit(task_id):
    task = Task.objects.get(id=task_id, kind="generation")
    if task.state not in ("failed", "cancelled", "succeeded", "needs_info"):
        raise ValueError("Only terminal tasks can be audited.")
    before = fingerprint(task)
    snapshot = GenerationSnapshot.objects.get(id=task.snapshot["input"]["snapshot_id"])
    context = build_generation_context(snapshot)
    groups, failures = [], []
    for question in context["input"]["questions"]:
        q = question["blueprint"]
        artifact = task.generation_artifacts.filter(key="r0:pair:" + q["id"]).first()
        if artifact is None:
            failures.append({"question_id": q["id"], "error": "No saved complete pair response."})
            continue
        try:
            groups.append(validate_group(q, copy.deepcopy(artifact.payload), context))
        except Exception as exc:
            failures.append({"question_id": q["id"], "error": type(exc).__name__ + ": " + str(exc)})
    payload = {"pairs": [g["pair"] for g in groups], "assets": [a for g in groups for a in g["assets"]]}
    report = {"task_id": str(task.id), "historical_state": task.state, "historical_error": task.error,
              "mode": "local_replay_only", "new_model_calls": 0,
              "current_context_hash": context["context_hash"], "source_policy": context["source_policy"],
              "validated_groups": len(groups), "structural_failures": failures,
              "source_diagnostics": [source_diagnostics(context, p) for p in payload["pairs"]],
              "program_checks": program_checks(context, payload) if not failures else [],
              "unexecuted": ["mathematical_checks", "blind_solving", "semantic_review", "repair", "publication"],
              "history_unchanged": before == fingerprint(task)}
    assert report["history_unchanged"]
    destination = ROOT / "var" / ("source-policy-audit-" + str(task.id) + ".json")
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("source_policy", "program_checks", "historical_error")},
                     ensure_ascii=True))
    print("Report: " + str(destination))


if __name__ == "__main__":
    audit(sys.argv[1])
