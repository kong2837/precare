# Generated by Django 4.2.7 on 2024-05-14 14:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0002_alter_usersurvey_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='answer',
            name='value',
            field=models.IntegerField(blank=True, db_column='value', help_text='질문에 값이 존재할 경우 값을 기재합니다.', null=True),
        ),
    ]
