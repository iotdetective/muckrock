# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2017-02-12 17:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foia', '0022_auto_20170125_2259'),
    ]

    operations = [
        migrations.AlterField(
            model_name='communicationopen',
            name='client_os',
            field=models.CharField(max_length=10, verbose_name=b'Client OS'),
        ),
    ]
