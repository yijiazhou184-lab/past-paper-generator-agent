"""Immutable per-stage records; public progress never needs answer-bearing details."""
from .runtime import save_artifact
from .models import GenerationArtifact
from .checks import check, release_gate, coverage_summary
from .review_policy import REVIEW_POLICY, REQUIRED_CATEGORIES, OPTIONAL_CATEGORIES
from app.core.idempotency import digest
from app.core.errors import DomainError


def save_check_stage(token, candidate, name, checks, **details):
    payload = {"candidate_id": str(candidate.id), "candidate_hash": candidate.payload_hash,
               "name": name, "checks": checks, **details}
    identity = digest({"candidate": candidate.payload_hash, "name": name, "policy": REVIEW_POLICY})
    return save_artifact(token, f"check:r{candidate.revision-1}:{name}", identity, payload, [])


def progress_report(candidate):
    stages = []
    checks = {}
    blind = []
    duplicates = {"retrieval_coverage": "Comparison retrieval has not finished.",
                  "compared_source_ids": [], "compared_paper_ids": []}
    ids = [p["question_id"] for p in candidate.payload["pairs"]]
    prefix = f"check:r{candidate.revision-1}:"
    for a in GenerationArtifact.objects.filter(task=candidate.task, key__startswith=prefix).order_by("created_at"):
        p = a.payload
        if a.payload_hash != digest(p) or p.get("candidate_hash") != candidate.payload_hash or p.get("candidate_id") != str(candidate.id):
            raise DomainError("CHECK_STAGE_CHANGED")
        targets = {qid for c in p["checks"] for qid in c["target_ids"]}
        stages.append({"name": p["name"], "status": p.get("status", "complete"),
                       "question_ids": [qid for qid in ids if qid in targets]})
        checks.update({c["check_id"]: c for c in p["checks"]})
        blind.extend(p.get("blind", []))
        if "duplicates" in p:
            duplicates = p["duplicates"]
    if not stages:
        return None
    names = {s["name"] for s in stages}
    ids = [p["question_id"] for p in candidate.payload["pairs"]]
    for stage in ("program", "math", "retrieval"):
        if stage not in names:
            c = check("pending:"+stage, ids, stage, "not_checked", "This required stage has not completed.")
            checks[c["check_id"]] = c
    expected = [(f"blind_available:{qid}", [qid], "blind_solver") for qid in ids]
    expected += [(f"semantic:{qid}:{category}", [qid], "semantic_review") for qid in ids for category in REQUIRED_CATEGORIES]
    expected += [("semantic:paper:paper_consistency", ids, "semantic_review")]
    for key, targets, method in expected:
        checks.setdefault(key, check(key, targets, method, "not_checked", "This required check has not completed."))
    for qid in ids:
        for category in OPTIONAL_CATEGORIES:
            key = f"optional:{qid}:{category}"
            checks.setdefault(key, check(key, [qid], "optional_review", "not_checked",
                                         "Optional check has not run; required checks take priority.", required=False))
    values = list(checks.values())
    return {"candidate_version_id": str(candidate.id), "complete": False, "version": digest([stages, values]),
            "checks": values, "stages": stages, "gate": {**release_gate(values), "allowed": False},
            "coverage_summary": coverage_summary(values), "blind_comparison": blind,
            "duplicate_review": duplicates, "repair_requests": []}
