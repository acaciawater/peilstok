'''
Created on Dec 10, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from csv import DictReader
from datetime import datetime
from acacia.data.models import MeetLocatie
import pytz

class Command(BaseCommand):
    args = ''
    help = 'Import EC metingen van Nico Tessel'
    
    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str, help='import_ec csvfile(s)')

    def handle(self, *args, **options):
        files = options.get('files')
        tz = pytz.timezone('Europe/Amsterdam')
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
                    date = datetime.strptime(date + ' ' + time,'%d/%m/%Y %H:%M')
                    date = tz.localize(date)
                    displayname='Peilstok{:02d}'.format(int(id))
                    print displayname
                    mloc = MeetLocatie.objects.get(name=displayname)
                    if ec1:
                        series = mloc.series_set.get(name='ECondiep')
                        series.datapoints.get_or_create(date=date,value=ec1)
                    if ec2:
                        series = mloc.series_set.get(name='ECdiep')
                        series.datapoints.get_or_create(date=date,value=ec2)
