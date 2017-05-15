from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime
from .models import Device, MasterModule, ECModule, PressureModule, GNSSModule
from .models import GNSS_MESSAGE, EC_MESSAGE, STATUS_MESSAGE, PRESSURE_MESSAGE

import logging
logger = logging.getLogger(__name__)

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

def parse_ttn(ttn):
    """ parse json from ttn server with peilstok data """

    devid = ttn['devid']
    time = parse_datetime(ttn['time'])
    type = ttn['type']
    
    logger.debug('{},{},{}'.format(devid, time, type))

    device = Device.objects.get(devid=devid)

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
    