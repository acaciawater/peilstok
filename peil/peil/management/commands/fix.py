'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device, RTKSolution

class Command(BaseCommand):
    args = ''
    help = 'Dump GPS fix results'
    
#     def add_arguments(self, parser):
#         parser.add_argument('dirs', nargs='+', type=str, help='photo dirs')

    def add_arguments(self, parser):
        parser.add_argument('-d','--device',
            action='store',
            dest='devid',
            help='device id')

    def handle(self, *args, **options):
        query = Device.objects.all()
        devid = options['devid']
        if devid:
            query = query.filter(devid=devid)
        print 'device,type,time,lat,lon,alt,vacc,x,y,z'
        fmt = '{},{},{:%Y-%m-%d %H:%M:%S},{},{},{},{},{},{},{}'
        for dev in query:
            for sur in dev.survey_set.all():
                print fmt.format(dev, 'sur', sur.time, '', '', '', sur.vacc/1e3, sur.location.x, sur.location.y, sur.altitude) 
            gps = dev.get_sensor('GPS')
            for pos in gps.loramessage_set.order_by('time'):
                x,y,z = pos.NAPvalue()
                # lon/lat have been switched
                lon = pos.lat/1e7
                lat = pos.lon/1e7
                print fmt.format(dev, 'gps', pos.time, lat, lon, pos.alt/1e3, pos.vacc/1e3, x, y, z)
            for sol in RTKSolution.objects.filter(ubx__device=dev).order_by('time'):
                print fmt.format(dev, 'rtk', sol.time, sol.lat, sol.lon, sol.alt, sol.sdu, sol.x, sol.y, sol.z)
                