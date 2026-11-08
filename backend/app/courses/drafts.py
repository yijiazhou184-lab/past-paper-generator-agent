import copy
from django.db import transaction
from django.shortcuts import get_object_or_404
from pydantic import ValidationError
from app.core.errors import DomainError
from app.core.idempotency import intent
from .models import Course, CourseDraft, UserStatement
from .schemas import CourseDraftPayload, validate_template
from .exam_template import exam_template_view, validate_exam_template
from .clarifications import classify_gaps
from .context import statement_list

EDITABLE = {"knowledge_nodes": {"title", "requirements", "depth", "node_kind"}, "scope_claims": {"text", "disposition"},
            "method_rules": {"text"}, "historical_style": {"text"}}


def get_field(payload, path):
    if len(path) == 1 and path[0] in ("title", "template_suggestion"):
        return payload, path[0]
    if len(path) == 2 and path[0] == "target_exam" and path[1] in ("label", "academic_year"):
        return payload["target_exam"], path[1]
    if len(path) == 3 and path[0] in EDITABLE and path[2] in EDITABLE[path[0]]:
        item = next((item for item in payload[path[0]] if item["id"] == path[1]), None)
        if item is not None:
            return item, path[2]
    raise DomainError("PATCH_PATH_INVALID", "This field is not editable or no longer exists.", status=400)


def apply_patch_value(payload, patch):
    parent, key = get_field(payload, patch["path"])
    parent[key] = copy.deepcopy(patch["value"])
    if patch["path"][0] in ("scope_claims", "method_rules", "historical_style") and patch.get("statement_id"):
        parent.update(provenance="user_statement", authority_status="unverified", status="declared",
                      statement_ids=[patch["statement_id"]])


def merge_manual(machine, previous):
    merged, warnings = copy.deepcopy(machine), []
    for patch in previous.manual_patches if previous else []:
        try:
            parent, key = get_field(merged, patch["path"])
            if parent.get(key,"objective") != patch.get("base_value") and parent.get(key,"objective") != patch["value"]:
                warnings.append({"path": patch["path"], "message": "New analysis differs from your saved edit. Your edit was kept.",
                                 "machine_value": copy.deepcopy(parent.get(key,"objective")), "manual_value": patch["value"]})
            apply_patch_value(merged, patch)
        except DomainError:
            # Retain an orphaned manually edited item, explicitly requiring review.
            path = patch["path"]
            if len(path) == 3 and path[0] in EDITABLE:
                old = next((i for i in previous.payload[path[0]] if i["id"] == path[1]), None)
                if old and not any(i["id"] == old["id"] for i in merged[path[0]]):
                    merged[path[0]].append(copy.deepcopy(old))
            warnings.append({"path": path, "message": "A manually edited item is absent from the new analysis. Review it before confirmation.",
                             "machine_value": None, "manual_value": patch["value"]})
    return merged, warnings


