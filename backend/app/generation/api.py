import os
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.core.api import task_view
from app.core.schemas import TaskSchema
from app.core.errors import DomainError
from app.courses.api import validate
from app.courses.models import Course, CourseVersion
from .models import GenerationDraft, PlanningGrant, Blueprint, GenerationSnapshot
from .planning import build_context, inspect_scope, submit_plan
from .snapshots import (draft_view, blueprint_view, snapshot_view, save_config, edit_blueprint,
                        confirm_structure, freeze_generation)


class WorkspaceSchema(serializers.Serializer):
    draft = serializers.JSONField(allow_null=True)
    versions = serializers.ListField(child=serializers.JSONField())
    latest_task = serializers.JSONField(allow_null=True)
    snapshots = serializers.ListField(child=serializers.JSONField())
    generation_available = serializers.BooleanField()


class ConfigRequest(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=0)
    config = serializers.JSONField()


class ConfigResponse(serializers.Serializer):
    draft = serializers.JSONField()
    committed_revision = serializers.IntegerField()


class PlanningPreflightSchema(serializers.Serializer):
    scope = serializers.JSONField()
    authorized = serializers.BooleanField()
    api_key_configured = serializers.BooleanField()


class PlanRequest(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1)
    context_hash = serializers.CharField(min_length=64, max_length=64)
    authorize_upload = serializers.BooleanField(default=False)


class BlueprintEditRequest(serializers.Serializer):
    config_revision = serializers.IntegerField(min_value=1)
    expected_revision = serializers.IntegerField(min_value=1)
    payload = serializers.JSONField()


class StructureConfirmRequest(serializers.Serializer):
    config_revision = serializers.IntegerField(min_value=1)
    blueprint_revision = serializers.IntegerField(min_value=1)
    config_hash = serializers.CharField(min_length=64, max_length=64)


class FreezeRequest(serializers.Serializer):
    confirmation_id = serializers.UUIDField()
    config_revision = serializers.IntegerField(min_value=1)
    config_hash = serializers.CharField(min_length=64, max_length=64)


class JsonResult(serializers.Serializer):
    result = serializers.JSONField()


class GenerationWorkspaceView(APIView):
    @extend_schema(responses=WorkspaceSchema)
    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        draft = GenerationDraft.objects.select_related("blueprint", "confirmation", "latest_task").filter(course=course).first()
        versions = [{"id": str(v.id), "number": v.number, "mode": v.evidence_manifest.get("analysis_mode", "unknown"),
            "payload": v.frozen_payload, "evidence": [{k: e[k] for k in ("id", "material_code", "material_version_id", "physical_page") if k in e}
                                                      for e in v.evidence_manifest["evidence"]]}
                    for v in CourseVersion.objects.filter(course=course).order_by("-number")]
        return Response({"draft": draft_view(draft), "versions": versions, "generation_available": True,
            "latest_task": task_view(draft.latest_task) if draft and draft.latest_task_id else None,
            "snapshots": [{"id": str(s.id), "mode": s.mode, "created_at": s.created_at,
                "confirmation_id": str(s.confirmation_id), "payload_hash": s.payload_hash}
                for s in GenerationSnapshot.objects.filter(course=course).order_by("-created_at")[:20]]})


class GenerationConfigView(APIView):
    @extend_schema(request=ConfigRequest, responses=ConfigResponse)
    def patch(self, request, course_id):
        data = validate(ConfigRequest, request.data)
        draft, rev = save_config(request.user, course_id, data["expected_revision"], data["config"], request.headers.get("Idempotency-Key"))
        return Response({"draft": draft_view(draft), "committed_revision": rev})


