from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime
from django.conf import settings
from django.http.response import HttpResponse, HttpResponseServerError

import datetime, pytz
import logging
import os, re

from .models import Device, GNSS_MESSAGE, EC_MESSAGE, STATUS_MESSAGE, PRESSURE_MESSAGE, ANGLE_MESSAGE
from peil.models import PressureSensor,PressureMessage, GNSS_Sensor, BatterySensor, StatusMessage, \
    AngleSensor, InclinationMessage, LocationMessage, ECSensor, ECMessage, UBXFile
from datetime import timedelta

logger = logging.getLogger(__name__)

def last_waterlevel(device, hours=2):
    """ returns last known waterlevel for a device """
    wps = device.get_sensor('Waterdruk',position=3)
    wp = wps.last_message()
    aps = device.get_sensor('Luchtdruk',position=0)
    ap = aps.last_message()

    tolerance = timedelta(hours=hours)
    if wp.time > ap.time:
        delta = wp.time - ap.time 
    else:
        delta = ap.time - wp.time

    if delta > tolerance:
        if ap.time < wp.time:
            # find any water pressure within tolerance
            fromtime = ap.time - tolerance
            wp = wps.loramessage_set.filter(time__gte=fromtime).last()
        else:
            fromtime = wp.time - tolerance
            ap = aps.loramessage_set.filter(time__gte=fromtime).last()

    level = None
    nap = None
    if ap and wp:
        time = wp.time
        ap = aps.value(ap)
        wp = wps.value(wp)
        level = (wp - ap) / 0.980638
        z = wps.elevation()
        if z is not None:
            nap = level/100.0 + z
    return {'time': time, 'cm': level, 'nap': nap}
    
def battery_status(battery):
    level = min(500,max(0,battery-3000)) / 5 # percent
    return {'level': level, 'icon': '{url}bat{index}.png'.format(url=settings.STATIC_URL, index=int(level/20))} 
    
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
        if created:
            logger.info('{}: {} sensor created'.format(sensor.device, sensor))
    
    def logmsg(msg, created):
        logger.debug('{}: {} {}. time={}'.format(msg.sensor.device, unicode(msg), 'added' if created else 'updated', msg.time ))

    if message_type == STATUS_MESSAGE:

        sensor, created = PressureSensor.objects.get_or_create(device=device,position=0,defaults={'ident':'Luchtdruk'})
        logsens(sensor, created)

        msg, created = PressureMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'adc': payload['pressure']})
        logmsg(msg,created)
        
        sensor, created = BatterySensor.objects.get_or_create(device=device,position=0,defaults={'ident':'Batterij'})
        logsens(sensor, created)
        
        msg, created = StatusMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults= {'battery': payload['battery']})
        logmsg(msg,created)

        sensor, created = AngleSensor.objects.get_or_create(device=device,position=0,defaults={'ident':'Inclinometer'})
        logsens(sensor, created)

        msg, created = InclinationMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'angle': payload['angle']})
        logmsg(msg,created)
        
    elif message_type == GNSS_MESSAGE:

        sensor, created = GNSS_Sensor.objects.get_or_create(device=device,position=0,defaults={'ident':'GPS'})
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
        pos = payload['position']
        sensor, created = ECSensor.objects.get_or_create(device = device, position=pos,defaults={'ident':'EC'+str(pos)})
        logsens(sensor, created)
        msg, created = ECMessage.objects.update_or_create(sensor=sensor, time=server_time, defaults = {
            'adc1': payload['ec1'],
            'adc2': payload['ec2'],
            'temperature': payload['temperature']})
        logmsg(msg,created)

    elif message_type == PRESSURE_MESSAGE:
        sensor, created = PressureSensor.objects.get_or_create(device = device, position=payload['position'],defaults={'ident':'Waterdruk'})
        logsens(sensor, created)
        msg, created = PressureMessage.objects.update_or_create(sensor=sensor, time=server_time, defaults = {'adc': payload['pressure']})
        logmsg(msg,created)

    elif message_type == ANGLE_MESSAGE:
        sensor, created = AngleSensor.objects.get_or_create(device=device,position=0,defaults={'ident':'Inclinometer'})
        logsens(sensor, created)
        msg, created = InclinationMessage.objects.update_or_create(sensor=sensor, time = server_time, defaults = {'angle': payload['angle']})
        logmsg(msg,created)
    
    else:
        raise Exception('Unknown message type:'+ str(message_type))
    
    return msg, True, False

def parse_ttn(ttn):
    """ parse json pushed from ttn server """
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
            logger.debug('device {} created'.format(unicode(device)))
        
        mod, created, updated = parse_payload(device, server_time, pf)
        
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
        return valid, fixType, {'timestamp': datetime.datetime(year, month, day, hour, min, sec, tzinfo = pytz.utc),
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
            valid, fix, fields = decode(data)
            if valid and fix == 3: # Allow only valid 3D fixes
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
 
def add_ubx(ubxfile):
    
    # extract serial number of peilstok from filename
    filename = os.path.basename(ubxfile.name)
    match = re.match('(?P<serial>[0-9A-F]+)\-\d+\.\w{3}',filename)
    serial = match.group('serial')
    
    # find Device
    try:
        device = Device.objects.get(serial=serial)
    except Device.DoesNotExist:
        logger.error('Device {} not found'.format(serial))
        return
    try:
        # find existing ubxfile for this device
        device.ubxfile_set.get(ubxfile__startswith='ubx/'+filename)
        logger.warning('UBX file bestaat al')
    except UBXFile.DoesNotExist:
        ubx = UBXFile(device=device)
        ubx.ubxfile.save(filename,ubxfile)
        
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

rdnap = TransNAP()
