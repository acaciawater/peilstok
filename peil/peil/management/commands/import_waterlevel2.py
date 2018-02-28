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
    help = 'Import waterhoogte metingen van survey feb 2018'
    
    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str, help='import_waterlevel2 csvfile(s)')

    def handle(self, *args, **options):
        files = options.get('files')
        tz = pytz.timezone('Europe/Amsterdam')
        for fname in files:
            print 'Importing '+fname
            with open(fname) as f:
                reader = DictReader(f)
                for row in reader:
                    displayname = row['Peilstok']
                    date = row['Datum']
                    time = row['Tijd']
                    stand = row['Waterstand - meetpunt (m)']
                    nap = row['Meetpunt (m tov NAP)']
                    if stand:
                        try:
                            stand = float(stand)
                            date = datetime.strptime(date + ' ' + time,'%Y-%m-%d %H:%M:%S')
                            date = tz.localize(date)
                        except Exception as e:
                            print e
                            continue
                        print displayname
                        if nap:
                            try:
                                nap = float(nap)
                            except:
                                continue
                            mloc = MeetLocatie.objects.get(name=displayname)
                            series = mloc.series_set.get(name='Waterstand')
                            series.datapoints.update_or_create(date=date,defaults={'value':nap-stand})
                        else:
                            print 'Geen NAP hoogte bekend'