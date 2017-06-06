# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-27 19:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basemodule',
            name='type',
            field=models.IntegerField(choices=[(6, b'Master'), (2, b'EC'), (3, b'Pressure')]),
        ),
        migrations.AlterUniqueTogether(
            name='basemodule',
            unique_together=set([('serial', 'time', 'type')]),
        ),
    ]
