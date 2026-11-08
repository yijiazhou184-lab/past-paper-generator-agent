import os
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.core.api import task_view
from app.core.models import Task
from app.core.schemas import TaskSchema
from .models import Course, CourseDraft, CourseVersion, AnalysisGrant
from .context import build_context, inspect_scope
from .analysis import submit_analysis
from .drafts import draft_view, save_draft, answer_clarification
from .confirmation import confirm_course, confirm_topics


class ProfileSchema(serializers.Serializer):
    draft = serializers.JSONField(allow_null=True)
    versions = serializers.ListField(child=serializers.JSONField())
    active_task_id = serializers.UUIDField(allow_null=True)
    latest_task_id = serializers.UUIDField(allow_null=True)
    draft_revision = serializers.IntegerField()
    topics = serializers.ListField(child=serializers.JSONField())


class PreflightSchema(serializers.Serializer):
    scope = serializers.JSONField()
    authorized = serializers.BooleanField()
    api_key_configured = serializers.BooleanField()


class MaterialSelection(serializers.Serializer):
    material_version_id = serializers.UUIDField()
    pages = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=300)


class TopicAnalysisSelection(serializers.Serializer):
    target_topic_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=1)
    material_selection = MaterialSelection(many=True)
    base_revision = serializers.IntegerField(min_value=0)


class AnalyseRequest(serializers.Serializer):
    target_topic_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    material_selection = MaterialSelection(many=True, required=False)
    base_revision = serializers.IntegerField(min_value=0, required=False)
    context_hash = serializers.CharField(max_length=64)
    authorize_upload = serializers.BooleanField(default=False)
    parent_id = serializers.UUIDField(required=False, allow_null=True)


class DraftRequest(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1)
    patches = serializers.ListField(child=serializers.JSONField(), max_length=100)
    acknowledge_merge = serializers.BooleanField(default=False)
    topic_id = serializers.UUIDField(required=False, allow_null=True)


class DraftResponse(serializers.Serializer):
    draft = serializers.JSONField()
    committed_revision = serializers.IntegerField()


class AnswerRequest(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1)
    question_id = serializers.CharField(max_length=120)
    text = serializers.CharField(max_length=3000,required=False,allow_blank=True,default="")
    option_ids = serializers.ListField(child=serializers.CharField(max_length=100),required=False,max_length=40)
    definition_hash = serializers.CharField(max_length=64,required=False)
    note = serializers.CharField(max_length=1000,required=False,allow_blank=True,default="")
    topic_id = serializers.UUIDField(required=False, allow_null=True)


class ConfirmRequest(serializers.Serializer):
    draft_id = serializers.UUIDField()
    selected_topic_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    include_exam_template = serializers.BooleanField(required=False, default=False)
    base_course_version_id = serializers.UUIDField(required=False, allow_null=True)
    expected_revision = serializers.IntegerField(min_value=1)


