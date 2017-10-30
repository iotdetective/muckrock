# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-10-23 10:37
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agency', '0012_auto_20171004_1403'),
        ('task', '0019_auto_20171004_1334'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewAgencyTask',
            fields=[
                ('task_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='task.Task')),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agency.Agency')),
            ],
            bases=('task.task',),
        ),
    ]
