'''
Created on Apr 25, 2017

@author: theo
'''
from django.db import models
from django.db.models import Q
import pandas as pd
import logging
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

# Sensor types
GNSS_SENSOR = 0
EC1_SENSOR = 1
EC2_SENSOR = 2
AIRPRESSURE_SENSOR = 3
WATERPRESSURE_SENSOR = 4
ANGLE_SENSOR = 5

SENSOR_CHOICES = (
    (GNSS_SENSOR,   'GPS'),
    (EC1_SENSOR,    'EC1'),
    (EC2_SENSOR,    'EC2'),
    (AIRPRESSURE_SENSOR, 'Luchtdruk'),
    (WATERPRESSURE_SENSOR, 'Waterdruk'),
    (ANGLE_SENSOR,  'Inclinometer'),
    )

# Factor to convert raw ADC-pressure value to hPa for master and slave
ADC_HPAMASTER = 0.8047603298
ADC_HPASLAVE = 0.5532727267

# Factor to convert raw ADC-pressure value to psi for master and slave
ADC_PSIMASTER = 0.01167206175
ADC_PSISLAVE = 0.008024542455

class CalibrationSeries(models.Model):
    """ Calibration data for EC modules """
    
    # unique name of the calibration series
    name = models.CharField(max_length=20)
    
    # optional description
    description = models.TextField(blank=True,null=True)    
    
    #date/time the series was created
    created = models.DateTimeField(auto_now_add = True)
    
    # date/time when this series was last modified/updated
    modified = models.DateTimeField(auto_now = True)
    
    def __unicode__(self):
        return str(self.name)
    
    class Meta:
        verbose_name = 'Calibratie reeks'
        verbose_name_plural = 'Calibratie reeksen'

    def _interpolate(self, x, points):
        """ interpolates value in array of x,y values (ascending x) """

        n = len(points)

        if n == 0:
            return None
        
        if n == 1:
            return points[0][1]
        
        for i,p in enumerate(points):
            if p[0] > x:
                break

        # make sure index is valid
        i = max(1,min(i,n-1))
        
        # get the x and y values 
        p1 = points[i-1]
        p2 = points[i]
        x1, y1 = p1
        x2, y2 = p2

#         # do not allow extrapolation beyond x limits
#         if x < x1 or x > x2:
#             return -1

        # linear interpolation of y-value        
        return y1 + (x-x1) * (y2-y1) / (x2-x1)
    
    def calibrate(self, module):
        """ returns single calibrated EC-value using raw ADC values """

        # select ADC and EC values to use
        if module.adc2 < 4000:
            adc = module.adc2
            queryset = self.calibrationdata_set.exclude(Q(adc2__isnull=True)|Q(adc2__ge=4000)).order_by('adc2').values_list('adc2', 'value')
        else:
            adc = module.adc1
            queryset = self.calibrationdata_set.exclude(Q(adc1__isnull=True)|Q(adc2__lt=4000)).order_by('adc1').values_list('adc1', 'value')
        
        if adc == 65535:
            return -1

        return self._interpolate(adc, list(queryset))
        
class CalibrationData(models.Model):
    """ Calibration data for EC modules """
    series = models.ForeignKey(CalibrationSeries)
    
    # raw ADC value 1x gain
    adc1 = models.FloatField(null=True)
    
    # raw ADC value 11x gain
    adc2 = models.FloatField(null=True,blank=True)
    
    # corresponding EC-value
    value = models.FloatField()
    
    class Meta:
        ordering = ('value',)
        verbose_name = 'ijkpunt'
        verbose_name_plural = 'ijkpunten'
        
