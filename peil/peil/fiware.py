'''
Created on Nov 7, 2017

@author: theo
'''

import requests
import json
from peil.util import last_ec, last_waterlevel
from peil.models import StatusMessage, PressureMessage, InclinationMessage,\
    ECMessage
import six
import logging
logger = logging.getLogger(__name__)

class NGSI:
    ''' formatters and converters for NGSI '''
    @staticmethod
    def attribute(msg):
        ''' return attribute name from lora message '''
        if isinstance(msg,StatusMessage):
            return 'batteryLevel'
        elif isinstance(msg, InclinationMessage):
            return 'inclination'
        elif isinstance(msg, PressureMessage):
            return 'airPressure'  if msg.sensor.position == 0 else 'waterPressure'
        elif isinstance(msg, ECMessage):
            return 'ecShallow' if msg.sensor.position < 3 else 'ecDeep'
        elif isinstance(msg,dict):
            return msg['name']
        elif isinstance(msg, six.string_types):
            return msg
        
    @staticmethod
    def entity(msg):
        ''' return device id from lora message '''
        return msg.sensor.device.devid

    @staticmethod
    def timestamp(arg):
        ''' return dict of timestamp in NGSI format '''
        if hasattr(arg, 'time'):
            t = arg.time
        elif isinstance(arg,dict):
            t = arg['time']
        else:
            # assume datetime
            t = arg
        return {'type':'DateTime','value': t.isoformat()}

    @staticmethod
    def measurement(value, typename, timestamp):
        ''' return dict of value/timestamp combination in NGSI format '''
        return {
            'value': value, 
            'type': typename, 
            'timestamp': NGSI.timestamp(timestamp)
        }
    
    @staticmethod
    def value(msg):
        ''' return dict with value/timestamp of measurement in lora message '''
        return {'value': msg.value(), 'timestamp': NGSI.timestamp(msg)}

    @staticmethod
    def lora_message(msg,value,typename,unit):
        ''' return NSGI dict of loramessage '''
        return { 
            NGSI.attribute(msg): {
                'type': 'LoraMessage',
                'value': NGSI.measurement(value, typename, msg),
                'metadata': {
                    'unit': {
                        'value': unit
                    }
                }
            }
        }

class Orion:
    ''' Interface to Orion Context Broker '''

    def __init__(self, url, **kwargs):
        self.url = url

    def log_response(self, response):
        ''' send response to log system '''
        if response.ok:
            logger.debug('response = {}'.format(response.status_code))
        else:
            logger.error('response = {}, reason = {}'.format(response.status_code, response.reason))
        return response
                   
    def get(self,path,**kwargs):
        return requests.get(self.url+path,**kwargs)
            
    def post(self,path,data,headers={'content-type':'application/json'}):
        return requests.post(self.url+path,data,headers=headers)

    def put(self,path,data,headers={'content-type':'application/json'}):
        return requests.put(self.url+path,data,headers=headers)

    def delete(self,path,headers={'content-type':'application/json'}):
        return requests.delete(self.url+path,headers=headers)

    def create_entity(self, data):
        ''' create new entity '''
        return self.post('entities',json.dumps(data))
    
    def update_attribute(self, entity_id, attribute_name, data):
        ''' update attribute of existing entity '''
        path = 'entities/{id}/attrs/{att}'.format(id=entity_id,att=attribute_name)
        return self.put(path,json.dumps(data))

    def update_value(self, entity_id, attribute_name, data):
        ''' update value of attribute of existing entity '''
        path = 'entities/{id}/attrs/{att}/value'.format(id=entity_id,att=attribute_name)
        return self.put(path,json.dumps(data))

    def create_device(self, device):
        ''' create a peilstok device in Orion '''
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
            # add lat and lon as separate attributes as well
            data['latitude'] = {
                'value': pos['lat'],
                'type': 'Float'
            }
            data['longitude'] = {
                'value': pos['lon'],
                'type': 'Float'
            }
        
        inc = device.get_sensor('Inclinometer',position=0).last_message()
        if inc:
            data.update(NGSI.lora_message(inc,inc.value(),'Integer','degree'))
        
        bat = device.get_sensor('Batterij',position=0).last_message()
        if bat:
            data.update(NGSI.lora_message(bat,bat.value(),'Integer','mV'))
        
        air = device.get_sensor('Luchtdruk',position=0).last_message()
        if air:
            data.update(NGSI.lora_message(air,air.value(),'Float','hPa'))
        
        wat = device.get_sensor('Waterdruk',position=3).last_message()
        if wat:
            data.update(NGSI.lora_message(wat,wat.value(),'Float','hPa'))        
        
        level = last_waterlevel(device)
        level['name'] = 'waterLevel'
        if level:
            data.update(NGSI.lora_message(level,level['cm'],'Float','cm'))

        ec = device.get_sensor('EC1',position=1).last_message() 
        if ec:
            data.update(NGSI.lora_message(ec,ec.value(),'Float','mS/cm'))

        ec = device.get_sensor('EC2',position=2).last_message() 
        if ec:
            data.update(NGSI.lora_message(ec,ec.value(),'Float','mS/cm'))

        logger.debug('Creating entity {}'.format(device.devid))
        response = self.create_entity(data)
        return self.log_response(response)

    def update_message(self, msg):
        ''' update value of attribute using LoraMessage msg '''
        entity = NGSI.entity(msg)
        attribute = NGSI.attribute(msg)
        logger.debug('Updating entity "{}", attribute "{}"'.format(entity,attribute))
        response = self.update_value(entity, attribute, NGSI.value(msg))
        return self.log_response(response)
    