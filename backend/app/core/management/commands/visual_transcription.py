import json
import uuid
from collections import Counter
from django.core.management.base import BaseCommand, CommandError
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.core.models import Task
from app.courses.models import Course
from app.materials.models import MaterialVersion, TranscriptionGrant
from app.materials.transcription import (visual_candidates, page_states, schedule, page_entry, current_evidence,
                                         cached, signal_pages, decide)


def parse_selection(values):
    selection = {}
    for value in values:
        version, _, pages = value.partition(":")
        numbers = set()
        for part in pages.split(","):
            start, _, end = part.partition("-")
            numbers.update(range(int(start), int(end or start) + 1))
        selection.setdefault(version, set()).update(numbers)
    return selection


class Command(BaseCommand):
    help = ("Inspect page-transcription status, preview an exact page-image scope, and grant it only after "
            "explicit user authorisation. Granting queues the background transcription.")

    def add_arguments(self, parser):
        parser.add_argument("--course", help="Course id; defaults to the local QM course")
        parser.add_argument("--select", action="append", default=[], metavar="VERSION_ID:PAGES",
                            help="Material version and pages, e.g. 1b2c...:2-6,8")
        parser.add_argument("--manual", action="store_true", help="Also allow selected text-route pages (signal: manual)")
        parser.add_argument("--authorize", action="store_true")
        parser.add_argument("--scope-hash")
        parser.add_argument("--source", default="Explicit development consent for the listed page images")
        parser.add_argument("--retry", action="store_true", help="Queue allowed pages again with a new task key")
        parser.add_argument("--report")

    def handle(self, **options):
        course = (Course.objects.get(pk=options["course"]) if options["course"]
                  else Course.objects.get(owner__username="local", code="MSIN0180"))
        if options["report"]:
            task = Task.objects.get(pk=options["report"], course=course, kind="visual_transcription")
            self.stdout.write(json.dumps({"id": str(task.id), "state": task.state, "error": task.error,
                "result": task.result, "checkpoint": task.checkpoint, "created_at": task.created_at,
                "started_at": task.started_at, "finished_at": task.finished_at,
                "calls": list(task.model_calls.values("call_key", "state", "metadata__model", "result__status",
                                                      "result__usage", "result__elapsed_seconds", "result__error_code"))},
                default=str, indent=2))
            return
        if options["retry"]:
            task = schedule(course, "manual_retry", key="transcribe-retry:" + str(uuid.uuid4()))
            self.stdout.write(json.dumps({"task_id": str(task.id) if task else None}))
            return
        if not options["select"]:
            states = page_states(course)
            self.stdout.write(json.dumps({"summary": Counter(s["status"] for s in states),
                                          "pages": [s for s in states if s["status"] != "not_needed"]}, indent=2))
            return
        entries = self.selected_entries(course, parse_selection(options["select"]), options["manual"])
        scope_hash = digest(entries)
        if not options["authorize"]:
            self.stdout.write(json.dumps({"scope_hash": scope_hash, "page_images": len(entries),
                "pages": [{k: e[k] for k in ("filename", "physical_page", "evidence_id", "image_sha256", "model")}
                          | {"signals": e["route"]["signals"]} for e in entries]}, indent=2))
            return
        if options["scope_hash"] != scope_hash:
            raise CommandError("The selected scope differs from the inspected scope hash. Inspect it again.")
        TranscriptionGrant.objects.get_or_create(course=course, scope_hash=scope_hash,
            defaults={"granted_by": course.owner, "scope": entries, "source": options["source"]})
        task = schedule(course, "grant")
        self.stdout.write(json.dumps({"grant_scope_hash": scope_hash, "task_id": str(task.id) if task else None,
                                      "url": f"http://127.0.0.1:5173/tasks/{task.id}" if task else None}))

    def selected_entries(self, course, selection, manual):
        (requested, manual_ids), entries = signal_pages(course), []
        for version_id, numbers in sorted(selection.items()):
            version = MaterialVersion.objects.select_related("blob", "material__course").get(pk=version_id, material__course=course)
            pages = {e.physical_page: e for e in current_evidence(version)}
            for number in sorted(numbers):
                if number not in pages:
                    raise CommandError(f"{version.original_filename} has no parsed page {number}.")
                decision = decide(pages[number], requested, manual_ids)
                if decision["route"] != "visual":
                    if not manual:
                        raise CommandError(f"{version.original_filename} p{number} is a text-route page; pass --manual to include it.")
                    decision = decide(pages[number], requested, {str(pages[number].id)})
                entry = page_entry(pages[number], decision)
                if cached(entry):
                    continue
                entries.append(entry)
        if not entries:
            raise DomainError("NOTHING_TO_TRANSCRIBE", "Every selected page already has an accepted transcription.")
        return entries
