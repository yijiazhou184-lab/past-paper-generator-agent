import hashlib
from pathlib import Path
from django.conf import settings
from django.db import migrations


def fill_hash(apps, schema_editor):
    ParseVersion = apps.get_model("materials", "ParseVersion")
    root = Path(settings.DATA_DIR).resolve()
    for parse in ParseVersion.objects.filter(state="ready", content_hash=""):
        path = (root / parse.document_key).resolve()
        if parse.document_key and path.is_relative_to(root) and path.is_file():
            parse.content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            parse.save(update_fields=["content_hash"])


class Migration(migrations.Migration):
    dependencies = [("materials", "0003_parseversion_content_hash")]
    operations = [migrations.RunPython(fill_hash, migrations.RunPython.noop)]
