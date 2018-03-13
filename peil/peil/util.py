from django.utils.dateparse import parse_datetime
from django.conf import settings
from django.http.response import HttpResponse, HttpResponseServerError

import datetime, pytz
import logging
import os, re
import numpy as np
import pandas as pd
import math

from .models import Device, GNSS_MESSAGE, EC_MESSAGE, STATUS_MESSAGE, PRESSURE_MESSAGE, ANGLE_MESSAGE
from peil.models import PressureSensor,PressureMessage, GNSS_Sensor, BatterySensor, StatusMessage, \
    AngleSensor, InclinationMessage, LocationMessage, ECSensor, ECMessage, UBXFile,\
    rounds
from datetime import timedelta
from peil.sensor import create_sensors
from peil.decoder import decode
from acacia.data.models import Series, MeetLocatie, Datasource

logger = logging.getLogger(__name__)

def haversine(origin,destination):
    ''' return distance between two points in meters using Haversine formula '''
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371000 # meter

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c
    return d    

def get_raw_sensor_data(device, sensor_name, **kwargs):
    """ 
    @return: Pandas dataframe with timeseries of raw sensor data
    @param device: the device to query 
    """  
    try:
        columns = kwargs.pop('columns',None)
        data = device.get_sensor(sensor_name,**kwargs).raw_data()
        df = pd.DataFrame(data).set_index('time')
        df = df.where(df<4096,np.nan).resample('H').mean() # clear extreme values and resample on every hour
        return df.rename(columns=columns) if columns else df
    except:
        return pd.DataFrame()

def get_raw_data(device, **kwargs):
    """ 
    @return: Pandas dataframe with timeseries of all raw sensor data
    @param device: the device to query 
    """  
    bat = get_raw_sensor_data(device,'Batterij',position=0,columns={'battery': 'BAT'})
    ec1 = get_raw_sensor_data(device,'EC1',position=1,columns={'adc1': 'EC1-ADC1', 'adc2': 'EC1-ADC2', 'temperature': 'EC1-TEMP'})
    ec2 = get_raw_sensor_data(device,'EC2',position=2,columns={'adc1': 'EC2-ADC1', 'adc2': 'EC2-ADC2', 'temperature': 'EC2-TEMP'})
    p1 = get_raw_sensor_data(device,'Luchtdruk',position=0,columns={'adc': 'PRES0-ADC'})
    p2 = get_raw_sensor_data(device,'Waterdruk',position=3,columns={'adc': 'PRES3-ADC'})
    return pd.concat([bat,ec1,ec2,p1,p2],axis=1)

def get_sensor_series(device, sensor_name, **kwargs):
    ''' returns pandas series with calibrated sensor data '''
    try:
        rule = kwargs.pop('resample')
        t,x=zip(*list(device.get_sensor(sensor_name,**kwargs).data()))       
        series = pd.Series(x,index=t)
        if rule:
            return series.resample(rule=rule).mean()
        else:
            return series
    except Exception as e:
        logger.error('ERROR loading sensor data for {}: {}'.format(sensor_name,e))
        return pd.Series()

def drift_correct(series, manual):
    ''' correct drift with manual measurements (both args are pandas series)'''
    left,right=series.align(manual)

    # interpolate values on index of manual measurements
    left = left.interpolate(method='time').groupby(left.index).last()
    
    # calculate difference at manual index
    diff = left.reindex(manual.index) - manual
    
    # interpolate differences to all measurements
    left,right=series.align(diff)
    right = right.interpolate(method='time').groupby(right.index).last()
    drift = right.reindex(series.index).fillna(0)
    
    return series-drift
        
def get_ec_series(device,rule):
    """ 
    @return: Pandas dataframe with timeseries of EC
    @param device: the device to query 
    """  
    ec1 = get_sensor_series(device,'EC1',position=1,resample=rule)
    ec2 = get_sensor_series(device,'EC2',position=2,resample=rule)

    # Feb 2018: find decagon series and append data
    try:
        ds = Datasource.objects.get(generator__name='Decagon', name__icontains=device.displayname)
        for param in ds.parameter_set.filter(name__contains='EC'):
            for series in param.series_set.all():
                data = series.to_pandas()
                if series.name.startswith('EC P1'):
                    ec1 = ec1.append(data)
                elif series.name.startswith('EC P2'):
                    ec2 = ec2.append(data)
    except Datasource.DoesNotExist:
        pass

    df = pd.DataFrame()
    if not ec1.empty:
        df['EC1'] = ec1.groupby(ec1.index).last()
    if not ec2.empty:
        df['EC2'] = ec2.groupby(ec2.index).last()



    return df
