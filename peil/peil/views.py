'''
Created on Apr 25, 2017

@author: theo
'''
from django.http.response import HttpResponse, HttpResponseBadRequest,\
    HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.decorators.gzip import gzip_page
from django.conf import settings

import re, time, datetime
import simplejson as json # allows for NaN conversion
from peil.models import Device, UBXFile
from peil.util import handle_post_data
import pandas as pd
import numpy as np

import logging
from django.shortcuts import get_object_or_404
logger = logging.getLogger(__name__)

def json_locations(request):
    """ return json response with last peilstok locations
        optionally filter messages on hacc (in mm)
    """
    result = []
    hacc = request.GET.get('hacc',None)
    for p in Device.objects.all():
        try:
            # select only valid fixes (with hacc > 0)
            g = p.get_sensor('GPS').loramessage_set.filter(locationmessage__hacc__gt=0).order_by('time')
            if hacc:
                # filter messages on maximum hacc
                g = g.filter(hacc__lt=hacc)
                
            # use last valid gps message
            g = g.last()

            if g.lon > 40*1e7 and g.lat < 10*1e7:
                # verwisseling lon/lat?
                t = g.lon
                g.lon = g.lat
                g.lat = t
            result.append({'id': p.id, 'name': p.devid, 'lon': g.lon*1e-7, 'lat': g.lat*1e-7, 'msl': g.msl*1e-3, 'hacc': g.hacc*1e-3, 'vacc': g.vacc*1e-3, 'time': g.time})
        except Exception as e:
            print e
            pass
    return HttpResponse(json.dumps(result, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')


class PopupView(DetailView):
    """ returns html response for leaflet popup """
    model = Device
    template_name = 'peil/popup.html'
    
    def get_context_data(self, **kwargs):
        return DetailView.get_context_data(self, **kwargs)
    
@csrf_exempt
def ttn(request):
    """ handle post from TTN server and update database """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            return handle_post_data(data)
        except:
            logger.exception('Cannot parse POST data')
            return HttpResponseServerError(reason='Error parsing POST data')
    return HttpResponseBadRequest()

@csrf_exempt
def ubx(request):
    """ handle post with raw ubx data from GNSS chip, create UbxFile instance and save data in media folder
        the raw data is sent in chunks with same filename. Append chunks to existing file
    """
    if request.method == 'POST':
        file = request.FILES['acacia']

        # extract serial number of peilstok from filename
        match = re.match('(?P<serial>[0-9A-F]+)\-\d+\.\w{3}',file.name)
        serial = match.group('serial')
        
        # find Device
        try:
            device = Device.objects.get(serial=serial)
        except Device.DoesNotExist:
            return HttpResponseBadRequest('Device {} not found'.format(serial))
        
        try:
            # find existing ubxfile for this device
            ubx = device.ubxfile_set.get(ubxfile__startswith='ubx/'+file.name)
            path = unicode(ubx.ubxfile.file)
            # append to existing file
            with open(path, "ab") as f:
                f.write(file.read())

            # remove existing nav messages
            # ubx.navpvt_set.all().delete()

        except UBXFile.DoesNotExist:
            # create new instance
            device.ubxfile_set.create(ubxfile=file)
        
        # TODO: schedule creation of new navpvt messages

        return HttpResponse('Done',status=201)
    return HttpResponseBadRequest()
    
class MapView(ListView):
    model = Device
    template_name = 'peil/leaflet_map.html'
    ordering = ('-last_seen',)
    
    def get_context_data(self, **kwargs):
        context = super(MapView, self).get_context_data(**kwargs)
        context['api_key'] = settings.GOOGLE_MAPS_API_KEY
        context['maptype'] = "ROADMAP"
        return context
    
class DeviceListView(ListView):
    model = Device
    
@gzip_page
def chart_as_json(request,pk):
    """ get chart data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    data = {}
    def getdata(name,**kwargs): 
        try:
            #t,x=zip(*list(device.get_sensor(name,**kwargs).data(time__gt = datetime.datetime(2017,6,28))))       
            t,x=zip(*list(device.get_sensor(name,**kwargs).data()))       
            return pd.Series(x,index=t).resample(rule='H').mean()
        except:
            return pd.Series()
               
    pts = getdata('EC1',position=1)
    data['EC1'] = zip(pts.index,pts.values)        
    
    pts = getdata('EC2',position=2)
    data['EC2'] = zip(pts.index,pts.values)
    
    h1=getdata('Luchtdruk',position=0)
    h2=getdata('Waterdruk',position=3)
    
    pts = (h2-h1)/0.980638
    data['H']=zip(pts.index,pts.values)
    return HttpResponse(json.dumps(data, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

@gzip_page
def data_as_json(request,pk):
    """ get raw sensor data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    data = {}

    def getdata(name,**kwargs): 
        try:
            data = device.get_sensor(name,**kwargs).raw_data()
            df = pd.DataFrame(data).set_index('time')
            df = df.where(df<4096,np.nan) # clear all extreme values
            return df.resample(rule='H').mean()
        except:
            return pd.DataFrame()
               
    pts = getdata('EC1',position=1)
    if not pts.empty:
        data['EC1_adc1'] = zip(pts.index,pts['adc1'])        
        data['EC1_adc2'] = zip(pts.index,pts['adc2'])
        data['EC1_temp'] = zip(pts.index,pts['temperature'])
            
    pts = getdata('EC2',position=2)
    if not pts.empty:
        data['EC2_adc1'] = zip(pts.index,pts['adc1'])        
        data['EC2_adc2'] = zip(pts.index,pts['adc2'])        
        data['EC2_temp'] = zip(pts.index,pts['temperature'])
        
    pts=getdata('Luchtdruk',position=0)
    if not pts.empty:
        data['Luchtdruk'] = zip(pts.index,pts['adc'])
    
    pts=getdata('Waterdruk',position=3)
    if not pts.empty:
        data['Waterdruk'] = zip(pts.index,pts['adc'])
    
    return HttpResponse(json.dumps(data, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

class PeilView(DetailView):
    """ Shows calibrated and raw sensor values """
    model = Device
    template_name = 'peil/chart.html'

    def get_context_data(self, **kwargs):
        context = super(PeilView, self).get_context_data(**kwargs)
        device = self.get_object()
        
        options = {
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      'marginLeft': 40, 
                      'marginRight': 60,
                      'spacingTop': 20,
                      'spacingBottom': 20
                      },
            'title': {'text': device.devid},
            'xAxis': {'type': 'datetime',
                      'crosshair': True,
                      'events': {'setExtremes': None},
                      },
            'legend': {'enabled': True},
            'tooltip': {'shared': True, 'valueDecimals': 2},
            'plotOptions': {'line': {'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'EC (mS/cm)'},},
                      {'title': {'text': 'Hoogte (cm)'},'opposite': 1},
                      ],
            'series': [{'name': 'EC ondiep', 'id': 'EC1', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'EC diep ', 'id': 'EC2', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'Waterhoogte', 'id': 'H', 'yAxis': 1, 'data': [], 'tooltip': {'valueSuffix': ' cm'}},
                        ]
                   }

        context['options1'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)

        options.update({
            'title': {'text': 'Ruwe sensor waardes'},
            'plotOptions': {'line': {'marker': {'enabled': True, 'radius': 3}}},            
            'tooltip': {'valueDecimals': 0, 'shared': True},
            'yAxis': [{'title': {'text': 'ADC waarde'},'labels':{'format': '{value}'}}],
            'series': [{'name': 'EC1-adc1', 'id': 'EC1_adc1', 'yAxis': 0, 'data': []},
                       {'name': 'EC1-adc2', 'id': 'EC1_adc2', 'yAxis': 0, 'data': []},
                       {'name': 'EC1-temp', 'id': 'EC1_temp', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-adc1', 'id': 'EC2_adc1', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-adc2', 'id': 'EC2_adc2', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-temp', 'id': 'EC2_temp', 'yAxis': 0, 'data': []},
                       {'name': 'Luchtdruk', 'id': 'Luchtdruk', 'yAxis': 0, 'data': []},
                       {'name': 'Waterdruk', 'id': 'Waterdruk', 'yAxis': 0, 'data': []},
                       ]
                   })
        context['options2'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)
        context['theme'] = 'None'
        return context
    