def draft_view(draft, topic_id=None):
    if draft is None:return None
    from .decisions import attach_answers,needs_analysis,reviewed_payload
    from .eligibility import objective_ids,eligible_targets
    from .topic_state import state_map
    original=draft;selected=None
    if topic_id is not None:
        from .topic_state import topic_slice,topic_base
        from .topic_confirmation import topic_status
        from .models import Topic
        topic=get_object_or_404(Topic,pk=topic_id,course=draft.course)
        payload=topic_slice(draft,str(topic_id))
        if payload is None:return None
        draft=copy.copy(draft);draft.payload=payload;draft.machine_base=copy.copy(topic_base(original,str(topic_id)))
        selected=state_map(original)[str(topic_id)].get("selected_knowledge_ids",objective_ids(payload))
        draft.machine_base.context={**draft.machine_base.context,"target_ids":selected}
        owned={i for ids in state_map(original)[str(topic_id)]["item_ids"].values() for i in ids}
        draft.manual_patches=[p for p in draft.manual_patches if len(p["path"])<3 or p["path"][1] in owned]
        draft.merge_warnings=[w for w in draft.merge_warnings if len(w["path"])<3 or w["path"][1] in owned]
    statements=statement_list(draft.course,[str(topic_id)] if topic_id else None)
    payload=reviewed_payload(draft.payload,statements)
    selected=selected if selected is not None else draft.machine_base.context["target_ids"]
    try:eligibility=eligible_targets(payload,selected)
    except DomainError as error:
        eligibility={"selected_ids":selected,"objective_ids":[],"dependency_ids":[],"allowed":False,
            "blockers":[{"code":error.payload["code"],"reason":"Review the selected learning objectives."}]}
    review_ids=eligibility["objective_ids"] or selected
    questions=classify_gaps(payload,review_ids)
    for q in questions:
        if topic_id:
            q["affected_topic_ids"]=[str(topic_id)]
            if q["id"]=="gap-exam-scope":q["id"]+=":"+str(topic_id)
        if q.get("kind")=="exam_scope":
            nodes=[n for n in payload["knowledge_nodes"] if n["id"] in q["affected_ids"] and n.get("node_kind","objective")!="group"]
            q["options"]=[{"id":n["id"],"text":n["title"]} for n in nodes]
            q["suggested_answers"]=[n["title"] for n in nodes];q["selection_mode"]="multiple"
    attach_answers(questions,draft,statements,[str(topic_id)] if topic_id else [])
    latest=draft.course.confirmed_versions.order_by("-number").first()
    used={s["id"] for s in draft.machine_base.context["statements"]}
    def relevant(s):
        affected=(s.get("decision") or {}).get("affected_ids",[])
        return not affected or bool(set(affected).intersection(review_ids))
    pending=any(needs_analysis(s,used) and relevant(s) for s in statements)
    blocks=[q for q in questions if q["impact"]=="blocks_selected_scope" or
        q["impact"]=="needs_confirmation" and q["status"]!="answered"]
    template, template_status = exam_template_view(original, latest)
    if topic_id is None:
        payload = {**payload, "exam_template": template}
    return {"id":str(draft.id),"revision":draft.revision,"payload":payload,
        "exam_template_status": template_status,
        "exam_template_suggestion": payload["template_suggestion"] if topic_id is None and not state_map(original) else None,
        "topic_id":str(topic_id) if topic_id else None,"topic_name":topic.name if topic_id else None,
        "topic_status":topic_status(original,str(topic_id),latest) if topic_id else None,
        "manual_patches":draft.manual_patches,"merge_warnings":draft.merge_warnings,
        "clarifications":questions,"mode":draft.machine_base.mode,
        "analysis_task_id":str(draft.machine_base.task_id),"updated_at":draft.updated_at,
        "target_ids":review_ids,"selected_knowledge_ids":selected,"eligibility":eligibility,
        "evidence":[{k:e[k] for k in ("id","material_version_id","physical_page","material_code")} for e in draft.machine_base.context["evidence"]],
        "statements":statements,"confirmed_revision":latest.draft_revision if latest else None,
        "answers_need_analysis":pending,"latest_version_id":str(latest.id) if latest else None,
        "change_summary":"User edits are preserved separately from the machine analysis.",
        "blocking_count":len(blocks)+len(draft.merge_warnings)+int(pending)+int(not eligibility["objective_ids"])}


@transaction.atomic
def save_draft(owner, course_id, expected_revision, patches, key, acknowledge_merge=False, topic_id=None):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    record = intent(owner, f"draft:{course.id}", key, {"revision": expected_revision, "patches": patches, "ack": acknowledge_merge, "topic_id":topic_id})
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), course=course)
    if record.response:
        # Return current server state; the committed revision is separately recorded for lost-response recovery.
        return draft, record.response["revision"]
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT", "A newer draft is saved. Compare it with your edits before continuing.")
    if not isinstance(patches, list) or len(patches) > 100:
        raise DomainError("PATCH_INVALID", status=400)
    from .topic_state import state_map, topic_slice, patch_topics
    states=state_map(draft)
    if topic_id is not None and str(topic_id) not in states:
        raise DomainError("TOPIC_ANALYSIS_REQUIRED")
    payload = copy.deepcopy(draft.payload)
    manual = {tuple(p["path"]): p for p in draft.manual_patches}
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {"path", "value"} or not isinstance(patch["path"], list):
            raise DomainError("PATCH_INVALID", status=400)
        path = patch["path"]
        if not all(isinstance(p, str) for p in path):
            raise DomainError("PATCH_INVALID", status=400)
        if path == ["exam_template"] and topic_id is None:
            value = None if patch["value"] is None else validate_exam_template(patch["value"], course)
            previous = draft.exam_template["value"] if draft.exam_template else None
            if value != previous:
                draft.exam_template = {"value": value, "revision": draft.revision + 1} if value is not None else None
            continue
        if topic_id is not None and (len(path)<3 or str(topic_id) not in patch_topics(draft,path)):
            if path!=["template_suggestion"]:
                raise DomainError("PATCH_OUTSIDE_TOPIC","Edit course-wide facts from Course overview.",status=400)
        if topic_id and path==["template_suggestion"]:
            states[str(topic_id)]["template_suggestion"]=copy.deepcopy(patch["value"])
            validate_template(patch["value"])
            continue
        parent, field = get_field(payload, path)
        entry = {**patch, "base_value": manual.get(tuple(path), {}).get("base_value", copy.deepcopy(parent.get(field,"objective")))}
        if path[0] in ("scope_claims", "method_rules", "historical_style"):
            statement = UserStatement.objects.create(course=course, text=str(patch["value"]), kind="manual_edit",
                source="Direct course profile edit", topic_ids=patch_topics(draft,path), submitted_by=owner)
            entry["statement_id"] = str(statement.id)
        apply_patch_value(payload, entry)
        manual[tuple(path)] = entry
    try:
        if states:
            projected=copy.copy(draft);projected.payload=payload;projected.topic_state=states
            for tid in states:
                CourseDraftPayload.model_validate(topic_slice(projected,tid))
        else:
            payload = CourseDraftPayload.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        raise DomainError("DRAFT_FIELD_INVALID", "Check the edited field values.", status=400)
    validate_template(payload["template_suggestion"])
    draft.payload = payload
    draft.topic_state = states
    draft.manual_patches = list(manual.values())
    draft.revision += 1
    if acknowledge_merge:
        if topic_id:
            draft.merge_warnings=[w for w in draft.merge_warnings if len(w["path"])==3 and str(topic_id) not in patch_topics(draft,w["path"])]
        else:
            draft.merge_warnings = []
    draft.save()
    record.response = {"revision": draft.revision}
    record.save(update_fields=["response"])
    return draft, draft.revision


