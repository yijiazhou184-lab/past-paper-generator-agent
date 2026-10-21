from rest_framework import serializers as s


class SessionSchema(s.Serializer):
    authenticated = s.BooleanField()
    csrf_token = s.CharField()
    local_access = s.BooleanField(required=False)
    database = s.CharField(required=False)
    batch = s.IntegerField(required=False)
    model_mode = s.CharField(required=False)
    course_data_upload = s.BooleanField(required=False)


class CourseSchema(s.Serializer):
    id = s.UUIDField()
    title = s.CharField()
    code = s.CharField()
    scope_statement = s.CharField()
    scope_provenance = s.CharField()


class CoursesSchema(s.Serializer):
    courses = CourseSchema(many=True)


class TaskEventSchema(s.Serializer):
    stage = s.CharField()
    created_at = s.DateTimeField()
    detail = s.DictField()


class TaskErrorSchema(s.Serializer):
    code = s.CharField(required=False)
    message = s.CharField(required=False)
    retryable = s.BooleanField(required=False)
    diagnostic_id = s.UUIDField(required=False)


class ModelCallSchema(s.Serializer):
    id = s.UUIDField()
    key = s.CharField()
    state = s.CharField()
    status = s.CharField()
    mode = s.CharField()
    model = s.CharField(allow_null=True)
    elapsed_seconds = s.FloatField(allow_null=True)
    usage = s.DictField()
    error_code = s.CharField(allow_null=True)
    payload = s.DictField(allow_null=True)
    source_url = s.CharField(allow_null=True)


class TaskSchema(s.Serializer):
    id = s.UUIDField()
    course_id = s.UUIDField()
    kind = s.CharField()
    state = s.CharField()
    stage = s.CharField()
    elapsed_seconds = s.FloatField()
    target_exceeded = s.BooleanField()
    created_at = s.DateTimeField()
    started_at = s.DateTimeField(allow_null=True)
    finished_at = s.DateTimeField(allow_null=True)
    heartbeat_at = s.DateTimeField(allow_null=True)
    epoch = s.IntegerField()
    result = s.DictField()
    error = TaskErrorSchema()
    checkpoint = s.DictField()
    parent_id = s.UUIDField(allow_null=True)
    events = TaskEventSchema(many=True)
    model_calls = ModelCallSchema(many=True)


class TasksSchema(s.Serializer):
    tasks = TaskSchema(many=True)
