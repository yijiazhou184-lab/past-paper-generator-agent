"""Question-only projection by default; answers and potentially revealing reports require an explicit request."""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from app.core.models import Task
from .models import CandidateVersion,CheckReport


class GenerationContentSchema(serializers.Serializer):
    mode=serializers.CharField()
    candidates=serializers.ListField(child=serializers.JSONField())


class GenerationAnswerSchema(serializers.Serializer):
    candidate_id=serializers.UUIDField()
    answers=serializers.ListField(child=serializers.JSONField())
    report=serializers.JSONField(allow_null=True)
    assets=serializers.ListField(child=serializers.JSONField())
    model_outputs=serializers.ListField(child=serializers.JSONField())


class GenerationContentView(APIView):
    @extend_schema(responses=GenerationContentSchema)
    def get(self,request,task_id):
        task=get_object_or_404(Task,pk=task_id,course__owner=request.user,kind="generation")
        sources={s["id"]:s for s in task.snapshot["input"]["sources"]}
        candidates=[]
        for c in task.candidates.order_by("revision"):
            report=CheckReport.objects.filter(candidate=c).first()
            pairs=[{k:p[k] for k in ("question_id","stem","parts","asset_ids","evidence_ids")} for p in c.payload["pairs"]]
            refs={b["asset_id"] for p in pairs for b in p["stem"]+[b for part in p["parts"] for b in part["prompt"]] if b["type"]=="asset_ref"}
            evidence={eid for p in pairs for eid in p["evidence_ids"]}
            candidates.append({"id":str(c.id),"revision":c.revision,"parent_id":str(c.parent_id) if c.parent_id else None,
                "mode":c.mode,"stage":c.stage,"payload_hash":c.payload_hash,"pairs":pairs,
                "assets":[{"id":a["id"],"svg":a["svg"],"alt":a["alt"]} for a in c.payload["assets"] if a["id"] in refs],
                "sources":[{k:sources[e][k] for k in ("id","material_code","material_version_id","physical_page") if k in sources[e]} for e in sorted(evidence)],
                "report": {"gate":report.gate,"coverage_summary":report.payload["coverage_summary"],
                           "checks":[{k:v for k,v in check.items() if k!="rationale"} for check in report.payload["checks"]]}
                          if report else None})
        return Response({"mode":task.snapshot["mode"],"candidates":candidates})


class GenerationAnswersView(APIView):
    @extend_schema(responses=GenerationAnswerSchema)
    def get(self,request,task_id,candidate_id):
        candidate=get_object_or_404(CandidateVersion,pk=candidate_id,task_id=task_id,task__course__owner=request.user)
        report=CheckReport.objects.filter(candidate=candidate).first()
        return Response({"candidate_id":str(candidate.id),
            "answers":[{"question_id":p["question_id"],"marking_basis":p["marking_basis"],
                        "answers":p["answers"]} for p in candidate.payload["pairs"]],
            "report":report.payload if report else None,
            "assets":[{"id":a["id"],"svg":a["svg"],"alt":a["alt"]} for a in candidate.payload["assets"]],
            "model_outputs":[{"key":c.call_key,"state":c.state,"result":c.result} for c in candidate.task.model_calls.order_by("created_at")]})
