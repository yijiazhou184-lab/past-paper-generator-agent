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
    assert GenerationArtifact.objects.count()==1
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
