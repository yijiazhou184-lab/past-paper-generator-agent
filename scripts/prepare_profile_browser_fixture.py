"""Create a separate, explicitly labelled browser-test course. Never calls a model."""
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from app.courses.models import Course, UserStatement
from app.courses.analysis import publish_analysis
from app.core.tasks import submit_task, claim_task

owner = get_user_model().objects.get(username="local")
course = Course.objects.create(owner=owner, title="Batch 2 browser fixture — not a model result", code="B2-TEST")
statement = UserStatement.objects.create(course=course, text="All fixture lecture content", kind="exam_scope", source="Synthetic browser test", submitted_by=owner)
payload = {"title": course.title, "target_exam": {"label": "Fixture examination", "academic_year": None},
    "knowledge_nodes": [{"id": "K1", "title": "Fixture derivatives", "parent_id": None, "depth": 1,
        "prerequisite_ids": [], "method_ids": [], "evidence_ids": [], "readiness": "supported", "requirements": "Fixture learning requirement"}],
    "scope_claims": [{"id": "fixture-scope", "text": "All fixture lecture content", "subject_ids": ["K1"],
        "applicability": "current_exam", "provenance": "user_statement", "authority_status": "unverified",
        "evidence_ids": [], "statement_ids": [str(statement.id)], "status": "declared", "disposition": "include"}],
    "method_rules": [], "historical_style": [], "issues": [],
    "template_suggestion": {"label": "suggested", "calibration": "not_calibrated_to_current_exam", "question_types": ["calculation"],
        "sections": [{"title": "Practice", "main_questions": 2, "marks_per_question": 10, "selection": "all", "choose_count": 2}],
        "duration_minutes": 30, "total_marks": 20, "rationale": "Synthetic template for browser verification only."},
    "clarifications": [{"id": "fixture-question", "question": "Fixture optional target exam label?", "reason": "Synthetic non-blocking clarification",
        "affected_ids": ["K1"], "impact": "informational", "suggested_answers": [], "resolves_issue_ids": [], "status": "open"}]}
context = {"target_ids": ["K1"], "evidence": [], "materials": [], "statements": [{"id": str(statement.id), "text": statement.text, "kind": "exam_scope"}]}
task = submit_task(course, "analysis", {"mode": "fixture"}, "browser-fixture-" + str(uuid.uuid4()))
draft = publish_analysis(claim_task(task.id), payload, context, "fixture")
result = {"course_id": str(course.id), "draft_id": str(draft.id), "mode": "fixture"}
(ROOT / "var/batch2-browser-fixture.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
