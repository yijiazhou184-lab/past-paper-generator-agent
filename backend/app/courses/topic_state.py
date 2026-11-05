"""Topic-local views and merge ownership beside the unchanged legacy payload schema."""
import copy
from types import SimpleNamespace
from app.core.errors import DomainError
from .models import CourseMachineBase, LegacyTopicMapping
COLLECTIONS=("knowledge_nodes","scope_claims","method_rules","historical_style","issues","clarifications")


def state_map(draft):
    if draft is None:return {}
    result=copy.deepcopy(draft.topic_state)
    if result:return result
    # The only legacy inference allowed is an explicitly reviewed ID mapping.
    latest=draft.course.confirmed_versions.order_by("-number").first()
    if not latest:return {}
    for mapping in LegacyTopicMapping.objects.filter(course_version=latest).select_related("topic"):
        ids=set(mapping.knowledge_ids)
        item_ids={}
        for key in COLLECTIONS:
            item_ids[key]=[i["id"] for i in draft.payload[key] if
                (i["id"] in ids if key=="knowledge_nodes" else bool(ids.intersection(i.get("subject_ids",i.get("affected_ids",[])))))]
        result[str(mapping.topic_id)]={"item_ids":item_ids,"knowledge_ids":list(mapping.knowledge_ids),
            "machine_base_id":str(draft.machine_base_id),"template_suggestion":copy.deepcopy(draft.payload["template_suggestion"]),
            "name":mapping.topic_name,"code":mapping.topic_code,"revision":draft.revision}
    return result


def topic_slice(draft, topic_id):
    state=state_map(draft).get(str(topic_id))
    if not state:return None
    payload=copy.deepcopy(draft.payload)
    for key in COLLECTIONS:
        payload[key]=[i for i in payload[key] if i["id"] in state["item_ids"].get(key,[])]
    payload["template_suggestion"]=copy.deepcopy(state["template_suggestion"])
    return payload


def topic_base(draft,topic_id):
    state=state_map(draft).get(str(topic_id))
    return CourseMachineBase.objects.get(pk=state["machine_base_id"],course=draft.course) if state else None


def patch_topics(draft,path):
    if len(path)<3:return list(state_map(draft))
    return [tid for tid,state in state_map(draft).items() if path[1] in state["item_ids"].get(path[0],[])]


def scoped_merge(payload, previous, context, base):
    from .drafts import merge_manual
    selected=context["target_topic_ids"]
    if len(selected)!=1:raise DomainError("ANALYSIS_TOPIC_SCOPE_INVALID")
    tid=selected[0];states=state_map(previous)
    target=next(t for t in context["target_topics"] if t["id"]==tid)
    owned=states.get(tid,{}).get("item_ids",{})
    foreign={i for other,state in states.items() if other!=tid for ids in state["item_ids"].values() for i in ids}
    for key in COLLECTIONS:
        for item in payload[key]:
            if item["id"] in foreign or foreign.intersection(item.get("subject_ids",item.get("affected_ids",[]))):
                raise DomainError("ANALYSIS_TOPIC_SCOPE_INVALID","Analysis attempted to modify another topic. No draft was replaced.")
    relevant=[p for p in previous.manual_patches if len(p["path"])==3 and p["path"][1] in owned.get(p["path"][0],[])] if previous else []
    old_view=SimpleNamespace(manual_patches=relevant,payload=topic_slice(previous,tid) or payload) if previous else None
    scoped,warnings=merge_manual(payload,old_view)
    combined=copy.deepcopy(previous.payload if previous else scoped)
    if previous:
        for key in COLLECTIONS:
            combined[key]=[i for i in combined[key] if i["id"] not in owned.get(key,[])]+scoped[key]
    states[tid]={"item_ids":{key:[i["id"] for i in scoped[key]] for key in COLLECTIONS},
        "knowledge_ids":[n["id"] for n in scoped["knowledge_nodes"]],"machine_base_id":str(base.id),
        "template_suggestion":copy.deepcopy(scoped["template_suggestion"]),"name":target["name"],
        "code":target.get("code",""),"revision":previous.revision+1 if previous else 1}
    prior_warnings=[w for w in previous.merge_warnings if len(w["path"])<3 or w["path"][1] not in owned.get(w["path"][0],[])] if previous else []
    if previous and "selected_knowledge_ids" in state_map(previous).get(tid,{}):
        states[tid]["selected_knowledge_ids"]=state_map(previous)[tid]["selected_knowledge_ids"]
    return combined,prior_warnings+warnings,states
