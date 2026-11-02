"""Summarise immutable local records. This module never calls models."""
import argparse,json
from pathlib import Path
from .records import summarise_runs


def read_latest(root):
    latest={}
    for path in Path(root).glob("*/*/record.json"):
        row=json.loads(path.read_text())
        if row["run_id"] not in latest or row["recorded_at"]>latest[row["run_id"]]["recorded_at"]:latest[row["run_id"]]=row
    return list(latest.values())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=str(Path(__file__).resolve().parents[2]/"var/evals/round1"))
    args=parser.parse_args()
    print(json.dumps(summarise_runs(read_latest(args.root)),indent=2))
if __name__=="__main__":main()
