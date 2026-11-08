import copy

import pytest
from rest_framework.test import APIClient

from app.core.errors import DomainError
from app.core.tasks import claim_task, submit_task
from app.courses.analysis import publish_analysis
from app.courses.confirmation import confirm_topics
from app.courses.context import ensure_statements, statement_list
from app.courses.drafts import save_draft
from app.courses.models import Course
from app.courses.topics import create_topic
from app.generation.planning import build_context, run_planning, submit_plan
from app.generation.snapshots import draft_view, save_config, validate_draft_blueprint
from test_course_analysis import analysis_context, course_payload
from test_exam_template import template
from test_topic_analysis import scoped_payload


def reviewed_exam(course, course_payload, analysis_context, structure, count=1):
    ensure_statements(course)
    topics = []
    for i in range(count):
        key = f"topic-{i}"
        topic = create_topic(course.owner, course.id, {"name": f"Topic {i+1}"}, key)
        topics.append(topic)
        payload, context = scoped_payload(course_payload, analysis_context, topic, f"objective-{i}")
        mapping = {e["id"]: e["id"] + "-" + key for e in context["evidence"]}
        for e in context["evidence"]:
            e["id"] = mapping[e["id"]]
        for row in [*payload["knowledge_nodes"], *payload["scope_claims"]]:
            row["evidence_ids"] = [mapping[eid] for eid in row["evidence_ids"]]
        context["statements"] = statement_list(course)
        payload["scope_claims"][0]["statement_ids"] = [context["statements"][0]["id"]]
        draft = publish_analysis(claim_task(submit_task(course, "analysis", {}, "analyse-"+key).id),
                                 payload, context, "fixture")
    draft, _ = save_draft(course.owner, course.id, draft.revision,
                          [{"path": ["exam_template"], "value": structure}], "save-template")
    version = confirm_topics(course.owner, course.id, draft.revision, None,
                             [str(t.id) for t in topics], "confirm-course", include_exam_template=True)
    return version, topics


def plan_exam(course, version, topics):
    source = version.frozen_payload["exam_template"]
    config = {"schema_version": "practice-config-v2", "course_version_id": str(version.id), "mode": "mock_exam",
              "selected_topic_ids": [str(t.id) for t in topics],
              "knowledge_ids": [node for t in version.frozen_payload["topic_manifest"] for node in t["knowledge_ids"]],
              "difficulty": "exam_standard",
              "main_question_count": sum(len(s["question_marks"]) for s in source["sections"]),
              "question_types": source["question_types"]}
    draft, _ = save_config(course.owner, course.id, 0, config, "mock-config")
    ctx = build_context(draft)
    task = submit_plan(course.owner, course.id, draft.revision, ctx["context_hash"], "mock-plan")
    run_planning(claim_task(task.id))
    draft.refresh_from_db()
    return draft


def alternate_template():
    return {**template(), "duration_minutes": 90, "question_types": ["explanation_proof"],
            "sections": [
                {"id": "methods", "title": "Methods", "question_marks": [15, 25],
                 "selection": {"mode": "all", "choose_count": 2}},
                {"id": "analysis", "title": "Analysis", "question_marks": [12, 18],
                 "selection": {"mode": "all", "choose_count": 2}},
            ]}


@pytest.mark.django_db
def test_mock_inherits_two_different_course_templates(course, course_payload, analysis_context):
    other = Course.objects.create(owner=course.owner, title="Independent course")
    client = APIClient()
    client.force_authenticate(course.owner)
    for obj, structure, count, totals in [
        (course, template(), 1, (40, 30)),
        (other, alternate_template(), 2, (70, 70)),
    ]:
        version, topics = reviewed_exam(obj, course_payload, analysis_context, structure, count)
        workspace = client.get(f"/api/v1/courses/{obj.id}/generation-workspace").json()
        assert workspace["capabilities"]["mock_exam"] and workspace["versions"][0]["mock_exam_blocker"] == ""
        draft = plan_exam(obj, version, topics)
        blueprint = draft.blueprint.payload
        assert (blueprint["printed_marks"], blueprint["attempt_marks"]) == totals
        assert blueprint["suggested_minutes"] == structure["duration_minutes"]
        assert [s["title"] for s in blueprint["sections"]] == [s["title"] for s in structure["sections"]]
        assert {p["response_type"] for q in blueprint["questions"] for p in q["parts"]} == set(structure["question_types"])
        assert draft_view(draft)["blueprint"]["topic_coverage"]["knowledge_coverage"]["uncovered"] == []


@pytest.mark.django_db
def test_mock_rejects_unequal_choice_marks_and_keeps_optional_coverage(course, course_payload, analysis_context):
    version, topics = reviewed_exam(course, course_payload, analysis_context, template(), 2)
    draft = plan_exam(course, version, topics)
    blueprint = copy.deepcopy(draft.blueprint.payload)
    for q in blueprint["questions"]:
        q["parts"][0]["knowledge_ids"] = ["objective-0"]
    validated = validate_draft_blueprint(draft, blueprint, recalculate=True)
    from app.generation.topic_coverage import validate_topic_coverage
    result = validate_topic_coverage(draft.config, validated, version.frozen_payload)
    assert result["knowledge_coverage"] == {"guaranteed": ["objective-0"], "optional": [], "uncovered": ["objective-1"]}
    blueprint["questions"][1]["parts"][0]["marks"] += 1
    with pytest.raises(DomainError, match="UNEQUAL_CHOICE_MARKS"):
        validate_draft_blueprint(draft, blueprint, recalculate=True)
