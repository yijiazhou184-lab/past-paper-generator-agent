"""Use a unique disposable PostgreSQL test database; never the app database."""
import os
from pathlib import Path
import sys
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = "test_batch5_" + uuid.uuid4().hex[:12]
import pytest
os.chdir(ROOT / "backend")
raise SystemExit(pytest.main(sys.argv[1:] or ["tests/test_papers.py", "-q"]))
