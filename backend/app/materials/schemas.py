from rest_framework import serializers as s


class PageRefSchema(s.Serializer):
    id = s.UUIDField()
    physical_page = s.IntegerField()
    fidelity_status = s.CharField()


class RelationSchema(s.Serializer):
    id = s.UUIDField()
    target_id = s.UUIDField()
    coverage = s.CharField()
    revision = s.IntegerField()


class IssueSchema(s.Serializer):
    code = s.CharField()
    message = s.CharField()
    pages = s.ListField(child=s.IntegerField(), required=False)


class MaterialSchema(s.Serializer):
    id = s.UUIDField()
    material_id = s.UUIDField()
    number = s.IntegerField()
    filename = s.CharField()
    aliases = s.ListField(child=s.CharField())
    sha256 = s.CharField()
    bytes = s.IntegerField()
    pages = s.IntegerField()
    roles = s.ListField(child=s.CharField())
    classification_basis = s.CharField()
    classification_revision = s.IntegerField()
    task_id = s.UUIDField(allow_null=True)
    state = s.CharField()
    parse_version_id = s.UUIDField(allow_null=True)
    parser = s.CharField(allow_null=True)
    issues = IssueSchema(many=True)
    evidence = PageRefSchema(many=True)
    answer_links = RelationSchema(many=True)
    metadata = s.DictField(child=s.CharField())


class MaterialLimitsSchema(s.Serializer):
    file_mib = s.IntegerField()
    unique_files = s.IntegerField()
    paths = s.IntegerField()
    unique_pages = s.IntegerField()


class MaterialsSchema(s.Serializer):
    materials = MaterialSchema(many=True)
    roles = s.ListField(child=s.CharField())
    limits = MaterialLimitsSchema()


class UploadResultSchema(s.Serializer):
    version_id = s.UUIDField()
    task_id = s.UUIDField()
    duplicate = s.BooleanField()


class SourceSchema(s.Serializer):
    id = s.UUIDField()
    material_version_id = s.UUIDField()
    parse_version_id = s.UUIDField()
    physical_page = s.IntegerField()
    printed_label = s.CharField(allow_null=True)
    text = s.CharField()
    blocks = s.ListField(child=s.DictField())
    fidelity_status = s.CharField()
    filename = s.CharField()
    sha256 = s.CharField()
    image_url = s.CharField()


class RelationResultSchema(s.Serializer):
    id = s.UUIDField()


class RemoveResultSchema(s.Serializer):
    removed = s.BooleanField()
