'''
Created on Apr 26, 2017

@author: theo
'''
from django.core.management.base import BaseCommand
from peil.util import add_ubx
import os

class Command(BaseCommand):
    args = ''
    help = 'Import ubx file'
    
    def add_arguments(self, parser):
        parser.add_argument('-f','--file',
                action='store',
                dest='fname')
        parser.add_argument('-d','--dir',
                action='store',
                dest='dname')

    def handle(self, *args, **options):
        fname = options.get('fname')
        if fname:
            print 'importing file', fname
            with open(fname) as f:
                add_ubx(f)
                
        dname = options.get('dname')
        if dname:
            print 'importing folder',dname
            for path,_dirs,files in os.walk(dname):
                for fname in files:
                    print 'importing file', fname
                    with open(os.path.join(path,fname)) as f:
                        add_ubx(f)
        
