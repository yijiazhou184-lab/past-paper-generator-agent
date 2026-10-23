from django.db import migrations

TABLES = ("blueprint", "structureconfirmation", "generationsnapshot", "planninggrant")


class Migration(migrations.Migration):
    dependencies = [("generation", "0001_initial")]
    operations = [migrations.RunSQL(
        """CREATE FUNCTION reject_generation_record_update() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Frozen generation records are immutable'; END;
        $$ LANGUAGE plpgsql;""" + "\n".join(
            f"CREATE TRIGGER immutable_{name} BEFORE UPDATE ON generation_{name} FOR EACH ROW EXECUTE FUNCTION reject_generation_record_update();"
            for name in TABLES),
        "\n".join(f"DROP TRIGGER immutable_{name} ON generation_{name};" for name in TABLES)
        + "DROP FUNCTION reject_generation_record_update();")]
