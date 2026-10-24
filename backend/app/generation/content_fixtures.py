"""Deterministic synthetic pipeline data. Never evidence of live model quality."""
import copy


def num(value): return {"op":"number","value":str(value),"args":[]}
def var(): return {"op":"variable","value":"x","args":[]}
def op(name,*args): return {"op":name,"value":None,"args":list(args)}
def text(value): return {"type":"text","text":value}
def math(value): return {"type":"math","latex":value,"display":True}


def fixture_pair(q):
    # Different polynomial families, not simply number substitutions.
    power=q["number"]+1
    expr=op("pow",var(),num(power))
    derivative=op("mul",num(power),op("pow",var(),num(power-1)))
    stem=[text("Synthetic fixture question. This validates software behaviour, not course difficulty."),
          math(f"f(x)=x^{{{power}}}")]
    parts=[]; answers=[]; assets=[]
    for index,p in enumerate(q["parts"]):
        prompt=[text(f"Part {p['label']}: find the derivative and explain the power rule.")]
        if "function_graph" in p["asset_needs"]:
            aid=q["id"]+"-graph-"+str(index)
            assets.append({"id":aid,"kind":"function_graph","expression":expr,"x_min":-2,"x_max":2,
                           "y_min":-10,"y_max":10,"samples":100,"x_label":"x","y_label":"f(x)","alt":"Synthetic polynomial graph"})
            prompt.append({"type":"asset_ref","asset_id":aid})
        if "data_table" in p["asset_needs"]:
            prompt.append({"type":"table","columns":["x","f(x)"],"rows":[["0","0"],["1","1"]],"caption":"Synthetic sample values"})
        parts.append({"part_id":p["id"],"prompt":prompt,"marks":p["marks"],"assumptions":["x is real"],
                      "response_type":p["response_type"],"knowledge_ids":p["knowledge_ids"]})
        answers.append({"part_id":p["id"],"worked_solution":[text("Apply the power rule: multiply by the exponent, then reduce the exponent by one.")],
            "final_answer":[math(f"{power}x^{{{power-1}}}")],
            "marking_points":[{"id":p["id"]+"-method","text":"Apply the rule and obtain the stated derivative.",
                               "marks":p["marks"],"alternative_group":None}],
            "acceptable_alternatives":["Use the limit definition with a complete derivation."],"units":None,"precision":"Exact",
            "checks":[{"id":p["id"]+"-derivative","part_id":p["id"],"kind":"derivative","expression":expr,"expected":derivative,
                "denominator":None,"variable":"x","domain":{"lower":None,"upper":None,"left_open":True,"right_open":True},
                "at":None,"direction":"+-","points":[],"optimum":None,"rationale":"Check the synthetic polynomial derivative."}]})
    return {"status":"complete","explanation":"Synthetic fixture only.",
        "pair":{"question_id":q["id"],"stem":stem,"parts":parts,"answers":answers,"asset_ids":[a["id"] for a in assets],
        "evidence_ids":q["evidence_ids"],"originality_notes":"Synthetic fixture; originality is not calibrated.","marking_basis":"suggested"},
        "assets":assets}


def fixture_blind(q):
    # Deterministic independent fixture calculation, never a real blind-solving claim.
    generated=fixture_pair(q)["pair"]
    return {"status":"complete","explanation":"Synthetic blind-solver adapter; no model call.",
            "answers":[{"part_id":a["part_id"],"reasoning":copy.deepcopy(a["worked_solution"]),
                        "final_answer":copy.deepcopy(a["final_answer"])} for a in generated["answers"]]}


CATEGORIES=("clarity","conditions","methods","reasoning","difficulty","preferences","originality","blind_agreement","math_relevance")


def fixture_review(pairs):
    return {"status":"complete","explanation":"Synthetic review; does not certify real quality.",
        "checks":[{"question_id":p["question_id"],"category":c,"result":"pass",
                   "rationale":"Deterministic fixture review, not a live judgement.","evidence_ids":p["evidence_ids"]}
                  for p in pairs for c in CATEGORIES],"repair_requests":[]}
