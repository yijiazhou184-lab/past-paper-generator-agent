from rest_framework import serializers


class PaperSchema(serializers.Serializer):
    id = serializers.UUIDField()
    course_id = serializers.UUIDField()
    task_id = serializers.UUIDField()
    content_version_id = serializers.UUIDField()
    content_hash = serializers.CharField()
    created_at = serializers.DateTimeField()
    metadata = serializers.JSONField()
    topic_summary = serializers.ListField(child=serializers.JSONField())
    export = serializers.JSONField()


class PapersSchema(serializers.Serializer):
    papers = PaperSchema(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class PaperContentSchema(serializers.Serializer):
    paper = PaperSchema()
    candidate = serializers.JSONField()


class ExportSchema(serializers.Serializer):
    paper_id = serializers.UUIDField()
    task_id = serializers.UUIDField(allow_null=True)
