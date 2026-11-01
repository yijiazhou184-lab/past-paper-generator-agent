import copy
from app.courses.topics import adapt_legacy_config, adapt_legacy_course


def test_legacy_projection_never_changes_original_fields_or_hash():
    from app.core.idempotency import digest
    config={"course_version_id":"v1","mode":"chapter_practice","topic_ids":["knowledge-a"],
        "difficulty":"exam_standard","main_question_count":3,"question_types":["calculation"]}
    payload={"knowledge_nodes":[{"id":"knowledge-a","title":"Rate"}]}
    mapping=[{"topic_id":"chapter-a","name":"Rates","code":"A","knowledge_ids":["knowledge-a"]}]
    before=copy.deepcopy(config); hashed=digest(config)
    view=adapt_legacy_config(config,mapping)
    assert view["knowledge_ids"]==["knowledge-a"] and view["selected_topic_ids"]==["chapter-a"]
    assert config==before and digest(config)==hashed and "schema_version" not in config
    assert adapt_legacy_course(payload,mapping)["knowledge_nodes"][0]["topic_ids"]==["chapter-a"]
    assert "topic_ids" not in payload["knowledge_nodes"][0]


from test_course_drafts import draft, course_payload, analysis_context


def test_mapping_freezes_names_without_mutating_confirmed_payload(course, draft):
    from app.courses.confirmation import confirm_course
    from app.courses.topics import create_topic, register_legacy_mapping, update_topic, legacy_mapping
    from app.core.idempotency import digest
    version = confirm_course(course.owner, course.id, draft.id, 1, "v")
    original = copy.deepcopy(version.frozen_payload)
    old_hash = version.payload_hash
    topic = create_topic(course.owner, course.id, {"name": "Reviewed topic"}, "topic")
    nodes = [n["id"] for n in original["knowledge_nodes"]]
    mapping = register_legacy_mapping(course.owner, version.id, topic.id, nodes, "Reviewed fixture correspondence")
    assert register_legacy_mapping(course.owner, version.id, topic.id, nodes, "Reviewed fixture correspondence").id == mapping.id
    update_topic(course.owner, topic.id, 1, {"name": "New catalogue label"})
    assert legacy_mapping(version)[0]["name"] == "Reviewed topic"
    version.refresh_from_db()
    assert version.frozen_payload == original and version.payload_hash == old_hash
    assert digest(version.frozen_payload) == digest(original)
