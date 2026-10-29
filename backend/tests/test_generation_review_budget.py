from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.generation.generator import run_generation
from app.generation import semantic_review
from test_generation_execution import start
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_count_overflow_splits_then_checks_whole_paper(course,planned):
    task,context,token=start(course,planned)
    actual=semantic_review.stage_output
    calls=[]
    def bounded(token,key,stage,data,output_type,fixture):
        calls.append((data["review_mode"],data["question_ids"]))
        if data["review_mode"]=="required" and len(data["question_ids"])>1:
            raise DomainError("TOKEN_BUDGET_EXCEEDED")
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=bounded):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="succeeded"
    assert ("paper", [p["blueprint"]["id"] for p in context["input"]["questions"]]) in calls
    assert task.candidates.get().check_report.gate["allowed"]


def test_optional_budget_failure_does_not_block_required_passes(course,planned):
    task,_,token=start(course,planned)
    actual=semantic_review.stage_output
    def bounded(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="optional":
            raise DomainError("TOKEN_BUDGET_EXCEEDED")
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=bounded):
        run_generation(token)
    task.refresh_from_db()
    report=task.candidates.get().check_report
    assert task.state=="succeeded" and report.gate["allowed"]
    optional=[c for c in report.payload["checks"] if c["method"]=="optional_review"]
    assert optional and all(c["result"]=="not_checked" and not c["required_for_release"] for c in optional)


def test_unknown_required_result_is_not_split_or_retried(course,planned):
    task,_,token=start(course,planned)
    with patch.object(semantic_review,"stage_output",side_effect=DomainError("MODEL_OUTCOME_UNKNOWN")) as call:
        with pytest.raises(DomainError,match="MODEL_OUTCOME_UNKNOWN"):
            run_generation(token)
    assert call.call_count==1
    assert not hasattr(task.candidates.get(), "check_report")


@pytest.mark.parametrize("error",["PROVIDER_TIMEOUT","MODEL_INCOMPLETE","MODEL_OUTCOME_UNKNOWN"])
def test_optional_provider_failure_is_recorded_without_retry(course,planned,error):
    task,_,token=start(course,planned)
    actual=semantic_review.stage_output
    attempts=[]
    def unavailable(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="optional":
            attempts.append(key)
            raise DomainError(error)
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=unavailable):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="succeeded" and len(attempts)==1
    assert any(error in c["rationale"] for c in task.candidates.get().check_report.payload["checks"])


def test_optional_cannot_swallow_cancellation(course,planned):
    task,_,token=start(course,planned)
    actual=semantic_review.stage_output
    def cancelled(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="optional":
            from app.core.tasks import cancel_task
            cancel_task(course.owner,task.id)
            raise DomainError("STALE_EXECUTION")
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=cancelled):
        with pytest.raises(DomainError,match="STALE_EXECUTION"):
            run_generation(token)
    task.refresh_from_db()
    assert task.state=="cancelled" and not hasattr(task.candidates.get(),"check_report")


def test_missing_paper_review_cannot_pass_after_splitting(course,planned):
    task,_,token=start(course,planned)
    actual=semantic_review.stage_output
    def missing(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="required" and len(data["question_ids"])>1:
            raise DomainError("TOKEN_BUDGET_EXCEEDED")
        if data["review_mode"]=="paper":
            return {"status":"complete","explanation":"Missing judgement","checks":[],"repair_requests":[]}
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=missing):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="failed"
    assert "semantic:paper:paper_consistency" in task.result["blocking_check_ids"]


def test_optional_count_uses_lower_cap_without_sending_model_request(course,planned):
    from app.ai.contracts import ModelCallSpec,ModelCallResult
    from app.ai.invocations import count_call
    from app.generation.content_schemas import SemanticOutput
    task,_,token=start(course,planned)
    spec=ModelCallSpec(stage="semantic_review",prompt_version="test",schema_version="test",
                       context_hash="test",input={},max_input_tokens=20000)
    with patch("app.ai.invocations.count_official",return_value=ModelCallResult(
        mode="fixture",status="parsed",payload={"input_tokens":20001})):
        with pytest.raises(DomainError,match="TOKEN_BUDGET_EXCEEDED"):
            count_call(token,"test-optional-count",spec,instructions="test",output_type=SemanticOutput,
                       api_key="test-not-real",model="fixture",timeout_seconds=10)
    task.refresh_from_db()
    assert task.call_count==0
    record=task.model_calls.get()
    assert record.metadata["token_limit"]==20000 and record.metadata["timeout_seconds"]<=10


def test_review_request_serialization_survives_json_key_reordering():
    from app.ai.contracts import ModelCallSpec
    from app.ai.responses import request_body
    from app.generation.content_schemas import SemanticOutput
    from app.core.idempotency import digest
    spec=ModelCallSpec(stage="semantic_review",prompt_version="test",schema_version="test",
                      context_hash="x",input={"b":{"y":2,"x":1},"a":0})
    first=request_body(spec,"test",SemanticOutput,"fixture",byte_admission=False)
    second=request_body(spec.model_copy(update={"input":{"a":0,"b":{"x":1,"y":2}}}),"test",SemanticOutput,"fixture",byte_admission=False)
    assert digest(first)==digest(second)


def test_review_policy_changes_require_new_preflight(course,planned):
    import copy
    from app.core.idempotency import digest
    from app.generation.runtime import verify_context
    task,context,_=start(course,planned)
    task.snapshot=copy.deepcopy(context)
    task.snapshot["review_policy"]["optional_input_tokens"]=60000
    task.snapshot["context_hash"]=digest({k:v for k,v in task.snapshot.items() if k!="context_hash"})
    with pytest.raises(DomainError,match="GENERATION_REVIEW_POLICY_CHANGED"):
        verify_context(task)


def test_alignment_requires_evidence_supplied_in_this_review_group(course,planned):
    from app.generation.content_fixtures import fixture_pair,fixture_review
    _,context,_=start(course,planned)
    pair=fixture_pair(context["input"]["questions"][0]["blueprint"])["pair"]
    checks=semantic_review.normalise_review(context,fixture_review([pair]),[pair["question_id"]],provided_evidence_ids=[])
    alignment=next(c for c in checks if c["check_id"].endswith(":source_alignment"))
    assert alignment["result"]=="inconclusive" and alignment["required_for_release"]
    assert all(c["result"]=="pass" for c in checks if not c["check_id"].endswith(":source_alignment"))
