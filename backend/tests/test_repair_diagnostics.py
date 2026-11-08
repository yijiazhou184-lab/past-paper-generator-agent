import copy
from app.generation.math_checks import check_math
from app.generation.checks import math_check
from app.generation.math_diagnostics import diagnose_spec
from app.generation.repair_diagnostics import build_repair_failures, validate_repaired_checks


def spec(points=None):
    return {"id":"interior-points","part_id":"part-b","kind":"stationary_points",
        "expression":{"op":"pow","value":None,"args":[{"op":"variable","value":"x","args":[]},{"op":"number","value":"2","args":[]}]},
        "expected":None,"denominator":None,"variable":"x",
        "domain":{"lower":"-2","upper":"2","left_open":True,"right_open":True},
        "at":None,"direction":"+-","points":points or ["0"],"optimum":None,"role":"core","rationale":"Compare the full solution set."}


def pair(s):
    return {"question_id":"question-a","parts":[{"part_id":"part-b","marks":4,"knowledge_ids":["objective"],"response_type":"calculation"}],
        "answers":[{"part_id":"part-b","checks":[s]}]}


def test_points_diagnostic_names_exact_field_value_and_supported_format():
    raw=spec(["-2/sqrt(3)"])
    d=diagnose_spec(raw)[0]
    assert d["code"]=="UNSUPPORTED_NUMERIC_LITERAL" and d["field_path"]=="points[0]"
    assert d["actual_value"]=="-2/sqrt(3)" and d["category"]=="specification_error"
    assert d["actionable"] and "fraction" in d["allowed_format"].lower()
    assert raw["points"]==["-2/sqrt(3)"]


def test_worker_preserves_diagnostic_and_does_not_treat_unsupported_as_wrong_answer():
    out=check_math(spec(["-2/sqrt(3)"]))
    assert out["result"]=="not_checked"
    c=math_check("interior-points",["question-a","part-b"],"core",out)
    assert c["required_for_release"] and c["diagnostics"][0]["question_id"]=="question-a"
    assert c["diagnostics"][0]["part_id"]=="part-b"


def test_numeric_fields_and_expression_leaves_have_paths():
    raw=spec();raw["domain"]["upper"]="1/0";raw["expression"]["args"][1]["value"]="sqrt(2)"
    paths={d["field_path"] for d in diagnose_spec(raw)}
    assert paths=={"domain.upper","expression.args[1].value"}


def test_repair_failure_has_original_spec_even_without_model_request():
    s=spec(["-2/sqrt(3)"]);out={"result":"not_checked","rationale":"The mathematical specification is invalid or unsupported.","diagnostics":diagnose_spec(s)}
    check=math_check(s["id"],["question-a","part-b"],"core",out)
    failures=build_repair_failures(pair(s),[check])
    assert len(failures)==1 and failures[0]["actionable"]
    assert failures[0]["specification"]==s
    assert failures[0]["diagnostics"][0]["field_path"]=="points[0]"
    assert "parentheses" in failures[0]["instructions"]
    assert "restricted expression object" in failures[0]["instructions"]


def test_unknown_math_failure_does_not_invent_an_action():
    c={"check_id":"math:unknown","target_ids":["question-a"],"method":"sympy_subprocess",
       "result":"inconclusive","required_for_release":True,"rationale":""}
    assert not build_repair_failures(pair(spec()),[c])[0]["actionable"]


def test_failed_conclusion_is_distinct_from_specification_error():
    c={"check_id":"math:interior-points","target_ids":["question-a","part-b"],"method":"sympy_subprocess",
       "result":"fail","required_for_release":True,"rationale":"The stated solution set differs."}
    f=build_repair_failures(pair(spec()),[c])[0]
    assert f["category"]=="content_error" and f["actionable"]


def test_repair_cannot_remove_or_demote_blocked_core_check():
    from app.core.errors import DomainError
    import pytest
    s=spec();p=pair(s);f=[{"check_id":"math:"+s["id"],"specification":s}]
    revised=copy.deepcopy(p);revised["answers"][0]["checks"][0]["role"]="auxiliary"
    with pytest.raises(DomainError,match="REPAIR_REQUIRED_CHECK_REMOVED"):validate_repaired_checks(p,revised,f)
    revised["answers"][0]["checks"]=[]
    with pytest.raises(DomainError,match="REPAIR_REQUIRED_CHECK_REMOVED"):validate_repaired_checks(p,revised,f)

def test_repair_receives_full_failures_and_rejects_cosmetic_model_advice():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.generation.repair import repair_candidate
    import pytest
    s=spec(["-2/sqrt(3)"]);p=pair(s)
    c=math_check(s["id"],["question-a","part-b"],"core",{"result":"not_checked","rationale":"Unsupported.","diagnostics":diagnose_spec(s)})
    report=SimpleNamespace(gate={"allowed":False},payload={"checks":[c],"repair_requests":[{"target_ids":["question-a"],"issue_codes":["format"],"instructions":"Add parentheses around sqrt."}],"duplicate_review":{"findings":[],"candidates":[]}})
    candidate=SimpleNamespace(id="candidate",revision=1,parent_id=None,payload={"pairs":[p],"assets":[]})
    context={"mode":"fixture","input":{"questions":[{"blueprint":{"id":"question-a"}}]},"checker_contract":{}}
    class Captured(Exception):pass
    captured={}
    def intercept(*args,**kwargs):captured.update(kwargs["repair_requests"]);raise Captured()
    with patch("app.generation.repair.Task.objects.get",return_value=SimpleNamespace(call_count=0)),patch("app.generation.repair.source_review_input",return_value={}),patch("app.generation.repair.generate_groups",side_effect=intercept):
        with pytest.raises(Captured):repair_candidate(SimpleNamespace(task_id="task"),context,candidate,report)
    request=captured["question-a"]
    assert request["failures"][0]["diagnostics"][0]["actual_value"]=="-2/sqrt(3)"
    assert request["model_suggestions"]==[] and request["protected_check_ids"]==["interior-points"]
    assert all("Add parentheses" not in r["instructions"] for r in request["issues"])


def test_no_actionable_failure_does_not_spend_a_repair_call():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.generation.repair import repair_candidate
    c={"check_id":"math:unknown","target_ids":["question-a"],"method":"sympy_subprocess","result":"inconclusive","required_for_release":True,"rationale":""}
    report=SimpleNamespace(gate={"allowed":False},payload={"checks":[c],"repair_requests":[],"duplicate_review":{"findings":[],"candidates":[]}})
    candidate=SimpleNamespace(id="candidate",revision=1,parent_id=None,payload={"pairs":[pair(spec())]})
    with patch("app.generation.repair.checkpoint") as log,patch("app.generation.repair.generate_groups") as generate:
        assert repair_candidate(None,{"input":{"questions":[{"blueprint":{"id":"question-a"}}]}},candidate,report) is None
    generate.assert_not_called()
    assert log.call_args.args[2]["unresolved_check_ids"]==["math:unknown"]
