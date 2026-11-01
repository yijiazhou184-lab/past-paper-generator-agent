from django.shortcuts import get_object_or_404
from rest_framework import serializers as s
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Topic
from .topics import create_topic, update_topic, list_topics, topic_view
from app.materials.schemas import AssignmentSchema
from app.materials.topic_assignments import set_topic_assignment, assignment_view


class TopicInput(s.Serializer):
    name = s.CharField(max_length=200)
    code = s.CharField(max_length=40, required=False, allow_blank=True)
    order = s.IntegerField(min_value=0, max_value=10000, required=False)
    provenance = s.ChoiceField(choices=["user_declared", "reviewed_material"], required=False)
    source_refs = s.ListField(child=s.JSONField(), max_length=30, required=False)


class TopicSchema(TopicInput):
    id = s.UUIDField()
    course_id = s.UUIDField()
    revision = s.IntegerField()
    archived = s.BooleanField()
    material_count = s.IntegerField()
    readiness = s.CharField()


class TopicListSchema(s.Serializer):
    topics = TopicSchema(many=True)
    capabilities = s.DictField(child=s.BooleanField())


class TopicPatchInput(TopicInput):
    name = s.CharField(max_length=200, required=False)
    expected_revision = s.IntegerField(min_value=1)


class AssignmentInput(AssignmentSchema):
    expected_revision = s.IntegerField(min_value=0)


class TopicsView(APIView):
    @extend_schema(responses=TopicListSchema)
    def get(self, request, course_id):
        return Response(list_topics(request.user, course_id))

    @extend_schema(request=TopicInput, responses={201: TopicSchema})
    def post(self, request, course_id):
        form = TopicInput(data=request.data); form.is_valid(raise_exception=True)
        topic = create_topic(request.user, course_id, form.validated_data, request.headers.get("Idempotency-Key"))
        return Response(topic_view(topic), status=201)


class TopicView(APIView):
    @extend_schema(request=TopicPatchInput, responses=TopicSchema)
    def patch(self, request, course_id, topic_id):
        get_object_or_404(Topic, pk=topic_id, course_id=course_id, course__owner=request.user)
        form = TopicPatchInput(data=request.data); form.is_valid(raise_exception=True)
        data = dict(form.validated_data); revision = data.pop("expected_revision")
        return Response(topic_view(update_topic(request.user, topic_id, revision, data)))


class TopicAssignmentView(APIView):
    @extend_schema(request=AssignmentInput, responses=AssignmentSchema)
    def patch(self, request, version_id):
        form = AssignmentInput(data=request.data); form.is_valid(raise_exception=True)
        data = dict(form.validated_data); revision = data.pop("expected_revision")
        data["topic_ids"] = [str(i) for i in data["topic_ids"]]
        row = set_topic_assignment(request.user, version_id, revision, data)
        return Response(assignment_view(row.material_version))
