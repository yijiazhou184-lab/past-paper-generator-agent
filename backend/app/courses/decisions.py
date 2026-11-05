"""Stable user decisions and effective statements; raw records remain intact."""
import copy
import re
from app.core.idempotency import digest


def normal(text):return re.sub(r"\s+"," ",text.strip()).casefold()


def decision_identity(question,scope):
    meaning=question.get("decision_key") or normal(question["question"])
    key=digest({"meaning":meaning,"scope":sorted(scope),"affected":sorted(question.get("affected_ids",[]))})
    definition=digest({"kind":question.get("kind","preference"),"options":sorted(question.get("suggested_answers",[])),
        "mode":question.get("selection_mode","single"),"actions":question.get("option_actions",[]),"affected":sorted(question.get("affected_ids",[])),"scope":sorted(scope)})
    return key,definition


def effective_statements(course,topic_ids=None):
    rows=list(course.statements.order_by("created_at","id").values(
        "id","text","kind","source","clarification_id","question","topic_ids","decision"))
    if topic_ids is not None:rows=[r for r in rows if not r["topic_ids"] or set(r["topic_ids"]).intersection(topic_ids)]
    byid={str(r["id"]):r for r in rows};hidden=set();latest={}
    for row in rows:
        row["id"]=str(row["id"]);meta=row.get("decision") or {}
        for old in meta.get("supersedes",[]):
            if str(old) in byid and set(byid[str(old)]["topic_ids"])==set(row["topic_ids"]):hidden.add(str(old))
        identity=meta.get("key") or ("legacy:"+normal(row["question"]) if row["kind"]=="clarification" and row["question"] else None)
        if identity:
            scoped=(identity,tuple(sorted(row["topic_ids"])))
            if scoped in latest:hidden.add(latest[scoped])
            latest[scoped]=row["id"]
    return [r for r in rows if r["id"] not in hidden]


def needs_analysis(statement,used_ids):
    return statement["kind"] in ("exam_scope","clarification") and statement["id"] not in used_ids and (statement.get("decision") or {}).get("requires_analysis",True)


def attach_answers(questions,draft,statements,scope):
    used={s["id"] for s in draft.machine_base.context["statements"]}
    for q in questions:
        key,definition=decision_identity(q,scope);q.update(meaning_key=q.get("decision_key") or normal(q["question"]),decision_key=key,definition_hash=definition)
        choices=[s for s in statements if (s.get("decision") or {}).get("key")==key]
        match=next((s for s in reversed(choices) if s["decision"].get("definition_hash")==definition),None)
        legacy=draft.clarification_answers.get(q["id"])
        if legacy is None:
            prior=next((s for s in reversed(statements) if not s.get("decision") and s.get("question") and normal(s["question"])==normal(q["question"])),None)
            if prior:legacy={"text":prior["text"],"statement_id":prior["id"],"reanalysis_required":prior["id"] not in used}
        if match:
            meta=match["decision"];pending=needs_analysis(match,used)
            q["answer"]={"text":match["text"],"statement_id":match["id"],"option_ids":meta.get("option_ids",[]),
                "reanalysis_required":pending,"application_status":"needs_analysis" if pending else "needs_scope_review" if meta.get("action")=="adjust_scope" else "applied"}
            q["status"]="answered"
        elif choices:
            q["status"]="open";q["decision_status"]="needs_review"
        elif legacy:
            pending=bool(legacy.get("reanalysis_required") and legacy.get("statement_id") not in used)
            q["status"]="answered";q["answer"]={**legacy,"reanalysis_required":pending,"application_status":"needs_analysis" if pending else "applied"}
        else:
            if q.get("impact")=="needs_confirmation":q["status"]="open"
            q["decision_status"]="unanswered"
    return questions


def reviewed_payload(payload,statements):
    result=copy.deepcopy(payload)
    from .clarifications import classify_gaps
    for statement in statements:
        meta=statement.get("decision") or {}
        if meta.get("requires_analysis",True):continue
        affected=meta.get("affected_ids",[])
        current=classify_gaps(payload,affected)
        for question in current:
            if question.get("kind")=="exam_scope":
                nodes=[n for n in payload["knowledge_nodes"] if n["id"] in question["affected_ids"] and n.get("node_kind","objective")!="group"]
                question["suggested_answers"]=[n["title"] for n in nodes]
                question["selection_mode"]="multiple"
        matching=next((q for q in current if decision_identity(q,meta.get("scope_ids",[]))==(meta.get("key"),meta.get("definition_hash"))),None)
        if matching is None:continue
        if meta.get("kind")=="exam_scope":
            ids=meta.get("knowledge_ids",[])
            if ids:
                result["scope_claims"].append({"id":"user-scope-"+statement["id"],"text":statement["text"],"subject_ids":ids,
                    "applicability":"current_exam","provenance":"user_statement","authority_status":"unverified",
                    "evidence_ids":[],"statement_ids":[statement["id"]],"status":"declared","disposition":"include"})
        elif meta.get("kind")=="source_conflict" and meta.get("action")=="practice_preference":
            # Adopt a practice convention without declaring either source officially correct.
            resolved=set(matching.get("resolves_issue_ids",[]))
            for issue in result["issues"]:
                if issue["id"] in resolved and issue.get("kind")=="source_conflict":
                    issue["severity"]="warning"
                    issue["explanation"]+=" Practice decision saved: "+statement["text"]+". The original uncertainty is retained."
            for question in result["clarifications"]:
                if question["id"]==matching["id"]:question["impact"]="needs_confirmation"
    from .eligibility import aggregate_groups
    return aggregate_groups(result)


def statement_fingerprint(statements,objective_ids=None):
    ids=set(objective_ids or [])
    relevant=[s for s in statements if s["kind"] in ("exam_scope","clarification") and
        (not objective_ids or not (s.get("decision") or {}).get("affected_ids") or ids.intersection(s["decision"]["affected_ids"]))]
    normalized=[{k:s.get(k,[] if k=="topic_ids" else {} if k=="decision" else "") for k in
        ("id","text","kind","source","clarification_id","question","topic_ids","decision")} for s in relevant]
    return digest(sorted(normalized,key=lambda row:row["id"]))


def prior_decisions(payload):
    fields=("id","kind","decision_key","question","affected_ids","suggested_answers","option_actions","selection_mode")
    return [{k:copy.deepcopy(q[k]) for k in fields if k in q} for q in (payload or {}).get("clarifications",[])]
