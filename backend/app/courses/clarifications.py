"""Only gaps affecting the selected chapter block its confirmation."""
def classify_gaps(payload, target_ids):
    selected = set(target_ids)
    questions = {q["id"]: dict(q) for q in payload["clarifications"]}
    issue_map = {i["id"]: i for i in payload["issues"]}
    for q in questions.values():
        linked = [issue_map[i] for i in q["resolves_issue_ids"] if i in issue_map]
        q["evidence_ids"] = sorted({e for issue in linked for e in issue["evidence_ids"]})
        q["action_kind"] = "clarification"
        if linked and all(i["code"].upper().startswith("MISSING_") for i in linked):
            q["action_kind"] = "review_existing_sources"
            q["question"] = "Review the existing source page images for missing mathematical notation."
            q["reason"] += " The PDFs are already saved locally. This is a transcription gap; no replacement upload is required."
    represented = {i for q in questions.values() for i in q["resolves_issue_ids"]}
    def add(key, question, reason, affected, blocking=True, issue_ids=None):
        questions[key] = {"id": key, "question": question, "reason": reason, "affected_ids": affected,
            "impact": "blocks_selected_scope" if blocking else "informational", "suggested_answers": [],
            "resolves_issue_ids": issue_ids or [], "status": "open", "evidence_ids": [], "action_kind": "clarification"}
    for issue in payload["issues"]:
        if issue["id"] in represented:
            continue
        matches = selected.intersection(issue["affected_ids"])
        add("gap-" + issue["id"], issue["suggested_action"] or "Review this source issue.", issue["explanation"],
            issue["affected_ids"], bool(matches and issue["severity"] == "blocking"), [issue["id"]])
        questions["gap-" + issue["id"]]["evidence_ids"] = issue["evidence_ids"]
        if issue["severity"] != "blocking":
            questions["gap-" + issue["id"]]["action_kind"] = "evidence_note"
    nodes = {n["id"]: n for n in payload["knowledge_nodes"]}
    for target in target_ids:
        node = nodes.get(target)
        if not node or node["readiness"] != "supported":
            if any(q["impact"] == "blocks_selected_scope" and target in q["affected_ids"] for q in questions.values()):
                continue
            add("gap-teaching-" + target, "Add readable teaching evidence or adjust the selected scope.",
                f"Teaching support for {node['title'] if node else target} is incomplete. A text answer cannot replace it.", [target])
    scope = [c for c in payload["scope_claims"] if c["applicability"] == "current_exam"
             and c["status"] in ("declared", "supported") and c["disposition"] == "include"]
    covered = {s for c in scope for s in c["subject_ids"]}
    if selected - covered:
        add("gap-exam-scope", "What is the exam scope?", "The selected topics need an explicit current scope statement.", sorted(selected - covered))
    for claim in payload["scope_claims"]:
        if (claim["applicability"] == "current_exam" and selected.intersection(claim["subject_ids"])
                and (claim["status"] == "disputed" or claim["disposition"] == "exclude")):
            add("gap-scope-" + claim["id"], "Resolve the current scope conflict or change the selection.", claim["text"], claim["subject_ids"])
    # A model cannot make an unrelated Topic 10 issue block Topic 2.
    for q in questions.values():
        if not selected.intersection(q["affected_ids"]):
            q["impact"] = "informational"
    return list(questions.values())
