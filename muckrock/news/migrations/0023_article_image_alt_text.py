# Generated by Django 4.2 on 2023-10-03 18:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0022_homepageoverride_hide_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="image_alt_text",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
