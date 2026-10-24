from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.middleware.csrf import get_token
from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from app.courses.models import Course
from .models import Task
from .tasks import cancel_task, submit_task
from .errors import DomainError


from .schemas import SessionSchema, CoursesSchema, TasksSchema, TaskSchema


def task_view(task, include_calls=False):
    elapsed = ((task.finished_at or timezone.now()) - task.created_at).total_seconds()
    calls = []
    if include_calls:
        for call in task.model_calls.order_by("created_at"):
            result = call.result
            source = call.metadata.get("source")
            calls.append({"id": str(call.id), "key": call.call_key, "state": call.state,
                "status": result.get("status", "outcome_not_recorded"),
                "mode": result.get("mode", call.metadata.get("mode", "unknown")),
                "model": result.get("model") or call.metadata.get("model"),
                "elapsed_seconds": result.get("elapsed_seconds"), "usage": result.get("usage", {}),
                "error_code": result.get("error_code"), "payload": None if task.kind == "generation" else result.get("payload"),
                "source_url": f'/courses/{task.course_id}/materials?source={source["evidence_id"]}' if source else None})
    return {"id": str(task.id), "course_id": str(task.course_id), "kind": task.kind,
            "state": task.state, "stage": task.stage, "elapsed_seconds": round(elapsed, 1),
            "target_exceeded": task.kind in ("analysis", "planning", "generation") and elapsed > 120, "created_at": task.created_at,
            "started_at": task.started_at, "finished_at": task.finished_at,
            "heartbeat_at": task.heartbeat_at, "epoch": task.execution_epoch,
            "result": task.result, "error": task.error, "checkpoint": task.checkpoint,
            "parent_id": str(task.parent_id) if task.parent_id else None,
            "events": list(task.events.order_by("created_at").values("stage", "created_at", "detail")),
            "model_calls": calls}


class SessionView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=SessionSchema)
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0].split(",")[0]
        return Response({"authenticated": request.user.is_authenticated, "csrf_token": get_token(request),
                         "local_access": settings.LOCAL_ACCESS,
                         "database": db_version, "batch": 4, "model_mode": "scoped_consent",
                         "course_data_upload": False})

    @extend_schema(request=None, responses=SessionSchema)
    def post(self, request):
        from rest_framework.authentication import SessionAuthentication
        SessionAuthentication().enforce_csrf(request)
        if not settings.LOCAL_ACCESS or request.META.get("REMOTE_ADDR") not in ("127.0.0.1", "::1"):
            raise DomainError("LOCAL_ACCESS_DISABLED", status=403)
        owner = get_user_model().objects.get(username="local")
        login(request, owner, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"authenticated": True, "csrf_token": get_token(request)})


class CoursesView(APIView):
    @extend_schema(responses=CoursesSchema)
    def get(self, request):
        return Response({"courses": list(Course.objects.filter(owner=request.user).order_by("created_at").values(
            "id", "title", "code", "scope_statement", "scope_provenance"))})


class TasksView(APIView):
    @extend_schema(responses=TasksSchema)
    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        return Response({"tasks": [task_view(t) for t in Task.objects.filter(course=course).order_by("-created_at")[:30]]})


class TaskView(APIView):
    @extend_schema(responses=TaskSchema)
    def get(self, request, task_id):
        return Response(task_view(get_object_or_404(Task, pk=task_id, course__owner=request.user), include_calls=True))


class CancelView(APIView):
    @extend_schema(request=None, responses=TaskSchema)
    def post(self, request, task_id):
        return Response(task_view(cancel_task(request.user, task_id)))


class RetryView(APIView):
    @extend_schema(request=None, responses={202: TaskSchema})
    def post(self, request, task_id):
        original = get_object_or_404(Task.objects.select_related("course"), pk=task_id, course__owner=request.user)
        if original.state not in ("failed", "cancelled"):
            raise DomainError("TASK_NOT_RETRYABLE")
        if original.kind == "ai_validation":
            raise DomainError("LIVE_VALIDATION_COMMAND_REQUIRED",
                              "Review the saved model calls before starting another paid validation run.")
        if original.kind in ("planning", "generation"):
            raise DomainError("PLANNING_REVIEW_REQUIRED", "Return to Generate, review the current configuration and start a new plan. The previous task is preserved.")
        task = submit_task(original.course, original.kind, original.snapshot,
                           request.headers.get("Idempotency-Key"), parent=original)
        if task.kind == "parse":
            from app.materials.models import MaterialVersion
            MaterialVersion.objects.filter(pk=task.snapshot["material_version_id"]).update(task=task)
        return Response(task_view(task), status=202)
