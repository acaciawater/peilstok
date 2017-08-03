# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-08-03 09:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0044_auto_20170712_1409'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='device',
            options={'ordering': ('displayname',), 'verbose_name': 'Peilstok', 'verbose_name_plural': 'Peilstokken'},
        ),
        migrations.AlterField(
            model_name='ecsensor',
            name='adc1_coef',
            field=models.CharField(default=b'[  1.43453540e+00,  -1.02708649e+04,   1.88152861e+07,  -3.30859300e+03]', max_length=200, verbose_name=b'Coefficienten ring1'),
        ),
        migrations.AlterField(
            model_name='ecsensor',
            name='adc1_limits',
            field=models.CharField(default=b'[3320,4095]', max_length=50, verbose_name=b'bereik ring1'),
        ),
        migrations.AlterField(
            model_name='ecsensor',
            name='adc2_coef',
            field=models.CharField(default=b'[  1.43517078e+02,  -1.13560300e+06,   2.25674636e+09,  -2.86028622e+03]', max_length=200, verbose_name=b'Coefficienten ring2'),
        ),
        migrations.AlterField(
            model_name='ecsensor',
            name='adc2_limits',
            field=models.CharField(default=b'[3500,4000]', max_length=50, verbose_name=b'bereik ring2'),
        ),
    ]