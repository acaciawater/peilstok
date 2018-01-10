'''
Created on Apr 25, 2017

@author: theo
'''
from django.db import models, transaction
from django.contrib.gis.db import models as geo
from polymorphic.models import PolymorphicModel
from sorl.thumbnail import ImageField
import numpy as np
import os
import logging
import calib
import json
from django.utils import timezone
from django.urls.base import reverse
from acacia.data.util import toWGS84
from datetime import datetime
import pytz
from django.db.models.aggregates import Min

logger = logging.getLogger(__name__)

# Message types sent by a peilstok device
GNSS_MESSAGE = 1
EC_MESSAGE = 2
PRESSURE_MESSAGE = 3
ANGLE_MESSAGE = 5
STATUS_MESSAGE = 6
 
MESSAGE_CHOICES = (
    (GNSS_MESSAGE,      'GNSS'),
    (EC_MESSAGE,        'EC'),
    (PRESSURE_MESSAGE,  'Pressure'),
    (ANGLE_MESSAGE,     'Angle'),
    (STATUS_MESSAGE,    'Master'),
    )

MESSAGES=dict(MESSAGE_CHOICES)
 
class Device(models.Model):
    """ Represents a 'Peilstok' device with sensors """ 

    class Meta:
        verbose_name = 'Peilstok'
        verbose_name_plural = 'Peilstokken'
        unique_together = ('serial', 'devid')
        ordering = ('displayname',)
        
    """ serial number (BLE MAC address) of device """
    serial = models.CharField(max_length=20,verbose_name='MAC-adres')
    
    """ identification of device """
    devid = models.CharField(max_length=40,verbose_name='identificatie')
    
    """ displayed name of device """
    displayname = models.CharField(max_length=40,verbose_name = 'naam')
    
    # date/time created
    created = models.DateTimeField(auto_now_add = True, verbose_name='Geregistreerd')
    
    last_seen = models.DateTimeField(null=True, verbose_name='Laatste contact')

    # length of device in mm
    length = models.IntegerField(null=True, verbose_name='Lengte', help_text = 'Totale lengte peilstok in mm')
    
    def get_absolute_url(self):
        return reverse('device-detail',args=[self.pk])
    
    def statuscolor(self):
        """ returns color for dots on map.
        Green is less than 6 hours old, yellow is 6 to 24 hrs, red is 1 - 7 days and gray is more than one week old 
         """
        try:
            now = timezone.now()
            age = now - self.last_seen
            if age.days < 0:
                # why does this happen??
                return 'green'
            elif age.days < 1:
                hours = float(age.seconds)/3600.0
                return 'green' if hours < 6 else 'yellow'
            else:
                return 'red' if age.days < 7 else 'grey'
        except:
            return 'grey'
        
    def last_survey(self):    
        return self.survey_set.order_by('time').last()

    def sensor_names(self):
        """ returns comma separated list of sensor names """
        return ', '.join(self.sensor_set.distinct('ident').order_by('ident').values_list('ident',flat=True))
        
    def get_sensor(self,ident,**kwargs):
        kwargs['ident__iexact'] = ident
        return self.sensor_set.get(**kwargs)

    def get_sensors(self,ident,**kwargs):
        kwargs['ident__iexact'] = ident
        return self.sensor_set.filter(**kwargs)

    def last_message(self,ident,**kwargs):
        ''' returns last known sensor message '''
        sensor = self.get_sensor(ident,**kwargs)
        return sensor.last_message()

    def last_value(self,ident,**kwargs):
        ''' returns last known value as dict '''
        msg = self.last_message(ident,**kwargs)
        return {'device': msg.sensor.device.displayname, 'sensor': msg.sensor.ident, 'time': msg.time, 'value': msg.value()}

    def delete(self):
        """ cascading delete does not work with polymorphic models """
        self.sensor_set.all().delete()
        super(Device,self).delete()

    def battery_status(self):
        from peil import util
        sensor = self.get_sensor('Batterij',position=0)
        if sensor:
            msg = sensor.last_message()
            if msg:
                level = sensor.value(msg)
                return util.battery_status(level)
        return None
    
    def battery_level(self):
        status = self.battery_status()
        return status['level']

    def battery_icon(self):
        status = self.battery_status()
        return status['icon'] if status else None

    def battery_tag(self):
        bat = self.battery_status()
        if bat:
            return '<img style="height:24px;" src="{}" title="level {}%"></img>'.format(bat['icon'],bat['level'])
        else:
            return None

    battery_tag.allow_tags=True
    battery_tag.short_description='Batterij'
        
    def get_nap(self):
        """ 
        get NAP level of top of device
        first try to find the NAP level of the survey
        if there is no survey, use the NAP value of the last GPS message
        """
        
        try:
            return float(self.last_survey().altitude)
        except:
            try:
                x,y,z = self.get_sensor('GPS').last_message().NAPvalue()
                return z
            except:
                return None

    def popup_photo(self):
        """ returns the foto to display in the leaflet popup on the map
            This is the first photo marked with ispopup=True or the last photo of this device 
        """
        foto = self.photo_set.filter(ispopup=True)
        return foto.first() if foto else self.photo_set.last()

    def current_location(self, hacc=1000):
        ''' returns current location '''

        # TODO: get last valid RTK fix
        
        # get latest valid location from on-board GPS (hAcc>0)
        g = self.get_sensor('GPS').loramessage_set.filter(locationmessage__hacc__gt=0)
        if g:
            if hacc:
                # filter messages on maximum allowed hacc
                g = g.filter(locationmessage__hacc__lt=hacc)
                
            # use latest valid gps message
            try:
                g = g.latest('time')
                lon,lat = g.lonlat
                x,y,z = g.NAPvalue()
                return {'id': self.id, 'name': self.displayname, 'lon': lon, 'lat': lat, 'msl': g.msl*1e-3, 
                        'hacc': g.hacc*1e-3, 'vacc': g.vacc*1e-3, 'time': g.time,
                        'x': x, 'y': y, 'z': z}
            except:
                pass

        # no valid GPS fix available, try survey
        try:
            # get latest surveyed position in lonlat (WGS84)
            s = self.survey_set.latest('time')
            if s:
                pos = s.lonlat
                return {'id': self.id, 'name': self.displayname, 'lon': pos.x, 'lat': pos.y, 'time': s.time,
                        'x': s.location.x, 'y': s.location.y, 'z': s.altitude}
        except:
            # no survey
            return {}
    
    def __unicode__(self):
        return self.displayname

