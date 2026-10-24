from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.core.tasks import claim_task, cancel_task
from app.generation.execution_context import submit_generation
from app.generation.generator import generate_groups, persist_candidate
from app.generation.models import GenerationArtifact, CandidateVersion
from test_generation_preflight import prepare
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def start(course,planned):
    saved,context=prepare(course,planned)
    task=submit_generation(course.owner,course.id,saved.confirmation_id,saved.revision,saved.config_hash,context["context_hash"],"generate")
    return task,context,claim_task(task.id)


def test_completed_groups_are_reused_after_interruption(course,planned):
    task,context,token=start(course,planned)
    from app.generation.content_fixtures import fixture_pair
    count=[0]
    def interrupted(q):
        count[0]+=1
        if count[0]==2: raise DomainError("WORKER_INTERRUPTED")
        return fixture_pair(q)
    with patch("app.generation.generator.fixture_pair",side_effect=interrupted):
        with pytest.raises(DomainError,match="WORKER_INTERRUPTED"):
            generate_groups(token,context)
    assert GenerationArtifact.objects.filter(key__startswith="validated:").count()==1
    with patch("app.generation.generator.fixture_pair",wraps=fixture_pair) as adapter:
        groups=generate_groups(token,context)
        assert adapter.call_count==2
    candidate=persist_candidate(token,context,groups)
    assert persist_candidate(token,context,groups).id==candidate.id
    assert len(candidate.payload["pairs"])==3
    assert task.model_calls.count()==0


def test_cancelled_execution_cannot_save_candidate(course,planned):
    task,context,token=start(course,planned)
    groups=generate_groups(token,context)
    cancel_task(course.owner,task.id)
    with pytest.raises(DomainError,match="STALE_EXECUTION"):
        persist_candidate(token,context,groups)
    assert not CandidateVersion.objects.exists()

def test_fixture_pipeline_and_blind_answer_isolation(course,planned):
    task,context,token=start(course,planned)
    from app.generation.generator import run_generation
    from app.generation import reviewer
    actual=reviewer.stage_output
    blind_requests=[]
    def capture(token,key,stage,data,output_type,fixture):
        if stage=="blind_solver":
            blind_requests.append(data)
            assert "answers" not in data["question"]
            assert "checks" not in str(data["question"])
            assert "worked_solution" not in str(data)
        return actual(token,key,stage,data,output_type,fixture)
    with patch("app.generation.reviewer.stage_output",side_effect=capture):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="succeeded", task.result
    assert task.result["allowed"]
    assert len(blind_requests)==3
    assert task.call_count==0
    assert CandidateVersion.objects.get(task=task).check_report.payload["coverage_summary"]["failed"]==0


def test_missing_semantic_category_cannot_pass(course,planned):
    task,context,token=start(course,planned)
    from app.generation.generator import run_generation
    from app.generation.content_fixtures import fixture_review
    def missing(pairs):
        output=fixture_review(pairs)
        output["checks"].pop()
        return output
    with patch("app.generation.reviewer.fixture_review",side_effect=missing):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="failed"
    assert not task.result["allowed"]
    assert any("math_relevance" in i for i in task.result["blocking_check_ids"])


@pytest.mark.parametrize("status",["refusal","truncated","provider_error","invalid_output"])
def test_unusable_model_response_preserves_no_completed_artifact(course,planned,status):
    task,context,token=start(course,planned)
    from app.ai.contracts import ModelCallResult
    from app.generation.runtime import stage_output
    from app.generation.content_schemas import PairOutput
    task.snapshot["mode"]="live"
    task.save(update_fields=["snapshot"])
    with patch("app.generation.runtime.verify_generation_sources"), patch("app.generation.runtime.count_call",return_value=100), patch(
        "app.generation.runtime.run_call",return_value=ModelCallResult(mode="fixture",status=status)):
        with pytest.raises(DomainError,match="GENERATION_MODEL_FAILED"):
            stage_output(token,"test-failure","question_pairs",{},PairOutput,lambda:None)
    assert not GenerationArtifact.objects.exists()

def test_new_attempt_reuses_only_validated_complete_groups(course,planned):
    task,context,token=start(course,planned)
    from app.core.tasks import fail_task
    from app.generation.models import GenerationDraft
    from app.generation.content_fixtures import fixture_pair
    from app.generation.generator import generate_group
    generate_group(token,context,context["input"]["questions"][0],[])
    fail_task(token,"TEST_INTERRUPTION","Synthetic known failure",True)
    saved=GenerationDraft.objects.get(course=course)
    retry=submit_generation(course.owner,course.id,saved.confirmation_id,saved.revision,
                            saved.config_hash,context["context_hash"],"new-attempt")
    with patch("app.generation.generator.fixture_pair",wraps=fixture_pair) as adapter:
        groups=generate_groups(claim_task(retry.id),context)
        assert adapter.call_count==2
    assert retry.parent_id==task.id and len(groups)==3


def test_unknown_call_is_not_automatically_replayed(course, planned):
    from app.core.models import ModelInvocation
    from app.generation.runtime import stage_output
    from app.generation.content_schemas import PairOutput
    task, context, token = start(course, planned)
    task.snapshot["mode"] = "live"
    task.save(update_fields=["snapshot"])
    ModelInvocation.objects.create(task=task, call_key="unknown", epoch=token.epoch,
                                   request_hash="x"*64, state="reserved")
    with patch("app.generation.runtime.verify_generation_sources"), patch("app.generation.runtime.count_call") as count, patch("app.generation.runtime.run_call") as call:
        with pytest.raises(DomainError, match="MODEL_OUTCOME_UNKNOWN"):
            stage_output(token, "unknown", "question_pairs", {}, PairOutput, lambda:None)
        count.assert_not_called()
        call.assert_not_called()
    assert not GenerationArtifact.objects.exists()


def test_candidate_and_report_cannot_be_overwritten(course, planned):
    from django.db import DatabaseError, transaction
    from app.core.idempotency import digest
    from app.generation.models import CheckReport
    task, context, token = start(course, planned)
    candidate = persist_candidate(token, context, generate_groups(token, context))
    report = CheckReport.objects.create(candidate=candidate, payload={"checks":[]},
        payload_hash=digest({"checks":[]}), gate={"allowed":False})
    for model, pk in [(CandidateVersion,candidate.id),(CheckReport,report.id)]:
        with pytest.raises(DatabaseError), transaction.atomic():
            model.objects.filter(pk=pk).update(payload={"tampered":True})
    candidate.refresh_from_db()
    report.refresh_from_db()
    assert candidate.payload_hash == digest(candidate.payload)
    assert report.gate["allowed"] is False
