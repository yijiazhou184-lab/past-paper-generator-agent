"""Freeze reviewed topic slices into one immutable course version."""
import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import digest, intent
from .models import Course, CourseDraft, CourseVersion, Topic
from .topic_state import state_map, topic_slice, topic_base, COLLECTIONS
from .context import statement_list
from .schemas import validate_template
from .clarifications import classify_gaps


def common_hash(course,payload,frozen_statements=None):
    statements=[s for s in (statement_list(course) if frozen_statements is None else frozen_statements) if not s.get("topic_ids") and s["kind"] in ("exam_scope","clarification")]
    return digest({"title":payload["title"],"target_exam":payload["target_exam"],"statements":[{k:s.get(k,"") for k in ("id","text","kind","source","clarification_id","question")} for s in statements]})


def sources_current(course,context):
    from app.materials.models import MaterialVersion
    from app.materials.topic_assignments import assignment_view
    for m in context.get("materials",[]):
        v=MaterialVersion.objects.filter(pk=m["material_version_id"],material__course=course).first()
        if not v or v.classification_revision!=m["classification_revision"]:return False
        links=[{"target_version_id":str(a.target_id),"coverage":a.coverage,"revision":a.revision} for a in v.answer_links.filter(active=True).order_by("id")]
        if links!=m["answer_links"]:return False
        if "assignment" in m and assignment_view(v)!=m["assignment"]:return False
    return True


def version_topics(version):
    if version is None:return {}
    saved=version.evidence_manifest.get("topic_snapshots")
    if saved is not None:return copy.deepcopy(saved)
    from .topics import legacy_mapping
    result={}
    for m in legacy_mapping(version):
        ids=set(m["knowledge_ids"]);payload=copy.deepcopy(version.frozen_payload)
        for key in COLLECTIONS:
            payload[key]=[i for i in payload[key] if (i["id"] in ids if key=="knowledge_nodes" else bool(ids.intersection(i.get("subject_ids",i.get("affected_ids",[])))))]
        result[m["topic_id"]]={"topic_id":m["topic_id"],"name":m["name"],"code":m["code"],"payload":payload,
            "context":copy.deepcopy(version.evidence_manifest),"draft_revision":version.draft_revision,
            "common_hash":common_hash(version.course,version.frozen_payload,version.statements),"manual_patches":copy.deepcopy(version.manual_patches),
            "analysis_mode":version.evidence_manifest.get("analysis_mode","unknown")}
    return result


def topic_status(draft,topic_id,latest=None):
    payload=topic_slice(draft,topic_id)
    if not payload:return "needs_analysis"
    base=topic_base(draft,topic_id)
    if any(q["impact"]=="blocks_selected_scope" for q in classify_gaps(payload,[n["id"] for n in payload["knowledge_nodes"]])):
        return "needs_information"
    latest=latest or draft.course.confirmed_versions.order_by("-number").first()
    previous=version_topics(latest).get(topic_id)
    if previous:
        if (digest(previous["payload"])==digest(payload) and previous["common_hash"]==common_hash(draft.course,payload)
                and sources_current(draft.course,previous["context"])):
            return "confirmed"
        return "changes_pending"
    return "ready_for_review"


