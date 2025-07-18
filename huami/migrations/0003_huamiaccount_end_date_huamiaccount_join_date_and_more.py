# Generated by Django 4.2.7 on 2024-09-26 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('huami', '0002_alter_huamiaccount_email_alter_huamiaccount_password_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='huamiaccount',
            name='end_date',
            field=models.DateTimeField(db_column='end_date', help_text='연구 종료일', null=True),
        ),
        migrations.AddField(
            model_name='huamiaccount',
            name='join_date',
            field=models.DateTimeField(db_column='join_date', help_text='연구 시작일', null=True),
        ),
        migrations.AddField(
            model_name='huamiaccount',
            name='name',
            field=models.CharField(db_column='name', help_text='사용자 이름', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='huamiaccount',
            name='research_status',
            field=models.CharField(choices=[('ongoing', '진행 중'), ('completed', '종료'), ('preparing', '준비')], db_column='research_status', default='preparing', max_length=10),
        ),
    ]
