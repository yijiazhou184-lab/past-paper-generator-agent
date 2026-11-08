from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("courses", "0009_user_decision_metadata")]

    operations = [
        migrations.AddField(
            model_name="coursedraft",
            name="exam_template",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
