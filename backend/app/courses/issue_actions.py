"""Program-owned routing from course problems to available user actions."""
from app.core.idempotency import digest


def decorate_action(q):
    q=dict(q)
    kind=q.get("kind","review_required")
    options=q.get("suggested_answers",[])
    action=q.get("action_kind","clarification")
    if action=="evidence_note":
        kind="information"
    elif action=="review_existing_sources":
        kind="processing_gap"
    elif action=="clarification" and (kind=="review_required" or not options and kind not in ("exam_scope","course_fact")):
        action="review_required"
    q.update(kind=kind,action_kind=action,
        allows_free_text=action=="clarification" and kind in ("exam_scope","course_fact"),
        selection_mode=q.get("selection_mode","single"),
        options=[{"id":digest({"text":text})[:24],"text":text,"action":q.get("option_actions",[])[i] if len(q.get("option_actions",[]))==len(options) else "needs_interpretation" if kind=="source_conflict" else "practice_preference"} for i,text in enumerate(options)])
    q["actions"]=[]
    if q.get("evidence_ids"):q["actions"].append({"kind":"view_source","evidence_ids":q["evidence_ids"]})
    if action=="review_existing_sources":q["actions"]+=[{"kind":"review_sources"},{"kind":"adjust_scope"}]
    if action=="review_required":q["actions"].append({"kind":"review_sources"})
    return q
