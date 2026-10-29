"""Overlap-fact evaluation set: preflight and scoring only. Sends nothing.

The labelled set lives in backend/tests/fixtures/intra_paper_overlap_eval.json. This script lists what a
later authorised sampling run would send and scores saved predictions against the labels. A live run
is not implemented here and needs its own exact-scope authorisation before it is added.

  python scripts/eval_overlap_facts.py                     # preflight
  python scripts/eval_overlap_facts.py --score preds.json  # score saved facts: [{"id", "same_stimulus", "same_conclusion"}]
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "backend/tests/fixtures/intra_paper_overlap_eval.json"
sys.path.insert(0, str(ROOT / "backend"))


def load():
    return json.loads(DATASET.read_text(encoding="utf-8"))


def score(dataset, predictions):
    labels = {c["id"]: c["expected"] for c in dataset["cases"]}
    by_id = {p["id"]: p for p in predictions}
    result = {"cases": len(labels), "answered": 0, "same_stimulus_agree": 0, "same_conclusion_agree": 0, "mismatches": []}
    for case_id, expected in labels.items():
        got = by_id.get(case_id)
        if got is None:
            result["mismatches"].append({"id": case_id, "reason": "missing"})
            continue
        result["answered"] += 1
        wrong = [k for k in ("same_stimulus", "same_conclusion") if got.get(k) != expected[k]]
        result["same_stimulus_agree"] += "same_stimulus" not in wrong
        result["same_conclusion_agree"] += "same_conclusion" not in wrong
        if wrong:
            result["mismatches"].append({"id": case_id, "fields": wrong})
    return result


def local_text(source):
    """Read private part prompts from the local database; never stored in Git."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from app.generation.models import CandidateVersion
    candidate = CandidateVersion.objects.get(pk=source["candidate_id"])
    prompts = {part["part_id"]: part["prompt"] for pair in candidate.payload["pairs"] for part in pair["parts"]}
    return prompts[source["part_a"]], prompts[source["part_b"]]


def preflight(dataset):
    rows = []
    for case in dataset["cases"]:
        local = case.get("source", {}).get("type") == "local_candidate"
        if local:
            try:
                local_text(case["source"])
                available = "local text available"
            except Exception as exc:
                available = f"local text unavailable ({type(exc).__name__})"
        rows.append({"id": case["id"], "subject": case["subject"], "category": case["category"],
                     "text": available if local else "synthetic text in dataset"})
    return {"dataset": dataset["version"], "cases": len(rows), "requests_if_run": len(rows),
            "model": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"), "sent": "nothing (preflight only)", "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--score", type=Path, help="Saved predictions to score; no model call")
    args = parser.parse_args()
    data = load()
    output = score(data, json.loads(args.score.read_text(encoding="utf-8"))) if args.score else preflight(data)
    print(json.dumps(output, ensure_ascii=False, indent=2))
