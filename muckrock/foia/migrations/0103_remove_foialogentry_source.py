# Generated by Django 4.2 on 2023-10-26 14:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("foia", "0102_foialog_foialogentry"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="foialogentry",
            name="source",
        ),
    ]
