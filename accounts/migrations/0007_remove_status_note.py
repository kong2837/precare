# Generated by Django 4.2.7 on 2024-06-28 07:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_alter_status_end_datetime_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='status',
            name='note',
        ),
    ]
