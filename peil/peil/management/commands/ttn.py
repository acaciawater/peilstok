'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
import json
from peil.models import MasterModule, ECModule, PressureModule, GNSSModule,\
    Device, BaseModule
from django.db.utils import IntegrityError
from django.db import transaction
from django.utils.dateparse import parse_datetime

def update_or_create(manager, **kwargs):
    assert kwargs, \
            'update_or_create() must be passed at least one keyword argument'
    obj, created = manager.get_or_create(**kwargs)
    defaults = kwargs.pop('defaults', {})
    if created:
        return obj, True, False
    else:
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

class Command(BaseCommand):
    args = ''
    help = 'Import ttn file'
    
    def add_arguments(self, parser):
        parser.add_argument('-f','--file',
                action='store',
                dest='fname',
                help='ttn filename')

        parser.add_argument('-s','--skip',
                action='store_true',
                default = False,
                dest='skip',
                help='Skip existing entries')

    def handle(self, *args, **options):
        last = BaseModule.objects.all().order_by('time').last()
        print 'Last message at {:%Y-%m-%d %H:%M:%S}'.format(last.time)
        fname = options.get('fname')
        skip = options.get('skip')
        with open(fname) as f:
            for line in f:
                try:
                    ttn = json.loads(line)
                    pf = ttn['payload_fields']
                except Exception as e:
                    print line[:40], e
                    continue

                serial = ttn['hardware_serial']
                devid = ttn['dev_id']
                device, created = Device.objects.get_or_create(serial=serial,devid=devid)
                
                appid = ttn['app_id']
                type = pf['type']
                meta = ttn['metadata']
                time = parse_datetime(meta['time'])
                
                if time < last.time and skip:
                    #print devid, type, time, 'skipped' 
                    #continue
                    pass

                print devid, type, time, 

                if type == 6:
                    mod,created,updated = update_or_create(MasterModule.objects,device=device,time=time,type=type,defaults = {
                        'appid': appid,
                        'angle': pf['angle'],
                        'battery': pf['battery'],
                        'air': pf['pressure'],
                        'total': pf['total']})
                    
                elif type == 1:
                    mod,created,updated = update_or_create(GNSSModule.objects,device=device,time=time,type=type, defaults = {
                        'appid': appid,
                        'gnsstime': pf['time'],
                        'lat': pf['latitude'],
                        'lon': pf['longitude'],
                        'alt': pf['height'],
                        'vacc': pf['vAcc'],
                        'hacc': pf['hAcc'],
                        'msl': pf['hMSL']})
                    
                elif type == 2:
                    mod,created,updated = update_or_create(ECModule.objects,device=device,time=time,type=type, defaults = {
                        'appid': appid,
                        'position': pf['position'],
                        'adc1': pf['ec1'],
                        'adc2': pf['ec2'],
                        'temperature': pf['temperature']})

                elif type == 3:
                    mod,created,updated = update_or_create(PressureModule.objects,device=device,time=time,type=type, defaults = {
                        'appid': appid,
                        'position': pf['position'],
                        'adc': pf['pressure']})
                
                else:
                    raise Exception('Unknown module type:'+ str(type))
                
                print 'Created' if created else 'Updated' if updated else '?'
