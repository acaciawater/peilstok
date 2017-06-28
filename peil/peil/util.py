from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime
from .models import Device, GNSS_MESSAGE, EC_MESSAGE, STATUS_MESSAGE, PRESSURE_MESSAGE, ANGLE_MESSAGE
import datetime, pytz
import logging

from peil.models import PressureSensor,\
    PressureMessage, GNSS_Sensor, BatterySensor, StatusMessage, AngleSensor,\
    InclinationMessage, LocationMessage, ECSensor, ECMessage
from django.http.response import HttpResponse, HttpResponseServerError

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

def parse_payload(device,server_time,payload):
    message_type = payload['type']
    msg = None
    
    def logsens(sensor, created):
        logger.debug('Sensor {} at position {} {}'.format(sensor, sensor.position, 'created' if created else 'found'))
    
    def logmsg(msg, created):
        logger.debug('{} {}. time={}'.format(type(msg).__name__, 'created' if created else 'updated', msg.time ))

    if message_type == STATUS_MESSAGE:

        sensor, created = PressureSensor.objects.get_or_create(device=device,position=0)
        logsens(sensor, created)

        msg, created = PressureMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'adc': payload['pressure']})
        logmsg(msg,created)
        
        sensor, created = BatterySensor.objects.get_or_create(device=device,position=0)
        logsens(sensor, created)
        
        msg, created = StatusMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults= {'battery': payload['battery']})
        logmsg(msg,created)

        sensor, created = AngleSensor.objects.get_or_create(device=device,position=0)
        logsens(sensor, created)

        msg, created = InclinationMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'angle': payload['angle']})
        logmsg(msg,created)
        
    elif message_type == GNSS_MESSAGE:

        sensor, created = GNSS_Sensor.objects.get_or_create(device=device,position=0)
        logsens(sensor, created)
        msg, created = LocationMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = { 
            'lat': payload['latitude'],
            'lon': payload['longitude'],
            'alt': payload['height'],
            'vacc': payload['vAcc'],
            'hacc': payload['hAcc'],
            'msl': payload['hMSL']})
        logmsg(msg,created)
        
    elif message_type == EC_MESSAGE:
        sensor, created = ECSensor.objects.get_or_create(device = device, position=payload['position'])
        logsens(sensor, created)
        msg, created = ECMessage.objects.update_or_create(sensor=sensor, time=server_time, defaults = {
            'adc1': payload['ec1'],
            'adc2': payload['ec2'],
            'temperature': payload['temperature']})
        logmsg(msg,created)

    elif message_type == PRESSURE_MESSAGE:
        sensor, created = PressureSensor.objects.get_or_create(device = device, position=payload['position'])
        logsens(sensor, created)
        msg, created = PressureMessage.objects.update_or_create(sensor=sensor, time=server_time, defaults = {'adc': payload['pressure']})
        logmsg(msg,created)

    elif message_type == ANGLE_MESSAGE:
        sensor, created = AngleSensor.objects.get_or_create(device=device,position=0)
        logsens(sensor, created)
        msg, created = InclinationMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'angle': payload['angle']})
        logmsg(msg,created)
    
    else:
        raise Exception('Unknown message type:'+ str(message_type))
    
    return msg, True, False

def parse_fiware(ttn):
    """ parse json from fiware server with peilstok data """

    devid = ttn['device_id']
    server_time = parse_datetime(ttn['time'])
    type = ttn['type']
    
    logger.debug('{},{},{}'.format(devid, server_time, type))

    device = Device.objects.get(devid=devid)
    device.last_seen = server_time
    device.save(update_fields=('last_seen',))

    mod, created, updated = parse_payload(device, server_time, ttn)
    #logger.debug('{} {}'.format(mod,'added' if created else 'updated' if updated else 'ignored'))
    return mod, created, updated

def parse_ttn(ttn):
    """ parse json from ttn server with peilstok data """

    try:
        serial = ttn['hardware_serial']
        devid = ttn['dev_id']
        appid = ttn['app_id']
        meta = ttn['metadata']
        server_time = parse_datetime(meta['time'])
        pf = ttn['payload_fields']
    except Exception as e:
        logger.error('Error parsing payload {}\n{}'.format(ttn,e))
        raise e

    try:
        device, created = Device.objects.update_or_create(serial=serial,devid=devid, defaults={'last_seen': server_time})

        if created:
            logger.debug('device {} created'.format(devid))
        
        mod, created, updated = parse_payload(device, server_time, pf)

