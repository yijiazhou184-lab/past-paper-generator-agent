"""Separate synthetic course for page-transcription display checks. No real course edits or API calls.

Page 1 carries an empty formula region (visual route) and a fixture transcription; page 2 is prose
(text route); page 3 has an empty formula region and no transcription (awaiting consent).
"""
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from app.core.models import Task
from app.courses.models import Course
from app.materials.models import MaterialBlob, Material, MaterialVersion, ParseVersion, Evidence, VisualTranscription
from app.materials.storage import write_bytes, path_for
from app.materials import transcription

PROSE = "Synthetic prose page. The derivative measures the instantaneous rate of change of a function."
FORMULA = [{"kind": "text", "text": "Definition (synthetic fixture)", "bbox": {"l": 50, "t": 760, "r": 400, "b": 740}},
           {"kind": "formula", "text": "", "bbox": {"l": 50, "t": 700, "r": 400, "b": 640}}]


@transaction.atomic
def prepare():
    owner = get_user_model().objects.get(username="local")
    course = Course.objects.create(owner=owner, title="Page transcription — development fixture", code="B4-VISUAL-FIXTURE")
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    for page in range(1, 4):
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(55, 760, f"Synthetic fixture page {page}. Not a teacher document.")
        pdf.setFont("Helvetica", 22)
        if page != 2:
            pdf.drawString(55, 670, "f'(x) = lim (f(x+h) - f(x)) / h as h -> 0")
        pdf.showPage()
    pdf.save()
    data = output.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    blob = MaterialBlob.objects.create(owner=owner, sha256=sha, bytes=len(data), pages=3, storage_key=f"blobs/{sha}.pdf")
    write_bytes(blob.storage_key, data)
    version = MaterialVersion.objects.create(material=Material.objects.create(course=course), blob=blob,
        original_filename="visual-fixture.pdf", path_aliases=["visual-fixture.pdf"], roles=["lecture"],
        classification_basis="user_corrected")
    # A finished parse task so the list shows the parsed state; the parse itself is synthetic.
    version.task = Task.objects.create(course=course, kind="parse", state="succeeded", stage="Complete (fixture)",
        snapshot={"material_version_id": str(version.id), "blob_sha256": sha, "fixture": True},
        started_at=timezone.now(), finished_at=timezone.now())
    version.save(update_fields=["task"])
    parse = ParseVersion.objects.create(blob=blob, parser_name="fixture", parser_version="fixture", config_hash="b4-visual",
                                        state="ready", document_key=f"parses/b4-visual-{sha}.json",
                                        issues=[{"code": "FIXTURE", "message": "Synthetic parse; not Docling output."}])
    write_bytes(parse.document_key, json.dumps({"fixture": True}).encode())
    parse.content_hash = hashlib.sha256(path_for(parse.document_key).read_bytes()).hexdigest()
    parse.save()
    pages = {}
    for number in (1, 2, 3):
        pages[number] = Evidence.objects.create(material_version=version, parse_version=parse, physical_page=number,
            text=PROSE if number == 2 else "Definition (synthetic fixture)", blocks=FORMULA if number != 2 else
            [{"kind": "text", "text": PROSE, "bbox": None}])
    evidence = Evidence.objects.select_related("material_version__blob", "material_version__material__course",
                                               "parse_version").get(pk=pages[1].pk)
    decision = transcription.decide(evidence)
    entry = transcription.page_entry(evidence, decision)
    empty = {k: None for k in ("columns", "rows", "units", "axes", "series", "labelled_values", "elements", "relations", "text")}
    payload = {"source": transcription.source_of(entry), "status": "transcribed", "page_title": "Synthetic fixture page 1",
               "faithful_transcription": "Synthetic fixture page 1. Not a teacher document.\n$f'(x) = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h}$",
               "items": [{"kind": "formula", "location": "upper middle", "legibility": "readable", "value_origin": "not_applicable",
                          **empty, "latex_as_printed": "f'(x) = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h}"}],
               "findings": [{"kind": "parser_loss", "observation": "The extracted text omits the formula.",
                             "evidence_on_page": "upper middle", "suggested_interpretation": None}],
               "teaching_use": "Fixture only", "unresolved": []}
    VisualTranscription.objects.create(evidence=evidence, **{k: entry[k] for k in transcription.KEY_FIELDS if k != "evidence_id"},
                                       route=decision, status="transcribed", payload=payload, origin="fixture")
    return {"course_id": str(course.id), "material_version_id": str(version.id),
            "evidence": {str(n): str(e.id) for n, e in pages.items()}}


if __name__ == "__main__":
    result = prepare()
    (ROOT / "var/batch4-visual-fixture.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
