"""Bounded reviews inside Generate. Only a confirmed input overflow may split a request."""
from django.utils import timezone
from app.core.errors import DomainError
from app.core.models import Task
from .runtime import stage_output
from .content_schemas import SemanticOutput
from .checks import check
from .source_policy import source_catalog
from .review_input import build_review_input
from .review_policy import REVIEW_POLICY, REQUIRED_CATEGORIES, OPTIONAL_CATEGORIES, PAPER_CATEGORY
from .check_progress import save_check_stage
from .originality_policy import POLICY as ORIGINALITY_POLICY, judge as judge_overlaps


def normalise_review(context, output, ids, *, paper=False, optional=False, provided_evidence_ids=None):
    categories = OPTIONAL_CATEGORIES if optional else REQUIRED_CATEGORIES
    expected = [(qid, c) for qid in ids for c in categories]
    if paper:
        expected.append(("paper", PAPER_CATEGORY))
    catalog = source_catalog(context)
    supplied = ({s["id"] for s in context["input"]["sources"]}
                if provided_evidence_ids is None else set(provided_evidence_ids))
    returned, repeated, notices = {}, set(), []
    for item in output["checks"]:
        key = item["question_id"], item["category"]
        if key not in expected:
            continue
        if key in returned:
            repeated.add(key)
        returned[key] = item
        unknown = sorted(set(item["evidence_ids"]) - set(catalog))
        if unknown:
            notices.append(check(f"review_reference_notice:{key[0]}:{key[1]}", [key[0]], "source_policy",
                                 "inconclusive", f"Review references cannot be resolved: {unknown}. No source content was invented.",
                                 unknown, required=False))
    results = []
    for qid, category in expected:
        item = returned.get((qid, category))
        if output["status"] != "complete" or item is None or (qid, category) in repeated:
            result, reason, evidence = "not_checked", output["explanation"] or "Expected judgement missing or duplicated.", []
        else:
            result, reason, evidence = item["result"], item["rationale"], item["evidence_ids"]
            if category == "source_alignment" and result == "pass" and not (set(evidence) & supplied):
                result, reason = "inconclusive", "Teaching alignment needs a supplied academic source. " + reason
        prefix = "optional" if optional else "semantic"
        results.append(check(f"{prefix}:{qid}:{category}", ids if qid == "paper" else [qid],
                             "optional_review" if optional else "semantic_review", result, reason, evidence,
                             required=not optional))
    return results + notices


def _fixture_for(fixture, pairs, mode, include_paper):
    if mode == "optional":
        return {"status": "complete", "explanation": "Synthetic optional review; no model call.",
                "checks": [{"question_id": p["question_id"], "category": c, "result": "pass",
                            "rationale": "Synthetic advisory judgement.", "evidence_ids": []}
                           for p in pairs for c in OPTIONAL_CATEGORIES], "intra_paper_overlaps": [], "repair_requests": []}
    output = fixture(pairs)
    if mode == "paper":
        output["checks"] = [c for c in output["checks"] if c["question_id"] == "paper"]
    elif not include_paper:
        output["checks"] = [c for c in output["checks"] if c["question_id"] != "paper"]
    return output


