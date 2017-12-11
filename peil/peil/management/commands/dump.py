'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device, RTKSolution, PressureMessage, ECMessage
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
        for dev in query:
            print dev
            stok = slugify(dev.displayname)
            with open('pressure_{}.csv'.format(stok),'w') as f:
                f.write('device,sensor,time,adc,hPa\n')
                for m in PressureMessage.objects.filter(sensor__device__id=dev.id):
                    sensor = m.sensor
                    f.write(','.join(map(str,[dev.displayname, sensor.ident, m.time, m.adc, sensor.value(m)])))
                    f.write('\n')
            with open('EC_{}.csv'.format(stok),'w') as f:
                f.write('device,sensor,time,adc1,adc2,temperature,EC,EC25\n')
                for m in ECMessage.objects.filter(sensor__device__id=dev.id):
                    sensor = m.sensor
                    ec_ambient = sensor.EC(m.adc1,m.adc2)
                    f.write(','.join(map(str,[dev.displayname, sensor.ident, m.time, m.adc1, m.adc2, m.temperature, ec_ambient, sensor.value(m)])))
                    f.write('\n')
            