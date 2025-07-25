# Generated by Django 4.2.7 on 2024-04-28 05:50

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('survey', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersurvey',
            name='user',
            field=models.ForeignKey(db_column='user_id', db_comment='user id', help_text='유저 id', on_delete=django.db.models.deletion.CASCADE, related_name='user_survey', to=settings.AUTH_USER_MODEL),
        ),
    ]
