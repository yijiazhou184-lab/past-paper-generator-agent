"""Synthetic regressions derived from failure shapes, without private course text."""
import copy
from unittest.mock import patch
import pytest
import sympy as sp
from app.generation.expressions import expression,number
from app.generation.math_worker import evaluate
from app.generation.duplicates import duplicate_candidates
from app.generation.content_fixtures import num,var,op,fixture_pair,fixture_review
from app.generation.generator import run_generation
from app.generation.models import CandidateVersion
from test_generation_checks import spec
from test_generation_execution import start
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_schema_numeric_forms_and_infinite_bounds_are_supported():
    assert number("-1/3")==-sp.Rational(1,3)
    s=spec()
    s["domain"]={"lower":"-inf","upper":"inf","left_open":True,"right_open":True}
    assert evaluate(s)["result"]=="pass"
    for bad in ("1/0","__import__('os')","1e9999","999999999/1","inf"):
        with pytest.raises(ValueError):number(bad)


def test_schema_bounded_variadic_arithmetic_and_invalid_arities():
    assert expression(op("add",num(1),num(2),num(3),num(4)))==10
    assert expression(op("mul",num(2),num(3),num(4)))==24
    for bad in (op("sub",num(1),num(2),num(3)),op("mul"),
                op("add",num(1)),op("add",*[num(1)]*5)):
        with pytest.raises(ValueError):expression(bad)


def test_long_question_still_receives_actual_bounded_comparison_excerpts():
    pair={"question_id":"q","stem":[{"type":"text","text":"Interpret the production model. "*100}],
          "parts":[{"prompt":[{"type":"text","text":"Justify the interval and derive the optimum."}]}]}
    sources=[{"id":f"s{i}","content":"Historical exercise about derivatives. "+("Other context. "*100),
              "physical_page":i+1,"material_version_id":"version"} for i in range(9)]
    result=duplicate_candidates([pair],sources,[])
    assert 1<=len(result["candidates"])<=6
    assert all(c["text"] and c["target_ids"]==["q"] for c in result["candidates"])
    assert result["compared_source_ids"]
    assert result["available_source_ids"]==[s["id"] for s in sources]
    assert result["retrieval_status"]=="complete"
    assert not result["findings"]


def test_empty_page_content_is_explicit_and_never_a_valid_retrieval():
    result=duplicate_candidates([{"question_id":"q","stem":[],"parts":[]}],
                                [{"id":"empty","content":""}],[])
    assert result["retrieval_status"]=="empty_source_content"
    assert result["compared_source_ids"]==[]


def test_repair_receives_target_diagnostics_and_returns_needs_info_truthfully(course,planned):
    task,context,token=start(course,planned)
    target=context["input"]["questions"][0]["blueprint"]["id"]
    def blocked(pairs):
        result=fixture_review(pairs)
        item=next(c for c in result["checks"] if c["question_id"]==target and c["category"]=="conditions")
        item["result"]="fail";item["rationale"]="Domain restriction missing."
        result["repair_requests"]=[{"target_ids":[target],"issue_codes":["domain"],
                                    "instructions":"Check the domain; rerun validation."}]
        return result
    from app.generation import generator
    original=generator.stage_output
    captured=[]
    def unavailable(token,key,stage,data,output_type,fixture):
        if stage=="repair":
            captured.append(data["repair_request"])
            return {"status":"needs_info","explanation":"Synthetic missing condition.","pair":None,"assets":[]}
        return original(token,key,stage,data,output_type,fixture)
    with patch("app.generation.reviewer.fixture_review",side_effect=blocked),patch(
        "app.generation.generator.stage_output",side_effect=unavailable):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="needs_info"
    assert task.result["allowed"] is False
    assert task.result["candidate_id"] and task.result["report_id"]
    assert task.candidates.count()==1 and not task.candidates.get().check_report.gate["allowed"]
    assert any(c["rationale"]=="Domain restriction missing." for c in captured[0]["local_checks"])
    assert "duplicate_comparison" in captured[0] and "checker_contract" in captured[0]
    assert all(r["target_ids"]==[target] for r in captured[0]["issues"])


def test_empty_comparison_content_blocks_even_if_semantic_fixture_passes(course,planned):
    task,context,token=start(course,planned)
    empty=duplicate_candidates([{"question_id":"q","stem":[],"parts":[]}],[{"id":"empty","content":""}],[])
    with patch("app.generation.reviewer.duplicate_candidates",return_value=empty):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="failed" and not task.result["allowed"]
    assert "local_duplicates" in task.result["blocking_check_ids"]


def test_checker_contract_is_frozen_and_changes_require_preflight(course,planned):
    from app.core.errors import DomainError
    from app.core.idempotency import digest
    from app.generation.runtime import verify_context
    task,context,token=start(course,planned)
    assert context["checker_contract"]
    task.snapshot=copy.deepcopy(context)
    task.snapshot["checker_contract"]["arity"]="Unrestricted"
    task.snapshot["context_hash"]=digest({k:v for k,v in task.snapshot.items() if k!="context_hash"})
    with pytest.raises(DomainError,match="GENERATION_CHECKER_CHANGED"):
        verify_context(task)