class PlanningPreflightView(APIView):
    @extend_schema(responses=PlanningPreflightSchema)
    def get(self, request, course_id):
        draft = get_object_or_404(GenerationDraft.objects.select_related("course_version", "course"), course_id=course_id, course__owner=request.user)
        snapshot = build_context(draft)
        return Response({"scope": inspect_scope(snapshot), "authorized": snapshot["mode"] == "fixture" or
            PlanningGrant.objects.filter(course=draft.course, context_hash=snapshot["context_hash"]).exists(),
            "api_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip())})


class PlansView(APIView):
    @extend_schema(request=PlanRequest, responses={202: TaskSchema})
    def post(self, request, course_id):
        data = validate(PlanRequest, request.data)
        task = submit_plan(request.user, course_id, data["expected_revision"], data["context_hash"], request.headers.get("Idempotency-Key"), data["authorize_upload"])
        return Response(task_view(task), status=202)


class BlueprintView(APIView):
    @extend_schema(responses=JsonResult)
    def get(self, request, course_id, blueprint_id):
        blueprint = get_object_or_404(Blueprint, pk=blueprint_id, draft__course_id=course_id, draft__course__owner=request.user)
        return Response({"result": blueprint_view(blueprint)})

    @extend_schema(request=BlueprintEditRequest, responses=ConfigResponse)
    def patch(self, request, course_id, blueprint_id):
        data = validate(BlueprintEditRequest, request.data)
        draft = edit_blueprint(request.user, course_id, blueprint_id, data["config_revision"], data["expected_revision"],
                               data["payload"], request.headers.get("Idempotency-Key"))
        return Response({"draft": draft_view(draft), "committed_revision": draft.revision})


class StructureConfirmView(APIView):
    @extend_schema(request=StructureConfirmRequest, responses=ConfigResponse)
    def post(self, request, course_id, blueprint_id):
        data = validate(StructureConfirmRequest, request.data)
        draft = confirm_structure(request.user, course_id, blueprint_id, data["config_revision"], data["blueprint_revision"],
                                  data["config_hash"], request.headers.get("Idempotency-Key"))
        return Response({"draft": draft_view(draft), "committed_revision": draft.revision})


class GenerationSnapshotView(APIView):
    @extend_schema(request=FreezeRequest, responses=JsonResult)
    def post(self, request, course_id):
        data = validate(FreezeRequest, request.data)
        snapshot = freeze_generation(request.user, course_id, data["confirmation_id"], data["config_revision"], data["config_hash"], request.headers.get("Idempotency-Key"))
        return Response({"result": snapshot_view(snapshot)})


class SnapshotDetailView(APIView):
    @extend_schema(responses=JsonResult)
    def get(self, request, course_id, snapshot_id):
        return Response({"result": snapshot_view(get_object_or_404(GenerationSnapshot, pk=snapshot_id, course_id=course_id, course__owner=request.user))})


class GenerationPreflightView(APIView):
    @extend_schema(request=FreezeRequest, responses=PlanningPreflightSchema)
    def post(self, request, course_id):
        from .execution_context import prepare_generation, inspect_generation_scope
        from .models import GenerationGrant
        data = validate(FreezeRequest, request.data)
        context = prepare_generation(request.user, course_id, data["confirmation_id"], data["config_revision"],
                                     data["config_hash"], request.headers.get("Idempotency-Key"))
        return Response({"scope": inspect_generation_scope(context),
            "authorized": context["mode"] == "fixture" or GenerationGrant.objects.filter(course_id=course_id, context_hash=context["context_hash"]).exists(),
            "api_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip())})


class GenerateRequest(FreezeRequest):
    context_hash = serializers.CharField(min_length=64, max_length=64)
    authorize_upload = serializers.BooleanField(default=False)


class GenerationsView(APIView):
    @extend_schema(request=GenerateRequest, responses={202: TaskSchema})
    def post(self, request, course_id):
        from .execution_context import submit_generation
        data = validate(GenerateRequest, request.data)
        task = submit_generation(request.user, course_id, data["confirmation_id"], data["config_revision"],
            data["config_hash"], data["context_hash"], request.headers.get("Idempotency-Key"), data["authorize_upload"])
        return Response(task_view(task), status=202)
