# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-16 10:25
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('peil', '0028_auto_20170615_2138'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fix',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField(verbose_name=b'Tijdstip van fix')),
                ('lon', models.DecimalField(decimal_places=7, max_digits=10, verbose_name=b'lengtegraad')),
                ('lat', models.DecimalField(decimal_places=7, max_digits=10, verbose_name=b'breedtegraad')),
                ('alt', models.DecimalField(decimal_places=3, max_digits=10, verbose_name=b'hoogte tov ellipsoide')),
                ('x', models.DecimalField(decimal_places=3, max_digits=10, verbose_name=b'x-coordinaat')),
                ('y', models.DecimalField(decimal_places=3, max_digits=10, verbose_name=b'y-coordinaat')),
                ('z', models.DecimalField(decimal_places=3, max_digits=10, verbose_name=b'hoogte tov NAP')),
                ('sdx', models.DecimalField(decimal_places=3, max_digits=6, verbose_name=b'Fout in x-richting')),
                ('sdy', models.DecimalField(decimal_places=3, max_digits=6, verbose_name=b'Fout in y-richting')),
                ('sdz', models.DecimalField(decimal_places=3, max_digits=6, verbose_name=b'Fout in hoogte')),
                ('ahn', models.DecimalField(decimal_places=3, max_digits=10, verbose_name=b'hoogte volgens AHN')),
            ],
        ),
        migrations.CreateModel(
            name='Sensor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('distance', models.IntegerField(default=0, help_text=b'afstand tov antenne in mm', verbose_name=b'afstand')),
                ('type', models.PositiveSmallIntegerField(choices=[(0, b'GPS'), (1, b'EC1'), (2, b'EC2'), (3, b'Luchtdruk'), (4, b'Waterdruk'), (5, b'Inclinometer')])),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='peil.Device')),
            ],
        ),
        migrations.AddField(
            model_name='fix',
            name='sensor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='peil.Sensor'),
        ),
    ]
