'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
import os
from peil.models import CalibrationSeries
from csv import DictReader
from django.db import transaction

class Command(BaseCommand):
    
    help = 'Load calibration data'
    
    def add_arguments(self, parser):
        parser.add_argument('-f','--file',
                action='store',
                dest='fname',
                help='calibration file')


    def handle(self, *args, **options):
        fname = options.get('fname')
        with open(fname) as f:
            reader = DictReader(f)
            with transaction.atomic():
                try:
                    series, created = CalibrationSeries.objects.get_or_create(name=os.path.basename(fname))
                    if not created:
                        # replace all datapoints
                        series.calibrationdata_set.all().delete()
                    for row in reader:
                        ec1 = row['EC1']
                        ec2 = row['EC2']
                        ec2 = float(ec2) if ec2 else None
                        ec = row['WTW']
                        series.calibrationdata_set.create(adc1=ec1,adc2=ec2,value=ec)
                        print ec, ec1, ec2
                except Exception as e:
                    transaction.rollback()
                    raise e