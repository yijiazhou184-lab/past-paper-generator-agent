import pytest
from app.courses.decisions import effective_statements
from app.courses.models import UserStatement


def add(course,text,decision=None,question="Choice"):
    return UserStatement.objects.create(course=course,text=text,kind="clarification",source="User choice",
        question=question,clarification_id="question",submitted_by=course.owner,decision=decision or {})


def test_effective_input_omits_superseded_text_without_deleting_history(course):
    first=add(course,"Old convention")
    last=add(course,"New convention",{"key":"policy","definition_hash":"v1","requires_analysis":False,"supersedes":[str(first.id)]})
    active=effective_statements(course)
    assert [s["text"] for s in active]==["New convention"]
    assert UserStatement.objects.filter(course=course).count()==2


def test_unrelated_scope_decisions_are_not_removed(course):
    a=add(course,"Topic A",{"key":"a","requires_analysis":False})
    b=add(course,"Topic B",{"key":"b","requires_analysis":False})
    assert {s["id"] for s in effective_statements(course)}=={str(a.id),str(b.id)}


def test_consumed_legacy_answer_no_longer_displays_pending(course):
    from types import SimpleNamespace
    from app.courses.decisions import attach_answers
    s=add(course,"User answer")
    draft=SimpleNamespace(machine_base=SimpleNamespace(context={"statements":[{"id":str(s.id)}]}),
        clarification_answers={"q":{"text":"User answer","statement_id":str(s.id),"reanalysis_required":True}})
    questions=[{"id":"q","question":"Choice","impact":"needs_confirmation","status":"open","suggested_answers":[]}]
    attach_answers(questions,draft,effective_statements(course),[])
    assert questions[0]["answer"]["application_status"]=="applied"
    assert questions[0]["answer"]["reanalysis_required"] is False
