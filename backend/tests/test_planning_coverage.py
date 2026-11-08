"""Part-level targets are the sole source of new planning coverage."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from unittest.mock import patch
import pytest
from pydantic import ValidationError
from app.core.errors import DomainError
from app.generation.schemas import PlanningOutput, validate_blueprint
from test_blueprint_rules import blueprint_inputs
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft
from test_generation_snapshot import version, config


def provider_payload(full):
    raw=copy.deepcopy(full)
    raw.pop("coverage")
    for q in raw["questions"]:
        q.pop("knowledge_ids")
    return raw


def test_model_contract_has_part_targets_but_no_aggregate_targets():
    schema=PlanningOutput.model_json_schema()
    plan=schema["$defs"]["PlanningBlueprintPayload"]["properties"]
    question=schema["$defs"]["PlanningQuestion"]["properties"]
    assert "coverage" not in plan and "knowledge_ids" not in question
    assert "knowledge_ids" in schema["$defs"]["Part"]["required"]


def test_model_cannot_supply_conflicting_aggregate_fields(blueprint_inputs):
    full=blueprint_inputs[1]
    with pytest.raises(ValidationError):
        PlanningOutput.model_validate({"status":"complete","explanation":"","blueprint":full})


def test_coverage_is_stable_deduplicated_and_does_not_mutate_input(blueprint_inputs):
    from app.generation.schemas import materialize_planning_blueprint
    config,full,course,evidence=blueprint_inputs
    raw=provider_payload(full)
    raw["questions"][0]["parts"][0]["knowledge_ids"]=["K2","K1","K2"]
    before=copy.deepcopy(raw)
    result=materialize_planning_blueprint(raw)
    assert raw==before
    assert result["questions"][0]["knowledge_ids"]==["K1","K2","K3"]
    assert result["coverage"]==[{"knowledge_id":k,"question_ids":["q1","q2"]} for k in ["K1","K2","K3"]]
    assert validate_blueprint(config,result,course,evidence)["coverage"]==result["coverage"]


@pytest.mark.parametrize("damage,code",[
    (lambda p:p["questions"][0]["parts"][0].update(knowledge_ids=["foreign"]),"KNOWLEDGE_OUTSIDE_SELECTION"),
    (lambda p:[q["parts"][2].update(knowledge_ids=["K1"]) for q in p["questions"]],"SELECTED_KNOWLEDGE_MISSING"),
    (lambda p:p["questions"][0].update(evidence_ids=["history"]),"KNOWLEDGE_EVIDENCE_MISSING"),
])
def test_derived_summary_does_not_bypass_scope_or_evidence(blueprint_inputs,damage,code):
    from app.generation.schemas import materialize_planning_blueprint
    config,full,course,evidence=blueprint_inputs
    raw=provider_payload(full)
    evidence.append({"id":"history","roles":["past_paper"]})
    damage(raw)
    with pytest.raises(DomainError,match=code):
        validate_blueprint(config,materialize_planning_blueprint(raw),course,evidence)


def test_edit_recalculates_stale_summaries_but_frozen_validation_stays_strict(blueprint_inputs):
    config,full,course,evidence=blueprint_inputs
    full["questions"][0]["knowledge_ids"]=["K1"]
    full["coverage"]=[]
    before=copy.deepcopy(full)
    with pytest.raises(DomainError,match="QUESTION_COVERAGE_MISMATCH"):
        validate_blueprint(config,full,course,evidence)
    result=validate_blueprint(config,full,course,evidence,recalculate=True)
    assert result["questions"][0]["knowledge_ids"]==["K1","K2","K3"]
    assert len(result["coverage"])==3 and full==before


@pytest.mark.parametrize(("references", "teaching_available", "expected_error"), [
    (["e1"], True, None),
    (["e3"], True, None),
    (["e3"], False, "SELECTED_KNOWLEDGE_NOT_READY"),
    (["foreign-source"], True, "EVIDENCE_REFERENCE_INVALID"),
])
def test_new_planning_output_is_expanded_before_normal_publication(
    course, config, monkeypatch, references, teaching_available, expected_error
):
    from app.ai.contracts import ModelCallResult
    from app.core.tasks import claim_task
    from app.generation.fixtures import fixture_blueprint
    from app.generation.models import Blueprint
    from app.generation.planning import build_context,submit_plan,run_planning
    from app.generation.snapshots import save_config
    saved,_=save_config(course.owner,course.id,0,config,"part-config")
    context=build_context(saved);context["mode"]="live"
    assert context["schema_version"]=="planning-v3-part-coverage"
    assert context["blueprint_schema_version"]=="blueprint-v2"
    full=fixture_blueprint(config,context["input"]["course"])
    raw = provider_payload(full)
    raw["questions"][0]["evidence_ids"] = references
    if not teaching_available:
        next(source for source in context["input"]["evidence"] if source["id"] == "e1")["roles"] = ["past_paper"]
    before = copy.deepcopy(raw)
    result=ModelCallResult(mode="fixture",status="parsed",payload={"status":"complete","explanation":"","blueprint":raw})
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-test-key-not-real")
    with patch("app.generation.planning.build_context",return_value=context):
        task=submit_plan(course.owner,course.id,saved.revision,context["context_hash"],"part-plan",authorize=True)
    with patch("app.generation.planning.run_call", return_value=result) as call:
        token = claim_task(task.id)
        if expected_error:
            with pytest.raises(DomainError, match=expected_error):
                run_planning(token)
        else:
            run_planning(token)
    assert call.call_count == 1 and raw == before
    if expected_error:
        assert not Blueprint.objects.filter(task=task).exists()
        return
    task.refresh_from_db()
    assert task.state == "succeeded"
    stored = Blueprint.objects.get(task=task)
    assert stored.payload["questions"][0]["knowledge_ids"] == ["K1"]
    assert stored.payload["questions"][0]["evidence_ids"] == list(dict.fromkeys([*references, "e1"]))
    assert stored.payload["questions"][1:] == full["questions"][1:]
    assert stored.payload["coverage"] == full["coverage"]


def test_matrix_allows_model_distribution_and_checks_whole_paper(blueprint_inputs):
    from evals.round1.run import check_matrix
    full=blueprint_inputs[1]
    run={"question_count":2,"parts":[3,3],"marks":[9,9],"minutes":30,
         "knowledge":["A","B","C"],"question_knowledge":[["A"],["B","C"]]}
    mapping={"A":"K1","B":"K2","C":"K3"}
    check_matrix(full,run,mapping)
    damaged=copy.deepcopy(full)
    for q in damaged["questions"]:
        for part in q["parts"]:
            part["knowledge_ids"]=["K1"]
    with pytest.raises(ValueError,match="whole-paper knowledge"):
        check_matrix(damaged,run,mapping)
