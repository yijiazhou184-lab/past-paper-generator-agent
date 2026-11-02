"""Explicit topic/page selection for analysis; no subject-specific defaults."""
import copy
from uuid import UUID
from django.shortcuts import get_object_or_404
from app.core.errors import DomainError
from app.core.idempotency import digest
from app.materials.models import MaterialVersion
from app.materials.evidence import build_evidence_pack
from app.materials.topic_assignments import assignment_view
from .models import Topic, CourseDraft
from .topic_state import topic_slice
from .context import attach_visual_evidence, statement_list, freeze_context
from app.materials.routing import RULE_VERSION


def selection_defaults(course, topic_id):
    """Suggestions only: empty ranges stay empty and cannot submit analysis."""
    from app.materials.topic_assignments import filter_materials
    result=[]
    for version in filter_materials(course.owner, course.id, topic_id, False).select_related("blob"):
        assignment=assignment_view(version)
        ranges=assignment["page_ranges_by_topic"].get(str(topic_id),[])
        result.append({"material_version_id":str(version.id),"pages":sorted({p for a,b in ranges for p in range(a,b+1)})})
    return result


def build_topic_analysis_context(course, target_topic_ids, material_selection, base_revision):
    if not isinstance(target_topic_ids,list) or len(target_topic_ids)!=1:
        raise DomainError("ANALYSIS_TOPIC_REQUIRED","Choose one topic for this analysis. Other topics keep their own drafts.",status=400)
    try: tid=str(UUID(str(target_topic_ids[0])))
    except (TypeError,ValueError): raise DomainError("TOPIC_NOT_FOUND",status=404)
    topic=get_object_or_404(Topic,pk=tid,course=course,archived=False)
    draft=CourseDraft.objects.filter(course=course).select_related("machine_base").first()
    if base_revision != (draft.revision if draft else 0):
        raise DomainError("DRAFT_REVISION_CONFLICT","The course draft changed. Refresh the analysis selection.")
    if not isinstance(material_selection,list) or not 1<=len(material_selection)<=20:
        raise DomainError("ANALYSIS_PAGES_REQUIRED","Select the material versions and physical pages to analyse.",status=400)
    selected={}
    versions={}
    for entry in material_selection:
        if not isinstance(entry,dict) or set(entry)!={"material_version_id","pages"}:
            raise DomainError("ANALYSIS_SELECTION_INVALID",status=400)
        try: mid=str(UUID(str(entry["material_version_id"])))
        except (TypeError,ValueError): raise DomainError("ANALYSIS_SELECTION_INVALID",status=400)
        if mid in selected: raise DomainError("ANALYSIS_SELECTION_INVALID",status=400)
        version=get_object_or_404(MaterialVersion.objects.select_related("blob"),pk=mid,material__course=course)
        assignment=assignment_view(version)
        if assignment["scope"]!="shared" and tid not in assignment["topic_ids"]:
            raise DomainError("MATERIAL_TOPIC_NOT_LINKED","Link this material to the selected topic or mark it course-wide first.",status=400)
        pages=entry["pages"]
        if not isinstance(pages,list) or not pages or len(pages)>300:
            raise DomainError("ANALYSIS_PAGES_REQUIRED","Empty page ranges do not select the whole file.",status=400)
        if any(type(p) is not int or not 1<=p<=version.blob.pages for p in pages) or len(set(pages))!=len(pages):
            raise DomainError("PAGE_RANGE_INVALID",status=400)
        selected[mid]=sorted(pages);versions[mid]=version
    if sum(map(len,selected.values()))>100:
        raise DomainError("ANALYSIS_PAGE_LIMIT","Choose at most 100 necessary pages for one analysis.",status=400)
    pack=build_evidence_pack(course.owner,list(selected))
    materials=[]
    for m in pack["materials"]:
        v=versions[m["material_version_id"]]
        materials.append({**m,"filename":v.original_filename,"code":"material-"+str(v.id)[:8],
            "selected_pages":selected[str(v.id)],"assignment":assignment_view(v)})
    byid={m["material_version_id"]:m for m in materials}
    evidence=[{**{k:v for k,v in e.items() if k!="blocks"},
        "material_code":byid[e["material_version_id"]]["code"],"roles":versions[e["material_version_id"]].roles,
        "blob_sha256":versions[e["material_version_id"]].blob.sha256}
        for e in pack["evidence"] if e["physical_page"] in selected[e["material_version_id"]]]
    attach_visual_evidence(course,evidence)
    prior=topic_slice(draft,tid) if draft else None
    nodes=prior["knowledge_nodes"] if prior else []
    data={"course_title":course.title,"target_topic_ids":[tid],
        "target_topics":[{"id":tid,"name":topic.name,"code":topic.code,"revision":topic.revision}],
        "base_revision":base_revision,"target_ids":[n["id"] for n in nodes],
        "target_knowledge":[{"id":n["id"],"title":n["title"]} for n in nodes],
        "materials":materials,"evidence":evidence,"route_rule_version":RULE_VERSION,
        "statements":statement_list(course,[tid]),
        "round1_exclusions":["software_command_answers"],
        "analysis_scope":"Discover knowledge only for the selected topic. Preserve supplied existing IDs when applicable.",
        "capabilities":{"response_types":["calculation","explanation_proof","applied_optimisation"],"mixed_topic_practice":False}}
    return freeze_context(data)