#     return pd.DataFrame({'EC1':get_sensor_series(device,'EC1',position=1),
#                          'EC2': get_sensor_series(device,'EC2',position=2)})

def get_level_series(device,rule,validate=True):
    """ 
    @return: Pandas dataframe with timeseries of water level
    @param device: the device to query 
    """  
    try:
        wp2=get_sensor_series(device,'Waterdruk',position=2,resample=rule)
        wp3=get_sensor_series(device,'Waterdruk',position=3,resample=rule)
        waterpressure = wp3.append(wp2)
    except:
        waterpressure=get_sensor_series(device,'Waterdruk',position=3,resample=rule)
        
    airpressure=get_sensor_series(device,'Luchtdruk',position=0,resample=rule)

    if validate:
        airpressure = airpressure.where((airpressure>950) & (airpressure<1050),np.NaN)
        
    # take the nearest air pressure values within a range of 2 hours from the time of water pressure measurements
    airpressure = airpressure.reindex(waterpressure.index,method='nearest',tolerance='2h')
    
    if validate:
        waterpressure = waterpressure.where(waterpressure>airpressure,np.NaN)
    
    # calculate water level in cm above the sensor
    waterlevel = (waterpressure-airpressure)/0.980638

    # Feb 2018: find decagon level data  and append to waterlevel
    try:
        ds = Datasource.objects.get(generator__name='Decagon', name__icontains=device.displayname)
        for param in ds.parameter_set.filter(name__startswith='Level P1'):
            for series in param.series_set.all():
                data = series.to_pandas() / 10  # convert mm to cm
                # TODO compensate for depth of decagon sensor
                waterlevel = waterlevel.append(data)
    except Datasource.DoesNotExist:
        pass

    waterlevel = waterlevel.groupby(waterlevel.index).last()

    # calculate elevation (m to NAP) of sensor
    sensor = device.get_sensor('Waterdruk',position=3)
    elevation = sensor.elevation()
    if elevation is None:
        # tolerate missing sensor elevation 
        elevation = 0
    
    # convert to water level in cm to meter to NAP
    peil = waterlevel/100.0 + elevation
    series = {'Waterhoogte': waterlevel, 'Waterpeil': peil}

    # recalibrate peil to fit manual measurementsPeil (m NAP)
    try:
        mloc = MeetLocatie.objects.get(name=device.displayname)
        manual = mloc.series_set.get(name='Waterstand').to_pandas()
        corrected = drift_correct(peil, manual)
        series['Corrected'] = corrected.groupby(corrected.index).last()
    except Exception as e:
        logger.exception(e)
    
    return pd.DataFrame(series)
    
def get_chart_series(device,rule):
    """ 
    @return: Pandas dataframe with timeseries of EC and water level
    @param device: the device to query 
    @param rule: resample rule 
    @summary: Query a device for EC and water level
    """  
    ecdata = get_ec_series(device,rule)
    ecdata = ecdata.groupby(ecdata.index).last()
    wldata = get_level_series(device,rule,validate=True)
    wldata = wldata.groupby(wldata.index).last()
    df = pd.concat([ecdata,wldata],axis=1)
    df.index.rename('Datum',inplace=True)
    return df

def last_waterlevel(device, hours=2):
    """ returns last known waterlevel for a device """
    try:
        # after update jan2018 waterdruk sensor is on position 2
        wps = device.get_sensor('Waterdruk',position=2)
        wp = wps.last_message()
    except:
        wps = device.get_sensor('Waterdruk',position=3)
        wp = wps.last_message()
        
    if wp:
        aps = device.get_sensor('Luchtdruk',position=0)
        ap = aps.last_message()
        #dekooy = Series.objects.get(name='Luchtdruk de Kooy')
        if ap:
            # we have some air pressure and water pressure messages, 
            # now check if messages were sent within time tolerance
            tolerance = timedelta(hours=hours)
            if wp.time > ap.time:
                delta = wp.time - ap.time 
            else:
                delta = ap.time - wp.time
        
            if delta > tolerance:
                # tolerance exceeded.
                if ap.time < wp.time:
                    # find last water pressure within tolerance
                    fromtime = ap.time - tolerance
                    wp = wps.loramessage_set.filter(time__gte=fromtime).last()
                else:
                    # find last air pressure within tolerance
                    fromtime = wp.time - tolerance
                    ap = aps.loramessage_set.filter(time__gte=fromtime).last()
            
            if ap and wp:
                air = aps.value(ap)
                #air = dekooy.at(wp.time).value
                water = wps.value(wp)
                if air and water:
                    level = (water - air) / 0.980638 # convert hPa to cm water column
                    z = wps.elevation()
                    nap = None if z is None else level/100 + z
                    return {'time': wp.time, 'cm': level, 'nap': nap}
    return {}