from django.db.models.signals import pre_save
from django.dispatch import receiver
import re

@receiver(pre_save, sender=Device)
def device_presave(sender, instance, **kwargs):
    ''' before saving, check displayname '''
    if not instance.displayname or instance.displayname == 'default':
        match = re.match(r'(?P<name>\D+)(?P<num>\d+$)',instance.devid)
        if match:
            name = match.group('name')
            number = int(match.group('num'))
            instance.displayname = '{}{:02d}'.format(name.title(),number)
        else:
            instance.displayname = instance.devid
        
class Photo(models.Model):
    ''' Photo of a peilstok '''
    device = models.ForeignKey(Device)
    photo = ImageField(upload_to='photos')
    order = models.PositiveIntegerField(default=1)
    ispopup = models.BooleanField(default=False,verbose_name='popup',help_text='Wordt getoond in popup venster op de kaart')
    ispopup.boolean = True

    def set_as_popup(self):
        ''' select this photo for the popup window on leaflet map '''
        # deselect other candidates
        self.device.photo_set.exclude(pk=self.pk).update(ispopup=False)
        if not self.ispopup:
            self.ispopup = True
            self.save(update_fields=['ispopup'])
            
    def __unicode__(self):
        return os.path.basename(self.photo.name)
    
    class Meta:
        verbose_name = 'foto'
        ordering = ('device','order','photo')
        
