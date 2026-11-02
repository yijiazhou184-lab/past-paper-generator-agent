import copy
import uuid
import pytest
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.generation.schemas import validate_config
from app.generation.config_compat import knowledge_ids
from test_course_analysis import course_payload, analysis_context


def configuration():
    return {"schema_version":"practice-config-v2","course_version_id":str(uuid.uuid4()),"mode":"chapter_practice",
        "selected_topic_ids":["topic-a"],"knowledge_ids":["K1"],"difficulty":"exam_standard","main_question_count":2,
        "question_types":["calculation"]}


def test_v2_selection_is_separate_from_v1_knowledge_ids(course_payload,analysis_context):
    payload=copy.deepcopy(course_payload);payload["topic_manifest"]=[{"topic_id":"topic-a","knowledge_ids":["K1"]}]
    data=configuration()
    result=validate_config(data,payload,analysis_context["evidence"])
    assert result["knowledge_ids"]==["K1"] and "topic_ids" not in result
    legacy={k:v for k,v in data.items() if k not in ("schema_version","selected_topic_ids","knowledge_ids")}
    legacy["topic_ids"]=["K1"];hashed=digest(legacy)
    assert validate_config(legacy,payload,analysis_context["evidence"])==legacy
    assert digest(legacy)==hashed and knowledge_ids(legacy)==knowledge_ids(result)


def test_backend_rejects_mixed_topics_and_other_topic_knowledge(course_payload,analysis_context):
    payload=copy.deepcopy(course_payload);payload["topic_manifest"]=[{"topic_id":"topic-a","knowledge_ids":["K1"]},{"topic_id":"topic-b","knowledge_ids":["other"]}]
    data=configuration();data["selected_topic_ids"]=["topic-a","topic-b"]
    with pytest.raises(DomainError,match="MIXED_TOPIC_PRACTICE_UNAVAILABLE"):validate_config(data,payload,analysis_context["evidence"])
    data=configuration();data["knowledge_ids"]=["other"]
    with pytest.raises(DomainError,match="KNOWLEDGE_OUTSIDE_TOPIC"):validate_config(data,payload,analysis_context["evidence"])
    data=configuration();data["selected_topic_ids"]=["not-in-version"]
    with pytest.raises(DomainError,match="TOPIC_OUTSIDE_VERSION"):validate_config(data,payload,analysis_context["evidence"])


from test_generation_snapshot import version
from test_course_drafts import draft


def test_legacy_course_version_supports_a_new_v2_plan_without_rewriting_it(course,version):
    from app.courses.topics import create_topic,register_legacy_mapping
    from app.generation.snapshots import save_config
    from app.generation.planning import build_context,submit_plan,run_planning
    from app.core.tasks import claim_task
    topic=create_topic(course.owner,course.id,{"name":"Explicitly mapped chapter"},"chapter")
    ids=[n["id"] for n in version.frozen_payload["knowledge_nodes"]]
    original=copy.deepcopy(version.frozen_payload)
    register_legacy_mapping(course.owner,version.id,topic.id,ids,"Reviewed fixture mapping")
    config=configuration();config.update(course_version_id=str(version.id),selected_topic_ids=[str(topic.id)],knowledge_ids=ids)
    saved,_=save_config(course.owner,course.id,0,config,"config-v2")
    context=build_context(saved)
    assert context["input"]["course"]["topic_manifest"][0]["topic_id"]==str(topic.id)
    task=submit_plan(course.owner,course.id,saved.revision,context["context_hash"],"new-plan")
    run_planning(claim_task(task.id))
    task.refresh_from_db();assert task.state=="succeeded"
    version.refresh_from_db();assert version.frozen_payload==original
