import io
import pytest
from reportlab.pdfgen import canvas
from app.courses.models import Course


@pytest.fixture(autouse=True)
def private_test_storage(settings, tmp_path):
    settings.DATA_DIR = tmp_path / "data"


@pytest.fixture
def course(db, django_user_model):
    owner = django_user_model.objects.create_user(username="learner", password="test-only-password")
    return Course.objects.create(owner=owner, title="Quantitative Methods")


@pytest.fixture
def pdf_bytes():
    out = io.BytesIO()
    document = canvas.Canvas(out)
    document.drawString(60, 700, "Topic 2 - Lecture: Differentiation and optimisation")
    document.showPage()
    document.drawString(60, 700, "Derivative definitions and the chain rule")
    document.save()
    return out.getvalue()
