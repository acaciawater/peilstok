'''
Created on Apr 25, 2017

@author: theo
'''
from django.db import models
from django.contrib.gis.db import models as geo
from polymorphic.models import PolymorphicModel
import numpy as np
import logging
import calib
import json
from django.utils import timezone
from django.urls.base import reverse

logger = logging.getLogger(__name__)

# Message types
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
    devid = models.CharField(max_length=20,verbose_name='identificatie')
    
    """ displayed name of device """
    displayname = models.CharField(max_length=20,verbose_name = 'naam')
    
    # date/time created
    created = models.DateTimeField(auto_now_add = True, verbose_name='Geregistreerd')
    
    last_seen = models.DateTimeField(null=True, verbose_name='Laatste contact')

    length = models.IntegerField(null=True, verbose_name='Lengte', help_text = 'Totale lengte peilstok in mm')
    
    def get_absolute_url(self):
        return reverse('device-detail',args=[self.pk])
    
    def statuscolor(self):
        """ returns led color """
        try:
            now = timezone.now()
            age = now - self.last_seen
            if age.days < 1:
                hours = float(age.seconds)/3600.0
                return 'green' if hours < 2 else 'yellow'
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
    
    def delete(self):
        """ cascading delete does not work with polymorphic models """
        self.sensor_set.all().delete()
        super(Device,self).delete()

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
                return self.get_sensor('GPS').last_message().NAPvalue()
            except:
                return None
                
    def __unicode__(self):
        return self.displayname

from django.db.models.signals import pre_save
from django.dispatch import receiver
import re

@receiver(pre_save, sender=Device)
def device_presave(sender, instance, **kwargs):
    if not instance.displayname or instance.displayname == 'default':
        match = re.match(r'(?P<name>\D+)(?P<num>\d+$)',instance.devid)
        if match:
            name = match.group('name')
            number = int(match.group('num'))
            instance.displayname = '{}{:02d}'.format(name.title(),number)
        else:
            instance.displayname = instance.devid
        
class Survey(geo.Model):
    """ Peilstok survey """
    device = models.ForeignKey(Device,verbose_name='peilstok')
    time = models.DateTimeField(verbose_name='tijdstip',help_text='tijdstip van inmeten')
    surveyor = models.CharField(max_length=100,verbose_name='waarnemer',help_text='naam van waarnemer')
    location = geo.PointField(srid=28992,verbose_name='locatie',help_text='locatie in Rijksdriehoekstelsel coorinaten')
    altitude = models.DecimalField(null=True,blank=True,max_digits=10,decimal_places=3,verbose_name='hoogte',help_text='hoogte van de deksel in m tov NAP')
    vacc = models.PositiveIntegerField(null=True,blank=True,verbose_name='vertikale nauwkeurigheid',help_text='vertikale nauwkeurigheid in mm')
    hacc = models.PositiveIntegerField(null=True,blank=True,verbose_name='horizontale naukeurigheid',help_text='horizontale naukeurigheid in mm')

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
    unit = models.CharField(max_length = 10, default='-')
    
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
        raise ValueError('Not implemented')

    def times(self):
        return [m.time for m in self.loramessage_set.all()]

    def values(self):
        return [self.value(message) for message in self.loramessage_set.all()]

    def data(self,**kwargs):
        q = self.loramessage_set.order_by('time')
        if kwargs:
            queryset = q.filter(**kwargs)
        else:
            queryset = q 
        for m in queryset:
            yield (m.time,self.value(m))

    def raw_data(self,**kwargs):
        q = self.loramessage_set
        if kwargs:
            queryset = q.filter(**kwargs)
        else:
            queryset = q.all() 
        for m in queryset:
            yield m.to_dict()
            
    def __unicode__(self):
        return self.ident
        #return self.get_real_instance_class()._meta.verbose_name
    
    class Meta:
        verbose_name = 'Sensor'
        verbose_name_plural = 'sensoren'
        ordering = ('position', 'ident')
        
