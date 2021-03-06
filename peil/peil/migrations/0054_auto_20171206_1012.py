# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-12-06 09:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0053_auto_20171007_1219'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='locationmessage',
            options={'verbose_name': 'GPS bericht', 'verbose_name_plural': 'GPS berichten'},
        ),
        migrations.AlterModelOptions(
            name='ubxfile',
            options={'verbose_name': 'GPS bestand', 'verbose_name_plural': 'GPS bestanden'},
        ),
        migrations.AlterField(
            model_name='device',
            name='displayname',
            field=models.CharField(max_length=40, verbose_name=b'naam'),
        ),
        migrations.AlterField(
            model_name='sensor',
            name='unit',
            field=models.CharField(default=b'-', max_length=10, verbose_name=b'eenheid'),
        ),
    ]