def last_ec(device):
    """ returns last known electrical conductivity for a device """

    def last(name,pos):
        try:
            sensor = device.get_sensor(name,position=pos)
            message = sensor.loramessage_set.filter(ecmessage__adc1__lt=30000,ecmessage__adc2__lt=30000).order_by('time').last()
            #message = sensor.last_message()
            return {'sensor': sensor, 'time': message.time, 'value': sensor.value(message)}
        except:
            return {}

    ec1 = last('EC1',1)
    ec2 = last('EC2',2)

    # Feb 2018: check if we have decagon data
    try:
        ds = Datasource.objects.get(generator__name='Decagon', name__icontains=device.displayname)
        for param in ds.parameter_set.filter(name__contains='EC'):
            for series in param.series_set.all():
                if series.name.startswith('EC P1'):
                    ec = ec1
                elif series.name.startswith('EC P2'):
                    ec = ec2
                else:
                    continue
                last = series.datapoints.latest('date')
                if last.date > ec['time']:
                    ec['time'] = last.date
                    ec['value'] = rounds(last.value,3)
    except Datasource.DoesNotExist:
        pass

    return {'EC1': ec1,'EC2': ec2}

def battery_status(battery):
    '''
    < 1% 0 bars 
    1-5%: 1 red bar
    5-20%: 1 green bar
    20-40% 2 bars
    40-60% 3 bars
    60-80% 4 bars
    80-100% 5 bars
    '''
    level = min(500,max(0,battery-3000)) / 5 # percent
    if level < 1:
        index = 0
    elif level < 5:
        # danger zone
        index = '1red'
    else:
        index = int(level/20)+1
    icon = '{url}bat{index}.png'.format(url=settings.STATIC_URL, index=index)
    return {'level': level, 'icon': icon} 
    
def parse_payload(device,server_time,payload,orion=None):
    message_type = payload['type']
    msg = None
    
    def logsens(sensor, created):
        if created:
            logger.info('{}: {} sensor created'.format(sensor.device, sensor))
    
    def logmsg(msg, created):
        logger.debug('{}: {} {}. time={}'.format(msg.sensor.device, unicode(msg), 'added' if created else 'updated', msg.time ))
        if orion:
            orion.update_message(msg)

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
            'temperature': np.short(payload['temperature'])})
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
        #appid = ttn['app_id']
        meta = ttn['metadata']
        server_time = parse_datetime(meta['time'])
        pf = ttn['payload_fields']
    except Exception as e:
        logger.error('Error parsing payload {}\n{}'.format(ttn,e))
        raise e

    try:
        if settings.USE_ORION:
            from peil.fiware import Orion
            orion = Orion(settings.ORION_URL)
        else:
            orion = None

        device, created = Device.objects.update_or_create(serial=serial,devid=devid, defaults={'last_seen': server_time})
        if created:
            logger.debug('device {} created'.format(unicode(device)))
            if orion:
                orion.create_device(device)

        return parse_payload(device, server_time, pf, orion)

    except Exception as e:
        logger.exception('Error parsing payload: {}'.format(ttn))
        raise e
    
def handle_post_data(json):
    try:
        msg, created, updated = parse_ttn(json)
        return HttpResponse(unicode(msg),status=201)
    except Exception as e:
        return HttpResponseServerError(e)

