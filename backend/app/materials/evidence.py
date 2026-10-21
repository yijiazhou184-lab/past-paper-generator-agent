import io
import pypdfium2 as pdfium
from django.shortcuts import get_object_or_404
from .models import Evidence, MaterialVersion
from .storage import path_for, write_bytes
from app.core.idempotency import digest
from app.core.errors import DomainError


def build_evidence_pack(owner, version_ids):
    """Snapshot only owned, fully parsed versions; preserve claims' provenance for AI 1."""
    versions = MaterialVersion.objects.filter(pk__in=version_ids, material__course__owner=owner).select_related("blob")
    if versions.count() != len(set(str(v) for v in version_ids)):
        from django.http import Http404
        raise Http404
    payload = {"schema_version": "r1-evidence-1", "materials": [], "evidence": []}
    for version in sorted(versions, key=lambda v: str(v.id)):
        evidence = list(version.evidence.select_related("parse_version").order_by("physical_page"))
        if len(evidence) != version.blob.pages:
            raise DomainError("EVIDENCE_NOT_READY", "Some selected pages have not finished parsing.")
        payload["materials"].append({"material_version_id": str(version.id), "sha256": version.blob.sha256,
            "pages": version.blob.pages, "roles": version.roles, "classification_basis": version.classification_basis,
            "classification_revision": version.classification_revision,
            "parse_issues": evidence[0].parse_version.issues,
            "answer_links": [{"target_version_id": str(a.target_id), "coverage": a.coverage, "revision": a.revision}
                             for a in version.answer_links.filter(active=True).order_by("id")]})
        for e in evidence:
            payload["evidence"].append({"id": str(e.id), "material_version_id": str(version.id),
                "parse_version_id": str(e.parse_version_id), "parser_version": e.parse_version.parser_version,
                "parse_content_hash": e.parse_version.content_hash,
                "parser_config_hash": e.parse_version.config_hash, "physical_page": e.physical_page,
                "printed_label": e.printed_label or None, "text": e.text, "blocks": e.blocks,
                "fidelity_status": e.fidelity_status})
    return {**payload, "manifest_hash": digest(payload)}


def get_source(owner, evidence_id):
    return get_object_or_404(Evidence.objects.select_related("material_version__blob", "parse_version"),
                            pk=evidence_id, material_version__material__course__owner=owner)


def render_page(owner, version_id, page_number):
    version = get_object_or_404(MaterialVersion.objects.select_related("blob"),
                               pk=version_id, material__course__owner=owner)
    if not 1 <= page_number <= version.blob.pages:
        from django.http import Http404
        raise Http404
    key = f"page-images/{version.blob_id}/{page_number}.png"
    if not path_for(key).exists():
        document = pdfium.PdfDocument(path_for(version.blob.storage_key))
        page = document[page_number - 1]
        bitmap = page.render(scale=min(2, 1400 / page.get_width()))
        image = bitmap.to_pil()
        output = io.BytesIO()
        image.save(output, format="PNG")
        write_bytes(key, output.getvalue())
        bitmap.close()
        page.close()
        document.close()
    return path_for(key)
