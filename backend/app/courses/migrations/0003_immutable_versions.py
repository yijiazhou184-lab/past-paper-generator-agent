from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("courses", "0002_coursemachinebase_coursedraft_userstatement_and_more")]
    operations = [migrations.RunSQL("""
        CREATE FUNCTION reject_course_version_update() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Confirmed course versions are immutable'; END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER immutable_course_version BEFORE UPDATE ON courses_courseversion
        FOR EACH ROW EXECUTE FUNCTION reject_course_version_update();
    """, """
        DROP TRIGGER immutable_course_version ON courses_courseversion;
        DROP FUNCTION reject_course_version_update();
    """)]
