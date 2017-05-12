'''
Created on Apr 28, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import MasterModule, ECModule, PressureModule
import os

class Command(BaseCommand):
    args = ''
    help = 'Dump data to file'
    
    def add_arguments(self, parser):
        parser.add_argument('-d','--dir',
                action='store',
                dest='dname',
                help='destination directory')

    def handle(self, *args, **options):
        dname = options.get('dname','.')
        if not os.path.exists(dname):
            os.makedirs(dname)
            
        with open(os.path.join(dname,'ec.csv'),'w') as f:
            f.write('id,time,ec1,ec2,temp\n')
            for m in ECModule.objects.all():
                f.write('{0},{1},{2},{3},{4}\n'.format(m.devid,m.time,m.adc1,m.adc2,m.temperature))

        with open(os.path.join(dname,'master.csv'),'w') as f:
            f.write('id,time,angle,battery,pressure\n')
            for m in MasterModule.objects.all():
                f.write('{0},{1},{2},{3},{4}\n'.format(m.devid,m.time,m.angle,m.battery,m.pressure))

        with open(os.path.join(dname,'pressure.csv'),'w') as f:
            f.write('id,time,pressure\n')
            for m in PressureModule.objects.all():
                f.write('{0},{1},{2}\n'.format(m.devid,m.time,m.pressure))
