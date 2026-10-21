from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .schemas import (MaterialsSchema, MaterialSchema, UploadResultSchema, RelationResultSchema, RemoveResultSchema, SourceSchema)
from app.core.errors import DomainError
from app.courses.models import Course
from .models import MaterialVersion, MaterialRelation
from .ingest import ingest_pdf
from .evidence import render_page, get_source
from .storage import path_for

ROLES = ["lecture", "summary", "seminar", "additional_questions", "past_paper", "answer",
         "assessment_brief", "personal_notes", "software_reference", "other"]


class UploadInput(serializers.Serializer):
    file = serializers.FileField()
    replace_material_id = serializers.UUIDField(required=False)


class ClassificationInput(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=ROLES), min_length=1, max_length=10)


class RelationInput(serializers.Serializer):
    target_version_id = serializers.UUIDField()
    coverage = serializers.CharField(max_length=500)


def material_view(version):
    evidence = version.evidence.order_by("physical_page")
    parse = evidence.first().parse_version if evidence.exists() else None
    return {"id": str(version.id), "material_id": str(version.material_id), "number": version.number,
            "filename": version.original_filename, "aliases": version.path_aliases,
            "sha256": version.blob.sha256, "bytes": version.blob.bytes, "pages": version.blob.pages,
            "roles": version.roles, "classification_basis": version.classification_basis,
            "classification_revision": version.classification_revision,
            "task_id": str(version.task_id) if version.task_id else None,
            "state": version.task.state if version.task_id else "queued",
            "parse_version_id": str(parse.id) if parse else None,
            "parser": f"{parse.parser_name} {parse.parser_version}" if parse else None,
            "issues": parse.issues if parse else [],
            "evidence": list(evidence.values("id", "physical_page", "fidelity_status")),
            "answer_links": list(version.answer_links.filter(active=True).values("id", "target_id", "coverage", "revision")),
            "metadata": version.content_metadata}


class MaterialsView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses=MaterialsSchema)
    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        versions = MaterialVersion.objects.filter(material__course=course).select_related("blob", "task").order_by("created_at")
        return Response({"materials": [material_view(v) for v in versions], "roles": ROLES,
                         "limits": {"file_mib": 20, "unique_files": 20, "paths": 30, "unique_pages": 300}})

    @extend_schema(request=UploadInput, responses={201: UploadResultSchema})
    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id, owner=request.user)
        form = UploadInput(data=request.data)
        form.is_valid(raise_exception=True)
        upload = form.validated_data["file"]
        if upload.size > 20 * 1024 * 1024:
            raise DomainError("FILE_TOO_LARGE", "The file exceeds 20 MiB.", 400)
        return Response(ingest_pdf(course, upload.read(), upload.name, request.headers.get("Idempotency-Key"),
                                  replace_id=str(form.validated_data["replace_material_id"]) if form.validated_data.get("replace_material_id") else None), status=201)


class ClassificationView(APIView):
    @extend_schema(request=ClassificationInput, responses=MaterialSchema)
    @transaction.atomic
    def patch(self, request, version_id):
        version = get_object_or_404(MaterialVersion.objects.select_for_update(), pk=version_id, material__course__owner=request.user)
        form = ClassificationInput(data=request.data)
        form.is_valid(raise_exception=True)
        if form.validated_data["expected_revision"] != version.classification_revision:
            raise DomainError("REVISION_CONFLICT", "The classification changed. Reload and review before saving.")
        version.roles = form.validated_data["roles"]
        version.classification_basis = "user_corrected"
        version.classification_revision += 1
        version.save()
        return Response(material_view(version))


class RelationsView(APIView):
    @extend_schema(request=RelationInput, responses={201: RelationResultSchema})
    @transaction.atomic
    def post(self, request, version_id):
        source = get_object_or_404(MaterialVersion.objects.select_for_update(), pk=version_id, material__course__owner=request.user)
        form = RelationInput(data=request.data)
        form.is_valid(raise_exception=True)
        target = get_object_or_404(MaterialVersion, pk=form.validated_data["target_version_id"], material__course=source.material.course)
        if source.id == target.id:
            raise DomainError("INVALID_RELATION", "Choose a different question paper.", 400)
        link, created = MaterialRelation.objects.get_or_create(source=source, target=target,
            defaults={"coverage": form.validated_data["coverage"], "active": True})
        if not created:
            link.coverage, link.active = form.validated_data["coverage"], True
            link.revision += 1
            link.save()
        return Response({"id": str(link.id)}, status=201)


class RemoveRelationView(APIView):
    @extend_schema(request=None, responses=RemoveResultSchema)
    def post(self, request, relation_id):
        link = get_object_or_404(MaterialRelation, pk=relation_id, source__material__course__owner=request.user)
        link.active = False
        link.revision += 1
        link.save()
        return Response({"removed": True})


class SourceView(APIView):
    @extend_schema(responses=SourceSchema)
    def get(self, request, evidence_id):
        source = get_source(request.user, evidence_id)
        return Response({"id": str(source.id), "material_version_id": str(source.material_version_id),
            "parse_version_id": str(source.parse_version_id), "physical_page": source.physical_page,
            "printed_label": source.printed_label or None, "text": source.text,
            "blocks": source.blocks, "fidelity_status": source.fidelity_status,
            "filename": source.material_version.original_filename,
            "sha256": source.material_version.blob.sha256,
            "image_url": f"/api/v1/material-versions/{source.material_version_id}/pages/{source.physical_page}"})


class PageImageView(APIView):
    @extend_schema(responses={(200, "image/png"): bytes})
    def get(self, request, version_id, page_number):
        return FileResponse(render_page(request.user, version_id, page_number).open("rb"), content_type="image/png")


class OriginalView(APIView):
    @extend_schema(responses={(200, "application/pdf"): bytes})
    def get(self, request, version_id):
        version = get_object_or_404(MaterialVersion.objects.select_related("blob"), pk=version_id, material__course__owner=request.user)
        return FileResponse(path_for(version.blob.storage_key).open("rb"), as_attachment=True, filename=version.original_filename)
