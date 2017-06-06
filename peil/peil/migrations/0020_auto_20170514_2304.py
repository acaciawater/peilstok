# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-14 21:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0019_auto_20170511_1706'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='basemodule',
            name='appid',
        ),
        migrations.AddField(
            model_name='basemodule',
            name='base_position',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='device',
            name='created',
            field=models.DateTimeField(),
        ),
    ]
