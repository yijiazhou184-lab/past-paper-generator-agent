"""Local Docling parsing. The originals are never modified or sent to a service."""
import importlib.metadata
import json
import hashlib
from collections import defaultdict
from django.conf import settings
from django.db import transaction
from app.core.tasks import checkpoint, locked_task, finish_task
from app.core.idempotency import digest
from app.core.errors import DomainError
from .models import MaterialVersion, ParseVersion, Evidence
from .storage import path_for, write_bytes

CONFIG = {"ocr": False, "tables": True, "formula_enrichment": False, "schema": "r1.1"}


def suggest_roles(text):
    """Content-based suggestions; never claim official exam authority."""
    text = text[:12000].lower()
    if "coursework" in text and ("brief" in text or "assessment" in text):
        return ["assessment_brief"]
    if "mock exam" in text:
        return ["answer"] if "answer" in text else ["past_paper"]
    if "mathematica" in text and ("syntax" in text or "d[" in text or "plot" in text):
        return ["software_reference"]
    if "additional questions" in text:
        return ["additional_questions"]
    if "seminar" in text:
        return ["seminar"]
    if "summary" in text:
        return ["summary"]
    if "lecture" in text:
        return ["lecture"]
    return ["other"]


def parse_material(token, version_id):
    version = MaterialVersion.objects.select_related("blob", "material").get(pk=version_id)
    with transaction.atomic():
        task = locked_task(token)
        if (str(version.id) != task.snapshot.get("material_version_id") or
            version.blob.sha256 != task.snapshot.get("blob_sha256") or
            version.material.course_id != task.course_id):
            raise DomainError("TASK_INPUT_MISMATCH", "The parser input does not match the frozen task.")
    parser_version = importlib.metadata.version("docling")
    parse, _ = ParseVersion.objects.get_or_create(blob=version.blob, parser_name="docling",
        parser_version=parser_version, config_hash=digest(CONFIG))
    checkpoint(token, "Reading PDF", {"pages_total": version.blob.pages, "parser_version": parser_version})
    if parse.state == "ready" and parse.document_key and path_for(parse.document_key).exists():
        saved_bytes = path_for(parse.document_key).read_bytes()
        if parse.content_hash and hashlib.sha256(saved_bytes).hexdigest() != parse.content_hash:
            raise ValueError("Cached parse failed integrity check")
        payload = json.loads(saved_bytes)
    else:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        options = PdfPipelineOptions(artifacts_path=settings.DOCLING_ARTIFACTS_PATH,
                                     do_ocr=False, do_table_structure=True,
                                     do_formula_enrichment=False)
        options.enable_remote_services = False
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        checkpoint(token, "Parsing page structure", {"pages_total": version.blob.pages})
        result = converter.convert(path_for(version.blob.storage_key))
        if str(result.status.value) != "success":
            raise RuntimeError("Docling returned an incomplete conversion")
        pages = defaultdict(list)
        for item, _ in result.document.iterate_items():
            for prov in getattr(item, "prov", []):
                if not 1 <= prov.page_no <= version.blob.pages:
                    raise ValueError("Parser page reference outside PDF")
                bbox = prov.bbox
                pages[prov.page_no].append({
                    "text": getattr(item, "text", ""),
                    "kind": str(getattr(item, "label", "unknown")),
                    "bbox": bbox.model_dump(mode="json"),
                })
        payload = {"parser": "docling", "version": parser_version, "config": CONFIG,
                   "pages": [{"physical_page": i, "blocks": pages[i],
                              "text": "\n".join(b["text"] for b in pages[i] if b["text"])}
                             for i in range(1, version.blob.pages + 1)],
                   "document": result.document.export_to_dict()}
        parse.document_key = f"parses/{parse.id}/document.json"
        write_bytes(parse.document_key, json.dumps(payload, ensure_ascii=False).encode())
    parse.content_hash = hashlib.sha256(path_for(parse.document_key).read_bytes()).hexdigest()
    issues = [{"code": "MATH_REVIEW_REQUIRED", "message": "Formula transcription has not been semantically verified. Compare important mathematics with the original page."}]
    empty_pages = [p["physical_page"] for p in payload["pages"] if not p["text"].strip()]
    if empty_pages:
        issues.append({"code": "EMPTY_TEXT_PAGES", "pages": empty_pages,
                       "message": "Some pages contain no extracted text. Page images remain available."})
    with transaction.atomic():
        locked_task(token)
        parse.state, parse.issues = "ready", issues
        parse.save()
        for page in payload["pages"]:
            Evidence.objects.get_or_create(material_version=version, parse_version=parse,
                physical_page=page["physical_page"], defaults={
                    "text": page["text"], "blocks": page["blocks"], "fidelity_status": "needs_review"})
        version.refresh_from_db()
        if version.classification_basis == "unclassified":
            version.roles = suggest_roles("\n".join(p["text"] for p in payload["pages"][:4]))
            version.classification_basis = "content_suggestion"
            version.save(update_fields=["roles", "classification_basis"])
        finish_task(token, {"material_version_id": str(version.id), "parse_version_id": str(parse.id),
                            "pages": version.blob.pages, "issues": issues})
