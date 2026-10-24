import copy
from app.generation.math_checks import check_math
from app.generation.checks import release_gate
from app.generation.duplicates import duplicate_candidates
from app.generation.content_fixtures import num,var,op

DOMAIN={"lower":None,"upper":None,"left_open":True,"right_open":True}


def spec(kind="derivative"):
    return {"id":"c","part_id":"p","kind":kind,"expression":op("pow",var(),num(2)),
        "expected":op("mul",num(2),var()),"denominator":None,"variable":"x",
        "domain":copy.deepcopy(DOMAIN),"at":None,"direction":"+-","points":[],"optimum":None,"rationale":"Test"}


def test_derivative_and_explicit_domain():
    assert check_math(spec())["result"]=="pass"
    s=spec(); s["expression"]=op("sqrt",var()); s["expected"]=op("div",num(1),op("mul",num(2),op("sqrt",var())))
    s["domain"]=None
    assert check_math(s)["result"]=="not_checked"
    s["domain"]={"lower":"0","upper":"10","left_open":False,"right_open":False}
    assert check_math(s)["result"]!="pass"
    s["domain"]["left_open"]=True
    assert check_math(s)["result"]=="pass"


def test_bounded_optimisation_requires_stationary_points_and_endpoints():
    s=spec("bounded_optimum")
    s.update(expression=op("pow",var(),num(2)),expected=num(4),optimum="max",
             domain={"lower":"-1","upper":"2","left_open":False,"right_open":False},points=["0"])
    assert check_math(s)["result"]=="fail"
    s["points"]=["-1","0","2"]
    assert check_math(s)["result"]=="pass"


def test_invalid_second_lhopital_step_fails():
    s=spec("lhopital")
    s.update(expression=num(1),denominator=num(1),expected=num(1),at="0")
    assert check_math(s)["result"]=="fail"


def test_cancelled_factors_do_not_hide_domain_holes():
    s=spec("equivalence")
    s.update(expression=op("div",var(),var()),expected=num(1))
    assert check_math(s)["result"]!="pass"


def test_release_gate_blocks_missing_ambiguous_and_failed_checks():
    for result in ("fail","not_checked","inconclusive","not_applicable"):
        assert not release_gate([{"check_id":"x","result":result,"required_for_release":True}])["allowed"]
    assert not release_gate([])["allowed"]
    assert release_gate([{"check_id":"x","result":"pass","required_for_release":True}])["allowed"]


def test_number_swaps_are_duplicate_candidates():
    pair={"question_id":"Q1","stem":[{"type":"text","text":"Find the maximum profit P(x)=3x-2x^2."}],"parts":[]}
    source={"id":"e1","kind":"extracted_text","content":"Find the maximum profit P(x)=7x-5x^2."}
    result=duplicate_candidates([pair],[source],[])
    assert result["compared_source_ids"]==["e1"]
    assert result["findings"][0]["code"]=="NUMBER_SWAP_DUPLICATE"


def test_blind_solver_cannot_see_answer_only_graphs():
    from app.generation.reviewer import blind_input
    pair={"question_id":"q","stem":[{"type":"asset_ref","asset_id":"question-graph"}],
          "parts":[{"part_id":"a","prompt":[{"type":"text","text":"Find the derivative."}]}],
          "asset_ids":["question-graph","answer-graph"],"answers":[{"worked_solution":"secret"}]}
    context={"input":{"course":{"method_rules":[],"scope_claims":[]},"statements":[]}}
    data=blind_input(context,pair,[{"id":"question-graph","alt":"Question","svg":"<svg/>"},
                                   {"id":"answer-graph","alt":"SECRET ANSWER GRAPH","svg":"<svg/>"}])
    assert [a["id"] for a in data["assets"]]==["question-graph"]
    assert "SECRET" not in str(data) and "answers" not in data["question"]

def test_symbolic_process_reused_with_separate_calculation_deadline():
    from app.generation.math_checks import MathWorker
    with MathWorker() as worker:
        assert worker.check(spec())["result"]=="pass"
        process=worker.process
        assert worker.check(spec())["result"]=="pass"
        assert worker.process is process
    assert process.poll() is not None


def test_timed_out_symbolic_process_is_killed_and_blocks_release(monkeypatch):
    import subprocess,sys
    from app.generation import math_checks
    original=subprocess.Popen
    script="import sys,json,time; print(json.dumps({'ready':True}),flush=True); sys.stdin.readline(); time.sleep(60)"
    def stalled(_command,**kwargs):
        return original([sys.executable,"-c",script],**kwargs)
    monkeypatch.setattr(math_checks.subprocess,"Popen",stalled)
    with math_checks.MathWorker(timeout_seconds=0.1) as worker:
        result=worker.check(spec())
        assert result["result"]=="not_checked"
        assert "calculation" in result["rationale"]
        assert worker.process is None