class Survey(geo.Model):
    """ Peilstok survey """
    device = models.ForeignKey(Device,verbose_name='peilstok')
    time = models.DateTimeField(verbose_name='tijdstip',help_text='tijdstip van inmeten')
    surveyor = models.CharField(max_length=100,verbose_name='waarnemer',help_text='naam van waarnemer')
    location = geo.PointField(srid=28992,verbose_name='locatie',help_text='locatie in Rijksdriehoekstelsel coorinaten')
    altitude = models.DecimalField(null=True,blank=True,max_digits=10,decimal_places=3,verbose_name='hoogte',help_text='hoogte van de deksel in m tov NAP')
    vacc = models.PositiveIntegerField(null=True,blank=True,verbose_name='vertikale nauwkeurigheid',help_text='vertikale nauwkeurigheid in mm')
    hacc = models.PositiveIntegerField(null=True,blank=True,verbose_name='horizontale naukeurigheid',help_text='horizontale naukeurigheid in mm')
    
    @property
    def lonlat(self):
        return toWGS84(self.location)
    
from math import log10, floor
def rounds(x, sig=2):
    """
    @summary: round floating point number to significant digits
    @param x: floating point value
    @param sig: number of significant digits (default=2)
    @return: input value rounded to `sig` significant digits   
    """
    return round(x, sig-int(floor(log10(abs(x))))-1)

class Sensor(PolymorphicModel):
    """ Sensor in a peilstok """

    """ device this sensor belongs to """
    device = models.ForeignKey('Device',verbose_name = 'peilstok')
    
    """ sensor identification (name) """
    ident = models.CharField(max_length=50,default='sensor',verbose_name='sensor')
    
    """ position of sensor (module number) """
    position = models.PositiveSmallIntegerField(default=0,verbose_name='positie')
    
    """ distance of sensor in mm from antenna """        
    distance = models.IntegerField(default = 0, verbose_name = 'afstand', help_text = 'afstand tov antenne')

    """ unit of calibrated values """
    unit = models.CharField(max_length = 10, default='-', verbose_name='eenheid')
    
    def message_count(self):
        """
        @summary: count number of loRa messages received 
        """
        return self.loramessage_set.count()
    message_count.short_description = 'Aantal berichten'
    
    def elevation(self):
        """ elevation of sensor wrt NAP """
        nap = self.device.get_nap()
        if nap is None:
            return None
        return nap - self.distance*1e-3
    
    def last_message(self):
        return self.loramessage_set.order_by('time').last()
    last_message.short_description = 'Laatste bericht'

    def first_message(self):
        return self.loramessage_set.order_by('time').first()
    first_message.short_description = 'Eerste bericht'
    
    def value(self, message):
        ''' returns (calibrated) sensor value in physical units '''
        raise ValueError('Not implemented')

    def times(self):
        ''' returns list of measurement times '''
        return [m.time for m in self.loramessage_set.all()]

    def values(self):
        ''' returns list of all measured values '''
        return [self.value(message) for message in self.loramessage_set.all()]

    def data(self,**kwargs):
        ''' returns list of tuples (time,value) of measurements '''
        q = self.loramessage_set.order_by('time')
        if kwargs:
            queryset = q.filter(**kwargs)
        else:
            queryset = q 
        for m in queryset:
            yield (m.time,self.value(m))

    def raw_data(self,**kwargs):
        ''' returns list of raw data ordered by time '''
        q = self.loramessage_set.order_by('time')
        if kwargs:
            queryset = q.filter(**kwargs)
        else:
            queryset = q.all() 
        for m in queryset:
            yield m.to_dict()

    @property            
    def statistics(self):
        try:
            stat = self.sensorstatistics
        except SensorStatistics.DoesNotExist:
            stat = SensorStatistics.objects.create(sensor=self)
            stat.update()
        return stat
    
    def update_statistics(self):
        try:
            stat = self.sensorstatistics
        except SensorStatistics.DoesNotExist:
            stat = SensorStatistics.objects.create(sensor=self)
        stat.update()
        return stat

    def __unicode__(self):
        return self.ident
        #return self.get_real_instance_class()._meta.verbose_name
    
    class Meta:
        verbose_name = 'Sensor'
        verbose_name_plural = 'sensoren'
        ordering = ('position', 'ident')

