from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("papers", "0001_initial"), ("generation", "0004_immutable_candidates")]
    operations = [migrations.RunSQL(
        "CREATE TRIGGER immutable_paper_content BEFORE UPDATE ON papers_contentversion FOR EACH ROW EXECUTE FUNCTION reject_generation_record_update();",
        "DROP TRIGGER immutable_paper_content ON papers_contentversion;"
    )]
