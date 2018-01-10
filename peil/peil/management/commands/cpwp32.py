'''
Created on Aug 05, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.models import Device

class Command(BaseCommand):
    args = ''
    help = 'Copy properties from wp sensor position 3 to wp sensor position 2'
    
    def add_arguments(self, parser):
        parser.add_argument('-d','--device',
            action='store',
            dest='name',
            help='device displayname')
        
    def handle(self, *args, **options):
        query = Device.objects.all()
        name = options['name']
        if name:
            query = query.filter(displayname__iexact=name)
        for dev in query:
            print dev
            try:
                w2 = dev.get_sensor('Waterdruk',position=2)
                w3 = dev.get_sensor('Waterdruk',position=3)
                w2.offset = w3.offset
                w2.scale = w3.scale
                w2.distance = w3.distance
                w2.unit = w3.unit
                w2.save()
            except Exception as e:
                print e