class SensorStatistics(models.Model):
    sensor = models.OneToOneField(Sensor)
    min = models.FloatField(null=True,blank=True,default=None)
    max = models.FloatField(null=True,blank=True,default=None)
    mean = models.FloatField(null=True,blank=True,default=None)
    nobs = models.IntegerField(null=True,blank=True,default=None)
    variance = models.FloatField(null=True,blank=True,default=None)
    skewness = models.FloatField(null=True,blank=True,default=None)
    kurtosis = models.FloatField(null=True,blank=True,default=None)

    def update(self):
        from scipy.stats.stats import describe
        try:
            sensor = self.sensor.get_real_instance()
            values = np.array(sensor.values(),dtype=np.float) # replaces None with np.nan
            stats = describe(values,nan_policy='omit')
            self.nobs = stats.nobs
            if self.nobs == 0:
                self.min = self.max = self.mean = self.variance = self.skewness = self.kurtosis = None
            else:
                self.min, self.max = stats.minmax
                self.mean = stats.mean
                self.variance = stats.variance
                self.skewness = stats.skewness
                self.kurtosis = stats.kurtosis
                self.save()
        except Exception as e:
            pass
        
class PressureSensor(Sensor):
    ''' Pressure sensor can be air pressure (position 0) or water pressure (position 3)'''
    offset = models.FloatField(default = 0.0)
    scale = models.FloatField(default = 1.0)

    def value(self, m):
        """ calculates pressure in hPa from raw ADC value in message """
        if m.adc < 1200:
            # Firmware error
            m.adc = int(m.adc / 1.2 * 3.3)
        if m.adc < 4096:
            return round(self.offset + m.adc * self.scale,2)
        else:
            return None

    class Meta:
        verbose_name = 'Druksensor'
        verbose_name_plural = 'druksensoren'

class ECSensor(Sensor):
    
    tempfactor = models.FloatField(default=0.0246534878,verbose_name = 'factor', help_text = 'factor voor conversie naar 25 oC')
    adc1_coef = models.CharField(max_length=200,verbose_name ='Coefficienten ring1', default=calib.ADC1EC)
    adc2_coef = models.CharField(max_length=200,verbose_name ='Coefficienten ring2', default=calib.ADC2EC)
    adc1_limits = models.CharField(max_length=50,verbose_name='bereik ring1',default=calib.ADC1EC_LIMITS)
    adc2_limits = models.CharField(max_length=50,verbose_name='bereik ring2',default=calib.ADC2EC_LIMITS)
    ec_range = models.CharField(max_length=50,verbose_name = 'bereik', default=calib.EC_RANGE)

    def EC1(self,adc1):
        ''' test EC1 '''
        def rat1(x, p, q):
            return np.polyval(p, x) / np.polyval([1] + q, x)
        def rat2(x, p0, p1, p2, q1):
            return rat1(x, [p0, p1, p2], [q1])
        return rat2(adc1, *json.loads(self.adc1_coef))

    def EC2(self,adc2):
        ''' test EC2 '''
        def rat1(x, p, q):
            return np.polyval(p, x) / np.polyval([1] + q, x)
        def rat2(x, p0, p1, p2, q1):
            return rat1(x, [p0, p1, p2], [q1])
        return rat2(adc2, *json.loads(self.adc2_coef))
        
    def EC(self,adc1,adc2):
        """ Calculates EC from raw ADC values """

        def rat1(x, p, q):
            return np.polyval(p, x) / np.polyval([1] + q, x)
        
        def rat2(x, p0, p1, p2, q1):
            return rat1(x, [p0, p1, p2], [q1])

        emin,emax = json.loads(self.ec_range)
        min1,max1 = json.loads(self.adc1_limits)
        min2,max2 = json.loads(self.adc2_limits)
        if adc1 >= max1:
            # out of range, dry?
            ec = None
        else:
            if adc1 >= min1:
                ec1 = rat2(adc1, *json.loads(self.adc1_coef))
                w1 = adc1 - min1
            else:
                ec1 = emax
                w1 = 0
            if adc2 < min2:
                ec2 = emax
                w2 = 1
            elif adc2 <= max2:
                # use adc2 only
                ec2 = rat2(adc2, *json.loads(self.adc2_coef))
                w2 = max2 - adc2
            else:
                ec2 = emin
                w2 = 0
            sumw = float(w1+w2)
            if sumw:
                ec = (ec1*w1 + ec2*w2)/sumw
            else:
                ec = None
        return ec * 1e-3 if ec else None

    # Aanpassingen na herijking Jan 2018
    jan2018 = pytz.utc.localize(datetime(2018,1,1))
    minadc = {}
    offsets = {
        "Peilstok01": [None,7.14],
        "Peilstok02": [18.25,15.175],
        "Peilstok03": [9.7175,6.7625],
        "Peilstok04": [9.3625,7.34],
        "Peilstok05": [31.93,19.37666667],
        "Peilstok06": [23.1,20.53],
        "Peilstok07": [13.1725,12.2225],
        "Peilstok08": [17.45333333,17.78333333],
        "Peilstok09": [21.92333333,12.59333333],
        "Peilstok10": [23.24,13.40666667],
        "Peilstok11": [None,16.55666667],
        "Peilstok12": [None,12.62666667],
        "Peilstok13": [10.505,14.0475],
        "Peilstok14": [17.8925,11.569],
        "Peilstok15": [18.8625,15.79333333],
        "Peilstok16": [25.0635,14.62333333],
        "Peilstok17": [14.6175,11.135],
        "Peilstok18": [16.815,12.38]
        }
        
    def EC_alt(self,adc1,adc2):
        # alternative berekening EC adhv herijking Jan 2018
        if not self in self.minadc:
            # cache minadc waarde voor deze sensor
            agg = self.loramessage_set.aggregate(amin=Min('ecmessage__adc1'))                
            self.minadc[self] = agg['amin'] 
        amin = self.minadc[self]
        if adc1 <= amin:
            return None
        return ((adc1 - amin) / 600.0) ** (-2.0/3.0)

    def EC25(self,adc1,adc2,temp,f=EC):
        try:
            ec = f(adc1,adc2)
        except Exception as e:
            raise
        if ec:
            emin,emax = json.loads(self.ec_range)
            ec25 = ec * (1.0 + (25.0 - temp/100.0) * self.tempfactor)
            ec25 = max(emin/1000,ec25)
            ec25 = min(emax/1000,ec25)
            return ec25
        return None
    
    def value(self, m):
        if m.time < self.jan2018:
            f = self.EC_alt
            ofs = ECSensor.offsets[self.device.displayname]
            offset = (ofs[0] if self.ident == 'EC1' else ofs[1]) or 0
        else:
            f = self.EC
            offset = 0
        ec = self.EC25(m.adc1, m.adc2, m.temperature, f)
        return rounds(ec+offset,3) if ec else None # 3 significant digits
        
    class Meta:
        verbose_name = 'EC-Sensor'
        verbose_name_plural = 'EC-sensoren'

