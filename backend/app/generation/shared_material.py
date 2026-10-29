"""Mathematical capability: find material that parts of different questions share.

These are hints for the whole-paper review, never a verdict. Other subject capabilities may supply
their own hints (for example identical data tables); without hints the rule still applies to the
reported facts.
"""
import sympy as sp
from .expressions import expression
from .originality_policy import MAX_HINTS, pair_key


def _material(pair):
    """Non-trivial subexpressions per part, keyed by a canonical form."""
    found = {}
    for answer in pair["answers"]:
        for spec in answer.get("checks", []):
            for field in ("expression", "denominator"):
                node = spec.get(field)
                if not node:
                    continue
                try:
                    expr = expression(node)
                except (ValueError, TypeError):
                    continue
                variable = next(iter(expr.free_symbols), None)
                for sub in sp.preorder_traversal(expr):
                    if sub.is_Atom or sp.count_ops(sub) < 2:
                        continue
                    # Plain polynomials are everyday material and would flood the review with hints.
                    if variable is not None and sub.is_polynomial(variable):
                        continue
                    found.setdefault(answer["part_id"], {})[sp.srepr(sub)] = sub
    return found


def overlap_hints(pairs):
    owners = {}
    question = {}
    for pair in pairs:
        for part_id, items in _material(pair).items():
            question[part_id] = pair["question_id"]
            for key, sub in items.items():
                owners.setdefault(key, (sub, set()))[1].add(part_id)
    shared = {}
    for key, (sub, parts) in owners.items():
        parts = sorted(parts)
        for i, a in enumerate(parts):
            for b in parts[i + 1:]:
                if question[a] != question[b]:
                    shared.setdefault(pair_key(a, b), []).append(sub)
    ranked = sorted(shared.items(), key=lambda item: (-len(item[1]), item[0]))[:MAX_HINTS]
    return [{"parts": list(k), "shared_material": [sp.sstr(s) for s in
             sorted(subs, key=lambda s: -sp.count_ops(s))[:3]]} for k, subs in ranked]
