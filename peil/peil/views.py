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

import re, time
import simplejson as json # allows for NaN conversion
from peil.models import Device, UBXFile
from peil.util import handle_post_data, battery_status
import pandas as pd
import numpy as np

import logging
from django.shortcuts import get_object_or_404
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.text import slugify

logger = logging.getLogger(__name__)

def json_locations(request):
    """ return json response with last peilstok locations
        optionally filter messages on hacc (in mm)
    """
    result = []
    hacc = request.GET.get('hacc',None)
    trans = None
    for p in Device.objects.all():
        try:
            # select survey
            s = p.survey_set.last()
            if s:
                pnt = s.location
                if trans is None:
                    wgs84 = SpatialReference(4326)
                    rdnew = SpatialReference(28992)
                    trans = CoordTransform(rdnew,wgs84)
                pnt.transform(trans)
                result.append({'id': p.id, 'name': p.displayname, 'lon': pnt.x, 'lat': pnt.y})
            else:
                # get location from on-board GPS
                # select only valid fixes (with hacc > 0)
                g = p.get_sensor('GPS').loramessage_set.filter(locationmessage__hacc__gt=0).order_by('time')
                if g:
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
                    result.append({'id': p.id, 'name': p.displayname, 'lon': g.lon*1e-7, 'lat': g.lat*1e-7, 'msl': g.msl*1e-3, 'hacc': g.hacc*1e-3, 'vacc': g.vacc*1e-3, 'time': g.time})
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

class NavMixin(object):
    """ Mixin for browsing through devices sorted by name """

    def nav(self,device):
        next = Device.objects.filter(displayname__gt=device.displayname)
        next = next.first() if next else None
        prev = Device.objects.filter(displayname__lt=device.displayname)
        prev = prev.last() if prev else None
        return {'next': next, 'prev': prev}

class NavDetailView(NavMixin, DetailView):
    """ Detailview with browsing through devices sorted by name """

    def get_context_data(self, **kwargs):
        context = super(NavDetailView, self).get_context_data(**kwargs)
        device = self.get_object()
        context['nav'] = self.nav(device)
        return context
    
class DeviceListView(ListView):
    model = Device

class DeviceDetailView(NavDetailView):
    model = Device

    def get_context_data(self, **kwargs):
        context = super(DeviceDetailView, self).get_context_data(**kwargs)
        device = self.get_object()
        try:
            sensor = device.get_sensor('Batterij',position=0)
            level = sensor.value(sensor.last_message())
            context['battery'] = battery_status(level)
        except:
            pass
        return context

def get_chart_data(device):
    """ 
    @return: Pandas dataframe with timeseries of EC and water level
    @param device: the device to query 
    @summary: Query a device for EC and water level resampled per hour
    """  
    def getdata(name,**kwargs): 
        try:
            t,x=zip(*list(device.get_sensor(name,**kwargs).data()))       
            return pd.Series(x,index=t).resample(rule='H').mean()
        except Exception as e:
            logger.error('ERROR loading sensor data for {}: {}'.format(name,e))
            return pd.Series()
    data = pd.DataFrame()
    data['EC ondiep'] = getdata('EC1',position=1)
    data['EC diep'] = getdata('EC2',position=2)
    
    waterpressure=getdata('Waterdruk',position=3)
    airpressure=getdata('Luchtdruk',position=0)
    # take the nearest air pressure values within a range of 2 hours from the time of water pressure measurements
    airpressure = airpressure.reindex(waterpressure.index,method='nearest',tolerance='2h')
    # calculate water level in cm above the sensor
    data['Waterhoogte'] = (waterpressure-airpressure)/0.980638
    # convert to water level in m +NAP
    nap_device = device.get_nap() # level of top of device in NAP (m)
    if nap_device:
        sensor = device.get_sensor('Waterdruk',position=3)
        # calculate NAP level of sensor (m)
        nap_sensor = nap_device - sensor.position/1000.0
    else:
        # no elevation data available
        nap_sensor = 0
    data['Waterpeil'] = data['Waterhoogte']/100.0 + nap_sensor
    return data
    
