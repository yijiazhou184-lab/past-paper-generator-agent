from collections import Counter
from app.core.errors import DomainError
from .content_validation import validate_group
from .math_checks import MathWorker
from .source_policy import source_diagnostics


def check(check_id,targets,method,result,rationale,evidence=None,required=True):
    return {"check_id":check_id,"target_ids":targets,"method":method,"result":result,
            "required_for_release":required,"rationale":rationale,"evidence_ids":evidence or []}


def program_checks(context,payload):
    checks=[]
    questions=context["input"]["questions"]
    if [p["question_id"] for p in payload["pairs"]]!=[q["blueprint"]["id"] for q in questions]:
        checks.append(check("structure",[],"program","fail","Question order or coverage differs from the blueprint."))
        return checks
    for q,pair in zip(questions,payload["pairs"]):
        assets=[a["spec"] for a in payload["assets"] if a["id"] in pair["asset_ids"]]
        try:
            validate_group(q["blueprint"],{"status":"complete","explanation":"","pair":pair,"assets":assets},context)
            status,reason="pass","IDs, marks, answer pairing, scoring groups and required assets match the frozen blueprint. Teaching evidence is assessed separately."
        except DomainError as exc:
            status,reason="fail",exc.payload["code"]
        checks.append(check("program:"+pair["question_id"],[pair["question_id"]],"program",status,reason,pair["evidence_ids"]))
        d=source_diagnostics(context,pair)
        checks.append(check("source_basis:"+pair["question_id"],[pair["question_id"]],"source_policy",
            "pass" if d["has_academic_basis"] else "fail",
            "A supplied course source is cited; teaching coverage and acceptable adjacent extension still require semantic review."
            if d["has_academic_basis"] else
            "No cited academic source has supplied content. Identify teaching evidence for the main knowledge target; background alone cannot establish it.",
            pair["evidence_ids"]))
        extras=d["additional_course_ids"]+d["background_only_ids"]+d["unresolved_ids"]
        if extras or d["duplicate_ids"]:
            checks.append(check("source_notice:"+pair["question_id"],[pair["question_id"]],"source_policy","inconclusive",
                "Reference scope notice (not an automatic failure): "
                f"additional course={d['additional_course_ids']}; background-only={d['background_only_ids']}; "
                f"unresolved={d['unresolved_ids']}; duplicates={d['duplicate_ids']}. "
                "Assess the actual knowledge used; justified minor extensions are acceptable. Move purely contextual citations to background references.",
                extras,required=False))
    return checks


def mathematical_checks(pairs):
    checks=[]
    with MathWorker() as worker:
        for pair in pairs:
            types={p["part_id"]:p["response_type"] for p in pair["parts"]}
            for answer in pair["answers"]:
                if not answer["checks"]:
                    qualitative=types[answer["part_id"]]=="explanation_proof"
                    checks.append(check("math:"+answer["part_id"],[pair["question_id"],answer["part_id"]],"symbolic",
                        "not_applicable" if qualitative else "not_checked",
                        "No quantitative symbolic claim supplied; semantic proof review remains mandatory." if qualitative else "No supported mathematical check was supplied.",
                        required=not qualitative))
                if answer["checks"] and types[answer["part_id"]] in QUANTITATIVE and \
                        not any(spec.get("role","core")=="core" for spec in answer["checks"]):
                    checks.append(check(f"math:{answer['part_id']}:core_missing",[pair["question_id"],answer["part_id"]],"symbolic",
                        "not_checked","No core check states this part's final answer; supporting checks cannot replace it."))
                for spec in answer["checks"]:
                    # Specifications saved before roles existed are treated as core, never relaxed.
                    role=spec.get("role","core")
                    output=worker.check({**spec,"role":role})
                    checks.append(math_check(spec["id"],[pair["question_id"],answer["part_id"]],role,output))
    return checks


QUANTITATIVE=("calculation","applied_optimisation")


def math_check(spec_id,targets,role,output):
    """core must pass; a refuted auxiliary claim blocks; an undecided auxiliary claim is a recorded limitation."""
    undecided=role=="auxiliary" and output["result"] in ("inconclusive","not_checked")
    item=check("math:"+spec_id,targets,"sympy_subprocess",output["result"],output["rationale"],
               required=not (role=="auxiliary" and output["result"]!="fail"))
    item["math_role"]=role
    if undecided:
        item["limitation"]="Auxiliary evidence not decided; recorded without blocking. The written reasoning is judged separately."
    return item


def release_gate(checks):
    required=[c for c in checks if c["required_for_release"]]
    blocking=[c["check_id"] for c in required if c["result"]!="pass"]
    if not required: blocking=["required_checks_missing"]
    return {"allowed":not blocking,"blocking_check_ids":blocking}


def coverage_summary(checks):
    required=[c for c in checks if c["required_for_release"]]
    counts=Counter(c["result"] for c in required)
    optional=[c for c in checks if not c["required_for_release"]]
    return {"required":len(required),"passed":counts["pass"],"failed":counts["fail"],
            "not_checked":counts["not_checked"],"inconclusive":counts["inconclusive"],
            "optional":len(optional),"optional_not_checked":sum(c["result"]=="not_checked" for c in optional),
            "auxiliary_unresolved":sum(1 for c in checks if c.get("limitation"))}
