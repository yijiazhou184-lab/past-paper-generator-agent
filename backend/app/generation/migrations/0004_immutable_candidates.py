from django.db import migrations

TABLES = ("generationgrant", "generationartifact", "candidateversion", "checkreport")


class Migration(migrations.Migration):
    dependencies = [("generation", "0003_generation_candidates")]
    operations = [migrations.RunSQL(
        "\n".join(f"CREATE TRIGGER immutable_{name} BEFORE UPDATE ON generation_{name} FOR EACH ROW EXECUTE FUNCTION reject_generation_record_update();" for name in TABLES),
        "\n".join(f"DROP TRIGGER immutable_{name} ON generation_{name};" for name in TABLES))]
