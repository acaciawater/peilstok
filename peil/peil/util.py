from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime
from .models import Device, MasterModule, ECModule, PressureModule, GNSSModule
from .models import GNSS_MESSAGE, EC_MESSAGE, STATUS_MESSAGE, PRESSURE_MESSAGE

import logging
from peil.models import CalibrationSeries
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

def parse_payload(device,time,type,payload):
    if type == STATUS_MESSAGE:
        return update_or_create(MasterModule.objects,device=device,time=time,type=type,defaults = {
            'angle': payload['angle'],
            'battery': payload['battery'],
            'air': payload['pressure'],
            'total': payload['total']})
        
    elif type == GNSS_MESSAGE:
        return update_or_create(GNSSModule.objects,device=device,time=time,type=type, defaults = {
            'gnsstime': payload['time'],
            'lat': payload['latitude'],
            'lon': payload['longitude'],
            'alt': payload['height'],
            'vacc': payload['vAcc'],
            'hacc': payload['hAcc'],
            'msl': payload['hMSL']})
        
    elif type == EC_MESSAGE:
        return update_or_create(ECModule.objects,device=device,time=time,type=type, defaults = {
            'position': payload['position'],
            'adc1': payload['ec1'],
            'adc2': payload['ec2'],
            'temperature': payload['temperature']})

    elif type == PRESSURE_MESSAGE:
        return update_or_create(PressureModule.objects,device=device,time=time,type=type, defaults = {
            'position': payload['position'],
            'adc': payload['pressure']})
    
    else:
        raise Exception('Unknown module type:'+ str(type))
    
def parse_fiware(ttn):
    """ parse json from fiware server with peilstok data """

    devid = ttn['device_id']
    time = parse_datetime(ttn['time'])
    type = ttn['type']
    
    logger.debug('{},{},{}'.format(devid, time, type))

    device = Device.objects.get(devid=devid)

    mod, created, updated = parse_payload(device, time, type, ttn)
    logger.debug('{} {}'.format(mod,'created' if created else 'updated' if updated else 'ignored'))
    return mod, created, updated

def parse_ttn(ttn):
    """ parse json from ttn server with peilstok data """

    try:
        serial = ttn['hardware_serial']
        devid = ttn['dev_id']
        appid = ttn['app_id']
        meta = ttn['metadata']
        time = parse_datetime(meta['time'])
        pf = ttn['payload_fields']
        type = pf['type']
    except Exception as e:
        logger.error('Error parsing TTN json' + str(e))
        raise e

    logger.debug('{},{},{}'.format(devid, time, type))
    cal_default = CalibrationSeries.objects.get(name='default')
    device, created = Device.objects.get_or_create(serial=serial,devid=devid, defaults={'cal':cal_default})
    if created:
        logger.debug('device {} created'.format(devid))

    mod, created, updated = parse_payload(device, time, type, pf)
    logger.debug('{} {}'.format(mod,'created' if created else 'updated' if updated else 'ignored'))
    return mod, created, updated
    
def handle_post_data(json):
    # start background process that handles post data from TTN server
    from threading import Thread
    t = Thread(target=parse_ttn, args=[json,])
    t.start()
    