@gzip_page
def chart_as_json(request,pk):
    """ get chart data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    pts = get_chart_data(device)
    data = {'EC1': zip(pts.index,pts['EC ondiep']),        
            'EC2': zip(pts.index,pts['EC diep']),
            'NAP': zip(pts.index,pts['Waterpeil']),
            'H': zip(pts.index,pts['Waterhoogte'])
            }
    return HttpResponse(json.dumps(data, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

@gzip_page
def chart_as_csv(request,pk):
    """ get chart data as csv for download """
    device = get_object_or_404(Device, pk=pk)
    data = get_chart_data(device)
    data.dropna(inplace=True,how='all')
    resp = HttpResponse(data.to_csv(float_format='%.2f'), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename=%s.csv' % slugify(unicode(device))
    return resp

def get_sensor_data(device):
    """ 
    @return: Pandas dataframe with timeseries of raw sensor data
    @param device: the device to query 
    @summary: Query a device for raw sensor data
    """  
    def getdata(name,**kwargs): 
        try:
            columns = kwargs.pop('columns',None)
            data = device.get_sensor(name,**kwargs).raw_data()
            df = pd.DataFrame(data).set_index('time')
            df = df.where(df<4096,np.nan).resample('H').mean() # clear extreme values and resample on every hour
            return df.rename(columns=columns) if columns else df
        except:
            return pd.DataFrame()
               
    bat = getdata('Batterij',position=0,columns={'battery': 'BAT'})
    ec1 = getdata('EC1',position=1,columns={'adc1': 'EC1-ADC1', 'adc2': 'EC1-ADC2', 'temperature': 'EC1-TEMP'})
    ec2 = getdata('EC2',position=2,columns={'adc1': 'EC2-ADC1', 'adc2': 'EC2-ADC2', 'temperature': 'EC2-TEMP'})
    p1=getdata('Luchtdruk',position=0,columns={'adc': 'PRES0-ADC'})
    p2=getdata('Waterdruk',position=3,columns={'adc': 'PRES3-ADC'})
    return pd.concat([bat,ec1,ec2,p1,p2],axis=1)
    
@gzip_page
def data_as_json(request,pk):
    """ get raw sensor data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    pts = get_sensor_data(device)
    data = {
        'Bat': zip(pts.index,pts['BAT']),
        'EC1adc1': zip(pts.index,pts['EC1-ADC1']),        
        'EC1adc2': zip(pts.index,pts['EC1-ADC2']),
        'EC1temp': zip(pts.index,pts['EC1-TEMP']),
        'EC2adc1': zip(pts.index,pts['EC2-ADC1']),        
        'EC2adc2': zip(pts.index,pts['EC2-ADC2']),
        'EC2temp': zip(pts.index,pts['EC2-TEMP']),
        'Luchtdruk': zip(pts.index,pts['PRES0-ADC']),
        'Waterdruk': zip(pts.index,pts['PRES3-ADC']),
        }
            
    return HttpResponse(json.dumps(data, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

@gzip_page
def data_as_csv(request, pk):
    device = get_object_or_404(Device, pk=pk)
    data = get_sensor_data(device)
    data.dropna(inplace=True,how='all')
    resp = HttpResponse(data.to_csv(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename=%s.csv' % slugify(unicode(device))
    return resp

class PhotoView(LoginRequiredMixin, NavDetailView):
    model = Device
    template_name = 'peil/photos.html'
    
class PeilView(LoginRequiredMixin, NavDetailView):
    """ Shows calibrated and raw sensor values """
    model = Device
    template_name = 'peil/chart.html'

    def get_context_data(self, **kwargs):
        context = super(PeilView, self).get_context_data(**kwargs)
        device = self.get_object()
                
        options = {
            'chart': {'type': 'spline', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      'marginLeft': 60, 
                      'marginRight': 60,
                      'spacingTop': 20,
                      'spacingBottom': 20
                      },
            'title': {'text': unicode(device)},
            'xAxis': {'type': 'datetime',
                      'crosshair': True,
                      'events': {'setExtremes': None},
                      },
            'legend': {'enabled': True},
            'tooltip': {'xDateFormat': '%a %d %B %Y %H:%M:%S', 'valueDecimals': 2},
            'plotOptions': {'spline': {'connectNulls': True, 'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'EC (mS/cm)'},},
                      {'title': {'text': 'Peil (m NAP)'},'opposite': 1},
#                      {'title': {'text': 'Hoogte (cm)'},'opposite': 1},
                      ],
            'series': [{'name': 'EC ondiep', 'id': 'EC1', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'EC diep ', 'id': 'EC2', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'Waterpeil', 'id': 'NAP', 'yAxis': 1, 'data': [], 'tooltip': {'valueSuffix': ' m NAP'}},
#                        {'name': 'Waterhoogte', 'id': 'H', 'yAxis': 2, 'data': [], 'tooltip': {'valueSuffix': ' cm'}},
                        ]
                   }

        context['options1'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)

        options.update({
            'title': {'text': 'Ruwe sensor waardes'},
            'plotOptions': {'spline': {'connectNulls': False, 'marker': {'enabled': False, 'radius': 3}}},            
            'tooltip': {'valueDecimals': 0, 'xDateFormat': '%a %d %B %Y %H:%M:%S'},
            'yAxis': [{'title': {'text': 'ADC waarde'},'labels':{'format': '{value}'}}],
            'series': [{'name': 'Batterij', 'id': 'Bat', 'yAxis': 0, 'data': []},
                       {'name': 'EC1-adc1', 'id': 'EC1adc1', 'yAxis': 0, 'data': []},
                       {'name': 'EC1-adc2', 'id': 'EC1adc2', 'yAxis': 0, 'data': []},
                       {'name': 'EC1-temp', 'id': 'EC1temp', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-adc1', 'id': 'EC2adc1', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-adc2', 'id': 'EC2adc2', 'yAxis': 0, 'data': []},
                       {'name': 'EC2-temp', 'id': 'EC2temp', 'yAxis': 0, 'data': []},
                       {'name': 'Luchtdruk', 'id': 'Luchtdruk', 'yAxis': 0, 'data': []},
                       {'name': 'Waterdruk', 'id': 'Waterdruk', 'yAxis': 0, 'data': []},
                       ]
                   })
        context['options2'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)
        return context
    