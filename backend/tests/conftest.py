import io
import pytest
from reportlab.pdfgen import canvas
from app.courses.models import Course


@pytest.fixture(autouse=True)
def private_test_storage(settings, tmp_path):
    settings.DATA_DIR = tmp_path / "data"


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch):
    """settings loads .env.local; tests must never reach the provider with the developer's real key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


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

@pytest.fixture(autouse=True)
def block_unmocked_provider_transport(monkeypatch):
    """MockTransport tests remain possible; default HTTPTransport must never send to OpenAI."""
    import httpx
    original = httpx.HTTPTransport.handle_request
    def guarded(self, request):
        if request.url.host == "api.openai.com":
            raise AssertionError("Tests must mock every official provider request, including token counts.")
        return original(self, request)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", guarded)
