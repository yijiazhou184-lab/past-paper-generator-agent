import copy
from app.core.idempotency import digest
from app.core.models import ModelInvocation
from app.generation.generator import generate_groups,persist_candidate
from app.generation.models import CheckReport
from test_generation_execution import start
from test_generation_snapshot import version,config,planned
from test_course_analysis import course_payload,analysis_context
from test_course_drafts import draft


def test_answers_are_separate_and_cross_course_is_denied(course,planned,client,django_user_model):
    task,context,token=start(course,planned)
    groups=generate_groups(token,context)
    groups[0]["pair"]["answers"][0]["final_answer"]=[{"type":"text","text":"ANSWER-ONLY-SECRET"}]
    candidate=persist_candidate(token,context,groups)
    payload={"checks":[{"rationale":"ANSWER-ONLY-SECRET"}],"coverage_summary":{"required":1,"passed":0,"failed":1,"not_checked":0,"inconclusive":0}}
    CheckReport.objects.create(candidate=candidate,payload=payload,payload_hash=digest(payload),
                               gate={"allowed":False,"blocking_check_ids":["math"]})
    ModelInvocation.objects.create(task=task,call_key="raw",epoch=token.epoch,request_hash="x"*64,
        state="completed",result={"payload":{"answer":"ANSWER-ONLY-SECRET"}})
    client.force_login(course.owner)
    url=f"/api/v1/tasks/{task.id}/generation-content"
    response=client.get(url)
    assert response.status_code==200
    assert "ANSWER-ONLY-SECRET" not in str(response.json())
    assert "ANSWER-ONLY-SECRET" not in str(client.get(f"/api/v1/tasks/{task.id}").json())
    answers=client.get(url+f"/{candidate.id}/answers")
    assert answers.status_code==200
    assert "ANSWER-ONLY-SECRET" in str(answers.json())
    client.force_login(django_user_model.objects.create_user(username="other"))
    assert client.get(url).status_code==404
    assert client.get(url+f"/{candidate.id}/answers").status_code==404


def test_references_are_separate_and_unknown_ids_do_not_break_preview(course, planned, client):
    task, context, token = start(course, planned)
    groups = generate_groups(token, context)
    pair = groups[0]["pair"]
    pair["evidence_ids"] += ["unknown", "unknown"]
    pair["background_references"] = [{"label":"ANSWER-ONLY-BACKGROUND", "evidence_id":pair["evidence_ids"][0],
                                      "url":"https://example.com/context", "note":"ANSWER-ONLY-SECRET"}]
    candidate = persist_candidate(token, context, groups)
    client.force_login(course.owner)
    url = f"/api/v1/tasks/{task.id}/generation-content"
    preview = client.get(url)
    assert preview.status_code == 200
    assert "ANSWER-ONLY" not in str(preview.json())
    summary = preview.json()["candidates"][0]["pairs"][0]["source_summary"]
    assert summary["background_count"] == 1
    assert summary["duplicate_count"] == 1
    assert summary["academic"][-1] == {"id":"unknown","status":"unresolved"}
    details = client.get(url+f"/{candidate.id}/answers").json()
    assert details["answers"][0]["background_references"][0]["note"] == "ANSWER-ONLY-SECRET"
    assert details["reference_sources"][0]["id"] == pair["evidence_ids"][0]
