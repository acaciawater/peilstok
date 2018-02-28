'''
Created on Dec 10, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.sensor import load_survey

class Command(BaseCommand):
    args = ''
    help = 'Import survey'
    
    def add_arguments(self, parser):
        parser.add_argument('files', nargs='+', type=str, help='import_survey csvfile')

    def handle(self, *args, **options):
        files = options.get('files')
        for fname in files:
            print 'Importing '+fname
            load_survey(fname)
