'''
Created on Dec 10, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from csv import DictReader
from datetime import datetime
from acacia.data.models import MeetLocatie
import pytz
from peil.models import Device

class Command(BaseCommand):
    args = ''
    help = 'Import waterhoogte metingen'
    
    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str, help='import_waterlevel csvfile(s)')

    def handle(self, *args, **options):
        files = options.get('files')
        tz = pytz.timezone('Europe/Amsterdam')
        for fname in files:
            print 'Importing '+fname
            with open(fname) as f:
                reader = DictReader(f)
                for row in reader:
                    id = row['Peilstok']
                    date = row['Datum']
                    time = row['Tijd']
                    stand = row['Waterstand']
                    if stand:
                        try:
                            stand = float(stand)
                            date = datetime.strptime(date + ' ' + time,'%d/%m/%Y %H:%M')
                            date = tz.localize(date)
                        except Exception as e:
                            print e
                            continue
                        displayname='Peilstok{:02d}'.format(int(id))
                        print displayname
                        device = Device.objects.get(displayname=displayname)
                        nap = device.get_nap()
                        if nap:
                            mloc = MeetLocatie.objects.get(name=displayname)
                            series = mloc.series_set.get(name='Waterstand')
                            series.datapoints.update_or_create(date=date,defaults={'value':nap-stand})
                        else:
                            print 'Geen NAP hoogte bekend'