class Device(models.Model):
    """ Represents a 'Peilstok' device with sensors """ 

    class Meta:
        verbose_name = 'Peilstok'
        verbose_name_plural = 'Peilstokken'
        unique_together = ('serial', 'devid')
            
    """ serial number (BLE MAC address) of device """
    serial = models.CharField(max_length=20,verbose_name='MAC-adres')
    
    """ name (or id) of device """
    devid = models.CharField(max_length=20,verbose_name='naam')
    
    # calibration series for EC values
    cal = models.ForeignKey(CalibrationSeries,verbose_name='ijkreeks') 

    # date/time created
    created = models.DateTimeField(auto_now_add = True, verbose_name='Geregistreerd')
    
    last_seen = models.DateTimeField(null=True,verbose_name='Laatste contact')
    
    def get_series(self, Module, entity, **kwargs):
        """ Get time series as array of tuples
        
            parameters:
            
                * `Module`: Module class to query
                * `entity`: Entity (fieldname) for query 
        
            examples:
             
                * device.get_series(ECModule,"adc1",position=2)
                  gets timeseries of adc1 values from EC Module at position 2
                * device.get_series(MasterModule,"battery")
                  gets timeseries of battery status from Master module
        """ 
        
        q = Module.objects.filter(device = self)
        # exclude values of 65535 (-1)
        kwargs.update({entity + "__lt": 65535})
        return q.filter(**kwargs).values_list("time", entity).order_by("time")

    def get_pandas(self, Module, entity, **kwargs):
        """ Build and return a Pandas time series for a module.entity """
    
        data = list(self.get_series(Module,entity,**kwargs))
        if data:
            dates,values=zip(*data)
            return pd.Series(values,index=dates)
        return pd.Series()
    
    def last(self,messagetype=''):
        """ returns last message received """
        queryset = self.basemodule_set
        if messagetype:
            queryset = queryset.filter(type=messagetype)
        last = queryset.order_by('time').last()
        return last
    last.short_description = 'Laatste bericht'

    def last_time(self,messagetype=''):
        # returns time of last message received
        last = self.last(messagetype)
        return last.time if last else None
    last_time.short_description = 'Laatste update'

    def last_ec(self):
        # returns last EC message received
        last = self.last(EC_MESSAGE)
        if last and hasattr(last,'ecmodule'):
            return last.ecmodule
        return None
    last_ec.short_description = 'Laatste EC-meting'

    def last_status(self):
        # returns last Status message received
        last = self.last(STATUS_MESSAGE)
        if last and hasattr(last,'mastermodule'):
            return last.mastermodule
        return None
    last_status.short_description = 'Laatste Status bericht'

    def last_pressure(self):
        # returns last pressure message received
        last = self.last(PRESSURE_MESSAGE)
        if last and hasattr(last,'pressuremodule'):
            return last.pressuremodule
        return None
    last_pressure.short_description = 'Laatste Drukmeting'

    def last_angle(self):
        # returns last angle message received
        last = self.last(ANGLE_MESSAGE)
        if last and hasattr(last,'anglemessage'):
            return last.anglemessage
        return None
    last_angle.short_description = 'Laatste Hoekmeting'

    def count(self):
        # returns number of messages
        return self.basemodule_set.count()
    count.short_description = 'Aantal berichten'

    def count_status(self):
        # returns number of status messages
        return self.basemodule_set.filter(type=STATUS_MESSAGE).count()
    count_status.short_description = 'Aantal status berichten'

    def count_ec(self):
        # returns number of ec messages
        return self.basemodule_set.filter(type=EC_MESSAGE).count()
    count_ec.short_description = 'Aantal EC-metingen'
    
    def count_pressure(self):
        # returns number of pressure messages
        return self.basemodule_set.filter(type=PRESSURE_MESSAGE).count()
    count_pressure.short_description = 'Aantal drukmetingen'

    def __unicode__(self):
        return self.devid

    def calc(self,rule='H'):
        
        def getdata(module, entity, **kwargs):
            s = self.get_pandas(module,entity,**kwargs)
            if s.empty:
                return []
            s[s>4094] = None
            if s.empty:
                return []
            return s.resample(rule=rule).mean()
            
        def calcec(adc1,adc2,temp):
            """calibration with polynomals """
            def p2(c,x):
                return c[0]*x*x + c[1]*x + c[2]
            
            #2nd order polynomal coefficients for the two rings
            c1 = [0.0141, -107.49, 206099] 
            c2 = [0.0044, -40.808, 91856]
            
            if adc1 > 3330 and adc1 < 4090:
                ec = p2(c1,adc1)
            elif adc2 < 3170:
                ec = p2(c2,adc2)
            elif adc1 < 4090 and adc2 < 4090:
                r1 = p2(c1,adc1)
                x1 = adc1 - 3330
                r2 = p2(c2,adc2)
                x2 = 3170 - adc2
                ec = (r1 * x2 + r2 * x1) / (x1+x2)
            else:
                ec = None
            return ec

        ec1adc1 = getdata(ECModule, 'adc1', position=1)
        ec1adc2 = getdata(ECModule, 'adc2', position=1)
        ec1temp = getdata(ECModule, 'temperature', position=1)

        ec2adc1 = getdata(ECModule, 'adc1', position=2)
        ec2adc2 = getdata(ECModule, 'adc2', position=2)
        ec2temp = getdata(ECModule, 'temperature', position=2)
        
        p1adc = getdata(MasterModule, 'air')
        p2adc = getdata(PressureModule, 'adc')

        ec1 = pd.DataFrame({'ec1_adc1': ec1adc1, 'ec1_adc2': ec1adc2, 'ec1_temp': ec1temp})
        ec2 = pd.DataFrame({'ec2_adc1': ec2adc1, 'ec2_adc2': ec2adc2, 'ec2_temp': ec2temp})
        druk = pd.DataFrame({'adc1': p1adc, 'adc2': p2adc})

        ec1['ec1'] = ec1.apply(lambda row: calcec(row['ec1_adc1'], row['ec1_adc2'], row['ec1_temp']), axis = 1)
        ec2['ec2'] = ec2.apply(lambda row: calcec(row['ec2_adc1'], row['ec2_adc2'], row['ec2_temp']), axis = 1)
        druk['lucht'] = druk[druk['adc1']<4090]['adc1']*ADC_HPAMASTER
        druk['water'] = druk[druk['adc2']<4090]['adc2']*ADC_HPASLAVE
        druk['verschil'] = druk['water'] - druk['lucht']
        druk['cmwater'] = druk['verschil'] / 0.980638
        return pd.concat([ec1,ec2,druk],axis=1)
    
