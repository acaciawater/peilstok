# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-07 19:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0005_auto_20170505_0055'),
    ]

    operations = [
        migrations.AddField(
            model_name='ecmodule',
            name='position',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pressuremodule',
            name='position',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='basemodule',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(1, b'GNSS'), (2, b'EC'), (3, b'Pressure'), (6, b'Master')]),
        ),
        migrations.AlterField(
            model_name='mastermodule',
            name='total',
            field=models.PositiveSmallIntegerField(),
        ),
    ]
