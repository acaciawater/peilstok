'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
import json
from peil.models import MasterModule, ECModule, PressureModule, GNSSModule,\
    Device, BaseModule
from peil.models import GNSS_MESSAGE, STATUS_MESSAGE, EC_MESSAGE, PRESSURE_MESSAGE
from django.db.utils import IntegrityError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.conf import settings
import requests

def update_or_create(manager, **kwargs):
    assert kwargs, \
            'update_or_create() must be passed at least one keyword argument'
    obj, created = manager.get_or_create(**kwargs)
    if created:
        return obj, True, False
    else:
        defaults = kwargs.pop('defaults', {})
        try:
            params = dict([(k, v) for k, v in kwargs.items() if '__' not in k])
            params.update(defaults)
            for attr, val in params.items():
                if hasattr(obj, attr):
                    setattr(obj, attr, val)
            sid = transaction.savepoint()
            obj.save(force_update=True)
            transaction.savepoint_commit(sid)
            return obj, False, True
        except IntegrityError, e:
            transaction.savepoint_rollback(sid)
            try:
                return manager.get(**kwargs), False, False
            except:
                raise e

def download_ttn(devid,since):
    """ download data from The Things Network """
    url = settings.TTN_URL
    if devid:
        url += '/' + devid
    if since:
        params = {'last': since }
    else:
        params = None
    headers = {'Authorization': 'key '+settings.TTN_KEY, 'Accept': 'application/json'}
    response = requests.get(url,params=params,headers=headers)
    return response
    
class Command(BaseCommand):
    help = 'Download from The Things Network'
    
    def add_arguments(self, parser):
        parser.add_argument('devid', type=str)

        parser.add_argument('-s','--since',
                action='store',
                default = '1h',
                dest='since',
                help='Download since')

    def handle(self, *args, **options):
        devid = options.get('devid')
        since = options.get('since','1h')
        device = Device.objects.get(devid=devid)
        last = device.last()
        print 'Last message at {:%Y-%m-%d %H:%M:%S}'.format(last)
        response = download_ttn(devid, since)
        if not response.ok:
            print response.reason
            return
        ttns = response.json()
        row = 0
        for ttn in ttns:
            row += 1
            try:
                time = parse_datetime(ttn['time'])

                print devid, time, 
    
                type = ttn['type']

                if type == STATUS_MESSAGE:
                    mod,created,updated = update_or_create(MasterModule.objects,device=device,time=time,type=type,defaults = {
                        'angle': ttn['angle'],
                        'battery': ttn['battery'],
                        'air': ttn['pressure'],
                        'total': ttn['total']})
                    
                elif type == GNSS_MESSAGE:
                    mod,created,updated = update_or_create(GNSSModule.objects,device=device,time=time,type=type, defaults = {
                        'gnsstime': ttn['time'],
                        'lat': ttn['latitude'],
                        'lon': ttn['longitude'],
                        'alt': ttn['height'],
                        'vacc': ttn['vAcc'],
                        'hacc': ttn['hAcc'],
                        'msl': ttn['hMSL']})
                    
                elif type == EC_MESSAGE:
                    mod,created,updated = update_or_create(ECModule.objects,device=device,time=time,type=type, defaults = {
                        'position': ttn['position'],
                        'adc1': ttn['ec1'],
                        'adc2': ttn['ec2'],
                        'temperature': ttn['temperature']})
    
                elif type == PRESSURE_MESSAGE:
                    mod,created,updated = update_or_create(PressureModule.objects,device=device,time=time,type=type, defaults = {
                        'position': ttn['position'],
                        'adc': ttn['pressure']})
                
                else:
                    raise Exception('Unknown module type:'+ str(type))
                
                print 'Created' if created else 'Updated' if updated else '?'
            
            except Exception as e:
                print row, e
                continue
