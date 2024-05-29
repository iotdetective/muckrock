# Generated by Django 4.2 on 2024-03-29 14:31

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("foia", "0104_alter_foialogentry_options"),
        ("task", "0054_alter_flaggedtask_category_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentinfotask",
            name="foia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="foia.foiarequest",
            ),
        ),
        migrations.AddField(
            model_name="paymentinfotask",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]