#        logger.debug('{} {} for {} {}'.format(type(mod).__name__, 'created' if created else 'updated' if updated else 'ignored', mod.device, mod.time))
        return mod, created, updated
    except Exception as e:
        logger.exception('Error parsing payload: {}'.format(ttn))
        raise e
    
def handle_post_data(json):
    try:
        mod, created, updated = parse_ttn(json)
        return HttpResponse(unicode(mod),status=201)
    except Exception as e:
        return HttpResponseServerError(e)

def handle_post_data_async(json):
    # start background process that handles post data from TTN server
    from threading import Thread
    t = Thread(target=parse_ttn, args=[json,])
    t.start()
    return t

UBX_HEADER = 0x62B5
UBX_NAV_PVT = 0x0701

def iterpvt(ubx):
    """ iterate over ubx file and yield pvt instances """

    import struct

    def decode(data):
        iTOW, year, month, day, hour, min, sec, valid, tAcc, nano, fixType, flags, reserved1, \
            numSV, lon, lat, height, hMSL, hAcc, vAcc, velN, velE, velD, gSpeed, heading, sAcc, \
            headingAcc, pDOP, reserved2, reserved3 = struct.unpack('<IHBBBBBbIiBbBBiiiiIIiiiiiIIHHI', data)
        return fixType, {'timestamp': datetime.datetime(year, month, day, hour, min, sec, tzinfo = pytz.utc),
                'lat': lat*1e-7, 
                'lon': lon*1e-7,
                'alt': height, 
                'msl' : hMSL, 
                'hAcc': hAcc,
                'vAcc': vAcc,
                'numSV': numSV,
                'pDOP': pDOP*1e-2}

    while True:
        data=ubx.read(6)
        if len(data) != 6:
            break
        hdr, msgid, length = struct.unpack('<HHH',data) 
        if hdr != UBX_HEADER:
            raise ValueError('UBX header tag expected')
        data = ubx.read(length)
        checksum = ubx.read(2) # TODO verify checksum
        if msgid == UBX_NAV_PVT:
            fix, fields = decode(data)
            if fix == 3: # Allow only 3D fixes
                yield fields
                
def ubxtime(ubx):
    """ return time of first and last observation in ubxfile """
    ubx.seek(0)
    start = stop = None
    for pvt in iterpvt(ubx):
        time = pvt['timestamp']
        if start == None:
            start = stop = time
        else:
            stop = time
    return start, stop
 
# GPS time=0
GPST0 = datetime.datetime(1980,1,6,0,0,0)

def gps2time(week,ms):
    ''' convert gps tow and week to python datetime '''
    if ms < -1e9 or ms > 1e9: ms = 0
    delta1 = datetime.timedelta(weeks=week)
    delta2 = datetime.timedelta(seconds=ms/1000.0)
    return GPST0 + delta1 + delta2

def time2gps(time):
    ''' convert python datetime to gps week and tow '''
    delta = time - GPST0
    sec = delta.total_seconds()
    week = int(sec/(86400*7))
    tow = sec - week * 86400*7 + delta.seconds # time of week
    dow = int(tow / 86400)-1 # day of week
    return week, dow, tow

class TransNAP:
    ''' transform 3D coordinates from WGS84 to RDNAP '''
  
    def __init__(self):
        import osr

        wgs = osr.SpatialReference()
        wgs.ImportFromProj4('+init=epsg:4326') # should be 4979, but this works as well
        #wgs.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        rd = osr.SpatialReference()
        rd.ImportFromProj4('+init=rdnap:rdnap')
        self.fwd = osr.CoordinateTransformation(wgs,rd)
        self.inv = osr.CoordinateTransformation(rd,wgs)
    
    def to_rdnap(self,x,y,z):
        return self.fwd.TransformPoint(x,y,z)

    def to_wgs84(self,x,y,z):
        return self.inv.TransformPoint(x,y,z)