class Sensor(models.Model):
    """ Sensor in a peilstok """
    # device this sensor belongs to
    device = models.ForeignKey(Device)
    
    # position of sensor
    position = models.PositiveSmallIntegerField(default=0,verbose_name='Sensorpositie')
    
    # distance of sensor in mm from bottom        
    distance = models.IntegerField(default = 0, verbose_name = 'afstand', help_text = 'afstand tov onderkant mm')

    # type of sensor
    type = models.PositiveSmallIntegerField(choices=SENSOR_CHOICES)

    def __unicode__(self):
        return SENSOR_CHOICES[self.type][1]

class PressureSensor(Sensor):
    offset = models.DecimalField(max_digits=10, decimal_places=2)

class ECSensor(Sensor):
    pass

class GNSS_Sensor(Sensor):
    pass

class AngleSensor(Sensor):
    pass

class LoraMessage(models.Model):
    """ Base class for all LoRa messages sent by a device """
    sensor = models.ForeignKey(Sensor)
 
    # time received by server
    time = models.DateTimeField(verbose_name='tijdstip')
    
    # type of message
    type = models.PositiveSmallIntegerField(choices=MESSAGE_CHOICES)

class ECMessage(LoraMessage):
    """ Contains data from an EC sensor """

    # temperature in 0.01 degrees C
    temperature = models.IntegerField(help_text='temperatuur in 0.01 graden Celcius')

    # raw ADC value 1x gain
    adc1 = models.IntegerField()

    # raw ADC value 11x gain
    adc2 = models.IntegerField()


class PressureMessage(LoraMessage):
    # raw ADC pressure value
    adc = models.IntegerField()

