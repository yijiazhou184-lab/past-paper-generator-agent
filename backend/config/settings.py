import json
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env.local")
runtime_file = BASE_DIR / "var" / "local.json"
local = json.loads(runtime_file.read_text()) if runtime_file.exists() else {}
LOCAL_ACCESS = bool(local.get("local_access", False))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or local.get("secret_key", "")
if not SECRET_KEY:
    raise RuntimeError("Run scripts/local.py setup to create private local settings.")
DEBUG = os.environ.get("APP_DEBUG", "false") == "true"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "rest_framework", "drf_spectacular", "app.core", "app.courses", "app.materials",
    "procrastinate.contrib.django",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
db = urlparse(os.environ.get("APP_DATABASE_URL") or local.get("database_url", ""))
if db.scheme not in ("postgres", "postgresql"):
    raise RuntimeError("A PostgreSQL APP_DATABASE_URL is required.")
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql", "NAME": db.path.lstrip("/"),
    "USER": db.username, "PASSWORD": db.password, "HOST": db.hostname,
    "PORT": db.port or 5432, "CONN_MAX_AGE": 0,
    "OPTIONS": {"connect_timeout": 5},
}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "app.core.errors.exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}
SPECTACULAR_SETTINGS = {"TITLE": "Past Paper Generator", "VERSION": "0.1.0", "SERVE_INCLUDE_SCHEMA": False}
PROCRASTINATE_IMPORT_PATHS = ["app.core.queue"]
PROCRASTINATE_WORKER_DEFAULTS = {"concurrency": 1}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "UTC"
USE_TZ = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
DATA_UPLOAD_MAX_MEMORY_SIZE = 21 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 21 * 1024 * 1024
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", str(BASE_DIR / "var/data")))
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DOCLING_ARTIFACTS_PATH = os.environ.get("DOCLING_ARTIFACTS_PATH") or str(BASE_DIR / "var/models")
if not Path(DOCLING_ARTIFACTS_PATH).is_absolute():
    DOCLING_ARTIFACTS_PATH = str(BASE_DIR / DOCLING_ARTIFACTS_PATH)
MODEL_MODE = os.environ.get("APP_MODEL_MODE", "disabled")
ALLOW_COURSE_DATA_UPLOAD = os.environ.get("ALLOW_COURSE_DATA_UPLOAD") == "true"
STATIC_URL = "/static/"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
