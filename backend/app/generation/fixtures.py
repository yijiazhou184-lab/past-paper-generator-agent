from .config_compat import knowledge_ids
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
                "marks": allocations[config["main_question_count"]][i], "knowledge_ids": knowledge_ids(config),
                "asset_needs": ["function_graph"] if number == 1 and i == 0 else []})
        questions.append({"id": f"q{number}", "number": number,
            "title": ["Derivative rules and interpretation", "Stationary points and classification", "Optimisation with constraints", "Connecting calculus methods"][number - 1],
            "objective": "Synthetic structure for testing configuration and confirmation. No model has assessed its educational suitability.",
            "knowledge_ids": knowledge_ids(config), "parts": parts,
            "evidence_ids": sorted({eid for k in knowledge_ids(config) for eid in nodes[k]["evidence_ids"]})})
    payload = {"sections": [{"id": "section-a", "title": "Topic 2 practice", "question_ids": [q["id"] for q in questions],
                            "selection": {"mode": "all", "choose_count": len(questions)}}], "questions": questions,
        "subquestion_count_locked": True, "suggested_minutes": {2: 25, 3: 40, 4: 55}[len(questions)],
        "differences": ["Synthetic fixture; no live model call."], "calibration": "uncalibrated"}
    return {**payload, **summarize(payload)}


def apply_fixture_exam_template(payload, template):
    """Keep synthetic planning on the same structural path as a real plan."""
    questions = payload["questions"]
    if sum(len(s["question_marks"]) for s in template["sections"]) != len(questions):
        return payload
    sections = []
    index = 0
    for section in template["sections"]:
        ids = []
        for marks in section["question_marks"]:
            question = questions[index]
            units, extra = divmod(int(marks * 2), len(question["parts"]))
            for part_index, part in enumerate(question["parts"]):
                part["marks"] = (units + (part_index < extra)) / 2
            ids.append(question["id"])
            index += 1
        sections.append({"id": section["id"], "title": section["title"], "question_ids": ids, "selection": section["selection"]})
    payload.update(sections=sections, suggested_minutes=template["duration_minutes"])
    return {**payload, **summarize(payload)}
