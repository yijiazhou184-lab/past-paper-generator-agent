"""Append-only acceptance evidence and pure timing/accounting functions."""
import dataclasses,json,hashlib,uuid
from pathlib import Path
from datetime import datetime,timezone


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


def iso(value):
    if value is None:return None
    return value.isoformat() if isinstance(value,datetime) else value


def moment(value):
    return datetime.fromisoformat(value.replace("Z","+00:00")) if isinstance(value,str) else value


def interval_seconds(intervals):
    ranges=sorted((moment(a),moment(b)) for a,b in intervals if a and b)
    combined=[]
    for start,end in ranges:
        if end<start:raise ValueError("Negative elapsed time")
        if combined and start<=combined[-1][1]:combined[-1]=(combined[-1][0],max(end,combined[-1][1]))
        else:combined.append((start,end))
    return sum((b-a).total_seconds() for a,b in combined)


def delivery_timing(generation,exports,pdfs_ready):
    gen=interval_seconds([generation]) if all(generation) else None
    complete=bool(pdfs_ready and exports and all(generation) and all(all(pair) for pair in exports))
    export_seconds=interval_seconds(exports) if exports and all(all(pair) for pair in exports) else None
    total=gen+export_seconds if complete else None
    user_wait=None
    if all(generation) and exports:
        # Manual gaps between export attempts are not silently charged as system processing.
        first=min(moment(a) for a,b in exports if a)
        end=max(moment(b) for a,b in exports if b) if all(b for a,b in exports) else None
        user_wait=max(0,(first-moment(generation[1])).total_seconds())
        if end and export_seconds is not None:user_wait+=max(0,(end-first).total_seconds()-export_seconds)
    return {"generation_seconds":gen,"export_seconds":export_seconds,"user_wait_seconds":user_wait,
        "complete_system_seconds":total,"delivery_complete":complete}


@dataclasses.dataclass
class RunRecord:
    run_id:str
    planned_slot:str|None=None
    kind:str="original"
    retest_of:str|None=None
    attempt_id:str=dataclasses.field(default_factory=lambda:str(uuid.uuid4()))
    recorded_at:str=dataclasses.field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    mode:str="live"
    status:str="not_executed"
    baseline_version:str|None=None
    bindings:dict=dataclasses.field(default_factory=dict)
    task_ids:list=dataclasses.field(default_factory=list)
    attempts:list=dataclasses.field(default_factory=list)
    calls:list=dataclasses.field(default_factory=list)
    timing:dict=dataclasses.field(default_factory=dict)
    usage:dict|None=None
    cost_estimate:dict|None=None
    cost_price_source:str|None=None
    outputs:dict=dataclasses.field(default_factory=dict)
    checks:dict=dataclasses.field(default_factory=dict)
    quality_review:dict=dataclasses.field(default_factory=lambda:{"status":"not_reviewed","reviewer":None,"units":[]})
    notes:list=dataclasses.field(default_factory=list)

    def as_dict(self):return dataclasses.asdict(self)


def write_record(root,record):
    data=record.as_dict() if isinstance(record,RunRecord) else record
    for value in (data["run_id"],data["attempt_id"]):
        if not value or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in value):
            raise ValueError("Invalid record identity")
    directory=Path(root)/data["run_id"]/data["attempt_id"];directory.mkdir(parents=True,exist_ok=True)
    path=directory/"record.json"
    with path.open("x",encoding="utf-8") as stream:json.dump(data,stream,indent=2,default=str)
    return path


def summarise_runs(records,rubric=None):
    rows=[r.as_dict() if isinstance(r,RunRecord) else r for r in records]
    originals={};extras=[];extensions=[]
    for row in rows:
        if row.get("retest_of") or row.get("kind")=="retest":extras.append(row);continue
        if row.get("planned_slot")=="E1" or row.get("kind")=="extension":extensions.append(row);continue
        slot=row.get("planned_slot")
        if row.get("mode")=="live" and slot in {f"R{i}" for i in range(1,7)}:
            if slot in originals:raise ValueError("Duplicate original slot; use a retest ID.")
            originals[slot]=row
    def passed(row):
        return bool(row.get("status")=="completed" and row.get("timing",{}).get("delivery_complete")
            and row.get("checks",{}).get("required_passed") is True
            and row.get("quality_review",{}).get("status")=="passed")
    attempted=[r for r in originals.values() if r.get("task_ids")]
    good=sum(passed(r) for r in originals.values())
    unknown=sum(r.get("usage") is None for r in attempted)
    skipped=sorted(s for s,r in originals.items() if r.get("status")=="skipped")
    return {"planned_total":6,"active_planned_total":6-len(skipped),"skipped_slots":skipped,"recorded_originals":len(originals),"attempted":len(attempted),"passed":good,
        "failed_slots":[s for s,r in originals.items() if r["status"]=="failed"],
        "not_executed_slots":[f"R{i}" for i in range(1,7) if f"R{i}" not in skipped and (f"R{i}" not in originals or not originals[f"R{i}"].get("task_ids"))],
        "planned_success_fraction":good/6,"executed_success_rate":good/len(attempted) if attempted else None,
        "baselines":sorted({r["baseline_version"] for r in attempted if r.get("baseline_version")}),
        "usage_unknown_runs":unknown,"retests":[r["run_id"] for r in extras],
        "extension_runs":[{"run_id":r["run_id"],"passed":passed(r),"status":r["status"]} for r in extensions],
        "all_six_passed":good==6}


def apply_quality_review(record,review):
    import copy
    result=copy.deepcopy(record.as_dict() if isinstance(record,RunRecord) else record)
    expected=set(result.get("outputs",{}).get("answer_unit_ids",[]))
    units=review.get("units",[])
    if not expected or len(units)!=len(expected) or {u.get("unit_id") for u in units}!=expected:
        raise ValueError("Review must cover every actual answer unit exactly once")
    if not review.get("reviewer") or review.get("content_hash")!=result["outputs"].get("content_hash"):
        raise ValueError("Review must identify its reviewer and exact content hash")
    statuses={"correct","minor_issue","major_issue","cannot_judge","not_checked"}
    if any(u.get("status") not in statuses for u in units):raise ValueError("Unknown review status")
    if any(u["status"]=="minor_issue" and not u.get("rationale") for u in units):raise ValueError("Minor issues need a rationale")
    checked=sum(u["status"] in ("correct","minor_issue","major_issue") for u in units)
    okay=all(u["status"] in ("correct","minor_issue") for u in units)
    result["quality_review"]={**review,"review_coverage":checked/len(expected),"status":"passed" if okay else "failed"}
    result["attempt_id"]=str(uuid.uuid4());result["recorded_at"]=datetime.now(timezone.utc).isoformat()
    return result
