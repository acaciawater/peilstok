# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-29 12:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0037_auto_20170629_1306'),
    ]

    operations = [
        migrations.AddField(
            model_name='ecsensor',
            name='ec_range',
            field=models.CharField(default=b'700,35000', max_length=50),
        ),
    ]
