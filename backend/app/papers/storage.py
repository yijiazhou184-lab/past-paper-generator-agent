import hashlib
from django.conf import settings


def artifact_path(artifact):
    root = settings.DATA_DIR.resolve()
    path = (root / artifact.path).resolve()
    if not path.is_relative_to(root / "papers"):
        raise ValueError("Invalid private artifact path")
    return path


def valid_artifact(artifact):
    try:
        data = artifact_path(artifact).read_bytes()
        return len(data) == artifact.size and data.startswith(b"%PDF-") and hashlib.sha256(data).hexdigest() == artifact.sha256
    except (OSError, ValueError):
        return False
