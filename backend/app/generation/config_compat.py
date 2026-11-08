"""Two unambiguous configuration formats; frozen v1 records are never rewritten."""
import copy
from app.core.errors import DomainError


COMPARISON_ROLES = {"past_paper", "practice", "seminar", "revision", "additional_questions", "assessment"}


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
    mixed = config["mode"] == "mixed_topic_practice"
    if config["mode"] == "chapter_practice" and len(selected) != 1:
        raise DomainError("MIXED_TOPIC_PRACTICE_UNAVAILABLE", "Switch to mixed-topic practice to select multiple topics.", status=400)
    if mixed and len(selected) < 2:
        raise DomainError("MIXED_TOPIC_SELECTION_REQUIRED", "Choose knowledge from at least two confirmed topics.", status=400)
    manifest = {m["topic_id"]: m for m in course_payload.get("topic_manifest", [])}
    if any(tid not in manifest for tid in selected):
        raise DomainError("TOPIC_OUTSIDE_VERSION", "Choose confirmed topics from this course version.", status=400)
    ids = set(config["knowledge_ids"])
    by_topic = [set(manifest[tid]["knowledge_ids"]) for tid in selected]
    if not ids <= set().union(*by_topic):
        raise DomainError("KNOWLEDGE_OUTSIDE_TOPIC", "Choose knowledge within the selected topics and version.", status=400)
    if any(not ids.intersection(targets) for targets in by_topic):
        raise DomainError("TOPIC_WITHOUT_KNOWLEDGE", "Select at least one knowledge target in every chosen topic.", status=400)


def selected_topics(config,version):
    manifest=course_projection(version)["topic_manifest"]
    ids=set(knowledge_ids(config))
    explicit = set(config.get("selected_topic_ids", []))
    return [{k:m[k] for k in ("topic_id","name","code")} for m in manifest
            if (not explicit or m["topic_id"] in explicit) and ids.intersection(m["knowledge_ids"])]


def mixed_topic_inputs(config, course, evidence_manifest, statements):
    """Select frozen teaching references and a small comparison sample per chosen topic."""
    from app.courses.eligibility import project_targets

    selected = set(config["selected_topic_ids"])
    targets = set(knowledge_ids(config))
    snapshots = evidence_manifest.get("topic_snapshots", {})
    fields = ("method_rules", "scope_claims", "historical_style", "issues", "clarifications")
    if selected <= snapshots.keys():
        course = dict(course)
        for field in fields:
            scoped_ids = {row["id"] for tid in selected for row in snapshots[tid]["payload"].get(field, [])}
            course[field] = [row for row in course.get(field, []) if row["id"] in scoped_ids]
    course = project_targets(course, knowledge_ids(config))
    course["topic_manifest"] = [
        {**topic, "knowledge_ids": [kid for kid in topic["knowledge_ids"] if kid in targets]}
        for topic in course["topic_manifest"] if topic["topic_id"] in selected
    ]
    course["template_suggestion"] = None
    reference_ids = {
        eid for field in ("knowledge_nodes", *fields)
        for row in course.get(field, []) for eid in row.get("evidence_ids", [])
    }
    for topic in sorted(selected):
        rows = snapshots.get(topic, {}).get("context", {}).get("evidence", [])
        candidates = [e for e in rows if COMPARISON_ROLES.intersection(e.get("roles", []))
                      and e.get("visual_status") != "visual_pending" and (e.get("text") or e.get("visual"))]
        reference_ids.update(e["id"] for e in sorted(candidates, key=lambda e: e["id"])[:2])
    evidence = [e for e in evidence_manifest["evidence"] if e["id"] in reference_ids]
    statements = [s for s in statements if not s.get("topic_ids") or selected.intersection(s["topic_ids"])]
    return course, evidence, statements
