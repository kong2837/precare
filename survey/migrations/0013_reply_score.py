from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("survey", "0012_actionfeedback")]

    operations = [
        migrations.AddField(
            model_name="reply",
            name="score",
            field=models.IntegerField(blank=True, null=True, help_text="제출 당시 선택한 응답의 점수"),
        ),
    ]