class GNSS_Sensor(Sensor):
    class Meta:
        verbose_name = 'GPS'
        verbose_name_plural = 'GPS'

    def value(self,m):
        return round(m.alt*1e-3,3)
    
#     def value(self,m):
#         lon,lat = m.lonlat
#         return (lon, lat, round(m.alt*1e-3,3))
        
class AngleSensor(Sensor):
    class Meta:
        verbose_name = 'Inclinometer'
        verbose_name_plural =  'Inclinometers'

    def value(self, m):
        return m.angle

class BatterySensor(Sensor):
    class Meta:
        verbose_name = 'Batterijspanning'
        verbose_name_plural =  'Batterijspanning'

    def value(self, m):
        if m.battery < 1500:
            # Firmware error
            return int(m.battery / 1.2 * 3.3)
        else:
            return m.battery

class LoraMessage(PolymorphicModel):
    """ Base class for all LoRa messages sent by a sensor """
    
    sensor = models.ForeignKey(Sensor)
 
    # time received by server
    time = models.DateTimeField(verbose_name='tijdstip')
    
    def __unicode__(self):
        return self.get_real_instance_class()._meta.verbose_name

    def device(self):
        return self.sensor.device
    device.short_description = 'Peilstok'
    
    def value(self):
        return self.sensor.value(self)
    
    def to_dict(self):
        return {'time': self.time}
      
    class Meta:
        verbose_name = 'LoRa bericht'
        verbose_name_plural = 'LoRa berichten'
        ordering = ['-time']
        
