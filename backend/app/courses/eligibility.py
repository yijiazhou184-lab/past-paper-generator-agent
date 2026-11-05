"""Eligibility depends on selected objectives and their actual prerequisites."""
import copy
from app.core.errors import DomainError


def objective_ids(payload):
    return [n["id"] for n in payload["knowledge_nodes"] if n.get("node_kind","objective")!="group"]


def eligible_targets(payload,selected_ids):
    nodes={n["id"]:n for n in payload["knowledge_nodes"]}
    if not isinstance(selected_ids,list) or not selected_ids or len(set(selected_ids))!=len(selected_ids):
        raise DomainError("KNOWLEDGE_SELECTION_INVALID","Choose at least one learning objective.",status=400)
    if any(k not in nodes or nodes[k].get("node_kind","objective")=="group" for k in selected_ids):
        raise DomainError("KNOWLEDGE_SELECTION_INVALID","Choose learning objectives from this draft.",status=400)
    selected=set();visiting=set()
    def visit(k):
        if k in visiting:raise DomainError("PREREQUISITE_CYCLE","Review the prerequisite cycle.")
        if k in selected:return
        if k not in nodes:raise DomainError("PREREQUISITE_MISSING","A required prerequisite is absent.")
        if nodes[k].get("node_kind","objective")=="group":
            children=[n["id"] for n in nodes.values() if n["parent_id"]==k]
            if not children:raise DomainError("PREREQUISITE_MISSING")
            visiting.add(k)
            for child in children:visit(child)
            visiting.remove(k);return
        visiting.add(k)
        for parent in nodes[k].get("prerequisite_ids",[]):visit(parent)
        visiting.remove(k);selected.add(k)
    for k in selected_ids:visit(k)
    from .clarifications import classify_gaps
    ids=[n["id"] for n in payload["knowledge_nodes"] if n["id"] in selected]
    blockers=[q for q in classify_gaps(payload,ids) if q["impact"]=="blocks_selected_scope"]
    return {"selected_ids":selected_ids,"objective_ids":ids,"dependency_ids":[k for k in ids if k not in selected_ids],"blockers":blockers,"allowed":not blockers}


def project_targets(payload,ids):
    result=copy.deepcopy(payload);nodes={n["id"]:n for n in result["knowledge_nodes"]};keep=set(ids)
    for k in ids:
        parent=nodes[k].get("parent_id");seen=set()
        while parent:
            if parent in seen:raise DomainError("KNOWLEDGE_CYCLE")
            seen.add(parent);keep.add(parent);parent=nodes[parent].get("parent_id")
    result["knowledge_nodes"]=[n for n in result["knowledge_nodes"] if n["id"] in keep]
    for field in ("scope_claims","method_rules","historical_style","issues","clarifications"):
        items=[]
        for item in result.get(field,[]):
            targets=item.get("subject_ids",item.get("affected_ids",[]))
            if targets and not keep.intersection(targets):continue
            for key in ("subject_ids","affected_ids"):
                if key in item:item[key]=[k for k in item[key] if k in keep]
            items.append(item)
        result[field]=items
    method_ids={m["id"] for m in result.get("method_rules",[])}
    issue_ids={i["id"] for i in result.get("issues",[])}
    for n in result["knowledge_nodes"]:
        n["method_ids"]=[k for k in n.get("method_ids",[]) if k in method_ids]
    for q in result.get("clarifications",[]):q["resolves_issue_ids"]=[k for k in q.get("resolves_issue_ids",[]) if k in issue_ids]
    return aggregate_groups(result)

def aggregate_groups(payload):
    result=copy.deepcopy(payload);nodes={n["id"]:n for n in result["knowledge_nodes"]}
    for group in nodes.values():
        if group.get("node_kind")!="group":continue
        children=[]
        for node in nodes.values():
            if node.get("node_kind")=="group":continue
            parent=node.get("parent_id");seen=set()
            while parent and parent not in seen:
                if parent==group["id"]:children.append(node);break
                seen.add(parent);parent=nodes.get(parent,{}).get("parent_id")
        group["readiness"]="supported" if children and all(n["readiness"]=="supported" for n in children) else "partial" if any(n["readiness"] in ("supported","partial") for n in children) else "unsupported"
    return result


def save_review_selection(owner,course_id,topic_id,revision,ids,key):
    from django.db import transaction
    from django.shortcuts import get_object_or_404
    from .models import Course,CourseDraft,Topic
    from .topic_state import state_map,topic_slice
    from app.core.idempotency import intent
    with transaction.atomic():
        course=get_object_or_404(Course.objects.select_for_update(),pk=course_id,owner=owner)
        get_object_or_404(Topic,pk=topic_id,course=course)
        record=intent(owner,f"review-selection:{course.id}",key,{"topic_id":str(topic_id),"revision":revision,"knowledge_ids":ids})
        draft=get_object_or_404(CourseDraft.objects.select_for_update(),course=course)
        if record.response:return draft
        if draft.revision!=revision:raise DomainError("DRAFT_REVISION_CONFLICT")
        payload=topic_slice(draft,str(topic_id))
        if payload is None:raise DomainError("TOPIC_ANALYSIS_REQUIRED")
        eligible_targets(payload,ids)
        states=state_map(draft);states[str(topic_id)]["selected_knowledge_ids"]=ids
        draft.topic_state=states;draft.revision+=1;draft.save()
        record.response={"revision":draft.revision};record.save(update_fields=["response"])
        return draft