@transaction.atomic
def answer_clarification(owner, course_id, question_id, text, expected_revision, key, topic_id=None, *, option_ids=None, definition_hash=None, note=""):
    course = get_object_or_404(Course.objects.select_for_update(), pk=course_id, owner=owner)
    record = intent(owner, f"answer:{course.id}", key, {"id":question_id,"text":text,"revision":expected_revision,"topic_id":topic_id,"option_ids":option_ids,"definition_hash":definition_hash,"note":note})
    draft = get_object_or_404(CourseDraft.objects.select_for_update(), course=course)
    if record.response:
        return draft
    if draft.revision != expected_revision:
        raise DomainError("DRAFT_REVISION_CONFLICT")
    view=draft_view(draft,topic_id)
    if view is None:raise DomainError("TOPIC_ANALYSIS_REQUIRED")
    questions = view["clarifications"]
    asked = next((q for q in questions if q["id"] == question_id), None)
    if asked is None:
        raise DomainError("CLARIFICATION_NOT_FOUND", status=404)
    from .decisions import normal
    options={o["id"]:o["text"] for o in asked.get("options",[])}
    structured=option_ids is not None
    if structured:
        if definition_hash!=asked["definition_hash"]:raise DomainError("DECISION_DEFINITION_CHANGED","Review the current question and choices.")
        if len(option_ids)!=len(set(option_ids)) or not option_ids or not set(option_ids)<=set(options):
            raise DomainError("ANSWER_OPTION_INVALID",status=400)
        if asked.get("selection_mode","single")=="single" and len(option_ids)!=1:raise DomainError("ANSWER_OPTION_INVALID",status=400)
        text="; ".join(options[i] for i in option_ids)
        if note.strip():text+="\n"+note.strip()
    elif options and text in options.values():
        option_ids=[i for i,v in options.items() if v==text];structured=True
    elif asked["action_kind"]!="clarification" or not asked.get("allows_free_text"):
        raise DomainError("ANSWER_ACTION_REQUIRED","Use the source review or scope action for this issue.",status=400)
    if not isinstance(text,str) or not 1<=len(text.strip())<=3000:raise DomainError("ANSWER_INVALID",status=400)
    kind=asked.get("kind","review_required")
    selected_actions={o.get("action","practice_preference") for o in asked.get("options",[]) if o["id"] in (option_ids or [])}
    action="needs_interpretation" if "needs_interpretation" in selected_actions else "adjust_scope" if "adjust_scope" in selected_actions else "practice_preference"
    requires_analysis=not structured or bool(note.strip()) or kind not in ("preference","source_conflict","exam_scope") or action=="needs_interpretation"
    prior=statement_list(course,[str(topic_id)] if topic_id else None)
    scope=[str(topic_id)] if topic_id else []
    supersedes=[s["id"] for s in prior if set(s.get("topic_ids",[]))==set(scope) and
        ((s.get("decision") or {}).get("key")==asked["decision_key"] or s.get("question") and normal(s["question"])==normal(asked["question"]))]
    metadata={"key":asked["decision_key"],"meaning_key":asked["meaning_key"],"definition_hash":asked["definition_hash"],"kind":kind,
        "option_ids":option_ids or [],"action":action,"question_version":asked["definition_hash"],"scope_ids":scope,
        "affected_ids":asked["affected_ids"],"evidence_ids":asked.get("evidence_ids",[]),"resolves_issue_ids":asked.get("resolves_issue_ids",[]),"requires_analysis":requires_analysis,"supersedes":supersedes}
    if kind=="exam_scope" and structured:metadata["knowledge_ids"]=option_ids
    statement=UserStatement.objects.create(course=course,text=text.strip(),kind="exam_scope" if kind=="exam_scope" else "clarification",
        source="Answer to course clarification",clarification_id=question_id,question=asked["question"],topic_ids=scope,
        submitted_by=owner,decision=metadata)
    draft.clarification_answers[question_id]={"text":text.strip(),"statement_id":str(statement.id),
        "option_ids":option_ids or [],"reanalysis_required":requires_analysis}
    draft.revision += 1
    draft.save()
    record.response = {"revision": draft.revision, "statement_id": str(statement.id)}
    record.save(update_fields=["response"])
    return draft
