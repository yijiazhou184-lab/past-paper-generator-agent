"""Two unambiguous configuration formats; frozen v1 records are never rewritten."""
import copy
from app.core.errors import DomainError


def knowledge_ids(config):
    return config["knowledge_ids"] if config.get("schema_version")=="practice-config-v2" else config["topic_ids"]


def course_projection(version):
    if "topic_manifest" in version.frozen_payload:return copy.deepcopy(version.frozen_payload)
    from app.courses.topics import legacy_mapping, adapt_legacy_course
    return adapt_legacy_course(version.frozen_payload,legacy_mapping(version))


def validate_topic_selection(config,course_payload,capabilities=None):
    if config.get("schema_version")!="practice-config-v2":return
    selected=config["selected_topic_ids"]
    if len(selected)!=len(set(selected)) or len(config["knowledge_ids"])!=len(set(config["knowledge_ids"])):
        raise DomainError("DUPLICATE_IDENTIFIER",status=400)
    if len(selected)!=1:
        raise DomainError("MIXED_TOPIC_PRACTICE_UNAVAILABLE","Choose knowledge from one topic. Mixed-topic practice is not available yet.",status=400)
    manifest={m["topic_id"]:m for m in course_payload.get("topic_manifest",[])}
    if selected[0] not in manifest:
        raise DomainError("TOPIC_OUTSIDE_VERSION","Choose a confirmed topic in this course version.",status=400)
    if not set(config["knowledge_ids"]) <= set(manifest[selected[0]]["knowledge_ids"]):
        raise DomainError("KNOWLEDGE_OUTSIDE_TOPIC","Choose knowledge within the selected topic and version.",status=400)


def selected_topics(config,version):
    manifest=course_projection(version)["topic_manifest"]
    ids=set(knowledge_ids(config))
    return [{k:m[k] for k in ("topic_id","name","code")} for m in manifest if ids.intersection(m["knowledge_ids"])]
