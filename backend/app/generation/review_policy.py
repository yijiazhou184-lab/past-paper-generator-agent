"""Code-owned release requirements, frozen with every new generation context."""
PIPELINE_VERSION = "generation-v7-repair-diagnostics"
REQUIRED_CATEGORIES = ("clarity", "conditions", "methods", "reasoning", "difficulty",
                       "preferences", "originality", "blind_agreement", "source_alignment", "math_relevance")
MODEL_REQUIRED_CATEGORIES = tuple(c for c in REQUIRED_CATEGORIES if c != "originality")
OPTIONAL_CATEGORIES = ("wording", "alternative_methods", "difficulty_detail", "background_references")
PAPER_CATEGORY = "paper_consistency"
REVIEW_POLICY = {
    "version": "review-policy-v3",
    "required_categories": list(REQUIRED_CATEGORIES),
    "optional_categories": list(OPTIONAL_CATEGORIES),
    "paper_category": PAPER_CATEGORY,
    "projection": "review-input-v2",
    "split_on": "official_input_token_overflow_only",
    "max_questions": 4,
    "optional_input_tokens": 20000,
    "optional_output_tokens": 4000,
    "optional_min_seconds": 60,
    "optional_call_seconds": 45,
    "optional_count_seconds": 10,
    "completion_reserve_seconds": 5,
}


def review_call_bound(question_count):
    return 1 if question_count <= 1 else question_count + 1