@transaction.atomic
def confirm_topics(owner,course_id,expected_revision,base_course_version_id,selected_topic_ids,key):
    course=get_object_or_404(Course.objects.select_for_update(),pk=course_id,owner=owner)
    if not isinstance(selected_topic_ids,list) or not selected_topic_ids or len(selected_topic_ids)!=len(set(selected_topic_ids)):
        raise DomainError("TOPIC_SELECTION_INVALID",status=400)
    selected=sorted(str(i) for i in selected_topic_ids)
    topics={str(t.id):t for t in Topic.objects.filter(course=course,id__in=selected,archived=False)}
    if len(topics)!=len(selected):raise DomainError("TOPIC_NOT_FOUND",status=404)
    request={"revision":expected_revision,"base_course_version_id":str(base_course_version_id) if base_course_version_id else None,"selected_topic_ids":selected}
    record=intent(owner,f"confirm-topics:{course.id}",key,request)
    if record.response:return CourseVersion.objects.get(pk=record.response["version_id"],course=course)
    draft=get_object_or_404(CourseDraft.objects.select_for_update(),course=course)
    if draft.revision!=expected_revision:raise DomainError("DRAFT_REVISION_CONFLICT")
    latest=course.confirmed_versions.order_by("-number").first()
    if (str(latest.id) if latest else None)!=request["base_course_version_id"]:
        raise DomainError("COURSE_VERSION_CONFLICT","A newer course version exists. Review it before confirming these topics.")
    draft.topic_state=state_map(draft)
    draft.save(update_fields=["topic_state"])
    shared=common_hash(course,draft.payload)
    snapshots={tid:s for tid,s in version_topics(latest).items() if s["common_hash"]==shared and sources_current(course,s["context"])}
    for tid in selected:
        state=state_map(draft).get(tid)
        if not state:raise DomainError("TOPIC_ANALYSIS_REQUIRED","Analyse this topic before confirming it.")
        payload=topic_slice(draft,tid);base=topic_base(draft,tid)
        if not payload["knowledge_nodes"] or any(q["impact"]=="blocks_selected_scope" for q in classify_gaps(payload,state["knowledge_ids"])):
            raise DomainError("COURSE_GAPS_BLOCK_CONFIRMATION","Resolve this topic's teaching or scope gaps first.")
        owned={i for ids in state["item_ids"].values() for i in ids}
        warnings=[w for w in draft.merge_warnings if len(w["path"])<3 or w["path"][1] in owned]
        if warnings:raise DomainError("MERGE_REVIEW_REQUIRED")
        if not sources_current(course,base.context):raise DomainError("MATERIAL_CONTEXT_CHANGED","Material classification or topic links changed. Review a new analysis first.")
        statements=statement_list(course,[tid]);used={s["id"] for s in base.context["statements"]}
        if any(s["kind"] in ("exam_scope","clarification") and s["id"] not in used for s in statements):
            raise DomainError("ANSWER_REANALYSIS_REQUIRED","Analyse the new statement for this topic before confirmation.")
        validate_template(payload["template_suggestion"])
        snapshots[tid]={"topic_id":tid,"name":topics[tid].name,"code":topics[tid].code,"payload":payload,
            "context":copy.deepcopy(base.context),"draft_revision":draft.revision,"common_hash":shared,
            "manual_patches":[p for p in draft.manual_patches if len(p["path"])<3 or p["path"][1] in owned],"analysis_mode":base.mode}
    frozen=copy.deepcopy(draft.payload)
    for field in COLLECTIONS:
        rows={}
        for snap in snapshots.values():
            for row in snap["payload"][field]:
                if row["id"] in rows and rows[row["id"]]!=row:raise DomainError("SHARED_KNOWLEDGE_CONFLICT")
                rows[row["id"]]=copy.deepcopy(row)
        frozen[field]=list(rows.values())
    frozen["topic_manifest"]=[{"topic_id":tid,"name":s["name"],"code":s["code"],
        "knowledge_ids":[n["id"] for n in s["payload"]["knowledge_nodes"]],"confirmed_draft_revision":s["draft_revision"],
        "template_suggestion":s["payload"]["template_suggestion"]} for tid,s in snapshots.items()]
    # The topic-specific template travels in the manifest; a whole-course template is not inferred.
    frozen["template_suggestion"]=snapshots[selected[0]]["payload"]["template_suggestion"] if len(snapshots)==1 else None
    contexts=[s["context"] for s in snapshots.values()]
    def union(field):
        values={}
        for c in contexts:
            for row in c.get(field,[]):
                identity=row.get("id") or row["material_version_id"]
                values[identity]=copy.deepcopy(row)
        return list(values.values())
    manifest={"topic_snapshots":snapshots,"evidence":union("evidence"),"materials":union("materials"),
        "statements":union("statements"),"target_ids":[n["id"] for n in frozen["knowledge_nodes"]],
        "course_title":frozen["title"],"round1_exclusions":["software_command_answers"],
        "analysis_mode":"live" if all(s["analysis_mode"]=="live" for s in snapshots.values()) else "fixture" if all(s["analysis_mode"]=="fixture" for s in snapshots.values()) else "mixed"}
    fingerprint=digest(request)
    version=CourseVersion.objects.filter(draft=draft,draft_revision=draft.revision,confirmation_fingerprint=fingerprint).first()
    if not version:
        version=CourseVersion.objects.create(course=course,number=(latest.number+1 if latest else 1),draft=draft,
            draft_revision=draft.revision,confirmation_fingerprint=fingerprint,payload_hash=digest(frozen),frozen_payload=frozen,
            evidence_manifest=manifest,statements=union("statements"),manual_patches=[p for s in snapshots.values() for p in s["manual_patches"]],confirmed_by=owner)
    record.response={"version_id":str(version.id)};record.save(update_fields=["response"])
    return version


def assert_topic_generation_current(version,config):
    """Old tasks remain readable; newly submitted work must review changed topic facts."""
    from app.generation.config_compat import selected_topics
    draft=CourseDraft.objects.filter(course=version.course).select_related("machine_base").first()
    if draft is None:return
    snapshots=version_topics(version)
    for summary in selected_topics(config,version):
        tid=summary["topic_id"];snap=snapshots.get(tid);current=topic_slice(draft,tid)
        if snap and (current is None or digest(current)!=digest(snap["payload"])
                or common_hash(version.course,draft.payload)!=snap["common_hash"]
                or not sources_current(version.course,snap["context"])):
            raise DomainError("TOPIC_REVIEW_REQUIRED","This topic or its course-wide information changed. Review and confirm it before new generation.")