class ECMessage(LoraMessage):
    """ Contains data sent by an EC sensor """

    # temperature in 0.01 degrees C
    temperature = models.IntegerField(help_text='temperatuur in 0.01 graden Celcius')

    # raw ADC value 1x gain
    adc1 = models.IntegerField()

    # raw ADC value 11x gain
    adc2 = models.IntegerField()

    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'adc1': self.adc1, 'adc2': self.adc2, 'temperature': self.temperature})
        return d

    def EC25(self):
        ''' EC value to display in admin pages '''
        return self.sensor.ecsensor.value(self)
    EC25.short_description = 'EC waarde'
    
    class Meta:
        verbose_name = 'EC-meting'
        verbose_name_plural = 'EC-metingen'
        
class PressureMessage(LoraMessage):
    """ raw ADC pressure value """
    adc = models.IntegerField()

    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'adc': self.adc})
        return d

    class Meta:
        verbose_name = 'Drukmeting'
        verbose_name_plural = 'Drukmetingen'

class LocationMessage(LoraMessage):
    """ Message generated by the on-board GNSS chip (ublox-7P) """
    
    # Latitude * 1e7 
    lat = models.IntegerField(verbose_name='breedtegraad')
    
    # Longitude * 1e7 
    lon = models.IntegerField(verbose_name='lengtegraad')
    
    # Height above ellipsoid in mm
    alt = models.IntegerField(verbose_name='ellipsoid',help_text='hoogte ten opzichte van ellipsoid in mm')
    
    # Vertical accuracy in mm
    vacc = models.IntegerField(verbose_name='vertikale nauwkeurigheid',help_text='vertikale nauwkeurigheid in mm')
    
    # Horizontal accuracy in mm
    hacc = models.IntegerField(verbose_name='horizontale nauwkeurigheid',help_text='horizontale nauwkeurigheid in mm')
    
    # Height above mean sea level in mm
    msl = models.IntegerField(verbose_name='zeeniveau',help_text='hoogte ten opzichte van zeeniveau in mm')

    @property
    def lonlat(self):
        if self.lon > self.lat:
            # omwisseling lon/lat in firmware
            t=self.lon
            self.lon=self.lat
            self.lat=t
        return (self.lon*1e-7,self.lat*1e-7)
     
    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'lon': self.lon, 'lat': self.lat, 'alt': self.alt, 'vacc': self.vacc, 'hacc': self.hacc, 'msl': self.msl})
        return d

    def NAPvalue(self):
        from peil.util import rdnap
        try:
            lon,lat=self.lonlat
            x,y,z = rdnap.to_rdnap(lon, lat, self.alt*1e-3)
            return (round(x,2), round(y,2), round(z,2))
        except:
            return None
        
    class Meta:
        verbose_name = 'GPS bericht'
        verbose_name_plural = 'GPS berichten'


class InclinationMessage(LoraMessage):
    """ Message generated by inclinometer """
    angle = models.IntegerField()

    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'angle': self.angle})
        return d

    class Meta:
        verbose_name = 'Hoekmeting'
        verbose_name_plural = 'Hoekmetingen'

class StatusMessage(LoraMessage):

    battery = models.IntegerField(verbose_name = 'batterijniveau')

    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'battery': self.battery})
        return d

    class Meta:
        verbose_name = 'Batterijmeting'
        verbose_name_plural = 'Batterijmetingen'

# --------------------------------------------------------------------------------------------------------------
# GPS and RTK stuff
# --------------------------------------------------------------------------------------------------------------

class UBXFile(models.Model):
    """ u-blox GNSS raw datafile """
    device = models.ForeignKey(Device)
    ubxfile = models.FileField(upload_to='ubx')
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True,verbose_name = 'begin')
    stop = models.DateTimeField(null=True,verbose_name = 'einde')
        
    def create_pvts(self):
        """ parse file and extract UBX-NAV-PVT messages """
        from peil.util import iterpvt
    
        count = 0
        for fields in iterpvt(self.ubxfile):
            timestamp = fields.pop('timestamp')
            self.navpvt_set.update_or_create(timestamp=timestamp,defaults=fields)
            count += 1
        return count
    
    def post(self):
        """ run rtk post """
        from peil import rtk
        import pytz
        
        count=0
        sol = rtk.post(self)
        if sol:
            with transaction.atomic():
                self.rtksolution_set.all().delete()
                for fields in rtk.itersol(sol):
                    time = fields.pop('time')
                    time = pytz.utc.localize(time) 
                    self.rtksolution_set.create(time=time, **fields)
                    count += 1
        return count
        
    def solution_count(self):
        return self.rtksolution_set.count()
    solution_count.short_description='rtk fixes'
    
    def last_solution(self):
        return self.rtksolution_set.latest('time')
    last_solution.short_description='laatste rtk fix'

    def solution_stats(self):
        from django.db.models import StdDev, Avg
        agg = self.rtksolution_set.all().aggregate(avg=Avg('z'), std=StdDev('z'))
        avg = agg['avg']
        std = agg['std']
        return (round(avg,3) if avg else None, round(std,3) if std else None) 
    solution_stats.short_description='avg, std'
        
    def __unicode__(self):
        return self.ubxfile.name

    class Meta:
        verbose_name = 'GPS bestand'
        verbose_name_plural = 'GPS bestanden'

