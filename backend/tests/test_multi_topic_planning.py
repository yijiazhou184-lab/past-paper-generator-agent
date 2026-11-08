import copy

import pytest

from app.core.errors import DomainError
from app.generation.fixtures import fixture_blueprint
from app.generation.schemas import validate_blueprint, validate_config
from app.generation.topic_coverage import validate_topic_coverage
from test_course_analysis import analysis_context, course_payload
from test_topic_generation_config import configuration


@pytest.fixture
def mixed_inputs(course_payload, analysis_context):
    config = configuration()
    config.update(mode="mixed_topic_practice", selected_topic_ids=["topic-a", "topic-b"], knowledge_ids=["K1", "second"])
    course = copy.deepcopy(course_payload)
    course["knowledge_nodes"].append({**course["knowledge_nodes"][0], "id": "second"})
    course["topic_manifest"] = [
        {"topic_id": "topic-a", "name": "Alpha", "knowledge_ids": ["K1"]},
        {"topic_id": "topic-b", "name": "Beta", "knowledge_ids": ["K1", "second"]},
    ]
    return config, course, analysis_context["evidence"]


def test_mixed_config_accepts_one_copy_of_a_shared_target(mixed_inputs):
    config, course, evidence = mixed_inputs
    assert validate_config(config, course, evidence)["knowledge_ids"] == ["K1", "second"]
    assert len(fixture_blueprint(config, course)["coverage"]) == 2


@pytest.mark.parametrize(("change","code"), [
    ({"selected_topic_ids":["topic-a"]}, "MIXED_TOPIC_SELECTION_REQUIRED"),
    ({"selected_topic_ids":["topic-a","other-version-topic"]}, "TOPIC_OUTSIDE_VERSION"),
    ({"knowledge_ids":["K1","unselected-target"]}, "KNOWLEDGE_OUTSIDE_TOPIC"),
    ({"knowledge_ids":["second"]}, "TOPIC_WITHOUT_KNOWLEDGE"),
    ({"knowledge_ids":["K1","K1","second"]}, "DUPLICATE_IDENTIFIER"),
])
def test_invalid_mixed_selection_is_rejected(mixed_inputs, change, code):
    config, course, evidence = mixed_inputs
    with pytest.raises(DomainError, match=code):
        validate_config({**config, **change}, course, evidence)


def test_cross_topic_marks_are_unique_and_every_choice_must_cover_targets(mixed_inputs):
    config, course, evidence = mixed_inputs
    plan = fixture_blueprint(config, course)
    plan["sections"][0]["selection"] = {"mode":"choose","choose_count":1}
    plan = validate_blueprint(config, plan, course, evidence, recalculate=True)
    report = validate_topic_coverage(config, plan, course)
    assert report["printed_marks"] == report["shared_printed_marks"] == 6
    assert report["attempt_marks"] == 3
    assert all(t["required_question_ids"] == [] and t["optional_question_ids"] == ["q1", "q2"] for t in report["topics"])
    plan["questions"][1]["parts"][0]["knowledge_ids"] = ["K1"]
    with pytest.raises(DomainError, match="MIXED_TOPIC_COVERAGE_CONFLICT"):
        validate_blueprint(config, plan, course, evidence, recalculate=True)
