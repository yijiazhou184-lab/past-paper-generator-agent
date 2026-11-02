import pytest
from rest_framework.test import APIClient
from app.courses.models import CourseVersion
from app.core.models import ModelInvocation, Task
from test_topic_analysis import topic_sources,course_payload,analysis_context
from test_topic_confirmation import two_topics


def test_scoped_profile_and_patch_are_isolated(course,two_topics):
    a,b,draft=two_topics
    client=APIClient();client.force_authenticate(course.owner)
    root=f"/api/v1/courses/{course.id}"
    view=client.get(root+f"/profile?topic={a.id}").json()
    assert [n["id"] for n in view["draft"]["payload"]["knowledge_nodes"]]==["node-a"]
    assert view["draft"]["topic_id"]==str(a.id) and len(view["topics"])==2
    response=client.patch(root+"/draft",{"topic_id":str(a.id),"expected_revision":draft.revision,
        "patches":[{"path":["knowledge_nodes","node-b","title"],"value":"Wrong scope"}]},format="json",HTTP_IDEMPOTENCY_KEY="wrong")
    assert response.status_code==400
    response=client.post(root+"/confirmations",{"draft_id":str(draft.id),"expected_revision":draft.revision,
        "selected_topic_ids":[str(a.id)],"base_course_version_id":None},format="json",HTTP_IDEMPOTENCY_KEY="scoped-confirm")
    assert response.status_code==200
    assert len(response.json()["frozen_payload"]["topic_manifest"])==1
    assert "node-b" not in [n["id"] for n in response.json()["frozen_payload"]["knowledge_nodes"]]
    assert client.post(root+"/confirmations",{"draft_id":str(draft.id),"expected_revision":draft.revision},format="json",HTTP_IDEMPOTENCY_KEY="bypass").status_code==409


def test_preflight_is_local_and_changes_have_new_hash(course,topic_sources):
    topic,version=topic_sources
    client=APIClient();client.force_authenticate(course.owner)
    url=f"/api/v1/courses/{course.id}/analysis-preflight"
    data={"target_topic_ids":[str(topic.id)],"base_revision":0,
        "material_selection":[{"material_version_id":str(version.id),"pages":[1]}]}
    first=client.post(url,data,format="json")
    assert first.status_code==200
    assert first.json()["scope"]["page_count"]==1
    data["material_selection"][0]["pages"]=[2]
    second=client.post(url,data,format="json")
    assert second.json()["scope"]["context_hash"]!=first.json()["scope"]["context_hash"]
    assert not ModelInvocation.objects.exists() and not Task.objects.filter(kind="analysis").exists()
