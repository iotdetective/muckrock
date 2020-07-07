# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-07-07 18:43
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('foia', '0070_auto_20200707_1435'),
    ]

    operations = [
        migrations.AlterField(
            model_name='communicationmovelog',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='foiacommunication',
            name='from_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sent_communications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='foiacommunication',
            name='likely_foia',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='likely_communications', to='foia.FOIARequest'),
        ),
        migrations.AlterField(
            model_name='foiacommunication',
            name='to_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='received_communications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='foiamultirequest',
            name='composer',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='multi', to='foia.FOIAComposer'),
        ),
        migrations.AlterField(
            model_name='foiamultirequest',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='foianote',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='outboundcomposerattachment',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pending_outboundcomposerattachment', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='outboundrequestattachment',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pending_outboundrequestattachment', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='rawemail',
            name='communication',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to='foia.FOIACommunication'),
        ),
    ]