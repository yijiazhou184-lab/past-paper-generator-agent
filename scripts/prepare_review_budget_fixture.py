"""Create isolated validation progress demos. Synthetic models only; no real API calls."""
import json
from unittest.mock import patch
from django.db import transaction
from prepare_source_policy_fixture import create as create_source_demo, ROOT
from app.core.errors import DomainError
from app.core.tasks import claim_task,fail_task
from app.core.models import Task,ModelInvocation
from app.generation.models import GenerationDraft
from app.generation.execution_context import prepare_generation,submit_generation
from app.generation.generator import run_generation
from app.generation import semantic_review
from app.courses.models import Course

@transaction.atomic
def create():
    before=ModelInvocation.objects.count()
    actual=semantic_review.stage_output
    def optional_overflow(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="optional":
            raise DomainError("TOKEN_BUDGET_EXCEEDED","Synthetic optional input overflow; no model call.")
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=optional_overflow):
        result=create_source_demo()
    course=Course.objects.get(pk=result["course_id"])
    course.code="B4-REVIEW-FIXTURE"
    course.title="Validation progress and optional checks — synthetic demo"
    course.save(update_fields=["code","title"])
    result["success_task_id"]=result["task_id"]
    result["success_url"]=result["task_url"]
    saved=GenerationDraft.objects.get(course=course)
    context=prepare_generation(course.owner,course.id,saved.confirmation_id,saved.revision,saved.config_hash,"review-interrupted-preflight")
    assert context["mode"]=="fixture"
    failed=submit_generation(course.owner,course.id,saved.confirmation_id,saved.revision,saved.config_hash,
                             context["context_hash"],"review-interrupted-demo")
    token=claim_task(failed.id)
    completed=[]
    def interrupted(token,key,stage,data,output_type,fixture):
        if data["review_mode"]=="required":
            if len(data["question_ids"])>1:
                raise DomainError("TOKEN_BUDGET_EXCEEDED","Synthetic group overflow; no model call.")
            if completed:
                raise DomainError("TOKEN_BUDGET_EXCEEDED","Synthetic single-question overflow; no model call.")
            completed.append(data["question_ids"][0])
        return actual(token,key,stage,data,output_type,fixture)
    with patch.object(semantic_review,"stage_output",side_effect=interrupted):
        try:
            run_generation(token)
        except DomainError as exc:
            fail_task(token,exc.payload["code"],exc.payload["message"],False)
        else:
            raise AssertionError("The demo must fail before required review completes.")
    failed.refresh_from_db()
    assert failed.state=="failed" and not hasattr(failed.candidates.get(),"check_report")
    result.update(failed_task_id=str(failed.id),failed_url="http://127.0.0.1:5173/tasks/"+str(failed.id),
                  completed_semantic_questions=completed,new_model_calls=ModelInvocation.objects.count()-before,
                  mode="synthetic_fixture")
    assert result["new_model_calls"]==0
    return result

if __name__=="__main__":
    result=create()
    (ROOT/"var/review-budget-fixture.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
