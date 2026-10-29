"""Intra-paper repetition rule. User decision, 2026-10-29.

用户决定（原文）：同一份卷子里的两道题，满足下面任意一条就可以接受：题目相同，考点不同；考点相同，题目不同。
只有题目和考点都相同时，才算题间重复，例如同一个函数被问同一个结论，或只换了数字、记号，解题路径完全相同。
"题目"指题干给出的具体函数、数据或情境；"考点"按最终要得出的结论判断。只要两题最终要得出的结论不同，就算考点不同，
即使中间用到相同的关键步骤。共用知识点、方法、证明技巧、具体函数或中间关键步骤，都不能单独作为失败理由。
与课程原题、历年卷比较时保持原规则；本规则只用于同一份卷子内部的题间比较。

The review model reports facts only; this module applies the rule. Nothing here depends on a course or subject.
"""

POLICY = {
    "version": "originality-policy-v1",
    "scope": "Comparisons between parts of different questions in the same candidate paper only. Comparisons with course and historical material keep the earlier rule.",
    "stimulus": "The specific material the question text gives the candidate to work with, such as a function, data or a scenario.",
    "conclusion": "The final result a part requires the candidate to reach. Intermediate steps, shared methods or shared techniques are not the conclusion.",
    "rule": "Two parts are an intra-paper duplicate only when they have the same stimulus AND the same final conclusion. Same stimulus with different conclusions, or the same conclusion with different stimuli, is acceptable.",
    "not_grounds": "Shared knowledge, methods, proof techniques, specific functions or key intermediate steps are never on their own a reason for failure.",
    "check_id": "paper:intra_duplicates",
}

# Program hints of shared material are capped; every hint must receive a fact record.
MAX_HINTS = 20


def is_duplicate(overlap):
    return bool(overlap["same_stimulus"]) and bool(overlap["same_conclusion"])


def pair_key(a, b):
    return tuple(sorted((a, b)))


def judge(overlaps, hints, part_question, *, reviewed):
    """Apply the rule to reported facts. Returns (result, rationale, duplicate_pairs).

    reviewed=False means the review that owns the whole-paper comparison did not complete.
    hints are program-detected pairs of parts that share material; an unreported hint is not a pass.
    """
    if not reviewed:
        return "not_checked", "The whole-paper review did not return complete overlap facts.", []
    reported, invalid = {}, []
    for o in overlaps:
        a, b = o["part_a"], o["part_b"]
        if a == b or a not in part_question or b not in part_question or part_question[a] == part_question[b]:
            invalid.append(f"{a}/{b}")
            continue
        reported[pair_key(a, b)] = o
    duplicates = [k for k, o in sorted(reported.items()) if is_duplicate(o)]
    if duplicates:
        listed = "; ".join(f"{a} and {b}" for a, b in duplicates)
        return "fail", f"Same stimulus and same final conclusion: {listed}.", [list(k) for k in duplicates]
    missing = [k for k in sorted({pair_key(*h["parts"]) for h in hints}) if k not in reported]
    if missing:
        listed = "; ".join(f"{a} and {b}" for a, b in missing)
        return "inconclusive", f"Shared material was detected but no facts were reported for: {listed}.", []
    note = f" Ignored invalid pairs: {', '.join(invalid)}." if invalid else ""
    accepted = sum(1 for o in reported.values() if o["same_stimulus"] or o["same_conclusion"])
    return "pass", (f"{len(reported)} related part pairs reported; none has both the same stimulus and the same final "
                    f"conclusion ({accepted} share one of the two, which the rule accepts).{note}"), []
