'''
Created on Nov 30, 2016

@author: theo
'''

from tastypie.resources import ModelResource, ALL, ALL_WITH_RELATIONS
from tastypie.authorization import DjangoAuthorization
from tastypie import fields
from tastypie.authentication import BasicAuthentication

from .models import Device
from peil.models import Sensor, LoraMessage, StatusMessage

class DeviceResource(ModelResource): 

    def dehydrate(self, bundle):
        device = bundle.obj
        if device:
            try:
                bundle.data['battery'] = '{}%'.format(device.battery_level())
                loc = device.current_location()
                if 'lon' in loc:
                    bundle.data['longitude'] = loc['lon'] 
                    bundle.data['latitude'] = loc['lat']
                    nap = device.get_nap() 
                    if nap:
                        bundle.data['elevation'] = nap
            except:
                pass 
        return bundle

    class Meta:
        queryset = Device.objects.order_by('-last_seen')
        resource_name = 'device'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'devid': ALL,
            'displayname': ALL,
            'serial': ALL,
            'last_seen': ALL
            }
    
class SensorResource(ModelResource): 
    device = fields.ForeignKey(DeviceResource,'device')
    
    def dehydrate(self, bundle):
        sensor = bundle.obj
        if sensor:
            bundle.data['device_devid'] = sensor.device.devid
            bundle.data['device_displayname'] = sensor.device.displayname
            last = sensor.last_message()
            if last:
                bundle.data['last_message'] = last.time 
                bundle.data['last_value'] = last.value()
        return bundle
    
    class Meta:
        queryset = Sensor.objects.all()
        resource_name = 'sensor'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'device': ALL_WITH_RELATIONS,
            'ident': ALL,
            }
    
class MessageResource(ModelResource): 
    sensor = fields.ForeignKey(SensorResource,'sensor')

    def dehydrate(self, bundle):
        msg = bundle.obj
        if msg:
            bundle.data.update(msg.to_dict())
            bundle.data['device_devid'] = msg.sensor.device.devid
            bundle.data['device_displayname'] = msg.sensor.device.displayname
            bundle.data['sensor_ident'] = msg.sensor.ident
            bundle.data['value'] = msg.value()
            bundle.data['unit'] = msg.sensor.unit
        return bundle
    
    class Meta:
        queryset = LoraMessage.objects.order_by('-time')
        resource_name = 'message'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'sensor': ALL_WITH_RELATIONS,
            'time': ALL
            }
    
class BatteryResource(MessageResource): 
    class Meta:
        queryset = StatusMessage.objects.order_by('-time')
        resource_name = 'battery'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'sensor': ALL_WITH_RELATIONS,
            'time': ALL,
            'battery': ALL
            }
    
