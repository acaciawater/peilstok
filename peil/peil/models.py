'''
Created on Apr 25, 2017

@author: theo
'''
from django.db import models
from django.db.models import Q
import pandas as pd

# Message types
GNSS_MESSAGE = 1
EC_MESSAGE = 2
PRESSURE_MESSAGE = 3
STATUS_MESSAGE = 6

TYPE_CHOICES = (
    (GNSS_MESSAGE,      'GNSS'),
    (EC_MESSAGE,        'EC'),
    (PRESSURE_MESSAGE,  'Pressure'),
    (STATUS_MESSAGE,    'Master'),
    )

# Factor to convert raw ADC-pressure value to N/m2
ADC_NM2 = 50.52059198# (ADC * 30) / 4096 * 6897.744825

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
    """ Represents a device with sensors """ 

    class Meta:
        verbose_name = 'Peilstok'
        verbose_name_plural = 'Peilstokken'
            
    # serial number (BLE MAC address) of device
    serial = models.CharField(max_length=20,unique=True,verbose_name='MAC-adres')
    
    # name or id of device
    devid = models.CharField(max_length=20,verbose_name='naam')
    
    # calibration series for EC values
    cal = models.ForeignKey(CalibrationSeries,verbose_name='ijkreeks') 

    # date/time created
    created = models.DateTimeField()
    
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
        dates,values=zip(*data)
        return pd.Series(values,index=dates)
    
    def last(self,messagetype=''):
        # returns last message received
        queryset = self.basemodule_set
        if messagetype:
            queryset = queryset.filter(type=messagetype)
        last = queryset.order_by('time').last()
        return last
    last.short_description = 'Laatse bericht'

    def last_ec(self):
        # returns last EC message received
        return self.last(EC_MESSAGE).ecmodule
    last_ec.short_description = 'Laatse EC'

    def last_status(self):
        # returns last Status message received
        return self.last(STATUS_MESSAGE).mastermodule
    last_status.short_description = 'Laatste Status bericht'

    def last_pressure(self):
        # returns last pressure message received
        return self.last(PRESSURE_MESSAGE).pressuremodule
    last_status.short_description = 'Laatste Drukmeting'

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
    count_ec.short_description = 'Aantal EC metingen'
    
    def count_pressure(self):
        # returns number of pressure messages
        return self.basemodule_set.filter(type=PRESSURE_MESSAGE).count()
    count_pressure.short_description = 'Aantal druk metingen'

    def __unicode__(self):
        return self.devid

class BaseModule(models.Model):
    """ Base class for all modules in a device """
    
    device = models.ForeignKey(Device)
    #appid = models.CharField(max_length=20,default='peilstok')
 
    # time received by server
    time = models.DateTimeField()
    
    # type of module
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)

    # position of module
    position = models.PositiveSmallIntegerField(default=0)

class MasterModule(BaseModule):
    """ Contains information about the state of the device itself, not its sensors """
    
    # Angle in degrees
    angle = models.IntegerField()

    # Battery level in mV
    battery = models.IntegerField()
    
    # Raw air pressure 12-bit ADC 
    air = models.IntegerField()
    
    # Max number of modules
    total = models.PositiveSmallIntegerField()

    def pressure(self):
        # returns pressure in N/m2
        return self.air * ADC_NM2

    def hPa(self):
        # returns pressure in hPa
        return round(self.pressure() / 100.0,1)

    class Meta:
        verbose_name = 'Toestand'
        verbose_name_plural = 'Toestand'

class GNSSModule(BaseModule):
    """ Contains data from the on-board GNSS chip (ublox-7P) """
    gnsstime = models.BigIntegerField()
    
    # Latitude * 1e7 
    lat = models.IntegerField()
    
    # Longitude * 1e7 
    lon = models.IntegerField()
    
    # Height above ellipsoid in mm
    alt = models.IntegerField()
    
    # Vertical accuracy in mm
    vacc = models.IntegerField()
    
    # Horizontal accuracy in mm
    hacc = models.IntegerField()
    
    # Height above mean sea level in mm
    msl = models.IntegerField()

    class Meta:
        verbose_name = 'Locatie'
        verbose_name_plural = 'Locaties'


class ECModule(BaseModule):
    """ Contains data from the EC sensor """

    # temperature in 0.01 degrees C
    temperature = models.IntegerField()

    # raw ADC value 1x gain
    adc1 = models.IntegerField()

    # raw ADC value 11x gain
    adc2 = models.IntegerField()
    
    # calibrated EC-value
    def EC(self):
        return int(self.device.cal.calibrate(self))
    
    class Meta:
        verbose_name = 'EC-meting'
        verbose_name_plural = 'EC-metingen'

class PressureModule(BaseModule):
    """ Contains data from the pressure sensor """
    
    # raw ADC pressure value
    adc = models.IntegerField()

    def pressure(self):
        # returns pressure in N/m2
        return self.adc * ADC_NM2

    def hPa(self):
        # returns pressure in hPa
        return round(self.pressure() / 100.0,1)
            
    class Meta:
        verbose_name = 'Drukmeting'
        verbose_name_plural = 'Drukmetingen'
