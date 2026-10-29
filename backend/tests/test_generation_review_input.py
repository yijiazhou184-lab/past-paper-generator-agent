import copy
import pytest
from app.generation.review_input import compact_expression, build_review_input
from app.generation.content_fixtures import num,var,op,fixture_pair,fixture_blind
from app.generation.duplicates import duplicate_candidates
from test_generation_preflight import prepare
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_expression_projection_preserves_tree_and_domain_holes():
    assert compact_expression(op("div",var(),var())) == "(x / x)"
    assert compact_expression(op("sub",num(1),op("sub",num(2),num(3)))) == "(1 - (2 - 3))"
    assert compact_expression(op("add",num(1),num(2),num(3))) == "(1 + 2 + 3)"
    assert compact_expression(op("abs",var())) == "abs(x)"
    with pytest.raises(ValueError):
        compact_expression({"op":"execute","value":"unsafe","args":[]})


def test_review_projection_is_lossless_for_checks_and_deduplicates_sources(course,planned):
    _,context=prepare(course,planned)
    q=context["input"]["questions"][0]["blueprint"]
    pair=fixture_pair(q)["pair"]
    source=next(s for s in context["input"]["sources"] if s["id"] in pair["evidence_ids"])
    source["content"]="Differentiation evidence. "*180
    source["material_version_id"]="fixed-version"
    source["physical_page"]=14
    duplicates=duplicate_candidates([pair],[source],[])
    payload={"pairs":[pair],"assets":[]}
    before=copy.deepcopy((context,payload,duplicates))
    data=build_review_input(context,payload,[],[],duplicates,[q["id"]])
    assert (context,payload,duplicates)==before
    checks=data["candidate"]["pairs"][0]["answers"][0]["checks"]
    assert checks[0]["expression"]=="(x ^ 2)"
    assert checks[0]["domain"]==pair["answers"][0]["checks"][0]["domain"]
    assert checks[0]["expected"]=="(2 * x)"
    evidence=next(e for e in data["evidence"] if e["id"]==source["id"])
    assert evidence["material_version_id"]=="fixed-version" and evidence["physical_page"]==14
    assert any(set(f["purposes"])=={"academic","comparison"} for f in evidence["fragments"])
    assert "text" not in data["duplicate_comparison"]["candidates"][0]
    assert "svg" not in str(data)
    assert data["required_categories"] and data["include_paper_check"]


def test_group_projection_keeps_only_target_blind_solutions_and_knowledge(course,planned):
    _,context=prepare(course,planned)
    pairs=[fixture_pair(q["blueprint"])["pair"] for q in context["input"]["questions"]]
    blind=[{"question_id":p["question_id"],"output":{"answers":[]},"comparison":[]} for p in pairs]
    data=build_review_input(context,{"pairs":pairs,"assets":[]},[],blind,duplicate_candidates(pairs,[],[]),[pairs[0]["question_id"]])
    assert len(data["candidate"]["pairs"])==len(data["blind_solutions"])==1
    assert not data["include_paper_check"]
    assert len(data["other_question_summaries"])==len(pairs)-1


def test_unsupported_check_retains_original_ast_for_diagnosis():
    from app.generation.review_input import compact_pair
    raw=op("sub",var())
    pair={"answers":[{"checks":[{"expression":raw,"expected":num(1),"denominator":None,"domain":{"lower":"0"}}]}]}
    before=copy.deepcopy(pair)
    projected=compact_pair(pair)
    assert pair==before
    spec=projected["answers"][0]["checks"][0]
    assert spec["expression"]==raw and spec["projection_warnings"]
    assert spec["expected"]=="1" and spec["domain"]=={"lower":"0"}
