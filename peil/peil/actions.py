from django.conf import settings
from django.contrib import messages
from acacia.data.models import ProjectLocatie, ManualSeries
from django.contrib.gis.geos.point import Point
from acacia.data.util import WGS84

def create_manuals(modeladmin, request, queryset):
    ''' create meetlocaties and manual series for peilstokken '''
    ploc = ProjectLocatie.objects.first()
    numok =0
    numerror=0
    for device in queryset:
        try:
            loc = device.current_location()
            mloc, created = ploc.meetlocatie_set.get_or_create(name = device.displayname, defaults = {
                'description': 'devid={}, serial={}'. format(device.devid, device.serial),
                'location': Point(x=loc['lon'], y=loc['lat'],srid=WGS84), 
                })
            ec1,created = ManualSeries.objects.get_or_create(mlocatie=mloc,name='ECondiep', defaults = {
                'unit': 'mS/cm',
                'type': 'scatter',
                'timezone': 'Europe/Amsterdam',
                'user': request.user,
                })
            ec2,created = ManualSeries.objects.get_or_create(mlocatie=mloc,name='ECdiep', defaults = {
                'unit': 'mS/cm',
                'type': 'scatter',
                'timezone': 'Europe/Amsterdam',
                'user': request.user,
                })
            level,created = ManualSeries.objects.get_or_create(mlocatie=mloc,name='Waterstand', defaults = {
                'unit': 'm',
                'type': 'scatter',
                'timezone': 'Europe/Amsterdam',
                'user': request.user,
                })
            numok += 1
        except:
            numerror += 1
            pass
create_manuals.short_description='Handpeilingen aanmaken'

def update_statistics(modeladmin, request, queryset):
    for s in queryset:
        s.update()
update_statistics.short_description='Statistiek actualiseren'
        
def create_pvts(modeladmin, request, queryset):
    '''Create pvty messages from ubx file '''
    for u in queryset:
        u.create_pvts()
create_pvts.short_description='UBX-NAV-PVT messages aanmaken'

def calcseries(modeladmin, request, queryset):
    for d in queryset:
        df = d.calc()
        df = df.dropna(how='all')
        df.to_csv('/home/theo/peilstok/testdata.csv')
        
calcseries.short_description='Tijdreeksen  berekenen'

def to_orion(modeladmin, request, queryset):
    from peil.fiware import Orion
    orion = Orion(settings.ORION_URL)
    errors = 0
    created = 0
    for dev in queryset:
        response = orion.create_device(dev)
        if response.ok:
            created += 1
        else:
            messages.error(request,response.json())
            errors += 1
    if not errors:
        messages.success(request,'{} Orion entities created'.format(created))
to_orion.short_description = 'Orion entities aanmaken'
        
def rtkpost(modeladmin, request, queryset):
    ''' Run postprocessing for ubx files '''
    success = 0
    fail = 0
    for u in queryset:
        sol = u.post()
        if sol:
            success += 1
        else:
            fail += 1
    if success == 1:
        messages.success(request, '{} processed successfully'.format(u))
    elif success > 1:
        messages.success(request, '{} files processed successfully'.format(success))
    if fail == 1:
        messages.error(request, 'processing failed for {}'.format(u))
    elif fail > 1:
        messages.error(request, 'processing failed for {} files'.format(fail))
    
rtkpost.short_description='Postprocessing uitvoeren'

def postdevice(modeladmin, request, queryset):
    ''' Run postprocessing for devices using most recent ubxfile '''
    for d in queryset:
        ubx = d.ubxfile_set.latest('start')
        ubx.post()
postdevice.short_description='Postprocessing uitvoeren'

def gpson(modeladmin, request, queryset):
    """ turn GPS on for selected devices"""
    import requests
    #url = 'https://integrations.thethingsnetwork.org/ttn-eu/api/v2/down/peilstok/fiware?key={}'.format(settings.TTN_KEY)
    url = 'https://integrations.thethingsnetwork.org/ttn-eu/api/v2/down/peilstok_abp/fiware_acacia?key={}'.format(settings.TTN_KEY)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    for d in queryset:
        data = {"dev_id": d.devid, "port": 1, "confirmed": False, "payload_fields": { "gpsON": True } }
        response = requests.post(url,json=data,headers=headers)
        if response.ok:
            messages.success(request,'GPS of {} switched on successfully'.format(d.displayname))
        else:
            messages.error(request, 'Failed to switch on GPS of {}: {}'.format(d.displayname, response.reason))
gpson.short_description='GPS aanzetten'