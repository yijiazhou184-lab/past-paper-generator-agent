import hashlib
import json
from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from app.materials.models import MaterialVersion
from app.materials.evidence import render_page


class Command(BaseCommand):
    help = "Check unchanged source hashes and report actual local parse outcomes."

    def handle(self, **options):
        root = settings.BASE_DIR
        inventory = json.loads((root / "backend/tests/fixtures/qm_inventory.json").read_text())
        mismatches = [i["path"] for i in inventory if hashlib.sha256(
            (root / "Quantitaive methods" / i["path"]).read_bytes()).hexdigest() != i["sha256"]]
        selected = json.loads((root / "backend/tests/fixtures/qm_manifest.json").read_text())
        report = {"time_utc": datetime.now(timezone.utc).isoformat(), "mode": "real_local_docling_no_api",
                  "source_paths_checked": len(inventory), "source_hash_mismatches": mismatches, "materials": [], "risk_pages": []}
        risk = {"M34": [14, 41], "M14": [5], "M33": [22], "M48": [20]}
        for item in selected:
            v = MaterialVersion.objects.select_related("task", "material__course__owner").get(
                blob__sha256=item["sha256"], material__course__owner__username="local", number=1)
            t = v.task
            report["materials"].append({"id": item["id"], "filename": v.original_filename,
                "material_version_id": str(v.id), "task_id": str(t.id), "aliases": v.path_aliases,
                "expected_pages": item["pages"], "evidence_pages": v.evidence.count(),
                "state": t.state, "error": t.error, "roles": v.roles,
                "processing_seconds": round((t.finished_at - t.started_at).total_seconds(), 2) if t.finished_at and t.started_at else None})
            for page in risk.get(item["id"], []):
                e = v.evidence.filter(physical_page=page).first()
                report["risk_pages"].append({"id": item["id"], "physical_page": page,
                    "image_path": str(render_page(v.material.course.owner, v.id, page)),
                    "extracted_text": e.text if e else None, "fidelity_status": e.fidelity_status if e else "not_parsed"})
        output = root / "var/batch1-audit.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(json.dumps({"report": str(output), "source_paths_checked": len(inventory),
            "hash_mismatches": len(mismatches), "states": [m["state"] for m in report["materials"]]}))