class LocationMessage(LoraMessage):
    """ Contains data from the on-board GNSS chip (ublox-7P) """
    #gnsstime = models.BigIntegerField()
    
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

class InclinationMessage(LoraMessage):
    """ Message generated when device is tilted is more than 45 degrees """
    angle = models.IntegerField()

        
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
    
class BaseModule(models.Model):
    
    """ Base class for all messages sent by a device """
    
    device = models.ForeignKey(Device,verbose_name='peilstok')
 
    # time received by server
    time = models.DateTimeField(verbose_name='tijdstip')
    
    # type of module
    type = models.PositiveSmallIntegerField(choices=MESSAGE_CHOICES)

    # position of module
    position = models.PositiveSmallIntegerField(default=0,verbose_name='Sensorpositie')
        
class MasterModule(BaseModule):
    """ Contains information about the state of the device itself, not its sensors """
    
    # Angle in degrees
    angle = models.IntegerField(verbose_name='inclinatiehoek')

    # Battery level in mV
    battery = models.IntegerField(verbose_name='Batterijspanning')
    
    # Raw air pressure 12-bit ADC 
    air = models.IntegerField(verbose_name='Luchtdruk')
    
    # Max number of modules
    total = models.PositiveSmallIntegerField(verbose_name='maximum aantal sensoren')

    def pressure(self):
        # returns pressure in psi
        return round(self.air * ADC_PSIMASTER,1)

    def hPa(self):
        # returns pressure in hPa
        return round(self.air * ADC_HPAMASTER,1)

    class Meta:
        verbose_name = 'Toestand'
        verbose_name_plural = 'Toestand'

class GNSSModule(BaseModule):
    """ Contains data from the on-board GNSS chip (ublox-7P) """
    #gnsstime = models.BigIntegerField()
    
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

    class Meta:
        verbose_name = 'Locatie'
        verbose_name_plural = 'Locaties'


class ECModule(BaseModule):
    """ Contains data from the EC sensor """

    # temperature in 0.01 degrees C
    temperature = models.IntegerField(help_text='temperatuur in 0.01 graden Celcius')

    # raw ADC value 1x gain
    adc1 = models.IntegerField()

    # raw ADC value 11x gain
    adc2 = models.IntegerField()
    
    def _calec(self):
        """calibration with polynomals """
        def p2(c,x):
            return c[0]*x*x + c[1]*x + c[2]
        
        #2nd order polynomal coefficients
        c1 = [0.0141, -107.49, 206099] 
        c2 = [0.0044, -40.808, 91856]
        
        if self.adc1 > 3330:
            ec = p2(c1,self.adc1)
        elif self.adc2 < 3170:
            ec = p2(c2,self.adc2)
        else:
            r1 = p2(c1,self.adc1)
            x1 = self.adc1 - 3330
            r2 = p2(c2,self.adc2)
            x2 = 3170 - self.adc2
            ec = (r1 * x2 + r2 * x1) / (x1+x2)
        return ec

    # calibrated EC-value33
    def EC(self):
        #return int(self.device.cal.calibrate(self))
        return self._calec()
    
    class Meta:
        verbose_name = 'EC-meting'
        verbose_name_plural = 'EC-metingen'

class PressureModule(BaseModule):
    """ Contains data from the pressure sensor """
    
    # raw ADC pressure value
    adc = models.IntegerField()

    def pressure(self):
        # returns pressure in psi
        return round(self.adc * ADC_PSISLAVE, 1)

    def hPa(self):
        # returns pressure in hPa
        return round(self.adc * ADC_HPASLAVE, 1)
            
    class Meta:
        verbose_name = 'Drukmeting'
        verbose_name_plural = 'Drukmetingen'

class AngleMessage(BaseModule):
    """ Message generated when device is tilted is more than 45 degrees """
    angle = models.IntegerField()

    class Meta:
        verbose_name = 'Beweging'
        verbose_name_plural = 'Bewegingen'

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
    
