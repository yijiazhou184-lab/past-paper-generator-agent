import io
import pytest
from app.materials.ingest import ingest_pdf
from app.materials.models import MaterialBlob, MaterialVersion
from app.core.errors import DomainError

pytestmark = pytest.mark.django_db


def test_duplicate_keeps_aliases_and_intent(course, pdf_bytes, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    first = ingest_pdf(course, pdf_bytes, "lecture.pdf", "a")
    second = ingest_pdf(course, pdf_bytes, "lecture-copy.pdf", "b")
    assert first["version_id"] == second["version_id"]
    assert MaterialBlob.objects.count() == 1
    assert len(MaterialVersion.objects.get(pk=first["version_id"]).path_aliases) == 2
    assert second["duplicate"] is True
    assert ingest_pdf(course, pdf_bytes, "lecture.pdf", "a") == first


def test_reject_corrupt_and_disguised_pdf(course, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    with pytest.raises(DomainError, match="INVALID_PDF"):
        ingest_pdf(course, b"not pdf", "real.pdf", "a")
    assert MaterialBlob.objects.count() == 0


def test_encrypted_pdf_is_reported(course, pdf_bytes, settings, tmp_path):
    from pypdf import PdfReader, PdfWriter
    settings.DATA_DIR = tmp_path
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf_bytes)))
    writer.encrypt("private")
    data = io.BytesIO()
    writer.write(data)
    with pytest.raises(DomainError, match="ENCRYPTED_PDF"):
        ingest_pdf(course, data.getvalue(), "locked.pdf", "a")
