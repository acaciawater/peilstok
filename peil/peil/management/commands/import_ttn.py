'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
import json
from peil.util import parse_ttn
from docutils.nodes import line

class Command(BaseCommand):
    args = ''
    help = 'Import ttn file'
    
    def add_arguments(self, parser):
        parser.add_argument('-f','--file',
                action='store',
                dest='fname',
                help='ttn filename')
    def handle(self, *args, **options):
        fname = options.get('fname')
        row = 0
        print fname
        with open(fname) as f:
            for line in f:
                row += 1
                try:
                    parse_ttn(json.loads(line))
                except Exception as e:
                    print line
                    print e