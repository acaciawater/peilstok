'''
Created on Jan 06, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device, ECMessage
from django.utils.text import slugify
from acacia.data.models import MeetLocatie
import pandas as pd

def select(query, time):
    ''' select (or interpolate) ec message '''
    m = query.filter(time=time).first()
    if m:
        # exact match
        return m
    
    query = query.order_by('time')
    first = query.first()
    if time < first.time:
        # time before first message, return first
        return first
    
    last = query.last()
    if time > last.time:
        # time after last message, return last
        return last

    # interpolate
    m1 = query.filter(time__lt=time).last()
    m2 = query.filter(time__gt=time).first()
    factor = (time - m1.time).total_seconds() / (m2.time - m1.time).total_seconds()
    m = ECMessage(sensor = m1.sensor,
                  time = time,
                  adc1 = round(m1.adc1 + (m2.adc1 - m1.adc1) * factor),
                  adc2 = round(m1.adc2 + (m2.adc2 - m1.adc2) * factor),
                  temperature = round(m1.temperature + (m2.temperature - m1.temperature) * factor))
    return m

class Command(BaseCommand):
    args = ''
    help = 'Dump EC measurements'
    
    def add_arguments(self, parser):
        parser.add_argument('-d','--device',
            action='store',
            dest='name',
            help='device displayname')
        
    def handle(self, *args, **options):
        query = Device.objects.all()
        name = options['name']
        if name:
            query = query.filter(displayname__iexact=name)
        with open('recalib.csv','w') as f:
            f.write('device,time,econdiep25,econdiep,tempondiep,ecdiep25,ecdiep,tempdiep,ec1adc1,ec1adc2,ec1temp,ec1ec25,ec2adc1,ec2adc2,ec2temp,ecec25\n')
            for dev in query:
                print dev.displayname
    
                try:
                    def getseries(name):
                        try:
                            return mloc.series_set.get(name=name).to_pandas()
                        except:
                            return None
                        
                    # handpeilingen ophalen
                    mloc = MeetLocatie.objects.get(name=dev.displayname)
                    ec_ondiep = getseries('ECondiep')
                    temp_ondiep = getseries('Tondiep')
                    ec_diep = getseries('ECdiep')
                    temp_diep = getseries('Tdiep')
                    hand = pd.DataFrame({'EC1': ec_diep, 'EC2': ec_ondiep, 'T1': temp_ondiep, 'T2': temp_diep})
        
                    # loop over handpeilingen
                    for index, row in hand.iterrows():
                        time = index
                        
                        ec1 = row['EC1']
                        t1 = row['T1']
                        if pd.isnull(ec1) or pd.isnull(t1):
                            ec1t = None
                        else:
                            ec1t = ec1 / (1 + (25 - t1) * 0.025)
                        
                        ec2 = row['EC2']
                        t2 = row['T2']
                        if pd.isnull(ec2) or pd.isnull(t2):
                            ec2t = None
                        else:
                            ec2t = ec2 / (1 + (25 - t2) * 0.025)
        
                        # select valid EC messages of this device
                        m = ECMessage.objects.filter(sensor__device__id=dev.id,adc1__lt=4096,adc2__lt=4096)
        
                        # select EC1 message
                        m1 = select(m.filter(sensor__ident = 'EC1'),time=time)
                        
                        #select EC2 message
                        m2 = select(m.filter(sensor__ident = 'EC2'),time=time)
                        
                        def mapper(obj):
                            if pd.isnull(obj):
                                return ''
                            return str(obj)
                        
                        f.write(','.join(map(mapper,[dev.displayname,
                                                  time, 
                                                  ec1, ec1t, t1,
                                                  ec2, ec2t, t2,
                                                  m1.adc1, m1.adc2, m1.temperature/100.0,
                                                  m1.sensor.value(m1),
                                                  m2.adc1, m2.adc2, m2.temperature/100.0,
                                                  m2.sensor.value(m2),
                                                  ])))
                        f.write('\n')
                except Exception as e:
                    print e
                    