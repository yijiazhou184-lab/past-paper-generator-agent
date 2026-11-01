"""Editable classification links; never modify a source file or assume permission to send it."""
from uuid import UUID
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.courses.models import Course, Topic
from .models import MaterialVersion, MaterialTopicAssignment


def assignment_view(version):
    row = MaterialTopicAssignment.objects.filter(material_version=version).first()
    return {"revision": row.revision if row else 0, "scope": row.scope if row else "unassigned",
        "topic_ids": row.topic_ids if row else [], "page_ranges_by_topic": row.page_ranges_by_topic if row else {},
        "shared_page_ranges": row.shared_page_ranges if row else [], "note": row.note if row else "",
        "provenance": "user_classification"}


def ranges(value, pages):
    if not isinstance(value, list) or len(value) > 100:
        raise DomainError("PAGE_RANGE_INVALID", status=400)
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2 or any(type(n) is not int for n in pair) or not 1 <= pair[0] <= pair[1] <= pages:
            raise DomainError("PAGE_RANGE_INVALID", "Use inclusive physical page ranges within this PDF.", status=400)
    return value


@transaction.atomic
def set_topic_assignment(owner, material_version_id, expected_revision, assignment):
    version = get_object_or_404(MaterialVersion.objects.select_for_update(), pk=material_version_id, material__course__owner=owner)
    row = MaterialTopicAssignment.objects.filter(material_version=version).first()
    if expected_revision != (row.revision if row else 0):
        raise DomainError("ASSIGNMENT_REVISION_CONFLICT", "Topic links changed. Compare the saved links before retrying.")
    if not isinstance(assignment, dict) or set(assignment) - {"scope", "topic_ids", "page_ranges_by_topic", "shared_page_ranges", "note", "revision", "provenance"}:
        raise DomainError("ASSIGNMENT_INVALID", status=400)
    scope = assignment.get("scope")
    ids = assignment.get("topic_ids", [])
    if scope not in ("topic", "shared", "unassigned") or not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(i, str) for i in ids):
        raise DomainError("ASSIGNMENT_INVALID", status=400)
    try:
        ids = [str(UUID(i)) for i in ids]
    except ValueError:
        raise DomainError("TOPIC_NOT_FOUND", status=404)
    if len(ids) != len(set(ids)) or (scope == "topic") != bool(ids):
        raise DomainError("ASSIGNMENT_INVALID", status=400)
    if Topic.objects.filter(course_id=version.material.course_id, pk__in=ids, archived=False).count() != len(ids):
        raise DomainError("TOPIC_NOT_FOUND", status=404)
    page_ranges = assignment.get("page_ranges_by_topic", {})
    shared = ranges(assignment.get("shared_page_ranges", []), version.blob.pages)
    if not isinstance(page_ranges, dict) or set(page_ranges) - set(ids) or (scope != "shared" and shared):
        raise DomainError("ASSIGNMENT_INVALID", status=400)
    page_ranges = {tid: ranges(value, version.blob.pages) for tid, value in page_ranges.items()}
    note = assignment.get("note", "")
    if not isinstance(note, str) or len(note) > 2000:
        raise DomainError("ASSIGNMENT_INVALID", status=400)
    row = row or MaterialTopicAssignment(material_version=version)
    row.scope, row.topic_ids, row.page_ranges_by_topic = scope, ids, page_ranges
    row.shared_page_ranges, row.note = shared, note
    row.revision = (row.revision if row.pk and not row._state.adding else 0) + 1
    row.save()
    return row


def filter_materials(owner, course_id, topic_id=None, include_shared=False):
    course = get_object_or_404(Course, pk=course_id, owner=owner)
    query = MaterialVersion.objects.filter(material__course=course)
    if not topic_id or topic_id == "all":
        return query
    if topic_id == "shared":
        return query.filter(topic_assignment__scope="shared")
    if topic_id == "unassigned":
        return query.filter(Q(topic_assignment__isnull=True) | Q(topic_assignment__scope="unassigned"))
    try:
        topic = get_object_or_404(Topic, pk=UUID(topic_id), course=course)
    except ValueError:
        raise DomainError("TOPIC_NOT_FOUND", status=404)
    criterion = Q(topic_assignment__topic_ids__contains=[str(topic.id)])
    if include_shared:
        criterion |= Q(topic_assignment__scope="shared")
    return query.filter(criterion)
