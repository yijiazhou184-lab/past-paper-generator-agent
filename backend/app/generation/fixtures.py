"""Synthetic local planning adapter; only accepts explicitly fixture-marked confirmed versions."""
from .schemas import summarize


def fixture_blueprint(config, course_payload):
    nodes = {n["id"]: n for n in course_payload["knowledge_nodes"]}
    questions = []
    # Deliberately varied examples to exercise arithmetic and coverage, not a real marking algorithm.
    allocations = {2: [3, 2, 4], 3: [2, 3, 2.5], 4: [3, 2.5, 3.5]}
    for number in range(1, config["main_question_count"] + 1):
        parts = []
        for i, kind in enumerate(config["question_types"]):
            parts.append({"id": f"q{number}-{i}", "label": chr(97 + i), "response_type": kind,
                "focus": f"Synthetic {kind.replace('_', ' ')} part for testing; not an assessed objective.",
                "marks": allocations[config["main_question_count"]][i], "knowledge_ids": config["topic_ids"],
                "asset_needs": ["function_graph"] if number == 1 and i == 0 else []})
        questions.append({"id": f"q{number}", "number": number,
            "title": ["Derivative rules and interpretation", "Stationary points and classification", "Optimisation with constraints", "Connecting calculus methods"][number - 1],
            "objective": "Synthetic structure for testing configuration and confirmation. No model has assessed its educational suitability.",
            "knowledge_ids": config["topic_ids"], "parts": parts,
            "evidence_ids": sorted({eid for k in config["topic_ids"] for eid in nodes[k]["evidence_ids"]})})
    payload = {"sections": [{"id": "section-a", "title": "Topic 2 practice", "question_ids": [q["id"] for q in questions],
                            "selection": {"mode": "all", "choose_count": len(questions)}}], "questions": questions,
        "subquestion_count_locked": True, "suggested_minutes": {2: 25, 3: 40, 4: 55}[len(questions)],
        "differences": ["Synthetic fixture; no live model call."], "calibration": "uncalibrated"}
    return {**payload, **summarize(payload)}
