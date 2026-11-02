from django.core import signing
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.core.errors import DomainError
from app.courses.models import Course
from app.generation.content_api import GenerationAnswerSchema
from .models import Paper, PDFArtifact
from .publication import submit_export, assert_integrity
from .reader import paper_topics, paper_summary, question_view, answer_view
from .schemas import PapersSchema, PaperContentSchema, ExportSchema, PaperSchema
from .storage import valid_artifact, artifact_path


def owned_paper(owner, paper_id):
    return get_object_or_404(Paper.objects.select_related("content__candidate", "latest_export"), pk=paper_id, course__owner=owner)


class PapersView(APIView):
    @extend_schema(responses=PapersSchema)
    def get(self, request, course_id):
        get_object_or_404(Course, pk=course_id, owner=request.user)
        qs = Paper.objects.filter(course_id=course_id).select_related("content", "latest_export").order_by("-created_at", "-id")
        cursor = request.query_params.get("cursor")
        if cursor:
            try:
                data = signing.loads(cursor, salt="paper-list")
                if data["course"] != str(course_id) or data.get("topic") != request.query_params.get("topic"): raise ValueError()
                qs = qs.filter(Q(created_at__lt=data["time"]) | Q(created_at=data["time"], id__lt=data["id"]))
            except (signing.BadSignature, KeyError, ValueError):
                raise DomainError("INVALID_CURSOR", status=400)
        topic_id=request.query_params.get("topic")
        if topic_id:
            from rest_framework import serializers
            topic_id=str(serializers.UUIDField().run_validation(topic_id))
            from app.courses.models import Topic
            get_object_or_404(Topic,pk=topic_id,course_id=course_id)
            items=[]
            for paper in qs.iterator(chunk_size=20):
                if any(t["topic_id"]==topic_id for t in paper_topics(paper)):
                    items.append(paper)
                if len(items)==21:break
        else:
            items = list(qs[:21])
        next_cursor = signing.dumps({"course": str(course_id), "topic":request.query_params.get("topic"), "time": items[19].created_at.isoformat(), "id": str(items[19].id)}, salt="paper-list") if len(items) > 20 else None
        return Response({"papers": [paper_summary(p) for p in items[:20]], "next_cursor": next_cursor})


class TaskPaperView(APIView):
    @extend_schema(responses=PaperSchema)
    def get(self, request, task_id):
        paper = get_object_or_404(Paper.objects.select_related("content", "latest_export"), generation_task_id=task_id, course__owner=request.user)
        return Response(paper_summary(paper))


class PaperView(APIView):
    @extend_schema(responses=PaperContentSchema)
    def get(self, request, paper_id):
        paper = owned_paper(request.user, paper_id)
        return Response({"paper": paper_summary(paper), "candidate": question_view(paper)})


class AnswersView(APIView):
    @extend_schema(responses=GenerationAnswerSchema)
    def get(self, request, paper_id):
        return Response(answer_view(owned_paper(request.user, paper_id)))


class ExportsView(APIView):
    @extend_schema(request=None, responses={202: ExportSchema})
    def post(self, request, paper_id):
        paper, task = submit_export(request.user, paper_id, request.headers.get("Idempotency-Key"))
        return Response({"paper_id": str(paper.id), "task_id": str(task.id) if task else None}, status=202)


class DownloadView(APIView):
    @extend_schema(responses={(200, "application/pdf"): bytes})
    def get(self, request, paper_id, kind):
        paper = owned_paper(request.user, paper_id)
        assert_integrity(paper.content)
        artifact = get_object_or_404(PDFArtifact, content=paper.content, kind=kind)
        if not valid_artifact(artifact):
            raise DomainError("PDF_UNAVAILABLE", "This file is unavailable. Retry PDF export to restore the same content.", status=409, retryable=True)
        filename = ("question-paper" if kind == "questions" else "mark-scheme") + f"-{str(paper.content_id)[:8]}.pdf"
        response = FileResponse(artifact_path(artifact).open("rb"), content_type="application/pdf", as_attachment=True, filename=filename)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
