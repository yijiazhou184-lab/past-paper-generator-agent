
"""Bounded source comparisons: report small facts, apply the same rule in code."""
from collections import Counter
from .checks import check
from .duplicates import block_text, terms
from .originality_policy import POLICY


def build_source_targets(pairs, comparison):
    """Choose up to two distinct supplied pages per part, reusing retrieved excerpts."""
    targets = []
    for pair in pairs:
        candidates = [c for c in comparison.get("candidates", []) if pair["question_id"] in c["target_ids"]]
        for part in pair["parts"]:
            query = terms(block_text(pair["stem"]) + " " + block_text(part["prompt"]))
            ranked = {}
            for candidate in candidates:
                words = terms(candidate["text"])
                score = len(query & words) / max(1, len(query | words))
                sid = candidate["source_id"]
                ranked[sid] = max(ranked.get(sid, 0), score)
            selected = sorted(ranked, key=lambda sid: (-ranked[sid], sid))[:POLICY["max_source_pages_per_part"]]
            targets.append({"subpart_id": part["part_id"], "source_ids": selected})
    return targets


def source_originality_checks(pairs, overlaps, targets, source_ids, *, reviewed):
    """A false fact can decide acceptance; absent/unknown facts cannot become false."""
    part_question = {p["part_id"]: q["question_id"] for q in pairs for p in q["parts"]}
    expected = {t["subpart_id"]: set(t["source_ids"]) for t in targets}
    supplied = set(source_ids)
    valid = [o for o in overlaps if o.get("subpart_id") in part_question and o.get("source_id") in supplied]
    counts = Counter((o["subpart_id"], o["source_id"]) for o in valid)
    facts = {(o["subpart_id"], o["source_id"]): o for o in valid}
    checks = []
    for pair in pairs:
        qid = pair["question_id"]
        parts = {p["part_id"] for p in pair["parts"]}
        required = {(pid, sid) for pid in parts for sid in expected.get(pid, ())}
        own = {key: value for key, value in facts.items() if key[0] in parts}
        duplicates = []
        unresolved = []
        for key, value in sorted(own.items()):
            if counts[key] != 1:
                unresolved.append(key)
            elif value["same_stimulus"] is True and value["same_conclusion"] is True:
                duplicates.append(key)
            elif value["same_stimulus"] is not False and value["same_conclusion"] is not False:
                unresolved.append(key)
        missing = sorted(required - own.keys())
        uncovered = sorted(pid for pid in parts if not expected.get(pid))
        evidence = sorted({sid for _, sid in own})
        if not reviewed:
            result, reason = "not_checked", "Source comparison did not return complete facts."
        elif duplicates:
            result = "fail"
            details = []
            for pid, sid in duplicates:
                note = own[(pid, sid)].get("note")
                details.append(f"{pid} / {sid}" + (f": {note}" if note else ""))
            reason = ("Same given material and same required conclusion: " + "; ".join(details) +
                      ". Change the given material or required conclusion while preserving the knowledge targets; "
                      "a shared standard method alone does not require changing.")
        elif missing or unresolved or uncovered:
            result = "inconclusive"
            reason = (f"Source comparison coverage is incomplete: {len(missing)} missing pair(s), "
                      f"{len(unresolved)} undecided or repeated pair(s), {len(uncovered)} part(s) without a comparison source.")
        else:
            result, reason = "pass", (
                f"{len(own)} supplied source comparisons checked; none has both the same given material and "
                "the same required conclusion. Coverage is bounded to the supplied excerpts, not exhaustive.")
        item = check(f"semantic:{qid}:originality", [qid], "source_originality_rule", result, reason, evidence)
        item["duplicate_sources"] = [{"subpart_id": pid, "source_id": sid} for pid, sid in duplicates] if reviewed else []
        checks.append(item)
    return checks
