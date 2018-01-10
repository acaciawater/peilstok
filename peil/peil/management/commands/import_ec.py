'''
Created on Dec 10, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from csv import DictReader
from datetime import datetime
from acacia.data.models import MeetLocatie
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
                    defaults={'user': user,'timezone':'Europe/Amsterdam','type':'scatter','unit': 'oC'}
                    if ec1:
                        series = mloc.series_set.get(name='ECondiep')
                        series.datapoints.get_or_create(date=date,value=ec1)
                    if ec2:
                        series = mloc.series_set.get(name='ECdiep')
                        series.datapoints.get_or_create(date=date,value=ec2)
                    if t1:
                        series,_ = mloc.series_set.get_or_create(name='Tdiep',defaults=defaults)
                        series.datapoints.get_or_create(date=date,value=t1)
                    if t2:
                        series,_ = mloc.series_set.get_or_create(name='Tondiep',defaults=defaults)
                        series.datapoints.get_or_create(date=date,value=t2)
