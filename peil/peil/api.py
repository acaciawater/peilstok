'''
Created on Nov 30, 2016

@author: theo
'''
from django.contrib.auth.models import User
from tastypie.resources import ModelResource, ALL, ALL_WITH_RELATIONS
from tastypie.authorization import DjangoAuthorization
from tastypie import fields
from tastypie.authentication import BasicAuthentication

from .models import Device

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
    
