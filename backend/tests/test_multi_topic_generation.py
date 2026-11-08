import copy
from unittest.mock import patch

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from app.core.errors import DomainError
from app.core.models import ModelInvocation
from app.core.tasks import claim_task, submit_task
from app.courses.analysis import publish_analysis
from app.courses.confirmation import confirm_topics
from app.courses.context import ensure_statements, statement_list
from app.courses.topics import create_topic
from app.generation.content_fixtures import fixture_pair
from app.generation.execution_context import prepare_generation, submit_generation
from app.generation.generator import run_generation
from app.generation.planning import build_context, run_planning, submit_plan
from app.generation.snapshots import confirm_structure, draft_view, edit_blueprint, save_config
from app.papers.export import run_export
from app.papers.models import Paper
from app.papers.publication import submit_export
from app.papers.reader import pdf_state
from app.papers.storage import artifact_path
from test_course_analysis import analysis_context, course_payload
from test_topic_analysis import scoped_payload


@pytest.fixture
def mixed_version(course, course_payload, analysis_context):
    ensure_statements(course)
    topics = []
    for name in ("Alpha", "Beta", "Excluded"):
        key = name.lower()
        topic = create_topic(course.owner, course.id, {"name": name}, "create-" + key)
        topics.append(topic)
        payload, context = scoped_payload(course_payload, analysis_context, topic, "objective-" + key)
        sources = {e["id"]: e["id"] + "-" + key for e in context["evidence"]}
        for e in context["evidence"]:
            e["id"] = sources[e["id"]]
        payload["knowledge_nodes"][0]["evidence_ids"] = [sources[e] for e in payload["knowledge_nodes"][0]["evidence_ids"]]
        context["statements"] = statement_list(course)
        payload["scope_claims"][0]["statement_ids"] = [context["statements"][0]["id"]]
        draft = publish_analysis(claim_task(submit_task(course,"analysis",{},"analyse-"+key).id),payload,context,"fixture")
    version = confirm_topics(course.owner,course.id,draft.revision,None,[str(t.id) for t in topics],"confirm-topics")
    return version, topics


def test_mixed_practice_delivers_a_single_paper_with_two_topic_summaries(course, mixed_version, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    version, topics = mixed_version
    selected = [str(t.id) for t in topics[:2]]
    config = {"schema_version":"practice-config-v2","course_version_id":str(version.id),"mode":"mixed_topic_practice",
              "selected_topic_ids":selected,"knowledge_ids":["objective-alpha","objective-beta"],
              "difficulty":"exam_standard","main_question_count":2,"question_types":["calculation"]}
    single = {**config, "mode":"chapter_practice", "selected_topic_ids":selected[:1],
              "knowledge_ids":["objective-alpha"]}
    draft, _ = save_config(course.owner,course.id,0,single,"save-single")
    planning = build_context(draft)
    task = submit_plan(course.owner,course.id,draft.revision,planning["context_hash"],"plan-single")
    run_planning(claim_task(task.id))
    draft.refresh_from_db()
    draft = confirm_structure(course.owner,course.id,draft.blueprint_id,draft.revision,draft.blueprint.revision,draft.config_hash,"confirm-single")
    args = (course.owner,course.id,draft.confirmation_id,draft.revision,draft.config_hash)
    context = prepare_generation(*args,"prepare-single")
    original_task = submit_generation(*args,context["context_hash"],"generate-single")
    run_generation(claim_task(original_task.id))
    original = Paper.objects.get(generation_task=original_task)
    original_hash = original.content.payload_hash

    draft, _ = save_config(course.owner,course.id,draft.revision,config,"save-mixed")
    assert draft.confirmation_id is None
    planning = build_context(draft)
    assert {t["topic_id"] for t in planning["input"]["selected_topics"]} == set(selected)
    assert {n["id"] for n in planning["input"]["course"]["knowledge_nodes"]} == set(config["knowledge_ids"])
    assert {e["id"] for e in planning["input"]["evidence"]} == {f"e{i}-{topic}" for i in (1,2,3) for topic in ("alpha","beta")}
    task = submit_plan(course.owner,course.id,draft.revision,planning["context_hash"],"plan-mixed")
    run_planning(claim_task(task.id))
    draft.refresh_from_db()
    report = draft_view(draft)["blueprint"]["topic_coverage"]
    assert {t["topic_id"] for t in report["topics"]} == set(selected)
    invalid = copy.deepcopy(draft.blueprint.payload)
    invalid["questions"][0]["evidence_ids"].append("e1-excluded")
    with pytest.raises(DomainError,match="EVIDENCE_REFERENCE_INVALID"):
        edit_blueprint(course.owner,course.id,draft.blueprint_id,draft.revision,draft.blueprint.revision,invalid,"invalid-mixed-edit")
    draft = confirm_structure(course.owner,course.id,draft.blueprint_id,draft.revision,draft.blueprint.revision,draft.config_hash,"confirm-mixed")
    args = (course.owner,course.id,draft.confirmation_id,draft.revision,draft.config_hash)
    context = prepare_generation(*args,"prepare-mixed")
    assert {e["id"] for e in context["input"]["sources"]} == {f"e{i}-{topic}" for i in (1,2,3) for topic in ("alpha","beta")}
    generation = submit_generation(*args,context["context_hash"],"generate-mixed")

    def mixed_pair(question):
        result = fixture_pair(question)
        result["pair"]["stem"][0]["text"] = "Synthetic cross-topic practice uses a separate test stimulus."
        return result

    with patch("app.generation.generator.fixture_pair", side_effect=mixed_pair):
        run_generation(claim_task(generation.id))
    generation.refresh_from_db()
    assert generation.state == "succeeded", (generation.error, generation.result)
    paper = Paper.objects.get(generation_task=generation)
    assert paper.content.payload["metadata"]["topic_coverage"] == report
    client = APIClient()
    client.force_authenticate(course.owner)
    url = f"/api/v1/courses/{course.id}/papers"
    assert [item["id"] for item in client.get(url).json()["papers"]] == [str(paper.id),str(original.id)]
    assert [item["id"] for item in client.get(url,{"topic":selected[0]}).json()["papers"]] == [str(paper.id),str(original.id)]
    assert [item["id"] for item in client.get(url,{"topic":selected[1]}).json()["papers"]] == [str(paper.id)]
    original.refresh_from_db()
    assert original.content.payload_hash == original_hash
    assert client.get(url,{"topic":str(topics[2].id)}).json()["papers"] == []
    _, export = submit_export(course.owner,paper.id,"export-mixed")
    run_export(claim_task(export.id))
    paper.refresh_from_db()
    assert pdf_state(paper)["status"] == "ready"
    assert set(paper.content.pdfs.values_list("kind",flat=True)) == {"questions","answers"}
    for artifact in paper.content.pdfs.all():
        text = " ".join(p.extract_text() for p in PdfReader(artifact_path(artifact)).pages)
        assert "Alpha" in text and "Beta" in text and "Excluded" not in text
        assert ("Worked solution" in text) == (artifact.kind=="answers")
    assert not ModelInvocation.objects.exists()
