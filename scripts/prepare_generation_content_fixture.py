"""Create an isolated batch-4 course with confirmed synthetic structure; no external model calls."""
import json
from prepare_generation_browser_fixture import prepare, ROOT
from app.courses.models import Course
from app.generation.models import GenerationDraft
from app.generation.planning import build_context,submit_plan,run_planning
from app.generation.snapshots import confirm_structure
from app.core.tasks import claim_task, submit_task, finish_task
from app.materials.models import Evidence

result=prepare()
course=Course.objects.get(pk=result["course_id"])
course.code="B4-FIXTURE"
course.title="Topic 2 generation — synthetic development fixture"
course.save(update_fields=["code","title"])
# Give the prebuilt synthetic parse an explicit terminal task, so its source viewer does not imply a pending real parse.
evidence=Evidence.objects.select_related("material_version","parse_version").get(pk=result["source_id"])
parse_task=submit_task(course,"parse",{"mode":"fixture","note":"Prebuilt synthetic PDF and parse"},"batch4-fixture-source")
finish_task(claim_task(parse_task.id),{"mode":"fixture","parse_version_id":str(evidence.parse_version_id)})
evidence.material_version.task=parse_task
evidence.material_version.save(update_fields=["task"])
result["material_version_id"]=str(evidence.material_version_id)
draft=GenerationDraft.objects.get(course=course)
task=submit_plan(course.owner,course.id,draft.revision,build_context(draft)["context_hash"],"batch4-fixture-plan")
run_planning(claim_task(task.id))
draft.refresh_from_db()
confirm_structure(course.owner,course.id,draft.blueprint_id,draft.revision,draft.blueprint.revision,draft.config_hash,"batch4-fixture-confirm")
(ROOT/"var/batch4-browser-fixture.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
