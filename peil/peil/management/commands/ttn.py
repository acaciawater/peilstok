'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
import json
from peil.models import MasterModule, ECModule, PressureModule, GNSSModule,\
    Device, BaseModule
from peil.models import GNSS_MESSAGE, STATUS_MESSAGE, EC_MESSAGE, PRESSURE_MESSAGE
from django.db.utils import IntegrityError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.conf import settings
import requests
from peil.util import parse_fiware

def download_ttn(devid,since):
    """ download data from The Things Network """
    url = settings.TTN_URL + 'query'
    if devid:
        url += '/' + devid
    if since:
        params = {'last': since }
    else:
        params = None
    headers = {'Authorization': 'key '+settings.TTN_KEY, 'Accept': 'application/json'}
    response = requests.get(url,params=params,headers=headers)
    return response
    
class Command(BaseCommand):
    help = 'Download from The Things Network'
    
    def add_arguments(self, parser):
        parser.add_argument('devid', type=str)

        parser.add_argument('-s','--since',
                action='store',
                default = '1h',
                dest='since',
                help='Download since')

    def handle(self, *args, **options):
        devid = options.get('devid')
        since = options.get('since','1h')
        device = Device.objects.get(devid=devid)
        last = device.last()
        print 'Last message at {:%Y-%m-%d %H:%M:%S}'.format(last.time)
        response = download_ttn(devid, since)
        if not response.ok:
            print response.reason
            return
        print 'received', len(response.content), 'bytes'
        ttns = response.json()
        row = 0
        for ttn in ttns:
            row += 1
            try:
                mod, created, updated = parse_fiware(ttn)
                print '{}, {}, {}'.format(mod.type, mod.time, 'Created' if created else 'Updated' if updated else '?')
            except Exception as e:
                print row, e
                continue