def run_semantic_review(token, context, candidate, local, blind, duplicates, fixture):
    all_ids = [p["question_id"] for p in candidate.payload["pairs"]]
    if not 1 <= len(all_ids) <= REVIEW_POLICY["max_questions"]:
        raise DomainError("REVIEW_STRUCTURE_UNSUPPORTED")
    results, repairs = [], []
    split = [False]

    def review(ids, path, mode="required"):
        data = build_review_input(context, candidate.payload, local, blind, duplicates, ids, mode)
        pairs = [p for p in candidate.payload["pairs"] if p["question_id"] in ids]
        try:
            output = stage_output(token, f"r{candidate.revision-1}:semantic:{path}", "semantic_review", data,
                                  SemanticOutput, lambda: _fixture_for(fixture, pairs, mode, data["include_paper_check"]))
        except DomainError as exc:
            if exc.payload["code"] != "TOKEN_BUDGET_EXCEEDED" or mode != "required" or len(ids) < 2:
                raise
            split[0] = True
            middle = len(ids) // 2
            review(ids[:middle], path + "L")
            review(ids[middle:], path + "R")
            return
        # A paper-only review must not regenerate the per-question coverage requirements.
        covered = [] if mode == "paper" else ids
        checks = normalise_review(context, output, covered, paper=data["include_paper_check"],
                                  provided_evidence_ids=[e["id"] for e in data["evidence"]])
        for c in checks:
            if c["check_id"] == "semantic:paper:paper_consistency":
                c["target_ids"] = all_ids
        details = {}
        if data["include_paper_check"]:
            # The model reports facts only; the user's rule is applied here.
            # Missing facts are never read as "no overlap".
            reported = output.get("intra_paper_overlaps")
            reviewed = output["status"] == "complete" and reported is not None
            overlaps = reported if reviewed else []
            part_question = {part["part_id"]: p["question_id"] for p in candidate.payload["pairs"] for part in p["parts"]}
            result, reason, duplicate_pairs = judge_overlaps(overlaps, data["intra_paper_overlap_hints"], part_question,
                                                             reviewed=reviewed)
            item = check(ORIGINALITY_POLICY["check_id"], all_ids, "intra_paper_rule", result, reason)
            item["duplicate_pairs"] = duplicate_pairs
            checks.append(item)
            details = {"intra_paper_overlaps": overlaps, "intra_paper_overlap_hints": data["intra_paper_overlap_hints"],
                       "originality_policy": ORIGINALITY_POLICY["version"]}
        requests = [r for r in output["repair_requests"] if set(r["target_ids"]) <= set(ids)]
        saved = save_check_stage(token, candidate, "semantic-" + path, checks, repair_requests=requests, **details)
        results.extend(saved["checks"])
        repairs.extend(saved["repair_requests"])

    review(all_ids, "all")
    if split[0]:
        review(all_ids, "paper", "paper")
    return results, repairs


OPTIONAL_ERRORS = {
    "OPTIONAL_TIME_BUDGET", "TOKEN_BUDGET_EXCEEDED", "CALL_BUDGET_EXCEEDED", "GENERATION_MODEL_FAILED", "MODEL_INCOMPLETE",
    "MODEL_REFUSAL", "OUTPUT_SCHEMA_INVALID", "MODEL_OUTCOME_UNKNOWN", "TOKEN_COUNT_FAILED",
    "PROVIDER_TIMEOUT", "PROVIDER_CONNECTION_FAILED", "PROVIDER_RESPONSE_FAILED", "PROVIDER_RATE_LIMIT",
    "PROVIDER_QUOTA_EXHAUSTED", "PROVIDER_HTTP_ERROR", "PROVIDER_BAD_REQUEST",
    "PROVIDER_AUTH_FAILED", "PROVIDER_ACCESS_DENIED", "MODEL_UNAVAILABLE",
}


def run_optional_review(token, context, candidate, local, blind, duplicates, fixture, *, required_passed):
    ids = [p["question_id"] for p in candidate.payload["pairs"]]
    task = Task.objects.get(pk=token.task_id)
    remaining = (task.deadline_at - timezone.now()).total_seconds()
    reason = None
    if not required_passed:
        reason = "Optional checks skipped: required checks take priority."
    elif remaining < REVIEW_POLICY["optional_min_seconds"]:
        reason = "Optional checks skipped: insufficient time remains."
    elif context["mode"] == "live" and task.call_count >= context["max_calls"]:
        reason = "Optional checks skipped: model-call budget is reserved for required checks."
    if reason is None:
        data = build_review_input(context, candidate.payload, local, blind, duplicates, ids, "optional")
        try:
            output = stage_output(token, f"r{candidate.revision-1}:optional", "semantic_review", data, SemanticOutput,
                                  lambda: _fixture_for(fixture, candidate.payload["pairs"], "optional", False))
            checks = normalise_review(context, output, ids, optional=True)
        except DomainError as exc:
            if exc.payload["code"] not in OPTIONAL_ERRORS:
                raise  # Cancellation, stale leases and integrity failures are never optional.
            reason = "Optional checks skipped: " + exc.payload["code"] + ". No pass judgement was inferred."
    if reason:
        checks = [check(f"optional:{qid}:{c}", [qid], "optional_review", "not_checked", reason, required=False)
                  for qid in ids for c in OPTIONAL_CATEGORIES]
    return save_check_stage(token, candidate, "optional", checks,
                            status="skipped" if reason else "complete")["checks"]
