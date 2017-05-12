'''
Created on Nov 30, 2016

@author: theo
'''
from django.contrib.auth.models import User
from tastypie.resources import ModelResource, ALL, ALL_WITH_RELATIONS
from tastypie.authorization import DjangoAuthorization
from tastypie import fields
from tastypie.authentication import BasicAuthentication

from .models import Device, ECModule, PressureModule, MasterModule, GNSSModule

class OpenGETAuthentication(BasicAuthentication):
    def is_authenticated(self, request, **kwargs):
        if request.method == 'GET':
            return True
        return BasicAuthentication.is_authenticated(self, request, **kwargs)

class DeviceResource(ModelResource): 
    class Meta:
        queryset = Device.objects.all()
        resource_name = 'device'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'devid': ALL,
            'serial': ALL,
            }
    
class ECResource(ModelResource):
    device = fields.ForeignKey(DeviceResource,'device') 
    class Meta:
        queryset = ECModule.objects.all()
        resource_name = 'ec'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'device': ALL_WITH_RELATIONS,
            }
    
class PressureResource(ModelResource): 
    device = fields.ForeignKey(DeviceResource,'device') 
    class Meta:
        queryset = PressureModule.objects.all()
        resource_name = 'pressure'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'device': ALL_WITH_RELATIONS,
            }

class GNSSResource(ModelResource): 
    device = fields.ForeignKey(DeviceResource,'device') 
    class Meta:
        queryset = GNSSModule.objects.all()
        resource_name = 'gnss'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'device': ALL_WITH_RELATIONS,
            }
        
class MasterResource(ModelResource): 
    device = fields.ForeignKey(DeviceResource,'device') 
    class Meta:
        queryset = MasterModule.objects.all()
        resource_name = 'master'
        authentication = BasicAuthentication(realm='Acacia Water')
        authorization = DjangoAuthorization()
        filtering = {
            'device': ALL_WITH_RELATIONS,
            }
    
