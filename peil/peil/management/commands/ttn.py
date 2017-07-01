'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.dateparse import parse_datetime
import requests

import logging
from peil.models import Device, MESSAGES
from peil.util import parse_payload
logger = logging.getLogger(__name__)

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
    logger.debug('url={}'.format(url))
    #logger.debug('headers={}'.format(headers))
    logger.debug('params={}'.format(params))
    response = requests.get(url,params=params,headers=headers)
    return response

def parse_ttn(ttn):
    """ parse json from ttn server """
    try:
        devid = ttn['device_id']
        server_time = parse_datetime(ttn['time'])
        message_type = ttn['type']
        name = MESSAGES.get(message_type,str(message_type))
        logger.debug('{},{},{}'.format(devid, server_time, name))
    except Exception as e:
        logger.error('Error parsing response {}\n{}'.format(ttn,e))
        raise e

    device, created = Device.objects.update_or_create(devid=devid, defaults={'last_seen': server_time})

    if created:
        logger.debug('device {} created'.format(devid))
    
    parse_payload(device, server_time, ttn)

class Command(BaseCommand):
    help = 'Download from The Things Network'
    
    def add_arguments(self, parser):
        parser.add_argument('devid', 
                            type=str, 
                            help='device name or "all" for all devices')

        parser.add_argument('-s','--since',
                action='store',
                default = '1h',
                dest='since',
                help='Download since, where since is something like 1h, 6h or 1d')

    def handle(self, *args, **options):
        devid = options.get('devid')
        if devid == 'all':
            devices = [d.devid for d in Device.objects.all()]
        else:
            devices = [devid]
        since = options.get('since','1h')
        for dev in devices:
            print dev
            response = download_ttn(dev, since)
            if not response.ok:
                logger.error('TTN server responds with code={}: {}'.format(response.status_code, response.reason))
                continue
            logger.debug('received {} bytes'.format(len(response.content)))
            try:
                ttns = response.json()
            except Exception as e:
                logger.error('Error parsing response\n{}'.format(response.text))
                continue
            row = 0
            for ttn in ttns:
                row += 1
                try:
                    parse_ttn(ttn)
                except Exception as e:
                    print row, e
                    continue
