# Generated by Django 4.2 on 2023-07-28 19:25

from django.db import migrations, models
import django.utils.timezone
import easy_thumbnails.fields


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0018_homepageoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepageoverride",
            name="image_override",
            field=easy_thumbnails.fields.ThumbnailerImageField(
                blank=True, null=True, upload_to="news_images/%Y/%m/%d"
            ),
        ),
        migrations.AddField(
            model_name="homepageoverride",
            name="pub_date_override",
            field=models.DateTimeField(
                blank=True,
                default=django.utils.timezone.now,
                null=True,
                verbose_name="Publish date",
            ),
        ),
        migrations.AddField(
            model_name="homepageoverride",
            name="summary_override",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="homepageoverride",
            name="title_override",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]