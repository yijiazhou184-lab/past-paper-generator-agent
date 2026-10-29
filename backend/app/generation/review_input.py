"""Deterministic model-facing projection; never edits the frozen candidate or evidence."""
import copy
from .source_policy import source_review_input
from .duplicates import source_text
from .review_policy import REQUIRED_CATEGORIES, OPTIONAL_CATEGORIES


def compact_expression(node):
    """Preserve operations and domain holes: no symbolic simplification or model rewrite."""
    def visit(item, depth):
        if depth > 12 or not isinstance(item, dict) or set(item) != {"op", "value", "args"}:
            raise ValueError("Invalid mathematical expression")
        name, value, args = item["op"], item["value"], item["args"]
        if not isinstance(args, list):
            raise ValueError("Invalid arguments")
        if name in ("number", "variable") and not args:
            from .expressions import number, VARIABLES
            if name == "number":
                number(value)
                return "(" + value + ")" if "/" in value or value.startswith("-") else value
            if value not in VARIABLES:
                raise ValueError("Invalid variable")
            return value
        if value is not None:
            raise ValueError("Invalid operator value")
        if name in ("add", "mul") and 2 <= len(args) <= 4:
            symbol = " + " if name == "add" else " * "
            return "(" + symbol.join(visit(a, depth + 1) for a in args) + ")"
        if name in ("sub", "div", "pow") and len(args) == 2:
            symbol = {"sub": " - ", "div": " / ", "pow": " ^ "}[name]
            return "(" + symbol.join(visit(a, depth + 1) for a in args) + ")"
        if name in ("sin", "cos", "exp", "log", "sqrt", "abs") and len(args) == 1:
            return name + "(" + visit(args[0], depth + 1) + ")"
        raise ValueError("Unsupported operator or arity")
    return visit(node, 0)


def compact_pair(pair, *, include_checks=True):
    result = copy.deepcopy(pair)
    for answer in result["answers"]:
        if not include_checks:
            answer.pop("checks", None)
            continue
        for spec in answer["checks"]:
            for field in ("expression", "expected", "denominator"):
                if spec.get(field) is not None:
                    try:
                        spec[field] = compact_expression(spec[field])
                    except ValueError:
                        # Keep the exact unsupported specification for diagnosis/repair.
                        # Never simplify it, silently drop it, or turn a local failure into pass.
                        spec.setdefault("projection_warnings", []).append(
                            field + ": retained original AST; compact representation is unsupported.")
    return result


def _evidence(context, source_review, comparison):
    sources = {s["id"]: s for s in context["input"]["sources"]}
    intervals = {}
    for e in source_review["academic_excerpts"]:
        intervals.setdefault(e["id"], []).append((0, len(e["text"]), "academic"))
    for e in comparison["candidates"]:
        start = e["chunk_index"] * 3500
        original = source_text(sources[e["source_id"]])
        raw = original[start:start+4000]
        start += len(raw) - len(raw.lstrip())
        intervals.setdefault(e["source_id"], []).append((start, start + len(e["text"]), "comparison"))
    result = []
    for eid, spans in sorted(intervals.items()):
        source = sources[eid]
        original = source_text(source)
        merged = []
        for start, end, purpose in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
                merged[-1][2].add(purpose)
            else:
                merged.append([start, end, {purpose}])
        result.append({
            **{k: source[k] for k in ("id", "material_code", "material_version_id", "physical_page",
                                     "content_hash", "fidelity_status") if k in source},
            "fragments": [{"start": a, "end": b, "purposes": sorted(purposes), "text": original[a:b]}
                          for a, b, purposes in merged],
            "full_text_chars": len(original),
        })
    return result


