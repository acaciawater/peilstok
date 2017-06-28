'''
Created on Jun 22, 2017

@author: theo
'''
from peil.models import GNSS_Sensor, AngleSensor, ECSensor, PressureSensor,\
    BatterySensor, MasterModule, PressureMessage, StatusMessage,\
    ECModule, ECMessage, PressureModule, GNSSModule, LocationMessage,\
    InclinationMessage

"""
migrate data to new structure with sensor layer
"""

def create_sensors(device):
    return (GNSS_Sensor.objects.update_or_create(device=device,defaults={'ident':'GPS'}),
        AngleSensor.objects.update_or_create(device=device,defaults={'ident':'Inclinometer'}),
        BatterySensor.objects.update_or_create(device=device,defaults={'ident':'Batterij'}),
        ECSensor.objects.update_or_create(device=device,position=1,defaults={'ident':'EC1'}),
        ECSensor.objects.update_or_create(device=device,position=2,defaults={'ident':'EC2'}),
        PressureSensor.objects.update_or_create(device=device,position=0,defaults={'ident':'Luchtdruk'}),
        PressureSensor.objects.update_or_create(device=device,position=3,defaults={'ident':'Waterdruk'}))

def copy_messages(device):
    print device
    for m in MasterModule.objects.filter(device=device):
        if m.position != 0:
            continue
        sensor = PressureSensor.objects.get(device=device,position=m.position)
        #print sensor
        PressureMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'adc': m.air,
            })
        sensor = AngleSensor.objects.get(device=device,position=m.position)
        #print sensor
        InclinationMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'angle': m.angle,
            })

        sensor = BatterySensor.objects.get(device=device,position=m.position)
        #print sensor
        StatusMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'battery': m.battery,
            })
            
    for m in ECModule.objects.filter(device=device):
        if m.position not in [1,2]:
            continue
        sensor = ECSensor.objects.get(device=device,position=m.position)
        #print sensor
        ECMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'adc1': m.adc1,
            'adc2': m.adc2,
            'temperature': m.temperature
            })

    for m in PressureModule.objects.filter(device=device):
        if m.position != 3:
            continue
        sensor = PressureSensor.objects.get(device=device,position=m.position)
        #print sensor
        PressureMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'adc': m.adc,
            })

    for m in GNSSModule.objects.filter(device=device):
        if m.position != 0:
            continue
        sensor = GNSS_Sensor.objects.get(device=device,position=0)
        #print sensor
        LocationMessage.objects.update_or_create(sensor=sensor, time = m.time, defaults = {
            'lat': m.lat,
            'lon': m.lon,
            'alt': m.alt,
            'vacc': m.vacc,
            'hacc': m.hacc,
            'msl': m.msl
            })
