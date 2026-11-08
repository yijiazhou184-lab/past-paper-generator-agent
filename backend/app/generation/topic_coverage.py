"""Coverage of a saved mixed-topic blueprint and its permitted answer paths."""
from itertools import combinations, product

from app.core.errors import DomainError


def answer_paths(blueprint):
    options = [list(combinations(s["question_ids"], s["selection"]["choose_count"]))
               for s in blueprint["sections"]]
    return [set().union(*groups) for groups in product(*options)]


def validate_topic_coverage(config, blueprint, course):
    selected = set(config["selected_topic_ids"])
    targets = set(config["knowledge_ids"])
    titles = {n["id"]: n["title"] for n in course["knowledge_nodes"]}
    paths = answer_paths(blueprint)
    always_questions = set.intersection(*paths)
    question_targets = {q["id"]: {kid for p in q["parts"] for kid in p["knowledge_ids"]}
                        for q in blueprint["questions"]}
    topic_count = dict.fromkeys(question_targets, 0)
    path_targets = [set().union(*(question_targets[qid] for qid in path)) for path in paths]
    guaranteed = set.intersection(*path_targets)
    topics = []
    for topic in course["topic_manifest"]:
        if topic["topic_id"] not in selected:
            continue
        required = targets.intersection(topic["knowledge_ids"])
        related = [qid for qid, assessed in question_targets.items() if required & assessed]
        missing = required - guaranteed
        if missing and config["mode"] != "mock_exam":
            raise DomainError("MIXED_TOPIC_COVERAGE_CONFLICT",
                f"{topic['name']} is missing selected knowledge on an allowed answer path. Reduce the selection or review question count and answer rules.",
                status=400)
        for qid in related:
            topic_count[qid] += 1
        topics.append({
            "topic_id": topic["topic_id"], "name": topic["name"], "code": topic.get("code", ""),
            "knowledge_ids": sorted(required),
            "knowledge": [{"id": kid, "title": titles[kid]} for kid in sorted(required)],
            "question_ids": related,
            "required_question_ids": [qid for qid in related if qid in always_questions],
            "optional_question_ids": [qid for qid in related if qid not in always_questions],
        })
    shared = [{"question_id": q["id"], "marks": sum(p["marks"] for p in q["parts"])}
              for q in blueprint["questions"] if topic_count[q["id"]] > 1]
    return {"topics": topics, "printed_marks": blueprint["printed_marks"], "attempt_marks": blueprint["attempt_marks"],
            "shared_questions": shared, "shared_printed_marks": sum(q["marks"] for q in shared),
        **({"knowledge_coverage": {
            "guaranteed": sorted(guaranteed),
            "optional": sorted(set.union(*path_targets) - guaranteed),
            "uncovered": sorted(targets - set.union(*path_targets)),
        }} if config["mode"] == "mock_exam" else {})}
