"""Separate teaching evidence from unrestricted, non-authoritative background references.

All classification is against the frozen context. No network lookups or mutable evidence reads.
"""
from collections import Counter
from .duplicates import source_text

SOURCE_POLICY = {
    "version": "source-policy-v1",
    "academic_scope": "Ground the main knowledge targets in supplied teaching evidence. Small adjacent extensions are acceptable when justified and do not replace the targets or require unsupported methods.",
    "background_scope": "unrestricted",
    "background_authority": "Background may use other course references, general context or external references. It is not proof of course coverage or official facts; external references are unverified and never fetched automatically.",
    "citation_handling": "Extra, duplicate or unresolved academic references are recorded, not a structural abort. Missing teaching basis or substantive scope drift requires targeted repair before release.",
    "review_excerpt_chars": 1200,
}


def source_catalog(context):
    """Only frozen local metadata can produce a source link; an arbitrary ID cannot."""
    catalog = {s["id"]: s for s in context["input"].get("background_source_catalog", [])}
    catalog.update({s["id"]: s for s in context["input"]["sources"]})
    return catalog


def source_diagnostics(context, pair):
    q = next(q["blueprint"] for q in context["input"]["questions"]
             if q["blueprint"]["id"] == pair["question_id"])
    planned = set(q["evidence_ids"])
    available = {s["id"] for s in context["input"]["sources"]}
    catalog = source_catalog(context)
    ids = list(dict.fromkeys(pair["evidence_ids"]))
    return {
        "question_id": pair["question_id"],
        "planned_ids": [i for i in ids if i in planned and i in available],
        "additional_course_ids": [i for i in ids if i not in planned and i in available],
        "background_only_ids": [i for i in ids if i not in available and i in catalog],
        "unresolved_ids": [i for i in ids if i not in catalog],
        "duplicate_ids": [i for i, n in Counter(pair["evidence_ids"]).items() if n > 1],
        "has_academic_basis": bool(set(ids) & available),
        "background_reference_count": len(pair.get("background_references", [])),
    }


def source_review_input(context, pairs):
    """Bounded excerpts only from already approved pages; clipping is explicit."""
    used = {i for p in pairs for i in p["evidence_ids"]}
    excerpts = []
    for source in context["input"]["sources"]:
        if source["id"] in used:
            text = source_text(source)
            limit = SOURCE_POLICY["review_excerpt_chars"]
            excerpts.append({
                "id": source["id"], "material_code": source.get("material_code"),
                "physical_page": source.get("physical_page"),
                "text": text[:limit], "truncated": len(text) > limit,
                "coverage": "Bounded excerpt; use course knowledge mappings too. Missing content is not evidence of validity.",
            })
    return {"policy": context.get("source_policy", SOURCE_POLICY),
            "questions": [source_diagnostics(context, p) for p in pairs],
            "academic_excerpts": excerpts}


def public_source_summary(context, pair):
    d = source_diagnostics(context, pair)
    statuses = {i: status for key, status in (
        ("planned_ids", "planned"), ("additional_course_ids", "additional_course"),
        ("background_only_ids", "background_only"), ("unresolved_ids", "unresolved"))
        for i in d[key]}
    return {"academic": [{"id": i, "status": statuses[i]} for i in dict.fromkeys(pair["evidence_ids"])],
            "duplicate_count": len(d["duplicate_ids"]),
            "background_count": d["background_reference_count"]}
