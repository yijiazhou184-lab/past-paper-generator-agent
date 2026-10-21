"""Read the approved sample without modifying any source file."""
import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from app.courses.models import Course
from app.materials.ingest import ingest_pdf


class Command(BaseCommand):
    help = "Import the 11 approved QM PDFs and all their identical path aliases locally."

    def handle(self, **options):
        root = settings.BASE_DIR / "Quantitaive methods"
        manifest = json.loads((settings.BASE_DIR / "backend/tests/fixtures/qm_manifest.json").read_text())
        course = Course.objects.get(owner__username="local", code="MSIN0180")
        paths_by_hash = {}
        for path in sorted(root.rglob("*.pdf")):
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            paths_by_hash.setdefault(sha, []).append(path)
        for item in manifest:
            source = root / item["path"]
            if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
                raise CommandError(f"Source changed: {item['id']}. Review the manifest first.")
            for path in paths_by_hash[item["sha256"]]:
                alias = path.relative_to(root).as_posix()
                result = ingest_pdf(course, path.read_bytes(), path.name,
                    "sample-path:" + hashlib.sha256(alias.encode()).hexdigest(), alias=alias)
            self.stdout.write(f"{item['id']}: version={result['version_id']} task={result['task_id']}")
