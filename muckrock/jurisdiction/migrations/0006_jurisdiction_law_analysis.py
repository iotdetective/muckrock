# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-12 16:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jurisdiction', '0005_law'),
    ]

    operations = [
        migrations.AddField(
            model_name='jurisdiction',
            name='law_analysis',
            field=models.TextField(blank=True, help_text=b'Our analysis of the state FOIA law, as a part of FOI95.'),
        ),
    ]
