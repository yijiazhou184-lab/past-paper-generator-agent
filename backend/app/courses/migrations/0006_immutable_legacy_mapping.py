from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("courses", "0005_topic_catalog")]
    operations = [migrations.RunSQL("""
        CREATE TRIGGER immutable_legacy_topic_mapping BEFORE UPDATE OR DELETE ON courses_legacytopicmapping
        FOR EACH ROW EXECUTE FUNCTION reject_course_version_update();
    """, "DROP TRIGGER immutable_legacy_topic_mapping ON courses_legacytopicmapping;")]
