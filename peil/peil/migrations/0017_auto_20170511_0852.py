# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-11 06:52
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0016_auto_20170510_2310'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pressuremodule',
            old_name='raw',
            new_name='adc',
        ),
    ]
