"""Course-local topic identity and read-only projections of legacy records."""
import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import intent
from .models import Course, Topic, LegacyTopicMapping

FIELDS = {"name", "code", "order", "provenance", "source_refs"}


def validate_patch(data):
    if not isinstance(data, dict) or set(data) - FIELDS:
        raise DomainError("TOPIC_FIELDS_INVALID", status=400)
    if "name" in data and (not isinstance(data["name"], str) or not 1 <= len(data["name"].strip()) <= 200):
        raise DomainError("TOPIC_NAME_INVALID", status=400)
    if "code" in data and (not isinstance(data["code"], str) or len(data["code"]) > 40):
        raise DomainError("TOPIC_CODE_INVALID", status=400)
    if "order" in data and (type(data["order"]) is not int or not 0 <= data["order"] <= 10000):
        raise DomainError("TOPIC_ORDER_INVALID", status=400)
    if "provenance" in data and data["provenance"] not in ("user_declared", "reviewed_material"):
        raise DomainError("TOPIC_PROVENANCE_INVALID", status=400)
    if "source_refs" in data and (not isinstance(data["source_refs"], list) or len(data["source_refs"]) > 30):
        raise DomainError("TOPIC_REFERENCES_INVALID", status=400)
    return {**data, **({"name": data["name"].strip()} if "name" in data else {})}


def validate_sources(course, data):
    from app.materials.models import MaterialVersion
    refs = data.get("source_refs", [])
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"material_version_id", "physical_page"}:
            raise DomainError("TOPIC_REFERENCES_INVALID", status=400)
        try:
            from uuid import UUID
            version_id = UUID(str(ref["material_version_id"]))
        except (ValueError, TypeError):
            raise DomainError("TOPIC_REFERENCES_INVALID", status=400)
        version = get_object_or_404(MaterialVersion, pk=version_id, material__course=course)
        page = ref["physical_page"]
        if type(page) is not int or not 1 <= page <= version.blob.pages:
            raise DomainError("TOPIC_REFERENCES_INVALID", status=400)
    if data.get("provenance") == "reviewed_material" and not refs:
        raise DomainError("TOPIC_REFERENCES_REQUIRED", status=400)


def topic_view(topic):
    from app.materials.models import MaterialTopicAssignment
    assignments = MaterialTopicAssignment.objects.filter(material_version__material__course=topic.course, topic_ids__contains=[str(topic.id)])
    return {"id": str(topic.id), "course_id": str(topic.course_id), "name": topic.name, "code": topic.code,
            "order": topic.order, "revision": topic.revision, "archived": topic.archived,
            "provenance": topic.provenance, "source_refs": topic.source_refs,
            "material_count": assignments.count(), "readiness": "needs_analysis" if assignments.exists() else "no_materials"}


def list_topics(owner, course_id):
    course = get_object_or_404(Course, pk=course_id, owner=owner)
    return {"topics": [topic_view(t) for t in course.topics.order_by("order", "created_at", "id")],
            "capabilities": {"mixed_topic_practice": False, "mock_exam": False}}


@transaction.atomic
def create_topic(owner, course_id, data, key):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    data = validate_patch(data)
    if not data.get("name"):
        raise DomainError("TOPIC_NAME_INVALID", status=400)
    validate_sources(course, data)
    record = intent(owner, f"topic-create:{course.id}", key, data)
    if record.response:
        return Topic.objects.get(pk=record.response["topic_id"], course=course)
    topic = Topic.objects.create(course=course, **data)
    record.response = {"topic_id": str(topic.id)}
    record.save(update_fields=["response"])
    return topic


@transaction.atomic
def update_topic(owner, topic_id, expected_revision, patch):
    topic = get_object_or_404(Topic.objects.select_for_update(), pk=topic_id, course__owner=owner)
    if topic.revision != expected_revision:
        raise DomainError("TOPIC_REVISION_CONFLICT", "Topic details changed. Reload and compare before saving.")
    patch = validate_patch(patch)
    validate_sources(topic.course, {"provenance": topic.provenance, "source_refs": topic.source_refs, **patch})
    for field, value in patch.items():
        setattr(topic, field, value)
    topic.revision += 1
    topic.save()
    return topic


def legacy_mapping(version):
    return [{"topic_id": str(m.topic_id), "name": m.topic_name, "code": m.topic_code,
             "knowledge_ids": m.knowledge_ids} for m in LegacyTopicMapping.objects.filter(course_version=version).order_by("id")]


def adapt_legacy_course(payload, mapping):
    result = copy.deepcopy(payload)
    result["topic_manifest"] = copy.deepcopy(mapping)
    for node in result["knowledge_nodes"]:
        node["topic_ids"] = [m["topic_id"] for m in mapping if node["id"] in m["knowledge_ids"]]
    return result


def adapt_legacy_config(config, mapping):
    result = copy.deepcopy(config)
    if result.get("schema_version") == "practice-config-v2":
        return result
    ids = list(result.pop("topic_ids"))
    result.update(schema_version="practice-config-v2", knowledge_ids=ids,
        selected_topic_ids=[m["topic_id"] for m in mapping if set(ids) & set(m["knowledge_ids"])])
    return result


@transaction.atomic
def register_legacy_mapping(owner, version_id, topic_id, knowledge_ids, source):
    """Explicit reviewed migration metadata, outside the immutable original payload."""
    from .models import CourseVersion
    version = get_object_or_404(CourseVersion, pk=version_id, course__owner=owner)
    topic = get_object_or_404(Topic.objects.select_for_update(), pk=topic_id, course=version.course)
    available = {n["id"] for n in version.frozen_payload["knowledge_nodes"]}
    if (not knowledge_ids or len(set(knowledge_ids)) != len(knowledge_ids)
            or set(knowledge_ids) - available or not isinstance(source, str) or not source.strip()):
        raise DomainError("LEGACY_MAPPING_INVALID", status=400)
    existing = LegacyTopicMapping.objects.filter(course_version=version, topic=topic).first()
    if existing:
        if existing.knowledge_ids != knowledge_ids:
            raise DomainError("LEGACY_MAPPING_IMMUTABLE")
        return existing
    return LegacyTopicMapping.objects.create(course_version=version, topic=topic,
        topic_name=topic.name, topic_code=topic.code, knowledge_ids=knowledge_ids, source=source)
