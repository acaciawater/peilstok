'''
Created on Apr 25, 2017

@author: theo
'''
from django.http.response import HttpResponse, HttpResponseBadRequest,\
    HttpResponseServerError, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.decorators.gzip import gzip_page
from django.conf import settings

import re, time
import simplejson as json # allows for NaN conversion
import numpy as np
from peil.models import Device, UBXFile, RTKSolution, Photo
from peil import util

import logging
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.text import slugify
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from acacia.data.models import Series
import datetime

logger = logging.getLogger(__name__)

class StaffRequiredMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(
                request,
                'Je het niet de vereiste rechten om de gevraagde bewerking uit te voeren.')
            return redirect(settings.LOGIN_URL)
        return super(StaffRequiredMixin, self).dispatch(request, *args, **kwargs)
        
def json_locations(request):
    """ return json response with last known peilstok locations
        optionally filter messages on hacc (in mm)
    """
    result = []
    hacc = request.GET.get('hacc',10000)
    for p in Device.objects.all():
        try:
            loc = p.current_location(hacc)
            if loc:
                result.append(loc)
        except Exception as e:
            print e
            pass
    return HttpResponse(json.dumps(result, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

@staff_member_required
def select_photo(request, pk):
    ''' select a photo to display on the leaflet popup window '''
    photo = get_object_or_404(Photo, pk=pk)
    photo.set_as_popup()
    back = request.GET.get('next',None) or request.META.get('HTTP_REFERER','/')
    return redirect(back)

class PopupView(DetailView):
    """ returns html response for leaflet popup """
    model = Device
    template_name = 'peil/popup_new.html'
    
    def get_context_data(self, **kwargs):
        context = DetailView.get_context_data(self, **kwargs)
        device = self.get_object()
        ec = util.last_ec(device)
        wl = util.last_waterlevel(device)
        for pos in ('EC1','EC2'):
            depth = wl['nap'] - ec[pos]['sensor'].elevation()
            ec[pos]['depth'] = depth * 100
            ec[pos]['dry'] = depth <= 0
        context['lastec'] = ec
        context['lastwl'] = wl
        try:
            context['battery'] = device.battery_status()
        except:
            pass
        return context

@csrf_exempt
def kpn(request):
    """ handle post data from KPN server and update database """
    if request.method == 'POST':
        try:
            logger.debug('KPN Post received')
            data = request.body
            return util.handle_kpn_post_data(data)
        except:
            logger.exception('Cannot parse POST data')
            return HttpResponseServerError(reason='Error parsing POST data')
    return HttpResponseBadRequest()
    
@csrf_exempt
def ttn(request):
    """ handle post data from TTN server and update database """
    if request.method == 'POST':
        try:
            logger.debug('TTN Post received')
            data = json.loads(request.body)
            return util.handle_post_data(data)
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
        nxt = Device.objects.filter(displayname__gt=device.displayname)
        nxt = nxt.first() if nxt else None
        prv = Device.objects.filter(displayname__lt=device.displayname)
        prv = prv.last() if prv else None
        return {'next': nxt, 'prev': prv}

class NavDetailView(NavMixin, DetailView):
    """ Detailview with browsing through devices sorted by name """

    def get_context_data(self, **kwargs):
        context = super(NavDetailView, self).get_context_data(**kwargs)
        device = self.get_object()
        context['nav'] = self.nav(device)
        return context
    
class DeviceListView(ListView):
    model = Device

class DeviceDetailView(StaffRequiredMixin,NavDetailView):
    model = Device

    def get_context_data(self, **kwargs):
        context = super(DeviceDetailView, self).get_context_data(**kwargs)
        device = self.get_object()
        try:
            context['battery'] = device.battery_status()
        except:
            pass
        try:
            context['level'] = util.last_waterlevel(device)
        except:
            pass
        return context
    
@gzip_page
def chart_as_json(request,pk):
    """ get chart data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    pts = util.get_chart_series(device)
    data = {'EC1': zip(pts.index,pts['EC1']),        
            'EC2': zip(pts.index,pts['EC2']),
            'NAP': zip(pts.index,pts['Waterpeil']),
            'H': zip(pts.index,pts['Waterhoogte']),
            }
    try:
        tide = Series.objects.get(name='Getij')
        start = pts.index[0]
        stop = pts.index[-1]
        getij = tide.to_array(start=start,stop=stop)
        data['Getij'] = getij
    except Exception as e:
        pass
    return HttpResponse(json.dumps(data, ignore_nan = True, default=lambda x: time.mktime(x.timetuple())*1000.0), content_type='application/json')

@gzip_page
def chart_as_csv(request,pk):
    """ get chart data as csv for download """
    device = get_object_or_404(Device, pk=pk)
    data = util.get_chart_series(device)
    data.dropna(inplace=True,how='all')
    resp = HttpResponse(data.to_csv(float_format='%.2f'), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename=%s.csv' % slugify(unicode(device))
    return resp

@gzip_page
def to_csv(request):
    """ get data as csv for wirecloud """
    query = {str(k):str(v) for k,v in request.GET.items()}
    try:
        device = Device.objects.get(**query)
    except Exception as ex:
        return HttpResponseNotFound(str(ex))
    
    data = util.get_chart_series(device)
    data.dropna(inplace=True,how='all')
    
    # fill empty cells, first forward, then backwards
    data = data.fillna(method='ffill').fillna(method='bfill').sort_index(ascending=False)
    # add timestamp column in msec after 1/1/1970 (for highcharts)
    data['Timestamp']= data.index.astype(np.int64) // 10 ** 6
    resp = HttpResponse(data.to_csv(float_format='%.2f'), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename=%s.csv' % slugify(unicode(device))
    return resp
    
@gzip_page
def data_as_json(request,pk):
    """ get raw sensor data as json array for highcharts """
    device = get_object_or_404(Device, pk=pk)
    pts = util.get_raw_data(device)
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
    data = util.get_raw_data(device)
    data.dropna(inplace=True,how='all')
    resp = HttpResponse(data.to_csv(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename=%s.csv' % slugify(unicode(device))
    return resp

class PhotoView(StaffRequiredMixin, NavDetailView):
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
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      'marginLeft': 60, 
                      'marginRight': 80,
                      'spacingTop': 20,
                      'spacingBottom': 20
                      },
            'title': {'text': unicode(device)},
            'xAxis': {'type': 'datetime',
                      'crosshair': True,
                      'events': {'setExtremes': None},
                      },
            'legend': {'enabled': True},
            'tooltip': {'shared': True, 'xDateFormat': '%a %d %B %Y %H:%M:%S', 'valueDecimals': 2},
            'plotOptions': {'line': {'connectNulls': True, 'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'EC (mS/cm)'},},
                      {'title': {'text': 'Peil (m NAP)'},'opposite': 1},
#                      {'title': {'text': 'Hoogte (cm)'},'opposite': 1},
                      ],
            'series': [
                        {'name': 'EC ondiep', 'id': 'EC1', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'EC diep ', 'id': 'EC2', 'yAxis': 0, 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'Waterpeil', 'id': 'NAP', 'yAxis': 1, 'data': [], 'tooltip': {'valueSuffix': ' m NAP'}},
#                        {'name': 'Waterhoogte', 'id': 'H', 'yAxis': 2, 'data': [], 'tooltip': {'valueSuffix': ' cm'}},
                        {'name': 'Getij', 'id': 'Getij', 'yAxis': 1, 'data': [], 'tooltip': {'valueSuffix': ' m NAP'}, 'zIndex': -1},
                        ]
                   }

        context['options1'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)

        options.update({
            'title': {'text': 'Ruwe sensor waardes'},
            'plotOptions': {'spline': {'connectNulls': False, 'marker': {'enabled': False, 'radius': 3}}},            
            'tooltip': {'shared': True, 'valueDecimals': 0, 'xDateFormat': '%a %d %B %Y %H:%M:%S'},
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
    
class PeilView2(LoginRequiredMixin, NavDetailView):
    """ Shows calibrated  sensor values """
    model = Device
    template_name = 'peil/chart2.html'

    def get_context_data(self, **kwargs):
        context = super(PeilView2, self).get_context_data(**kwargs)
        device = self.get_object()
                
        options = {
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      'marginLeft': 60, 
                      'marginRight': 80,
                      'spacingTop': 20,
                      'spacingBottom': 20
                      },
            'title': {'text': 'Geleidbaarheid '+unicode(device)},
            'xAxis': {'type': 'datetime',
                      'crosshair': True,
                      'events': {'setExtremes': None},
                      },
            'legend': {'enabled': True},
            'tooltip': {'shared': True, 'xDateFormat': '%a %d %B %Y %H:%M:%S', 'valueDecimals': 2},
            'plotOptions': {'line': {'connectNulls': True, 'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'EC (mS/cm)'}}],
            'series': [
                        {'name': 'EC ondiep', 'id': 'EC1', 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        {'name': 'EC diep ', 'id': 'EC2', 'data': [], 'tooltip': {'valueSuffix': ' mS/cm'}},
                        ]
                   }

        context['options1'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)

        ec1 = device.get_sensor('EC1',position=1).elevation()
        ec2 = device.get_sensor('EC2',position=2).elevation()
        
        options.update({
            'title': {'text': 'Waterstand '+unicode(device)},
            'yAxis': [
                {'title': {'text': 'Peil (m NAP)'},
                'plotLines': [
                    {
                     'value': ec1,
                     'zIndex': 998,
                     'color': 'green',
                     'dashStyle': 'shortdash',
                     'width': 1,
                     'label': {
                         'text': 'ondiepe EC sensor',
                         'style': {'color': 'green'}
                     }
                    },
                    {
                     'value': ec2,
                     'zIndex': 999,
                     'color': 'red',
                     'dashStyle': 'shortdash',
                     'width': 1,
                     'label': {
                         'text': 'diepe EC sensor',
                         'style': {'color': 'red'}
                     }
                    }]},
                                            
            ],
            'series': [
                        {'name': 'Waterpeil', 'id': 'NAP', 'data': [], 'tooltip': {'valueSuffix': ' m NAP'}},
                        {'name': 'Getij', 'id': 'Getij', 'visible': False, 'data': [], 'lineWidth': 1, 'tooltip': {'valueSuffix': ' m NAP'}, 'zIndex': -1},
                        {'name': 'ec1', 'showInLegend': False, 'type': 'scatter', 'marker': {'enabled': False}, 'data': [(datetime.datetime.now(),ec1)]},
                        {'name': 'ec2', 'showInLegend': False, 'type': 'scatter', 'marker': {'enabled': False}, 'data': [(datetime.datetime.now(),ec2)]}
                        ]
                   })
        context['options2'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)
        return context

class PostView(StaffRequiredMixin,NavDetailView):
    model = Device
    template_name = 'peil/post.html'

    def get_context_data(self, **kwargs):
        context = super(PostView, self).get_context_data(**kwargs)
        device = self.get_object()
        q = RTKSolution.objects.filter(ubx__device=device).order_by('time')
        data = list(q.values_list('time','z'))
        options = {
            'chart': {'type': 'line', 
                      'animation': False, 
                      'zoomType': 'x',
                      'events': {'load': None},
                      'marginLeft': 80, 
                      'marginRight': 80,
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
            'plotOptions': {'line': {'connectNulls': True, 'marker': {'enabled': False}}},            
            'credits': {'enabled': True, 
                        'text': 'acaciawater.com', 
                        'href': 'http://www.acaciawater.com',
                       },
            'yAxis': [{'title': {'text': 'm tov NAP'}}
                      ],
            'series': [{'name': 'Hoogte', 'id': 'NAP', 'yAxis': 0, 'data': data, 'tooltip': {'valueSuffix': ' m tov NAP'}},
                        ]
            }

        try:
            survey = device.last_survey()
            alt = float(survey.altitude)
            maxalt = alt + survey.vacc*1e-3
            minalt = alt - survey.vacc*1e-3
            #surveydata = [[data[0][0],minalt,maxalt],[data[-1][0],minalt,maxalt]]
            surveydata = [[data[0][0],alt],[data[-1][0],alt]]
            options['series'].append({'name': 'survey', 'id': 'survey', 'yAxis': 0, 'data': surveydata})
        except Exception as e:
            survey = None
            
        context['options'] = json.dumps(options,default=lambda x: time.mktime(x.timetuple())*1000.0)
        return context
    