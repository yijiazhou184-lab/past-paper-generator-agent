"""Wire-schema compatibility, separate from permissive legacy payload loading."""
from app.courses.schemas import AnalysisOutput,CourseDraftPayload
from app.ai.contracts import ModelCallSpec
from app.ai.responses import request_body
from test_course_analysis import course_payload


def test_course_analysis_wire_requires_every_property_and_has_no_defaults():
    spec=ModelCallSpec(stage="course_analysis",prompt_version="test",schema_version="test",context_hash="test",input={})
    schema=request_body(spec,"Synthetic",AnalysisOutput,"gpt-6.1-sol")["text"]["format"]["schema"]
    def inspect(value):
        if isinstance(value,dict):
            assert "default" not in value
            if value.get("type")=="object":
                assert value.get("additionalProperties") is False
                assert set(value.get("required",[]))==set(value.get("properties",{}))
            for child in value.values():inspect(child)
        elif isinstance(value,list):
            for child in value:inspect(child)
    inspect(schema)


def test_wire_strictness_keeps_legacy_loading_defaults(course_payload):
    loaded=CourseDraftPayload.model_validate(course_payload)
    assert loaded.knowledge_nodes[0].node_kind=="objective"
    out=AnalysisOutput.model_validate({"status":"complete","explanation":"Synthetic legacy fixture","draft":course_payload,"visual_review_requests":[]})
    assert out.draft.knowledge_nodes[0].node_kind=="objective"
