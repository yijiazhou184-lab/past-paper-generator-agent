import copy

import pytest
from rest_framework.test import APIClient

from app.core.idempotency import digest
from app.courses.models import Course
from app.materials.models import Material, MaterialBlob, MaterialVersion
from test_course_analysis import analysis_context, course_payload
from test_topic_confirmation import two_topics


def template(origin="user_entry", sources=None):
    return {
        "sections": [
            {"id": "required", "title": "Required", "question_marks": [20],
             "selection": {"mode": "all", "choose_count": 1}},
            {"id": "optional", "title": "Options", "question_marks": [10, 10],
             "selection": {"mode": "choose", "choose_count": 1}},
        ],
        "duration_minutes": 45, "question_types": ["calculation"],
        "permitted_aids": None, "origin": origin, "sources": sources or [],
    }


def exam_source(course, roles):
    blob = MaterialBlob.objects.create(owner=course.owner, sha256="a" * 64, bytes=1, pages=3, storage_key="test")
    return MaterialVersion.objects.create(material=Material.objects.create(course=course), blob=blob,
                                          original_filename="Practice.pdf", roles=roles)


def patch_template(client, course, revision, value, key):
    return client.patch(f"/api/v1/courses/{course.id}/draft", {
        "expected_revision": revision, "patches": [{"path": ["exam_template"], "value": value}],
    }, format="json", HTTP_IDEMPOTENCY_KEY=key)


def confirm(client, course, draft, topic_ids, key, base=None, include=True):
    return client.post(f"/api/v1/courses/{course.id}/confirmations", {
        "draft_id": str(draft["id"]), "expected_revision": draft["revision"],
        "selected_topic_ids": topic_ids, "base_course_version_id": base, "include_exam_template": include,
    }, format="json", HTTP_IDEMPOTENCY_KEY=key)


@pytest.mark.django_db
def test_courses_keep_independent_templates_and_only_current_evidence(course, two_topics):
    a, _, draft = two_topics
    client = APIClient()
    client.force_authenticate(course.owner)
    other = Course.objects.create(owner=course.owner, title="Another course")
    foreign = exam_source(other, ["past_paper"])
    value = template("historical_reference", [{"material_version_id": str(foreign.id), "physical_page": 2}])
    assert patch_template(client, course, draft.revision, value, "foreign").status_code == 400
    foreign.material.course = course
    foreign.material.save()
    value["origin"] = "current_instruction"
    assert patch_template(client, course, draft.revision, value, "unsupported-authority").status_code == 400
    value["origin"] = "historical_reference"
    result = patch_template(client, course, draft.revision, value, "save")
    assert result.status_code == 200, result.json()
    saved = result.json()["draft"]
    assert saved["payload"]["exam_template"]["origin"] == "historical_reference"
    response = confirm(client, course, saved, [str(a.id)], "first")
    assert response.status_code == 200, response.json()
    assert response.json()["frozen_payload"]["exam_template"]["calibration"] == "uncalibrated"
    assert other.confirmed_versions.count() == 0
    assert not other.materials.exists()


@pytest.mark.django_db
def test_template_edit_is_preserved_and_requires_new_confirmation(course, two_topics):
    a, _, draft = two_topics
    client = APIClient()
    client.force_authenticate(course.owner)
    value = template()
    current = patch_template(client, course, draft.revision, value, "save").json()["draft"]
    first = confirm(client, course, current, [str(a.id)], "first").json()
    assert first["frozen_payload"]["exam_template"]["duration_minutes"] == 45
    updated = {**value, "duration_minutes": 60}
    current = patch_template(client, course, current["revision"], updated, "new").json()["draft"]
    current = patch_template(client, course, current["revision"], value, "restore").json()["draft"]
    assert current["exam_template_status"] == "changes_pending"
    response = confirm(client, course, current, [], "confirm-updated", base=first["id"])
    assert response.status_code == 200, response.json()
    second = response.json()
    assert second["id"] != first["id"]
    assert second["frozen_payload"]["exam_template"]["template_revision"] > first["frozen_payload"]["exam_template"]["template_revision"]
    old = course.confirmed_versions.get(pk=first["id"])
    assert old.frozen_payload == first["frozen_payload"]
    assert old.payload_hash == digest(old.frozen_payload)


@pytest.mark.django_db
def test_unequal_choice_marks_are_rejected(course, two_topics):
    _, _, draft = two_topics
    client = APIClient()
    client.force_authenticate(course.owner)
    invalid = copy.deepcopy(template())
    invalid["sections"][1]["question_marks"] = [10, 15]
    response = patch_template(client, course, draft.revision, invalid, "invalid")
    assert response.status_code == 400
    assert response.json()["code"] == "EXAM_TEMPLATE_MARKS_INVALID"
