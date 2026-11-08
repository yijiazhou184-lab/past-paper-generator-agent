import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from app.core.errors import DomainError
from app.core.models import ModelInvocation
from app.core.tasks import claim_task
from app.courses.drafts import save_draft
from app.generation.execution_context import prepare_generation, submit_generation
from app.generation.generator import run_generation
from app.generation.snapshots import confirm_structure
from app.papers.export import run_export
from app.papers.models import Paper
from app.papers.publication import submit_export
from app.papers.storage import artifact_path
from test_course_analysis import analysis_context, course_payload
from test_exam_template import template
from test_mock_exam_structure import alternate_template, plan_exam, reviewed_exam


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(("data","topic_count","text"), [
    (template(), 1, "Answer 1 of 2 questions"),
    (alternate_template(), 2, "Answer all questions"),
])
def test_mock_saves_every_printed_pair_and_exports_both_pdfs(course, course_payload, analysis_context, data, topic_count, text):
    version, topics = reviewed_exam(course, course_payload, analysis_context, data, topic_count)
    draft = plan_exam(course, version, topics)
    draft = confirm_structure(course.owner, course.id, draft.blueprint_id, draft.revision,
                              draft.blueprint.revision, draft.config_hash, "confirm-structure")
    args = (course.owner, course.id, draft.confirmation_id, draft.revision, draft.config_hash)
    context = prepare_generation(*args, "prepare")
    task = submit_generation(*args, context["context_hash"], "generate")
    run_generation(claim_task(task.id))
    task.refresh_from_db()
    assert task.state == "succeeded", (task.error, task.result)
    paper = Paper.objects.get(generation_task=task)
    content = paper.content
    assert content.payload["metadata"]["exam_template"] == version.frozen_payload["exam_template"]
    client = APIClient()
    client.force_authenticate(course.owner)
    url = f"/api/v1/papers/{paper.id}"
    assert all("answers" not in p for p in client.get(url).json()["candidate"]["pairs"])
    question_count = sum(len(s["question_marks"]) for s in data["sections"])
    assert len(client.get(url+"/answers").json()["answers"]) == question_count
    _, export = submit_export(course.owner, paper.id, "export")
    run_export(claim_task(export.id))
    export.refresh_from_db()
    assert export.state == "succeeded", export.error
    original_hashes = {}
    for artifact in content.pdfs.all():
        data_text = " ".join(p.extract_text() for p in PdfReader(artifact_path(artifact)).pages)
        assert "Mock exam" in data_text and text in data_text and str(content.id) in data_text
        assert ("Worked solution" in data_text) == (artifact.kind == "answers")
        original_hashes[artifact.kind] = artifact.sha256
    assert set(original_hashes) == {"questions", "answers"}
    course_draft = version.draft
    updated = {**data, "duration_minutes": data["duration_minutes"] + 1}
    save_draft(course.owner, course.id, course_draft.revision,
               [{"path": ["exam_template"], "value": updated}], "new-template")
    with pytest.raises(DomainError, match="EXAM_TEMPLATE_NOT_READY"):
        prepare_generation(*args, "prepare")
    assert client.get(url).json()["paper"]["content_hash"] == content.payload_hash
    assert dict(content.pdfs.values_list("kind", "sha256")) == original_hashes
    assert not ModelInvocation.objects.exists()
