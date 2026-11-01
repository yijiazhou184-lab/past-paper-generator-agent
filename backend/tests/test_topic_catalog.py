import pytest
from rest_framework.test import APIClient
from app.core.errors import DomainError
from app.courses.topics import create_topic, update_topic, list_topics


def test_catalog_identity_idempotency_and_revision(course):
    topic = create_topic(course.owner, course.id, {"name": "Rates of change", "code": "T-A"}, "first")
    assert create_topic(course.owner, course.id, {"name": "Rates of change", "code": "T-A"}, "first").id == topic.id
    another = create_topic(course.owner, course.id, {"name": "Rates of change"}, "second")
    assert another.id != topic.id
    changed = update_topic(course.owner, topic.id, 1, {"name": "Renamed", "order": 3})
    assert changed.id == topic.id and changed.revision == 2
    with pytest.raises(DomainError, match="TOPIC_REVISION_CONFLICT"):
        update_topic(course.owner, topic.id, 1, {"name": "Stale"})
    assert len(list_topics(course.owner, course.id)["topics"]) == 2


def test_topic_api_owner_and_invalid_fields(course, django_user_model):
    client = APIClient(); client.force_authenticate(course.owner)
    url = f"/api/v1/courses/{course.id}/topics"
    response = client.post(url, {"name": "Topic alpha"}, format="json", HTTP_IDEMPOTENCY_KEY="one")
    assert response.status_code == 201
    tid = response.json()["id"]
    assert client.patch(f"{url}/{tid}", {"expected_revision": 1, "order": -2}, format="json").status_code == 400
    assert client.get(url).json()["capabilities"]["mixed_topic_practice"] is False
    other = django_user_model.objects.create_user(username="other")
    client.force_authenticate(other)
    assert client.get(url).status_code == 404
    assert client.patch(f"{url}/{tid}", {"expected_revision": 1, "name": "Wrong owner"}, format="json").status_code == 404


def test_topic_sources_are_explicit_pages_in_own_course(course, pdf_bytes):
    from app.materials.ingest import ingest_pdf
    from app.courses.models import Course
    from django.http import Http404
    result = ingest_pdf(course, pdf_bytes, "lecture.pdf", "source")
    ref = {"material_version_id": result["version_id"], "physical_page": 1}
    topic = create_topic(course.owner, course.id, {"name": "Alpha", "provenance": "reviewed_material", "source_refs": [ref]}, "reviewed")
    assert topic.source_refs == [ref]
    with pytest.raises(DomainError, match="TOPIC_REFERENCES_REQUIRED"):
        create_topic(course.owner, course.id, {"name": "No reference", "provenance": "reviewed_material"}, "empty")
    with pytest.raises(DomainError, match="TOPIC_REFERENCES_INVALID"):
        update_topic(course.owner, topic.id, 1, {"source_refs": [{**ref, "physical_page": 3}]})
    other = Course.objects.create(owner=course.owner, title="Another course")
    with pytest.raises(Http404):
        create_topic(course.owner, other.id, {"name": "Foreign", "source_refs": [ref]}, "foreign")
