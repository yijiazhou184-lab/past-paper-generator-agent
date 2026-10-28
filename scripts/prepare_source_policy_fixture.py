"""An isolated synthetic reference-policy demonstration. Never calls a real model."""
import json
from unittest.mock import patch
from django.db import transaction
from prepare_generation_browser_fixture import prepare, ROOT
from app.courses.models import Course
from app.generation.models import GenerationDraft
from app.generation.planning import build_context, submit_plan, run_planning
from app.generation.snapshots import confirm_structure
from app.generation.execution_context import prepare_generation, submit_generation
from app.generation.generator import run_generation
from app.generation.content_fixtures import fixture_pair
from app.core.tasks import claim_task, submit_task, finish_task
from app.materials.models import Evidence


@transaction.atomic
def create():
    result = prepare()
    course = Course.objects.get(pk=result["course_id"])
    course.code = "B4-SOURCE-FIXTURE"
    course.title = "Teaching and background references — synthetic demo"
    course.save(update_fields=["code", "title"])
    evidence = Evidence.objects.select_related("material_version", "parse_version").get(pk=result["source_id"])
    parse = submit_task(course, "parse", {"mode":"fixture"}, "source-policy-fixture-parse")
    finish_task(claim_task(parse.id), {"mode":"fixture", "parse_version_id":str(evidence.parse_version_id)})
    evidence.material_version.task = parse
    evidence.material_version.save(update_fields=["task"])
    draft = GenerationDraft.objects.get(course=course)
    planning = submit_plan(course.owner, course.id, draft.revision, build_context(draft)["context_hash"], "source-policy-plan")
    run_planning(claim_task(planning.id))
    draft.refresh_from_db()
    confirm_structure(course.owner, course.id, draft.blueprint_id, draft.revision,
                      draft.blueprint.revision, draft.config_hash, "source-policy-confirm")
    draft.refresh_from_db()
    context = prepare_generation(course.owner, course.id, draft.confirmation_id, draft.revision,
                                 draft.config_hash, "source-policy-preflight")
    assert context["mode"] == "fixture"
    task = submit_generation(course.owner, course.id, draft.confirmation_id, draft.revision,
                             draft.config_hash, context["context_hash"], "source-policy-demo")
    def sample(q):
        data = fixture_pair(q)
        if q["number"] == 1:
            data["pair"]["evidence_ids"].append("unresolved-context-example")
            data["pair"]["background_references"] = [
                {"label":"Synthetic business setting", "evidence_id":None,
                 "url":"https://example.com/", "note":"Illustrative context from outside the course. This fixture does not verify an external source."},
                {"label":"Local teaching page used as context", "evidence_id":result["source_id"],
                 "url":None, "note":"Background role remains separate from the teaching-evidence role."}]
        return data
    with patch("app.generation.generator.fixture_pair", side_effect=sample):
        run_generation(claim_task(task.id))
    task.refresh_from_db()
    assert task.state == "succeeded", task.error
    assert task.model_calls.count() == 0
    result.update(task_id=str(task.id), material_version_id=str(evidence.material_version_id),
                  task_url="http://127.0.0.1:5173/tasks/"+str(task.id), new_model_calls=0)
    return result


if __name__ == "__main__":
    result = create()
    (ROOT/"var/source-policy-fixture.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))
