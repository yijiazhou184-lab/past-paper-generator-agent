import hashlib
import io
from pathlib import PurePosixPath
from django.db import transaction
from pypdf import PdfReader
from app.courses.models import Course
from app.core.errors import DomainError
from app.core.idempotency import intent
from app.core.tasks import submit_task
from .models import MaterialBlob, Material, MaterialVersion
from .storage import write_bytes


def validate_pdf(data, filename):
    if len(data) > 20 * 1024 * 1024:
        raise DomainError("FILE_TOO_LARGE", "The file exceeds the 20 MiB limit.", 400)
    if not filename.lower().endswith(".pdf") or not data.startswith(b"%PDF-"):
        raise DomainError("INVALID_PDF", "Choose a genuine digital PDF file.", 400)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DomainError("ENCRYPTED_PDF", "Encrypted PDFs cannot be processed. Upload an unlocked copy.", 400)
        pages = len(reader.pages)
        if not 0 < pages <= 300:
            raise DomainError("PAGE_LIMIT", "The file must contain 1–300 pages.", 400)
        metadata = {str(k): str(v)[:1000] for k, v in (reader.metadata or {}).items()}
        return pages, metadata
    except DomainError:
        raise
    except Exception:
        raise DomainError("INVALID_PDF", "The PDF could not be read.", 400) from None


@transaction.atomic
def ingest_pdf(course, data, filename, key, alias=None, replace_id=None):
    filename = PurePosixPath(filename.replace("\\", "/")).name[:255]
    page_count, metadata = validate_pdf(data, filename)
    sha = hashlib.sha256(data).hexdigest()
    course = Course.objects.select_for_update().get(pk=course.id)
    record = intent(course.owner, f"upload:{course.id}", key, {"sha": sha, "name": filename, "alias": alias, "replace": replace_id})
    if record.response:
        return record.response
    versions = list(MaterialVersion.objects.filter(material__course=course).select_related("blob"))
    aliases = sum(len(v.path_aliases) for v in versions)
    duplicate = next((v for v in versions if v.blob.sha256 == sha), None)
    adds_alias = replace_id or not duplicate or (alias or filename) not in duplicate.path_aliases
    if aliases >= 30 and adds_alias:
        raise DomainError("PATH_LIMIT", "This course has reached its 30-path limit.", 400)
    unique = {v.blob.sha256: v.blob for v in versions}
    if sha not in unique:
        if len(unique) >= 20 or sum(b.pages for b in unique.values()) + page_count > 300:
            raise DomainError("COURSE_PAGE_LIMIT", "This course supports 20 unique PDFs and 300 unique pages.", 400)
        if sum(b.bytes for b in unique.values()) + len(data) > 100 * 1024 * 1024:
            raise DomainError("COURSE_SIZE_LIMIT", "This course exceeds 100 MiB.", 400)
    if duplicate and not replace_id:
        entry = alias or filename
        if entry not in duplicate.path_aliases:
            duplicate.path_aliases.append(entry)
            duplicate.save(update_fields=["path_aliases"])
        result = {"version_id": str(duplicate.id), "task_id": str(duplicate.task_id), "duplicate": True}
    else:
        blob, created = MaterialBlob.objects.get_or_create(owner=course.owner, sha256=sha,
            defaults={"bytes": len(data), "pages": page_count, "storage_key": f"blobs/{course.owner_id}/{sha}.pdf"})
        if created:
            write_bytes(blob.storage_key, data)
        if replace_id:
            material = Material.objects.filter(pk=replace_id, course=course).first()
            if not material:
                raise DomainError("NOT_FOUND", status=404)
            number = material.versions.count() + 1
        else:
            material, number = Material.objects.create(course=course), 1
        version = MaterialVersion.objects.create(material=material, blob=blob, number=number,
            original_filename=filename, path_aliases=[alias or filename], content_metadata=metadata)
        task = submit_task(course, "parse", {"material_version_id": str(version.id), "blob_sha256": sha}, f"parse:{version.id}")
        version.task = task
        version.save(update_fields=["task"])
        result = {"version_id": str(version.id), "task_id": str(task.id), "duplicate": False}
    record.response = result
    record.save(update_fields=["response"])
    return result