def build_review_input(context, payload, local, blind, duplicates, question_ids, mode="required"):
    ids = set(question_ids)
    pairs = [p for p in payload["pairs"] if p["question_id"] in ids]
    all_ids = {p["question_id"] for p in payload["pairs"]}
    paper = mode == "paper"
    optional = mode == "optional"
    source_review = source_review_input(context, pairs)
    comparison = copy.deepcopy(duplicates)
    comparison["candidates"] = [c for c in comparison["candidates"] if ids.intersection(c["target_ids"])]
    comparison["findings"] = [f for f in comparison["findings"] if ids.intersection(f["target_ids"])]
    evidence = _evidence(context, source_review, comparison) if not (paper or optional) else []
    for e in source_review["academic_excerpts"]:
        e.pop("text")
        for key in ("coverage", "material_code", "physical_page"):
            e.pop(key, None)
    for c in comparison["candidates"]:
        c.pop("text")
        c.pop("material_version_id", None)
        c.pop("physical_page", None)
    course = context["input"]["course"]
    knowledge = {k for p in pairs for part in p["parts"] for k in part["knowledge_ids"]}
    knowledge.update(k for q in context["input"]["blueprint"]["questions"] if q["id"] in ids for k in q["knowledge_ids"])
    used_evidence = {e for p in pairs for e in p["evidence_ids"]}
    def relevant(issue):
        targets = set(issue.get("knowledge_ids", []))
        refs = set(issue.get("evidence_ids", []))
        return (not targets and not refs) or bool(targets & knowledge or refs & used_evidence)
    course_view = {k: copy.deepcopy(course[k]) for k in ("title", "target_exam", "method_rules", "scope_claims",
                                                          "clarifications", "historical_style") if k in course}
    course_view["knowledge_nodes"] = [copy.deepcopy(k) for k in course["knowledge_nodes"] if k["id"] in knowledge]
    course_view["issues"] = [copy.deepcopy(i) for i in course.get("issues", []) if relevant(i)]
    blueprint = copy.deepcopy(context["input"]["blueprint"])
    blueprint["questions"] = [q for q in blueprint["questions"] if q["id"] in ids]
    assets = []
    needed_assets = {aid for p in pairs for aid in p["asset_ids"]}
    for asset in payload["assets"]:
        if asset["id"] not in needed_assets:
            continue
        a = copy.deepcopy({k: v for k, v in asset.items() if k != "svg"})
        if a.get("spec", {}).get("expression"):
            a["spec"]["expression"] = compact_expression(a["spec"]["expression"])
        assets.append(a)
    data = {
        "review_mode": mode, "question_ids": list(question_ids),
        "required_categories": [] if paper or optional else list(REQUIRED_CATEGORIES),
        "optional_categories": list(OPTIONAL_CATEGORIES) if optional else [],
        "include_paper_check": paper or (not optional and ids == all_ids),
        "candidate": {"pairs": [compact_pair(p, include_checks=not (paper or optional)) for p in pairs], "assets": assets},
        "blueprint": blueprint, "course": course_view,
        "user_preferences": copy.deepcopy(context["input"]["statements"]), "config": copy.deepcopy(context["input"]["config"]),
        "local_checks": [{k: copy.deepcopy(v) for k, v in c.items() if k != "evidence_ids"}
                         for c in local if not c["target_ids"] or ids.intersection(c["target_ids"])],
        "blind_solutions": [copy.deepcopy(b) for b in blind if b["question_id"] in ids] if not (paper or optional) else [],
        "duplicate_comparison": comparison if not (paper or optional) else {"findings": comparison["findings"]},
        "source_review": source_review if not (paper or optional) else {"policy": source_review["policy"]},
        "evidence": evidence,
        "evidence_coverage": "One copy of each frozen source span. academic_excerpts link by id, comparison candidates by source_id/chunk_index. Fragment purposes identify use; omitted spans have not been read.",
        "other_question_summaries": [{"question_id": p["question_id"], "stem": p["stem"],
                                     "parts": p["parts"]} for p in payload["pairs"] if p["question_id"] not in ids],
        "expression_format": "Parenthesised infix; ^ means power. All original operations, domains, points and per-step hypotheses retained. Never treat a correct unrelated identity as answer validation.",
    }
    if paper:
        # Whole-paper comparisons need full printed questions and solution paths, not per-answer ASTs.
        data["candidate"]["pairs"] = [
            {"question_id": p["question_id"], "stem": p["stem"], "parts": p["parts"],
             "solution_paths": [{"part_id": a["part_id"], "worked_solution": a["worked_solution"],
                                 "final_answer": a["final_answer"]} for a in p["answers"]]}
            for p in pairs]
        data["course"] = {k: v for k, v in course_view.items() if k in ("title", "scope_claims")}
    if optional:
        data["course"] = {"title": course_view.get("title")}
        data["local_checks"] = []
        data.pop("blueprint")
    return data