class VersionSchema(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.IntegerField()
    mode = serializers.CharField()
    draft_revision = serializers.IntegerField()
    payload_hash = serializers.CharField()
    frozen_payload = serializers.JSONField()
    evidence_manifest = serializers.JSONField()
    statements = serializers.JSONField()
    manual_patches = serializers.JSONField()
    created_at = serializers.DateTimeField()


def validate(serializer, data):
    instance = serializer(data=data)
    instance.is_valid(raise_exception=True)
    return instance.validated_data


def version_view(version):
    return {"id": str(version.id), "number": version.number, "draft_revision": version.draft_revision,
        "mode": version.evidence_manifest.get("analysis_mode", "unknown"),
        "payload_hash": version.payload_hash, "frozen_payload": version.frozen_payload,
        "evidence_manifest": version.evidence_manifest, "statements": version.statements,
        "manual_patches": version.manual_patches, "created_at": version.created_at}


class ProfileView(APIView):
    @extend_schema(responses=ProfileSchema)
    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        tid=request.query_params.get("topic")
        if tid:
            tid=str(serializers.UUIDField().run_validation(tid))
            from .models import Topic
            get_object_or_404(Topic,pk=tid,course=course)
        draft=CourseDraft.objects.filter(course=course).select_related("machine_base", "course").first()
        latest_query=Task.objects.filter(course=course,kind="analysis")
        if tid:latest_query=latest_query.filter(snapshot__input__target_topic_ids__contains=[tid])
        latest=latest_query.order_by("-created_at").first()
        from .topics import list_topics
        return Response({"draft": draft_view(draft,tid), "draft_revision":draft.revision if draft else 0,
            "topics":list_topics(request.user,course_id)["topics"],
            "versions": list(course.confirmed_versions.order_by("-number").values("id", "number", "draft_revision", "created_at")),
            "active_task_id": str(latest.id) if latest and latest.state in ("queued", "processing") else None,
            "latest_task_id": str(latest.id) if latest else None})


class AnalysisPreflightView(APIView):
    @extend_schema(responses=PreflightSchema)
    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        snapshot = build_context(course)
        return Response({"scope": inspect_scope(snapshot), "api_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            "authorized": AnalysisGrant.objects.filter(course=course, context_hash=snapshot["context_hash"]).exists()})


    @extend_schema(request=TopicAnalysisSelection,responses=PreflightSchema)
    def post(self,request,course_id):
        from .topic_context import build_topic_analysis_context
        data=validate(TopicAnalysisSelection,request.data)
        course=get_object_or_404(Course,pk=course_id,owner=request.user)
        selection=[{"material_version_id":str(x["material_version_id"]),"pages":x["pages"]} for x in data["material_selection"]]
        snapshot=build_topic_analysis_context(course,[str(i) for i in data["target_topic_ids"]],selection,data["base_revision"])
        return Response({"scope":inspect_scope(snapshot),"api_key_configured":bool(os.environ.get("OPENAI_API_KEY","").strip()),
            "authorized":AnalysisGrant.objects.filter(course=course,context_hash=snapshot["context_hash"]).exists()})


class AnalyseView(APIView):
    @extend_schema(request=AnalyseRequest, responses={202: TaskSchema})
    def post(self, request, course_id):
        data = validate(AnalyseRequest, request.data)
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        parent = get_object_or_404(Task, pk=data["parent_id"], course=course, kind="analysis", state__in=["failed", "cancelled", "needs_info"]) if data.get("parent_id") else None
        task = submit_analysis(course, data["context_hash"], request.headers.get("Idempotency-Key"),
            authorize=data["authorize_upload"], parent=parent,
            **({"target_topic_ids":[str(i) for i in data["target_topic_ids"]],
                "material_selection":[{"material_version_id":str(x["material_version_id"]),"pages":x["pages"]} for x in data.get("material_selection",[])],
                "base_revision":data.get("base_revision")} if "target_topic_ids" in data else {}))
        return Response(task_view(task), status=202)


class DraftView(APIView):
    @extend_schema(request=DraftRequest, responses=DraftResponse)
    def patch(self, request, course_id):
        data = validate(DraftRequest, request.data)
        draft, revision = save_draft(request.user, course_id, data["expected_revision"], data["patches"],
            request.headers.get("Idempotency-Key"), data["acknowledge_merge"],topic_id=str(data["topic_id"]) if data.get("topic_id") else None)
        return Response({"draft": draft_view(draft,str(data["topic_id"]) if data.get("topic_id") else None), "committed_revision": revision})


class AnswerView(APIView):
    @extend_schema(request=AnswerRequest, responses=DraftResponse)
    def post(self, request, course_id):
        data = validate(AnswerRequest, request.data)
        draft = answer_clarification(request.user, course_id, data["question_id"], data["text"],
            data["expected_revision"], request.headers.get("Idempotency-Key"),topic_id=str(data["topic_id"]) if data.get("topic_id") else None,
            option_ids=data.get("option_ids"),definition_hash=data.get("definition_hash"),note=data["note"])
        return Response({"draft": draft_view(draft,str(data["topic_id"]) if data.get("topic_id") else None), "committed_revision": draft.revision})


class ConfirmView(APIView):
    @extend_schema(request=ConfirmRequest, responses=VersionSchema)
    def post(self, request, course_id):
        data = validate(ConfirmRequest, request.data)
        if "selected_topic_ids" in data:
            draft=get_object_or_404(CourseDraft,pk=data["draft_id"],course_id=course_id,course__owner=request.user)
            return Response(version_view(confirm_topics(request.user,course_id,data["expected_revision"],data.get("base_course_version_id"),
                [str(i) for i in data["selected_topic_ids"]],request.headers.get("Idempotency-Key"),
                  include_exam_template=data["include_exam_template"])))
        draft=get_object_or_404(CourseDraft,pk=data["draft_id"],course_id=course_id,course__owner=request.user)
        from .topic_state import state_map
        if state_map(draft):
            from app.core.errors import DomainError
            raise DomainError("TOPIC_CONFIRMATION_REQUIRED","Select which topics you reviewed before confirming.")
        return Response(version_view(confirm_course(request.user, course_id, data["draft_id"], data["expected_revision"], request.headers.get("Idempotency-Key"),
                                                   include_exam_template=data["include_exam_template"])))


class VersionView(APIView):
    @extend_schema(responses=VersionSchema)
    def get(self, request, course_id, version_id):
        return Response(version_view(get_object_or_404(CourseVersion, pk=version_id, course_id=course_id, course__owner=request.user)))

class ReviewSelectionRequest(serializers.Serializer):
    topic_id=serializers.UUIDField()
    expected_revision=serializers.IntegerField(min_value=1)
    knowledge_ids=serializers.ListField(child=serializers.CharField(max_length=100),min_length=1,max_length=40)


class ReviewSelectionView(APIView):
    @extend_schema(request=ReviewSelectionRequest,responses=DraftResponse)
    def post(self,request,course_id):
        data=validate(ReviewSelectionRequest,request.data)
        from .eligibility import save_review_selection
        tid=str(data["topic_id"])
        draft=save_review_selection(request.user,course_id,tid,data["expected_revision"],data["knowledge_ids"],request.headers.get("Idempotency-Key"))
        return Response({"draft":draft_view(draft,tid),"committed_revision":draft.revision})
