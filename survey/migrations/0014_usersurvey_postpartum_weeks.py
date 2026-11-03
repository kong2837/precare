from django.db import migrations, models


def rename_postpartum_survey(apps, schema_editor):
    Survey = apps.get_model("survey", "Survey")
    Survey.objects.using(schema_editor.connection.alias).filter(
        models.Q(title__icontains="EPDS") | models.Q(title__icontains="산후우울") | models.Q(title__icontains="산후 우울")
    ).update(title="[연구종료시]산후우울검사")


class Migration(migrations.Migration):
    dependencies = [("survey", "0013_reply_score")]
    operations = [
        migrations.AddField(
            model_name="usersurvey", name="postpartum_weeks",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="출산 후 경과(주)", help_text="산후우울검사 작성 시 출산 후 경과 주수"),
        ),
        migrations.RunPython(rename_postpartum_survey, migrations.RunPython.noop),
    ]
