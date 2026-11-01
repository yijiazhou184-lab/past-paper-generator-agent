"""Frozen personal history; distinct from teaching evidence and never course authority."""
from app.generation.duplicates import question_text, block_text, terms
from .models import Paper
from .publication import assert_integrity


def history_snapshot(course_id):
    papers = list(Paper.objects.filter(course_id=course_id).select_related("content").order_by("-created_at", "-id")[:20])
    rows = []
    for paper in papers:
        assert_integrity(paper.content)
        pairs = paper.content.payload["content"]["pairs"]
        rows.append({"paper_id": str(paper.id), "content_version_id": str(paper.content_id),
                     "content_hash": paper.content.payload_hash, "created_at": paper.created_at.isoformat(),
                     "questions": [{"question_id": p["question_id"], "text": question_text(p),
                                    "conclusion": " ".join(block_text(a["final_answer"]) for a in p["answers"])} for p in pairs]})
    return rows


def history_for_question(context, question):
    rows = context["input"].get("history_papers", [])
    query = terms(question["blueprint"]["title"] + " " + question["blueprint"]["objective"])
    ranked = []
    for paper in rows:
        for item in paper["questions"]:
            words = terms(item["text"])
            score = len(query & words) / max(1, len(query | words))
            ranked.append((score, paper["paper_id"], item))
    return [{"paper_id": pid, "question_id": item["question_id"], "question_excerpt": item["text"][:1200],
             "truncated": len(item["text"]) > 1200} for _,pid,item in sorted(ranked, key=lambda x:(-x[0],x[1],x[2]["question_id"]))[:3]]
