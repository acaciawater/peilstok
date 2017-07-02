'''
Created on Jun 22, 2017

@author: theo
'''
from peil.models import GNSS_Sensor, AngleSensor, ECSensor, PressureSensor, BatterySensor,\
    Device
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.gis.geos import Point
import calib

def load_distance(filename):
    # load sensor distance to antenna from csv file
    import pandas as pd
    df = pd.read_csv(filename)
    for _,r in df.iterrows():
        try:
            stok = r['Peilstok']
            sensors = PressureSensor.objects.filter(device__devid__iexact=stok, ident='Luchtdruk')
            for sensor in sensors:
                sensor.distance = r['Luchtdruk']
                sensor.save()
            sensors = PressureSensor.objects.filter(device__devid__iexact=stok, ident='Waterdruk')
            for sensor in sensors:
                sensor.distance = r['Waterdruk']
                sensor.save()
            sensors = ECSensor.objects.filter(device__devid__iexact=stok, ident='EC1')
            for sensor in sensors:
                sensor.distance = r['Bovenste EC']
                sensor.save()
            sensors = ECSensor.objects.filter(device__devid__iexact=stok, ident='EC2')
            for sensor in sensors:
                sensor.distance = r['Onderste EC']
                sensor.save()
            sensors = ECSensor.objects.filter(device__devid__iexact=stok, ident='GPS')
            for sensor in sensors:
                sensor.distance = r['Antenne']
                sensor.save()
        except ObjectDoesNotExist:
            continue

def load_survey(filename):
    # load survey data from csv file
    import pandas as pd
    df = pd.read_csv(filename)
    for _,r in df.iterrows():
        try:
            stok = r['Peilstok']
            device = Device.objects.get(devid__iexact=stok)
            surveyor = r['Waarnemer']
            date = r['Datum']
            time = r['Tijd']
            x = r['X']
            y = r['Y']
            z = r['Meetpunt (m tov NAP)']
            vacc = r['Nauwkeurigheid (m)'] * 1000
            time = date+time
            device.survey_set.update_or_create(time=time,defaults = {
                'surveyor': surveyor,
                'location': Point(x,y),
                'altitude': z,
                'vacc': vacc,
                'hacc': 0
                })
        except ObjectDoesNotExist:
            #logger.error('peilstok "{}" does not exist'.format(stok))
            continue

def load_offsets(filename):
    # load pressure sensor offsets from csv file
    import pandas as pd
    df = pd.read_csv(filename)
    for _,r in df.iterrows():
        try:
            p = r['peilstok']
            stok = 'peilstok{}'.format(p)
            sensors = PressureSensor.objects.filter(device__devid__iexact=stok, ident='Luchtdruk')
            for master in sensors:
                master.offset = r['master']
                master.scale = calib.ADC_HPAMASTER
                master.save()
            sensors = PressureSensor.objects.filter(device__devid__iexact=stok, ident='Waterdruk')
            for slave in sensors:
                slave.offset = r['slave']
                slave.scale = calib.ADC_HPASLAVE
                slave.save()
        except ObjectDoesNotExist:
            continue
        
def create_sensors(device):
    return (GNSS_Sensor.objects.update_or_create(device=device,defaults={'ident':'GPS'}),
        AngleSensor.objects.update_or_create(device=device,defaults={'ident':'Inclinometer'}),
        BatterySensor.objects.update_or_create(device=device,defaults={'ident':'Batterij'}),
        ECSensor.objects.update_or_create(device=device,position=1,defaults={
            'ident':'EC1',
            'adc1_coef' :calib.ADC1EC,
            'adc2_coef': calib.ADC2EC,
            'adc1_limits': calib.ADC1EC_LIMITS,
            'adc2_limits': calib.ADC2EC_LIMITS,
            'ec_range': calib.EC_RANGE
            }),
        ECSensor.objects.update_or_create(device=device,position=2,defaults={
            'ident':'EC2',
            'adc1_coef' :calib.ADC1EC,
            'adc2_coef': calib.ADC2EC,
            'adc1_limits': calib.ADC1EC_LIMITS,
            'adc2_limits': calib.ADC2EC_LIMITS,
            'ec_range': calib.EC_RANGE
            }),
        PressureSensor.objects.update_or_create(device=device,position=0,defaults={'ident':'Luchtdruk','scale': calib.ADC_HPAMASTER}),
        PressureSensor.objects.update_or_create(device=device,position=3,defaults={'ident':'Waterdruk','scale': calib.ADC_HPASLAVE}))
