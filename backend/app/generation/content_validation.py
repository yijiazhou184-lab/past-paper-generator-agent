import copy
from collections import Counter
from pydantic import ValidationError
from app.core.errors import DomainError
from .content_schemas import PairOutput
from .assets import render_graph


def unique(items):
    items = list(items)
    return len(items) == len(set(items))


def validate_group(question, output, context):
    output=copy.deepcopy(output)
    if isinstance(output.get("pair"),dict):
        output["pair"].setdefault("background_references",[])  # Read old artifacts without rewriting them.
    try:
        data=PairOutput.model_validate(output).model_dump(mode="json")
    except ValidationError:
        raise DomainError("PAIR_SCHEMA_INVALID", "The returned question or answer did not match the content contract.") from None
    if data["status"] != "complete" or data["pair"] is None:
        raise DomainError("GENERATION_NEEDS_INFO", data["explanation"] or "Question generation needs more information.")
    pair=data["pair"]
    def require(condition, code):
        if not condition:
            raise DomainError(code, "The question and answer group did not pass structural validation.")
    require(pair["question_id"] == question["id"], "QUESTION_ID_MISMATCH")
    ids=[p["id"] for p in question["parts"]]
    require([p["part_id"] for p in pair["parts"]] == ids, "QUESTION_PARTS_MISMATCH")
    require(Counter(a["part_id"] for a in pair["answers"]) == Counter(ids), "ANSWER_PAIRING_INVALID")
    # Source scope is assessed in the saved report, not an early structural abort.
    # Preserve unresolved/extra references for diagnosis and the bounded repair round.
    # This round has no official part-by-part rubric attached to the confirmed blueprint.
    require(pair["marking_basis"] == "suggested", "OFFICIAL_MARKING_UNSUPPORTED")
    answers={a["part_id"]:a for a in pair["answers"]}
    asset_ids=[a["id"] for a in data["assets"]]
    require(unique(asset_ids) and unique(pair["asset_ids"]) and set(asset_ids)==set(pair["asset_ids"]), "ASSET_REFERENCE_INVALID")
    for expected, part in zip(question["parts"],pair["parts"]):
        require(part["marks"] == expected["marks"] and part["response_type"] == expected["response_type"]
                and set(part["knowledge_ids"]) == set(expected["knowledge_ids"])
                and unique(part["knowledge_ids"]), "PART_BLUEPRINT_MISMATCH")
        a=answers[part["part_id"]]
        points=a["marking_points"]
        require(unique(p["id"] for p in points), "DUPLICATE_MARKING_POINT")
        independent=sum(p["marks"] for p in points if p["alternative_group"] is None)
        groups={}
        for p in points:
            if p["alternative_group"] is not None:
                require(bool(p["alternative_group"].strip()), "EMPTY_ALTERNATIVE_GROUP")
                groups[p["alternative_group"]]=max(groups.get(p["alternative_group"],0),p["marks"])
        require(independent+sum(groups.values()) == part["marks"], "MARKING_TOTAL_MISMATCH")
        require(all(c["part_id"]==part["part_id"] for c in a["checks"]) and unique(c["id"] for c in a["checks"]), "MATH_CHECK_TARGET_INVALID")
        blocks=pair["stem"]+part["prompt"]+a["worked_solution"]+a["final_answer"]
        for b in blocks:
            if b["type"] == "asset_ref":
                require(b["asset_id"] in asset_ids, "ASSET_REFERENCE_INVALID")
            if b["type"] == "table":
                require(all(len(row)==len(b["columns"]) for row in b["rows"]), "TABLE_SHAPE_INVALID")
        visible=pair["stem"]+part["prompt"]
        if "function_graph" in expected["asset_needs"]:
            require(any(b["type"]=="asset_ref" for b in visible), "REQUIRED_GRAPH_MISSING")
        if "data_table" in expected["asset_needs"]:
            require(any(b["type"]=="table" for b in visible), "REQUIRED_TABLE_MISSING")
    try:
        rendered=[render_graph(a) for a in data["assets"]]
    except (ValidationError,ValueError,TypeError):
        raise DomainError("ASSET_INVALID", "The graph description is unsafe or outside supported bounds.") from None
    return {"pair":pair,"assets":rendered}
