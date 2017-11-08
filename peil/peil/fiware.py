'''
Created on Nov 7, 2017

@author: theo
'''

import requests
import json
from peil.util import last_ec, last_waterlevel
from peil.models import Device

class Orion:
    ''' Interface to Orion Context Broker '''

    def __init__(self, url, **kwargs):
        self.url = url
    
    def get(self,path,**kwargs):
        return requests.get(self.url+path,**kwargs)
            
    def post(self,path,data,headers={'content-type':'application/json'}):
        return requests.post(self.url+path,data,headers=headers)

    def put(self,path,data,headers={'content-type':'application/json'}):
        return requests.put(self.url+path,data,headers=headers)

    def create(self, data):
        return self.post('entities',json.dumps(data))
    
    def update(self, entity, attribute, data):
        path = 'entities/{id}/attrs/{att}'.format(id=entity,att=attribute)
        return self.put(path,json.dumps(data))

    def update_value(self, entity, attribute, data):
        path = 'entities/{id}/attrs/{att}/value'.format(id=entity,att=attribute)
        return self.put(path,data,headers={'content-type':'text/plain'})

    def createDevice(self, device):
        ''' create peilstok device in Orion '''
                
        def timestamp(arg):
            if hasattr(arg, 'time'):
                t = arg.time
            elif isinstance(arg,dict):
                t = arg['time']
            else:
                # assume datetime
                t = arg
            return {'type':'DateTime','value': t.isoformat()}

        def attr(arg,value,typename,unit):
            return {
                'type' : 'LoraMessage',
                'value' : {
                    'value': value, 
                    'type': typename, 
                    'timestamp': timestamp(arg)
                },
                'metadata': {
                    'unit': {
                        'value': unit
                    }
                }
            }
                            
        data = {
            'id': device.devid,
            'type': 'Peilstok',
            'displayName': {
                'value': device.displayname
            }
        }

        pos = device.current_location()
        if pos:
            data['location'] = {
                'type': 'geo:Point',
                'value': '{lon},{lat}'.format(lon=pos['lon'], lat=pos['lat']),
                'metadata': {
                'coordinateSystem': {
                    'value': 'EPSG4326'
                    }
                }
            }
        
        inc = device.get_sensor('Inclinometer',position=0).last_message()
        if inc:
            data['inclination'] = attr(inc,inc.value(),'Integer','degree')
        
        bat = device.get_sensor('Batterij',position=0).last_message()
        if bat:
            data['batteryLevel'] = attr(bat,bat.value(),'Integer','mV')
        
        air = device.get_sensor('Luchtdruk',position=0).last_message()
        if air:
            data['airPressure'] = attr(air,air.value(),'Float','hPa')
        
        wat = device.get_sensor('Waterdruk',position=3).last_message()
        if wat:
            data['waterPressure'] = attr(wat,wat.value(),'Float','hPa')        
        
        level = last_waterlevel(device)
        if level:
            data['waterLevel'] = attr(level,level['cm'],'Float','cm')

        ec = last_ec(device)
        ec1 = ec['EC1']
        ec2 = ec['EC2']
        if ec2:
            data['ecDiep'] = attr(ec2,ec2['value'],'Float','mS/cm')
        if ec1:
            data['ecOndiep'] = attr(ec1,ec1['value'],'Float','mS/cm')
        
        return self.create(data)

    def updateDevice(self, msg):
        device = msg.sensor.device
        
