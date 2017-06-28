'''
Created on Apr 25, 2017

@author: theo
'''
from django.http.response import HttpResponse, HttpResponseBadRequest,\
    HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.conf import settings

import re, json, time
from peil.models import ECModule, PressureModule, MasterModule, Device,\
    GNSS_MESSAGE, UBXFile
from peil.util import handle_post_data

import logging
logger = logging.getLogger(__name__)

def json_locations(request):
    """ return json response with last peilstok locations
        optionally filter messages on hacc (in mm)
    """
    result = []
    hacc = request.GET.get('hacc',None)
    for p in Device.objects.all():
        try:
            # get GNSS messages
            gnss = p.basemodule_set.filter(type=GNSS_MESSAGE)
            # select only valid fixes (with hacc > 0)
            gnss = gnss.filter(gnssmodule__hacc__gt=0).order_by('time')
            if hacc:
                # filter messages on maximum hacc
                gnss = gnss.filter(gnssmodule__hacc__lt=hacc)
            # use last valid gnss message
            g = gnss.last().gnssmodule

            if g.lon > 40*1e7 and g.lat < 10*1e7:
                # verwisseling lon/lat?
                t = g.lon
                g.lon = g.lat
                g.lat = t
            result.append({'id': p.id, 'name': p.devid, 'lon': g.lon*1e-7, 'lat': g.lat*1e-7, 'msl': g.msl*1e-3, 'hacc': g.hacc*1e-3, 'vacc': g.vacc*1e-3, 'time': g.time})
        except:
            pass
    return HttpResponse(json.dumps(result, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

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
    
class DeviceView(DetailView):
    """ Shows raw sensor data with Highcharts """

    model = Device

    def get_context_data(self, **kwargs):
        context = super(DeviceView, self).get_context_data(**kwargs)
        device = self.get_object()
        
        def getdata(module, entity, **kwargs):
            s = device.get_pandas(module,entity,**kwargs)
            if s.empty:
                return []
            s = s.resample(rule='20min').mean()
            return zip(s.index,s.values)
        
        adc1 = getdata(ECModule, 'adc1', position=1)
        adc2 = getdata(ECModule, 'adc1', position=2)
        waterpressure = getdata(PressureModule, 'adc')
        bat = getdata(MasterModule, 'battery')
        airpressure = getdata(MasterModule, 'air')
        
        options1 = {
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      },
            'title': {'text': device.devid},
            'xAxis': {'type': 'datetime'},
            'legend': {'enabled': True},
            'plotOptions': {'line': {'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'ADC'},},
                      {'title': {'text': 'Pressure'},'opposite': 1},
                      ],
            'series': [{'name': 'EC1', 'yAxis': 0, 'data': list(adc1)},
                        {'name': 'EC2', 'yAxis': 0, 'data': list(adc2)},
                        {'name': 'Pressure', 'yAxis': 1, 'data': list(waterpressure)},
                        ]
                   }

        options2 = options1.copy()
        options2.update({
            'yAxis': [{'title': {'text': 'mV'}},
                      {'title': {'text': 'Pressure'},'opposite': 1}],
            'series': [{'name': 'Battery', 'yAxis': 0, 'data': list(bat)},
                       {'name': 'Pressure', 'yAxis': 1, 'data': list(airpressure)}]
            })
        context['options1'] = json.dumps(options1,default=lambda x: time.mktime(x.timetuple())*1000.0)
        context['options2'] = json.dumps(options2,default=lambda x: time.mktime(x.timetuple())*1000.0)
        context['theme'] = 'None' #ser.theme()
        return context

class PeilView(DetailView):
    """ Shows calibrated values """
    model = Device
    template_name = 'peil/chart.html'

    def get_context_data(self, **kwargs):
        context = super(PeilView, self).get_context_data(**kwargs)
        device = self.get_object()
        
        df = device.calc('H')

        def getdata(name,scale=1):
            s = df[name] * scale
            return zip(s.index,s.values)
        
        ec1 = getdata('ec1',0.001)        
        ec2 = getdata('ec2',0.001)        
        h = getdata('cmwater')
        
        options1 = {
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      },
            'title': {'text': device.devid},
            'xAxis': {'type': 'datetime'},
            'legend': {'enabled': True},
            'tooltip': {'valueDecimals': 2},
            'plotOptions': {'line': {'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'EC (mS/cm)'},},
                      {'title': {'text': 'Hoogte (cm)'},'opposite': 1},
                      ],
            'series': [{'name': 'EC1', 'yAxis': 0, 'data': list(ec1), 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'EC2 ', 'yAxis': 0, 'data': list(ec2), 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'Waterhoogte', 'yAxis': 1, 'data': list(h), 'tooltip': {'valueSuffix': ' cm'}},
                        ]
                   }

        context['options1'] = json.dumps(options1,default=lambda x: time.mktime(x.timetuple())*1000.0)
        context['theme'] = 'None' #ser.theme()
        return context
    