class PressureSensor(Sensor):

    offset = models.FloatField(default = 0.0)
    scale = models.FloatField(default = 1.0)

    def value(self, m):
        """ calculates pressure in hPa from raw ADC value in message """
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

    def EC(self,adc1,adc2):
        """ Calculates EC from raw ADC values """

        def rat1(x, p, q):
            return np.polyval(p, x) / np.polyval([1] + q, x)
        
        def rat2(x, p0, p1, p2, q1):
            return rat1(x, [p0, p1, p2], [q1])

        emin,emax = json.loads(self.ec_range)
        min1,max1 = json.loads(self.adc1_limits)
        min2,max2 = json.loads(self.adc2_limits)
        sign = ''
        if adc1 >= max1:
            # out of range
            sign = '<'
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
                w1 = w1/sumw
                w2 = w2/sumw
                ec = ec1*w1 + ec2*w2
            else:
                ec = None
        return sign, ec * 1e-3 if ec else None# to mS/cm

    def EC25(self,adc1,adc2,temp):
        sign,ec = self.EC(adc1,adc2)
        if sign:
            return ec
        else:
            return ec * (1.0 + (25.0 - temp/100.0) * self.tempfactor) if ec else None

    def value(self, m):
        ec = self.EC25(m.adc1, m.adc2, m.temperature)
        return rounds(ec,3) if ec else None # 3 significant digits
        
    class Meta:
        verbose_name = 'EC-Sensor'
        verbose_name_plural = 'EC-sensoren'

class GNSS_Sensor(Sensor):
    class Meta:
        verbose_name = 'GPS'
        verbose_name_plural = 'GPS'

    def value(self,m):
        return (m.lon*1e-7, m.lat*1e-7, round(m.alt*1e-3,3))
        
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
    """ Contains data from an EC sensor """

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
    
    class Meta:
        verbose_name = 'EC-meting'
        verbose_name_plural = 'EC-metingen'
        
class PressureMessage(LoraMessage):
    """ raw ADC pressure value """
    adc = models.IntegerField()

    def pressure(self):
        """ returns pressure in hPa """
        sensor = self.sensor.get_real_instance()
        return sensor.pressure(self.adc)
    
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

    def to_dict(self):
        d = LoraMessage.to_dict(self)
        d.update({'lon': self.lon, 'lat': self.lat, 'alt': self.alt, 'vacc': self.vacc, 'hacc': self.hacc, 'msl': self.msl})
        return d

    def NAPvalue(self):
        from peil.util import rdnap
        try:
            x,y,z = rdnap.to_rdnap(self.lat*1e-7, self.lon*1e-7, self.alt*1e-3)
            return (round(x,2), round(y,2), round(z,2))
        except:
            return None
        
    class Meta:
        verbose_name = 'Plaatsbepaling'
        verbose_name_plural = 'Plaatsbepalingen'


class InclinationMessage(LoraMessage):
    """ Message generated when device is tilted is more than 45 degrees """
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

class Fix(models.Model):
    """ GNSS fix for a peilstok """
    sensor = models.ForeignKey(GNSS_Sensor)
    time = models.DateTimeField(verbose_name='Tijdstip van fix')
    lon = models.DecimalField(max_digits=10,decimal_places=7,verbose_name='lengtegraad')
    lat = models.DecimalField(max_digits=10,decimal_places=7,verbose_name='breedtegraad')
    alt = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='hoogte tov ellipsoide')
    x = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='x-coordinaat')
    y = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='y-coordinaat')
    z = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='hoogte tov NAP')
    sdx = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Fout in x-richting')
    sdy = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Fout in y-richting')
    sdz = models.DecimalField(max_digits=6,decimal_places=3,verbose_name='Fout in hoogte')
    ahn = models.DecimalField(max_digits=10,decimal_places=3,verbose_name='hoogte volgens AHN')
    