@receiver(pre_save, sender=UBXFile)
def ubxfile_save(sender, instance, **kwargs):
    """ find out time of first and last message when saving to database """
    from peil.util import ubxtime
    instance.start, instance.stop = ubxtime(instance.ubxfile)

QUALITY_CHOICES = (
    (0, 'None'),
    (1, 'Fixed'),
    (2, 'Float'),
    (4, 'DGPS'),
    (5, 'Single'),
    (6, 'PPP')
    )

class RTKSolution(models.Model):
    """ RTK solution for a raw u-blox datafile """
    ubx = models.ForeignKey(UBXFile)
    time = models.DateTimeField(verbose_name='Tijdstip')
    lon = models.DecimalField(max_digits=10,decimal_places=7,verbose_name='lengtegraad (deg)')
    lat = models.DecimalField(max_digits=10,decimal_places=7,verbose_name='breedtegraad (deg)')
    alt = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='hoogte tov ellipsoide (m)')
    q = models.PositiveSmallIntegerField(choices=QUALITY_CHOICES, verbose_name='Type of fix')
    ns = models.PositiveSmallIntegerField(verbose_name='Aantal satellieten')
    sde = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Stdev x (m)')
    sdn = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Stdev y (m)')
    sdu = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Stdev z (m)')
    x = models.DecimalField(null=True,blank=True,max_digits=10,decimal_places=3,verbose_name='x-coordinaat (m)')
    y = models.DecimalField(null=True,blank=True,max_digits=10,decimal_places=3,verbose_name='y-coordinaat (m)')
    z = models.DecimalField(null=True,blank=True,max_digits=10,decimal_places=3,verbose_name='hoogte tov NAP (m)')
    
    def __unicode__(self):
        return ', '.join([str(self.lon), str(self.lat), str(self.alt), str(self.sdu)])
    
    def device(self):
        return self.ubx.device
    
    class Meta:
        verbose_name = 'RTK Fix'
        verbose_name_plural = 'RTK Fixes'
        unique_together=('ubx', 'time')
        
class NavPVT(models.Model):
    """ UBX-NAV-PVT message extracted from ubx file """
    ubx = models.ForeignKey(UBXFile)
    timestamp = models.DateTimeField(verbose_name='Tijdstip')
    lat = models.DecimalField(max_digits=10, decimal_places=7,verbose_name='Breedtegraad')
    lon = models.DecimalField(max_digits=10, decimal_places=7,verbose_name='Lengtegraad')
    alt = models.IntegerField(verbose_name='Ellipsoide', help_text='Hoogte tov ellipsoide in mm')
    msl = models.IntegerField(verbose_name='Zeeniveau', help_text ='Hoogte tov zeeniveau in mm')
    hAcc = models.PositiveIntegerField(verbose_name='hAcc', help_text='Horizontale nauwkeurigheid in mm')
    vAcc = models.PositiveIntegerField(verbose_name='vAcc', help_text='verticale nauwkeurigheid in mm') # mm
    numSV = models.PositiveSmallIntegerField(verbose_name='satellieten', help_text='Aantal zichtbare satellieten')
    pDOP = models.DecimalField(max_digits=10, decimal_places=2,verbose_name='DOP', help_text='Dilution of Precision')

    class Meta:
        verbose_name = 'NAV-PVT message'
        verbose_name_plural = 'NAV-PVT messages'
