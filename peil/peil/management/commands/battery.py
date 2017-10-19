'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Sensor

class Command(BaseCommand):
    args = ''
    help = 'Dump battery status'
    
#     def add_arguments(self, parser):
#         parser.add_argument('dirs', nargs='+', type=str, help='photo dirs')

    def add_arguments(self, parser):
        parser.add_argument('-d','--device',
            action='store',
            dest='devid',
            help='device id')

    def handle(self, *args, **options):
        query = Sensor.objects.filter(ident='Batterij')
        devid = options['devid']
        if devid:
            query = query.filter(device__devid=devid)
        print 'device,timestamp,level,percentage'
        fmt = '{}, {:%Y-%m-%d %H:%M}, {:.2f} mV, {}%'
        for sensor in query:
            m = sensor.last_message()
            level = int(min(500,max(0,m.battery-3000)) / 5.0)
            print fmt.format(sensor.device, m.time, m.battery*1e-3, level)