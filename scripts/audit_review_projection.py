"""Read-only replay of saved generation inputs. Does not call the API or change historical tasks."""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.db import connection,transaction
from app.core.models import Task,ModelInvocation
from app.core.idempotency import digest
from app.generation.reviewer import blind_input
from app.generation.checks import program_checks,mathematical_checks,check
from app.generation.duplicates import duplicate_candidates
from app.generation.source_policy import source_review_input
from app.generation.review_input import build_review_input

def audit(task_id):
    with transaction.atomic():
        with connection.cursor() as cursor:cursor.execute("SET TRANSACTION READ ONLY")
        before=ModelInvocation.objects.count()
        task=Task.objects.get(pk=task_id,kind="generation")
        candidate=task.candidates.order_by("-revision").first()
        assert candidate and digest(candidate.payload)==candidate.payload_hash
        context=task.snapshot
        pairs=candidate.payload["pairs"]
        program=program_checks(context,candidate.payload)
        math=mathematical_checks(pairs)
        local=program+math
        blind=[]
        for pair in pairs:
            data=blind_input(context,pair,candidate.payload["assets"])
            artifact=task.generation_artifacts.get(key="blind:"+digest(data)[:48])
            assert digest(artifact.payload)==artifact.payload_hash
            output=artifact.payload
            available=output["status"]=="complete" and sorted(a["part_id"] for a in output["answers"])==sorted(p["part_id"] for p in pair["parts"])
            local.append(check("blind_available:"+pair["question_id"],[pair["question_id"]],"blind_solver","pass" if available else "inconclusive",
                               "Independent solution returned for every part." if available else output["explanation"] or "Blind solution missing parts."))
            generated={a["part_id"]:a["final_answer"] for a in pair["answers"]}
            blind.append({"question_id":pair["question_id"],"output":output,
                          "comparison":[{"part_id":a["part_id"],"exact_match":digest(a["final_answer"])==digest(generated.get(a["part_id"]))} for a in output["answers"]]})
        sources=[s for s in context["input"]["sources"] if s["id"] in context["input"]["comparison_source_ids"]]
        duplicates=duplicate_candidates(pairs,sources,context["input"]["history_content_ids"])
        assert not duplicates["findings"] and duplicates["candidates"], "This audit expects a completed local retrieval without exact duplicates."
        local.append(check("local_duplicates",[p["question_id"] for p in pairs],"normalised_retrieval","pass",
                           "No exact or number-only match in the supplied comparison and within this candidate; semantic review is still required."))
        old={"candidate":candidate.payload,"blueprint":context["input"]["blueprint"],"course":context["input"]["course"],
             "user_preferences":context["input"]["statements"],"config":context["input"]["config"],"local_checks":local,
             "blind_solutions":blind,"duplicate_comparison":duplicates,"source_review":source_review_input(context,pairs)}
        ids=[p["question_id"] for p in pairs]
        new=build_review_input(context,candidate.payload,local,blind,duplicates,ids)
        chars=lambda value:len(json.dumps(value,ensure_ascii=False))
        wire=lambda value:len(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")))
        count=task.model_calls.get(call_key="count:r0:semantic")
        result={"task_id":str(task.id),"candidate_id":str(candidate.id),"mode":"offline_replay",
                "historical_error":task.error,"historical_input_tokens":count.result["payload"]["input_tokens"],
                "old_input_hash_matches":digest({"context_hash":context["context_hash"],"stage":"semantic_review","input":old})==count.metadata["context_hash"],
                "original_input_chars":chars(old),"compact_input_chars":wire(new),
                "input_char_reduction_percent":round(100*(1-wire(new)/chars(old)),2),
                "compact_section_chars":{k:wire(v) for k,v in new.items()},
                "single_question_chars":{qid:wire(build_review_input(context,candidate.payload,local,blind,duplicates,[qid])) for qid in ids},
                "paper_check_chars":wire(build_review_input(context,candidate.payload,local,blind,duplicates,ids,"paper")),
                "program_results":dict(Counter(c["result"] for c in program)),"math_results":dict(Counter(c["result"] for c in math)),
                "new_official_token_count":None,"new_semantic_review":"not_executed","new_model_calls":ModelInvocation.objects.count()-before,
                "note":"Character sizes are not token counts. Old record unchanged; no complete live validation is claimed."}
        return result

if __name__=="__main__":
    result=audit(sys.argv[1])
    destination=ROOT/"var"/("review-projection-"+result["task_id"]+".json")
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,indent=2))
