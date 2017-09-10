from django.conf import settings
from django.contrib import messages

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
    url = 'https://integrations.thethingsnetwork.org/ttn-eu/api/v2/down/peilstok/fiware?key={}'.format(settings.TTN_KEY)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    for d in queryset:
        data = {"dev_id": d.devid, "port": 1, "confirmed": False, "payload_fields": { "gpsON": True } }
        response = requests.post(url,json=data,headers=headers)
        print response, response.reason
gpson.short_description='GPS aanzetten'