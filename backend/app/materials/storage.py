import os
import tempfile
from pathlib import Path
from django.conf import settings


def path_for(key):
    root = settings.DATA_DIR.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Storage path outside private data root")
    return path


def write_bytes(key, content):
    path = path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return key
