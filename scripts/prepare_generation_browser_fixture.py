"""Separate synthetic course and PDF for batch-3 interaction checks. No real course edits or API calls."""
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
from app.core.idempotency import digest
from app.core.tasks import submit_task, claim_task
from app.courses.models import Course, UserStatement
from app.courses.analysis import publish_analysis
from app.courses.confirmation import confirm_course
from app.materials.models import MaterialBlob, Material, MaterialVersion, ParseVersion, Evidence
from app.materials.storage import write_bytes
from app.generation.snapshots import save_config


@transaction.atomic
def prepare():
    owner = get_user_model().objects.get(username="local")
    course = Course.objects.create(owner=owner, title="Topic 2 practice — development fixture", code="B3-FIXTURE")
    text = "Synthetic teaching fixture: derivatives, stationary points and optimisation. Not real QM evidence."
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(55, 760, "Topic 2 - Synthetic development fixture")
    pdf.setFont("Helvetica", 11)
    for y, line in zip([720, 690, 660, 630], ["Not a teacher document. Not a model result.", "Derivative rules and interpretation.",
                     "Stationary points and classification.", "Optimisation problems using single-variable calculus."]):
        pdf.drawString(55, y, line)
    pdf.save()
    raw = output.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    storage_key = f"fixtures/{course.id}/teaching.pdf"
    write_bytes(storage_key, raw)
    blob = MaterialBlob.objects.create(owner=owner, sha256=sha, bytes=len(raw), pages=1, storage_key=storage_key)
    material = Material.objects.create(course=course)
    mv = MaterialVersion.objects.create(material=material, blob=blob, original_filename="Topic 2 - SYNTHETIC teaching fixture.pdf",
        path_aliases=["Synthetic local test document"], roles=["lecture"], classification_basis="user_confirmed")
    parse = ParseVersion.objects.create(blob=blob, parser_name="fixture", parser_version="1", config_hash=digest("fixture"), state="ready")
    evidence = Evidence.objects.create(material_version=mv, parse_version=parse, physical_page=1, text=text, fidelity_status="fixture")
    statement = UserStatement.objects.create(course=course, text="All synthetic lecture targets are selected for this test.",
        kind="exam_scope", source="Synthetic test declaration", submitted_by=owner)
    nodes = [{"id": f"K{i}", "title": title, "parent_id": None, "depth": 2, "prerequisite_ids": [], "method_ids": [],
        "evidence_ids": [str(evidence.id)], "readiness": "supported", "requirements": "Synthetic requirement for local workflow testing."}
        for i, title in enumerate(["Derivative rules and interpretation", "Stationary points and classification", "Applied optimisation"], 1)]
    payload = {"title": course.title, "target_exam": {"label": "Synthetic practice test", "academic_year": None}, "knowledge_nodes": nodes,
        "scope_claims": [{"id": "fixture-scope", "text": statement.text, "subject_ids": [n["id"] for n in nodes],
            "applicability": "current_exam", "provenance": "user_statement", "authority_status": "unverified",
            "evidence_ids": [], "statement_ids": [str(statement.id)], "status": "declared", "disposition": "include"}],
        "method_rules": [], "historical_style": [], "issues": [], "clarifications": [], "template_suggestion": None}
    context = {"target_ids": [n["id"] for n in nodes],
        "materials": [{"material_version_id": str(mv.id), "classification_revision": 1, "answer_links": []}],
        "evidence": [{"id": str(evidence.id), "roles": ["lecture"], "material_code": "FX01", "material_version_id": str(mv.id),
            "physical_page": 1, "parse_version_id": str(parse.id), "fidelity_status": "fixture", "text": text}],
        "statements": [{"id": str(statement.id), "kind": "exam_scope", "text": statement.text, "source": statement.source}]}
    task = submit_task(course, "analysis", {"mode": "fixture"}, "create-fixture")
    draft = publish_analysis(claim_task(task.id), payload, context, "fixture")
    version = confirm_course(owner, course.id, draft.id, draft.revision, "fixture-confirm")
    config = {"course_version_id": str(version.id), "mode": "chapter_practice", "difficulty": "exam_standard", "main_question_count": 3,
        "topic_ids": [n["id"] for n in nodes], "question_types": ["calculation", "explanation_proof", "applied_optimisation"]}
    save_config(owner, course.id, 0, config, "fixture-initial-config")
    return {"course_id": str(course.id), "course_version_id": str(version.id), "source_id": str(evidence.id), "mode": "fixture",
            "url": f"http://127.0.0.1:5173/courses/{course.id}/generate"}


if __name__ == "__main__":
    result = prepare()
    (ROOT / "var/batch3-browser-fixture.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
