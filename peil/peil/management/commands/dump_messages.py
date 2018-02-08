'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device, PressureMessage, ECMessage, LoraMessage
from django.utils.text import slugify

class Command(BaseCommand):
    args = ''
    help = 'Dump data'
    
#     def add_arguments(self, parser):
#         parser.add_argument('dirs', nargs='+', type=str, help='photo dirs')

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
        with open('messages.csv','w') as f:
            f.write('device,sensor,time,value\n')
            for dev in query:
                print dev
                for m in LoraMessage.objects.filter(sensor__device__id=dev.id).order_by('time'):
                    sensor = m.sensor
                    f.write(','.join(map(str,[dev.displayname, sensor.ident, m.time.strftime('%Y-%m-%d %H:%M:%S'), sensor.value(m)])))
                    f.write('\n')
            