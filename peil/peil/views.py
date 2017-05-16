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

import json, time
from peil.models import ECModule, PressureModule, MasterModule, Device
from peil.util import handle_post_data
from django.views.generic.base import TemplateView

@csrf_exempt
def ttn(request):
    """ push data from TTN server and update database """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            handle_post_data(data)
            return HttpResponse(status_code=200) 
        except:
            return HttpResponseServerError()
    return HttpResponseBadRequest()

class MapView(ListView):
    model = Device
    template_name = 'peil/device_map.html'

    def get_context_data(self, **kwargs):
        context = super(MapView, self).get_context_data(**kwargs)
        context['api_key'] = settings.GOOGLE_MAPS_API_KEY
        context['maptype'] = "ROADMAP"
        return context
    
class DeviceListView(ListView):
    model = Device
    
class DeviceView(DetailView):
    """ Shows raw sensor data in Highcharts """

    model = Device

    def get_context_data(self, **kwargs):
        context = super(DeviceView, self).get_context_data(**kwargs)
        device = self.get_object()
        
        def getdata(module, entity, **kwargs):
            s = device.get_pandas(module,entity,**kwargs).resample(rule='20min').mean()
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
    