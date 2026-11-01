import pytest
from app.core.errors import DomainError
from app.materials.ingest import ingest_pdf
from app.materials.models import MaterialBlob
from app.courses.topics import create_topic
from app.materials.topic_assignments import set_topic_assignment, assignment_view, filter_materials


def test_shared_blob_two_topics_filter_and_ranges(course, pdf_bytes):
    from app.materials.models import MaterialVersion
    result = ingest_pdf(course, pdf_bytes, "sample.pdf", "upload")
    version = MaterialVersion.objects.get(pk=result["version_id"])
    a=create_topic(course.owner,course.id,{"name":"Alpha"},"a")
    b=create_topic(course.owner,course.id,{"name":"Beta"},"b")
    assignment=set_topic_assignment(course.owner,version.id,0,{"scope":"topic","topic_ids":[str(a.id),str(b.id)],
        "page_ranges_by_topic":{str(a.id):[[1,1]],str(b.id):[[1,2]]},"shared_page_ranges":[],"note":"User classification"})
    assert assignment.revision==1
    assert filter_materials(course.owner,course.id,str(a.id),False).count()==1
    assert filter_materials(course.owner,course.id,str(b.id),False).count()==1
    assert MaterialBlob.objects.count()==1
    with pytest.raises(DomainError,match="ASSIGNMENT_REVISION_CONFLICT"):
        set_topic_assignment(course.owner,version.id,0,assignment_view(version))
    with pytest.raises(DomainError,match="PAGE_RANGE_INVALID"):
        set_topic_assignment(course.owner,version.id,1,{"scope":"topic","topic_ids":[str(a.id)],
            "page_ranges_by_topic":{str(a.id):[[1,3]]},"shared_page_ranges":[]})


def test_shared_unassigned_and_foreign_topic_are_not_implicit_scope(course, pdf_bytes):
    from app.materials.models import MaterialVersion
    from app.courses.models import Course
    result = ingest_pdf(course, pdf_bytes, "shared.pdf", "one")
    version = MaterialVersion.objects.get(pk=result["version_id"])
    a = create_topic(course.owner, course.id, {"name": "Alpha"}, "alpha")
    assert filter_materials(course.owner, course.id, "unassigned").count() == 1
    assert not filter_materials(course.owner, course.id, str(a.id)).exists()
    set_topic_assignment(course.owner, version.id, 0, {"scope": "shared", "topic_ids": [], "shared_page_ranges": [[2, 2]]})
    assert filter_materials(course.owner, course.id, "shared").count() == 1
    assert filter_materials(course.owner, course.id, str(a.id), True).count() == 1
    assert not filter_materials(course.owner, course.id, str(a.id), False).exists()
    assert not filter_materials(course.owner, course.id, "unassigned").exists()
    other = Course.objects.create(owner=course.owner, title="Another course")
    b = create_topic(course.owner, other.id, {"name": "Foreign topic"}, "beta")
    with pytest.raises(DomainError, match="TOPIC_NOT_FOUND"):
        set_topic_assignment(course.owner, version.id, 1, {"scope": "topic", "topic_ids": [str(b.id)]})
    duplicate = ingest_pdf(course, pdf_bytes, "another-path.pdf", "duplicate")
    assert duplicate["duplicate"] and duplicate["version_id"] == result["version_id"]
    assert assignment_view(version)["shared_page_ranges"] == [[2, 2]]


def test_assignment_api_validates_owner_and_revision(course, pdf_bytes, django_user_model):
    from rest_framework.test import APIClient
    result = ingest_pdf(course, pdf_bytes, "lecture.pdf", "api")
    client = APIClient(); client.force_authenticate(course.owner)
    url = f"/api/v1/material-versions/{result['version_id']}/topic-assignment"
    data = {"expected_revision": 0, "scope": "shared", "topic_ids": [], "page_ranges_by_topic": {}, "shared_page_ranges": []}
    assert client.patch(url, data, format="json").status_code == 200
    assert client.patch(url, data, format="json").status_code == 409
    client.force_authenticate(django_user_model.objects.create_user(username="outsider"))
    assert client.patch(url, {**data, "expected_revision": 1}, format="json").status_code == 404
