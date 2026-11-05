"""Only gaps affecting the selected chapter block its confirmation."""
def classify_gaps(payload, target_ids):
    from .issue_actions import decorate_action
    selected = set(target_ids)
    nodes={n["id"]:n for n in payload["knowledge_nodes"]}
    def expand(ids):
        result=set(ids)
        for node in nodes.values():
            parent=node.get("parent_id");seen=set()
            while parent and parent not in seen:
                if parent in ids:result.add(node["id"]);break
                seen.add(parent);parent=nodes.get(parent,{}).get("parent_id")
        return result
    def local_example_only(issue):
        if issue.get("coverage_role")!="supporting_example" or issue.get("kind") not in ("processing_gap","source_gap"):return False
        affected=[nodes[k] for k in expand(issue["affected_ids"]) if k in nodes and nodes[k].get("node_kind","objective")!="group"]
        missing=set(issue["evidence_ids"])
        return bool(missing and affected) and all(n["readiness"]=="supported" and set(n["evidence_ids"])-missing for n in affected)
    questions = {q["id"]: dict(q) for q in payload["clarifications"]}
    issue_map = {i["id"]: i for i in payload["issues"]}
    for q in questions.values():
        linked = [issue_map[i] for i in q["resolves_issue_ids"] if i in issue_map]
        q["evidence_ids"] = sorted({e for issue in linked for e in issue["evidence_ids"]})
        q["affected_ids"]=sorted(expand(q["affected_ids"]))
        q["action_kind"] = "clarification"
        if linked and all(i.get("kind") in ("processing_gap","source_gap") or i["code"].upper() in ("MISSING_FORMULA","MISSING_TABLE","MISSING_FIGURE","MISSING_VISUAL_TRANSCRIPTION") for i in linked):
            q["action_kind"] = "review_existing_sources"
            q["question"] = "Review the existing source content."
            q["reason"] += " Check the cited location and its processing result before using the affected content."
        if linked and all(local_example_only(i) for i in linked):
            q.update(impact="informational",action_kind="evidence_note")
    represented = {i for q in questions.values() for i in q["resolves_issue_ids"]}
    def add(key, question, reason, affected, blocking=True, issue_ids=None):
        questions[key] = {"id": key, "question": question, "reason": reason, "affected_ids": affected,
            "impact": "blocks_selected_scope" if blocking else "informational", "suggested_answers": [],
            "resolves_issue_ids": issue_ids or [], "status": "open", "evidence_ids": [], "action_kind": "clarification"}
    for issue in payload["issues"]:
        if issue["id"] in represented:
            continue
        matches = selected.intersection(expand(issue["affected_ids"]))
        add("gap-" + issue["id"], issue["suggested_action"] or "Review this source issue.", issue["explanation"],
            sorted(expand(issue["affected_ids"])), bool(matches and issue["severity"] == "blocking" and not local_example_only(issue)), [issue["id"]])
        questions["gap-" + issue["id"]]["evidence_ids"] = issue["evidence_ids"]
        if issue.get("kind") in ("processing_gap","source_gap"):
            questions["gap-"+issue["id"]]["action_kind"]="review_existing_sources"
        if issue["severity"] != "blocking" or local_example_only(issue):
            questions["gap-" + issue["id"]]["action_kind"] = "evidence_note"
    nodes = {n["id"]: n for n in payload["knowledge_nodes"]}
    for target in nodes:
        node = nodes.get(target)
        if node and node.get("node_kind")=="group":continue
        if not node or node["readiness"] != "supported":
            if any(q["impact"] == "blocks_selected_scope" and target in q["affected_ids"] for q in questions.values()):
                continue
            add("gap-teaching-" + target, f"{node['title'] if node else target} — source review needed",
                f"Teaching support for {node['title'] if node else target} is incomplete. A text answer cannot replace it.", [target])
            questions["gap-teaching-"+target].update(action_kind="review_existing_sources",evidence_ids=node.get("evidence_ids",[]) if node else [])
    scope = [c for c in payload["scope_claims"] if c["applicability"] == "current_exam"
             and c["status"] in ("declared", "supported") and c["disposition"] == "include"]
    covered = {s for c in scope for s in expand(c["subject_ids"])}
    if selected - covered:
        add("gap-exam-scope", "What is the exam scope?", "The selected topics need an explicit current scope statement.", sorted(selected - covered))
        questions["gap-exam-scope"]["kind"]="exam_scope"
    for claim in payload["scope_claims"]:
        if (claim["applicability"] == "current_exam" and selected.intersection(expand(claim["subject_ids"]))
                and (claim["status"] == "disputed" or claim["disposition"] == "exclude")):
            add("gap-scope-" + claim["id"], "Resolve the current scope conflict or change the selection.", claim["text"], sorted(expand(claim["subject_ids"])))
    # A model cannot make an unrelated Topic 10 issue block Topic 2.
    for q in questions.values():
        if not selected.intersection(q["affected_ids"]):
            q["impact"] = "informational"
            q["action_kind"] = "evidence_note"
    return [decorate_action(q) for q in questions.values()]
