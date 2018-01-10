'''
Created on Jan 06, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device, PressureMessage
import pandas as pd
from acacia.data.models import Series

class Command(BaseCommand):
    args = ''
    help = 'Dump luchtdruk metingen'
    
    def add_arguments(self, parser):
        parser.add_argument('-d','--device',
            action='store',
            dest='name',
            help='device displayname')
        
    def handle(self, *args, **options):
        query = Device.objects.all()
        name = options['name']
        if name:
            query = query.filter(displayname__iexact=name)
        dekooy = Series.objects.get(name='Luchtdruk de Kooy')
        with open('luchtdruk.csv','w') as f:
            f.write('device,time,adc,hPa,deKooy\n')
            for dev in query:
                print dev.displayname
                try:
                    def mapper(obj):
                        if pd.isnull(obj):
                            return ''
                        return str(obj)

                    for m in PressureMessage.objects.filter(sensor__device__id=dev.id,sensor__ident='Luchtdruk'):
                        f.write(','.join(map(mapper,[
                            dev.displayname,
                            m.time, 
                            m.adc,
                            m.sensor.value(m),
                            dekooy.at(m.time).value
                            ])))
                        f.write('\n')
                except Exception as e:
                    print e
