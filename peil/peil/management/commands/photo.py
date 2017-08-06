'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
import os, re, shutil
from peil.models import Device

class Command(BaseCommand):
    args = ''
    help = 'Import photos'
    
    def add_arguments(self, parser):
        parser.add_argument('dirs', nargs='+', type=str, help='photo dirs')

    def handle(self, *args, **options):
        upload = os.path.join(settings.MEDIA_ROOT,'photos')
        if not os.path.exists(upload):
            os.makedirs(upload)
        dirs = options.get('dirs')
        for folder in dirs:
            for path, _dirs, files in os.walk(folder):
                for fname in files:
                    match = re.match('OWMP(\d+)#(\d+)',fname)
                    if match:
                        print fname
                        num = match.group(1)
                        seq = match.group(2)
                        try:
                            device = Device.objects.get(displayname__iexact = 'Peilstok'+num)
                        except Device.DoesNotExist:
                            continue
                        source = os.path.join(path,fname)
                        dest = os.path.join(upload,fname)
                        shutil.copy(source, dest)
                        device.photo_set.update_or_create(photo='photos/'+fname,defaults={'order':int(seq)})