class Meta:
    verbose_name = 'Fix'
    verbose_name_plural = 'Fix'
    unique_together=('sensor', 'time')
    
class RTKConfig(models.Model):
    """ RTKLIB configuration for peilstok app """

    class Meta:
        verbose_name = 'RTKLIB configuratie'
        verbose_name_plural = 'RTKLIB configuraties'
        
    name = models.CharField(max_length=20)
    description = models.TextField(null=True,blank=True)
    
    #RTKLIB commands
    convbin = models.CharField(max_length=200)
    convbin_args = models.CharField(max_length=200)
    rnx2rtkp = models.CharField(max_length=200)
    rnx2rtkp_args = models.CharField(max_length=200)
    
    # igs corrrection files
    # ultra after 6 hours (no clock files)
    # rapid after 1 day 
    # final after 3 weeks
    #igsurl = models.URLField(default='ftp://ftp.igs.org/pub/product/')
                
    def __unicode__(self):
        return self.name
    
class UBXFile(models.Model):
    """ u-blox GNSS raw datafile """
    device = models.ForeignKey(Device)
    ubxfile = models.FileField(upload_to='ubx')
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField(null=True,verbose_name = 'Tijdstip eerste observatie')
    stop = models.DateTimeField(null=True,verbose_name = 'Tijdstip laatste observatie')
        
    def create_pvts(self):
        """ parse file and extract UBX-NAV-PVT messages """
        from peil.util import iterpvt
        for fields in iterpvt(self.ubxfile):
            timestamp = fields.pop('timestamp')
            self.navpvt_set.update_or_create(timestamp=timestamp,defaults=fields)
            
    def __unicode__(self):
        return self.ubxfile.name

    class Meta:
        verbose_name = 'u-blox bestand'
        verbose_name_plural = 'u-blox bestanden'

    def rtkpost(self, config, **kwargs):
        """ postprocessing with RTKLIB """
        import os, re
        import subprocess32 as subprocess

        path = unicode(self.ubxfile.file)
        dir = os.path.dirname(path)
        ubx = os.path.basename(path)
        logger.debug('RTKPOST started for {}'.format(ubx))
        name, ext = os.path.splitext(ubx)
        obs = name+'.obs'
        nav = name+'.nav'
        sbs = name+'.sbs'
        pos = name+'.pos'
        start = kwargs.get('start',self.start)
        date = start.strftime('%Y/%m/%d')
        time = start.strftime('%H:%M:%S')
        vars = locals()

        def build_command(command, args):
            """ build array of popenargs (for subprocess call to Popen) """
            arglist = [command] 
            for arg in args.split():
                arg = arg.strip()
                match = re.match(r'\{(\w+)\}',arg)
                if match:
                    var = match.group(1)
                    if var in vars:
                        arg = vars[var]
                    else: 
                        continue
                arglist.append(arg)
            return  arglist 
        
        os.chdir(dir)
        command = build_command(config.convbin, config.convbin_args)
        logger.debug('Running {}'.format(' '.join(command)))
        ret = subprocess.call(command)
        logger.debug('{} returned exit code {}'.format(command[0], ret))
        if ret == 0:
            command = build_command(config.rnx2rtkp, config.rnx2rtkp_args)
            logger.debug('Running {}'.format(' '.join(command)))
            ret = subprocess.call(command)
            logger.debug('{} returned exit code {}'.format(command[0], ret))
        logger.debug('RTKPOST finished')
        return ret

from django.db.models.signals import pre_save
from django.dispatch.dispatcher import receiver

@receiver(pre_save, sender=UBXFile)
def ubxfile_save(sender, instance, **kwargs):
    """ find out time of first and last message when saving to database """
    from peil.util import ubxtime
    instance.start, instance.stop = ubxtime(instance.ubxfile)
    
class NavPVT(models.Model):
    """ UBX-NAV-PVT message extracted from ubx file """
    ubxfile = models.ForeignKey(UBXFile)
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
