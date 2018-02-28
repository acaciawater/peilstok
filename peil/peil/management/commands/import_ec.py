'''
Created on Dec 10, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from csv import DictReader
from datetime import datetime
from acacia.data.models import MeetLocatie, ManualSeries
import pytz
from django.contrib.auth.models import User

class Command(BaseCommand):
    args = ''
    help = 'Import EC metingen van Nico Tessel'
    
    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str, help='import_ec csvfile(s)')

    def handle(self, *args, **options):
        files = options.get('files')
        tz = pytz.timezone('Europe/Amsterdam')
        user = User.objects.get(username='theo')
        for fname in files:
            print 'Importing '+fname
            with open(fname) as f:
                reader = DictReader(f)
                for row in reader:
                    id = row['Peilstok']
                    ec1 = row['ECondiep']
                    ec2 = row['ECdiep']
                    date = row['Datum']
                    time = row['Tijd']
                    t1 = row['Tondiep']
                    t2 = row['Tdiep']
                    date = datetime.strptime(date + ' ' + time,'%d/%m/%Y %H:%M')
                    date = tz.localize(date)
                    displayname='Peilstok{:02d}'.format(int(id))
                    print displayname
                    mloc = MeetLocatie.objects.get(name=displayname)
                    ec_defaults={'user': user,'timezone':'Europe/Amsterdam','type':'scatter','unit': 'mS/cm'}
                    defaults={'user': user,'timezone':'Europe/Amsterdam','type':'scatter','unit': 'oC'}
                    if ec1:
                        series,_ = ManualSeries.objects.get_or_create(mlocatie=mloc,name='ECondiep',defaults=ec_defaults)
                        series.datapoints.update_or_create(date=date,value=ec1)
                    if ec2:
                        series,_ = ManualSeries.objects.get_or_create(mlocatie=mloc,name='ECdiep',defaults=ec_defaults)
                        series.datapoints.update_or_create(date=date,value=ec2)
                    if t1:
                        series,_ = ManualSeries.objects.get_or_create(mlocatie=mloc,name='Tdiep',defaults=defaults)
                        series.datapoints.update_or_create(date=date,value=t1)
                    if t2:
                        series,_ = ManualSeries.objects.get_or_create(mlocatie=mloc,name='Tondiep',defaults=defaults)
                        series.datapoints.update_or_create(date=date,value=t2)
