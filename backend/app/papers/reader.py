import copy
from app.generation.source_policy import source_catalog, public_source_summary
from .publication import assert_integrity
from .storage import valid_artifact


def pdf_state(paper):
    artifacts = {a.kind: a for a in paper.content.pdfs.all()}
    files = {}
    for kind in ("questions", "answers"):
        artifact = artifacts.get(kind)
        ready = bool(artifact and valid_artifact(artifact))
        files[kind] = {"ready": ready, "pages": artifact.pages if ready else None,
                       "sha256": artifact.sha256 if ready else None,
                       "url": f"/api/v1/papers/{paper.id}/files/{kind}" if ready else None}
    task = paper.latest_export
    if all(f["ready"] for f in files.values()) and paper.exports_ready_at:
        status = "ready"
    elif task and task.state in ("queued", "processing"):
        status = "generating"
    elif task and task.state == "cancelled":
        status = "cancelled"
    elif task:
        status = "failed"
    else:
        status = "not_generated"
    return {"status": status, "files": files, "task_id": str(task.id) if task else None,
            "stage": task.stage if task else None, "error": task.error if task else None}


def paper_topics(paper):
    frozen=paper.content.payload
    saved=frozen["metadata"].get("selected_topics")
    if saved is not None:return copy.deepcopy(saved)
    from app.generation.config_compat import selected_topics
    return selected_topics(frozen["metadata"]["config"],paper.content.candidate.snapshot.confirmation.course_version)


def paper_summary(paper):
    m = paper.content.payload["metadata"]
    return {"id": str(paper.id), "course_id": str(paper.course_id), "task_id": str(paper.generation_task_id),
            "content_version_id": str(paper.content_id), "content_hash": paper.content.payload_hash,
            "created_at": paper.created_at.isoformat(), "metadata": m, "topic_summary":paper_topics(paper), "export": pdf_state(paper)}


def question_view(paper):
    assert_integrity(paper.content)
    frozen = paper.content.payload
    context, content, report = frozen["context"], frozen["content"], frozen["report"]
    catalog = source_catalog(context)
    pairs = []
    for p in content["pairs"]:
        item = {k: copy.deepcopy(p[k]) for k in ("question_id", "stem", "parts", "evidence_ids")}
        item["source_summary"] = public_source_summary(context, p)
        pairs.append(item)
    refs = {b["asset_id"] for p in pairs for b in p["stem"] + [b for part in p["parts"] for b in part["prompt"]] if b["type"] == "asset_ref"}
    evidence = {e for p in pairs for e in p["evidence_ids"]}
    candidate = paper.content.candidate
    return {"id": str(candidate.id), "revision": candidate.revision, "parent_id": str(candidate.parent_id) if candidate.parent_id else None,
            "mode": frozen["metadata"]["mode"], "stage": "saved", "pairs": pairs,
            "sources": [{k: catalog[e][k] for k in ("id", "material_code", "material_version_id", "physical_page") if k in catalog[e]} for e in sorted(evidence) if e in catalog],
            "assets": [{k: a[k] for k in ("id", "svg", "alt")} for a in content["assets"] if a["id"] in refs],
            "report": {"gate": {"allowed": True, "blocking_check_ids": []}, "coverage_summary": report["coverage_summary"],
                       "version": frozen["metadata"]["report_hash"], "checks": [], "complete": True}}


def answer_view(paper):
    assert_integrity(paper.content)
    frozen = paper.content.payload
    catalog = source_catalog(frozen["context"])
    pairs = frozen["content"]["pairs"]
    ids = {r.get("evidence_id") for p in pairs for r in p.get("background_references", [])}
    return {"candidate_id": str(paper.content.candidate_id),
            "answers": [{k: p.get(k, []) for k in ("question_id", "answers", "marking_basis", "background_references")} for p in pairs],
            "assets": [{k: a[k] for k in ("id", "svg", "alt")} for a in frozen["content"]["assets"]],
            "report": frozen["report"], "model_outputs": [],
            "reference_sources": [{k: catalog[e][k] for k in ("id", "material_code", "material_version_id", "physical_page") if k in catalog[e]} for e in sorted(e for e in ids if e in catalog)]}
