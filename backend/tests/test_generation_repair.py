import copy
from unittest.mock import patch
import pytest
from app.core.errors import DomainError
from app.generation.generator import generate_groups,persist_candidate,run_generation
from app.generation.reviewer import check_candidate
from app.generation.repair import repair_candidate
from app.generation.models import CandidateVersion
from app.generation.content_fixtures import fixture_review
from test_generation_execution import start
from test_generation_preflight import prepare
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_one_targeted_repair_retains_original_and_rechecks(course,planned):
    task,context,token=start(course,planned)
    calls=[0]
    target=context["input"]["questions"][0]["blueprint"]["id"]
    def review(pairs):
        result=fixture_review(pairs)
        calls[0]+=1
        if calls[0]==1:
            item=next(c for c in result["checks"] if c["question_id"]==target and c["category"]=="conditions")
            item["result"]="fail"; item["rationale"]="State the domain explicitly."
            result["repair_requests"]=[{"target_ids":[target],"issue_codes":["domain"],"instructions":"Clarify the domain."}]
        return result
    with patch("app.generation.reviewer.fixture_review",side_effect=review):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="succeeded"
    original,repaired=list(CandidateVersion.objects.filter(task=task).order_by("revision"))
    assert repaired.parent_id==original.id
    assert not original.check_report.gate["allowed"]
    assert repaired.check_report.gate["allowed"]
    assert original.payload["pairs"][1:]==repaired.payload["pairs"][1:]
    assert task.generation_artifacts.filter(key__startswith="r1:pair:").count()==1
    assert task.generation_artifacts.filter(key__startswith="blind:").count()==3


def test_second_repair_round_is_rejected(course,planned):
    task,context,token=start(course,planned)
    groups=generate_groups(token,context)
    first=persist_candidate(token,context,groups)
    second=persist_candidate(token,context,groups,2,first)
    with pytest.raises(DomainError,match="REPAIR_ROUND_LIMIT"):
        repair_candidate(token,context,second,None)


def test_persistent_required_failure_never_publishes(course,planned):
    task,context,token=start(course,planned)
    target=context["input"]["questions"][0]["blueprint"]["id"]
    def fail(pairs):
        result=fixture_review(pairs)
        for c in result["checks"]:
            if c["question_id"]==target and c["category"]=="reasoning":
                c["result"]="fail"
        result["repair_requests"]=[{"target_ids":[target],"issue_codes":["reasoning"],"instructions":"Repair the argument."}]
        return result
    with patch("app.generation.reviewer.fixture_review",side_effect=fail):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="failed" and not task.result["allowed"]
    assert task.candidates.count()==2


def paper_failure(target=None):
    """A review whose only failure is the whole-paper check, optionally with a request naming one question."""
    calls=[0]
    def review(pairs):
        result=fixture_review(pairs)
        calls[0]+=1
        if calls[0]==1:
            paper=next(c for c in result["checks"] if c["question_id"]=="paper")
            paper["result"]="fail"; paper["rationale"]="The blueprint's paper-level note is not addressed."
            if target:
                result["repair_requests"]=[{"target_ids":[target],"issue_codes":["paper_note"],"instructions":"Address the note in this question."}]
        return result
    return review


def test_paper_level_failure_repairs_only_the_questions_the_review_named(course,planned):
    task,context,token=start(course,planned)
    ids=[q["blueprint"]["id"] for q in context["input"]["questions"]]
    target=ids[-1]
    with patch("app.generation.reviewer.fixture_review",side_effect=paper_failure(target)):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="succeeded"
    original,repaired=list(CandidateVersion.objects.filter(task=task).order_by("revision"))
    # Only the named question was rewritten; the whole-paper target list did not widen the repair.
    assert [a.key for a in task.generation_artifacts.filter(key__startswith="r1:pair:")]==[f"r1:pair:{target}"]
    assert original.payload["pairs"][:-1]==repaired.payload["pairs"][:-1]


def test_paper_level_failure_without_a_named_question_spends_no_repair_call(course,planned):
    task,context,token=start(course,planned)
    with patch("app.generation.reviewer.fixture_review",side_effect=paper_failure()):
        run_generation(token)
    task.refresh_from_db()
    assert task.state=="failed" and task.result["blocking_check_ids"]==["semantic:paper:paper_consistency"]
    assert task.candidates.count()==1
    assert not task.generation_artifacts.filter(key__startswith="r1:pair:").exists()
    assert task.events.filter(stage="No justified repair available").exists()


def test_question_writer_receives_the_paper_level_planning_notes(course,planned):
    from app.generation.generator import question_input
    _,context,_=start(course,planned)
    notes=context["input"]["blueprint"]["differences"]
    assert notes
    for q in context["input"]["questions"]:
        assert question_input(context,q,[])["paper_planning_notes"]==notes