def parse_kpn(xml):
    """ parse xml pushed from kpn server """
    import xml.etree.ElementTree as ET
    try:
        ns = {'lora':'http://uri.actility.com/lora'}
        tree = ET.fromstring(xml)
        serial = tree.find('lora:DevEUI',ns).text
        time = tree.find('lora:Time',ns).text
        time = parse_datetime(time)
        hex = tree.find('lora:payload_hex',ns).text 
        payload = decode(hex)
    except Exception as e:
        logger.error('Error parsing payload {}\n{}'.format(xml,e))
        raise e

    try:
        if settings.USE_ORION:
            from peil.fiware import Orion
            orion = Orion(settings.ORION_URL)
        else:
            orion = None

        device, created = Device.objects.get_or_create(serial=serial,defaults={
            'devid': 'peilstok{}'.format(serial),
            'displayname':'Peilstok_{}'.format(serial),
            'last_seen': time})

        if not created:
            device.last_seen=time
            device.save()
        else:
            logger.debug('device {} created'.format(unicode(device)))
            create_sensors(device)
            if orion:
                orion.create_device(device)

        return parse_payload(device, time, payload, orion)

    except Exception as e:
        logger.exception('Error parsing payload: {}'.format(payload))
        raise e
    
def handle_kpn_post_data(xml):
    try:
        msg, created, updated = parse_kpn(xml)
        return HttpResponse(unicode(msg),status=201)
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
    """ iterate over ubx file and yield navpvt instances """
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
    """ add ubx file to database """
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
GPST0 = datetime.datetime(1980,1,6,0,0,0,tzinfo=pytz.utc)

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
    tow = sec - week * 86400 * 7# time of week
    dow = int(tow / 86400) # day of week
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

def download(url,dest):
    """ download a file from url and store as dest """
    import ftplib
    from urlparse import urlparse
    res = urlparse(url)
    ftp = ftplib.FTP(res.hostname)
    ftp.login()
    destdir = os.path.dirname(dest)
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    try:
        with open(dest,"wb") as f:
            def save(data):
                f.write(data)
            response = ftp.retrbinary("RETR "+res.path, callback=save, blocksize=1024)
            return True
    except:
        os.remove(dest)
        return False

def getfile(root,path,remote):
    """ get local file root/path. Download from remote if file does not exist """ 
    local_file = os.path.join(root,path)
    if not os.path.exists(local_file):
        logger.debug('Downloading {} from {}'.format(path,remote))
        try:
            if not download(remote + path, local_file):
                logger.debug('Download failed')
                return None
        except Exception as e:
            logger.exception('Download failed: {}'.format(e))
    return local_file

def get_broadcast_files(time, satcodes='G'):
    """ Gets broadcast files for the day of given time stamp. Download if they do not exist. 
    Possible satellite codes are:
        G GPS
        R GLONASS
        E Galileo
        C Beidou
        M Mixed
    """
    url = 'ftp://igs.bkg.bund.de/IGS/'
    year = time.year
    doy = time.timetuple().tm_yday
    files = []
    for sat in satcodes:
        path = 'BRDC/{year}/{doy:03}/BRDC00WRD_R_{year}{doy:03}0000_01D_{sat}N.rnx.gz'.format(year=year,doy=doy,sat=sat)
        local_file = getfile(settings.GNSS_ROOT,path,url)
        if local_file is None:
            continue
        files.append(local_file)
    return files

def get_ephemeres_files(time, types = ['clk','sp3','erp'], products='sru'):
    """ get pathnames of ephemeris and clock files for given time. Download if they do not exist """
    week, dow, _tow = time2gps(time)

    delta = datetime.datetime.now(pytz.utc) - time
    secs = delta.total_seconds()
    if secs < 60:
        # ultra forecast not available
        products = products.replace('v','')
    if secs < (3*60*60):
        # ultra not available
        products = products.replace('u','')
    if secs < (17*60*60):
        # rapid not available
        products = products.replace('r','')
    if delta.days < 12:
        # final not available
        products = products.replace('s','')
    
    files = []
    #url = 'ftp://ftp.igs.org/pub/product/'
    url = 'ftp://igs.ensg.ign.fr/pub/igs/products/'
    for _type in types:
        for product in products:
            if product in 'uv':
                hour = (time.hour // 6) * 6 # 0, 6, 12, 18
                path = '{week}/ig{product}{week}{dow}_{hour:02}.{type}.Z'.format(week=week,dow=dow,hour=hour,product=product,type=_type)
            else:
                path = '{week}/ig{product}{week}{dow}.{type}.Z'.format(week=week,dow=dow,product=product,type=_type)
            local_file = getfile(settings.GNSS_ROOT,path,url)
            if not local_file:
                continue
            files.append(local_file)
            break
    return files
