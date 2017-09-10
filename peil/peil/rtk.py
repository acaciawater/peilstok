'''
Created on Sep 2, 2017

@author: theo
'''
import os
import logging
import shutil
from csv import DictReader
from peil.util import get_broadcast_files, get_ephemeres_files, rdnap
import datetime

logger = logging.getLogger(__name__)

def itersol(pos):
    """ iterate over rtk solution file """ 
    with open(pos) as fpos:
        names = None
        for line in fpos:
            if line.startswith('%  GPST'):
                line = line[2:]
                names = [h.strip() for h in line.split(',')]
                break
        if not names:
            yield {}
        reader = DictReader(fpos,fieldnames=names)
        for row in reader:
            gpst = row['GPST']
            lat = float(row['latitude(deg)'])
            lon = float(row['longitude(deg)'])
            alt = float(row['height(m)'])
            x,y,z = rdnap.to_rdnap(lon,lat,alt)
            yield {
                'time': datetime.datetime.strptime(gpst[:-4],'%Y/%m/%d %H:%M:%S'),
                'lat': lat,
                'lon': lon,
                'alt': alt,
                'q': int(row['Q']),
                'ns': int(row['ns']),
                'sdn': float(row['sdn(m)']),
                'sde': float(row['sde(m)']),
                'sdu': float(row['sdu(m)']),
                'x': x,
                'y': y,
                'z': z
            }

            
def post(ubx, **kwargs):
    """ post processing with RTKLIB """
    import subprocess32 as subprocess
    
    path = unicode(ubx.ubxfile.file)
    ubxdir = os.path.dirname(path)
    ubxfile = os.path.basename(path)
    
    os.chdir(ubxdir)

    logger.debug('Postprocessing started for {}, file={}'.format(unicode(ubx.device), ubxfile))

    # convert ubx file to rinex
    command = ['convbin', ubxfile]
    logger.debug('Running {}'.format(' '.join(command)))
    ret = subprocess.call(command)
    if ret:
        logger.error('convbin failed. Exit code = %d' % ret)
        return None
    
    name, ext = os.path.splitext(ubxfile)
    obs = name+'.obs'
    nav = name+'.nav'
    sbs = name+'.sbs'
    pos = name+'.pos'
    
    start = kwargs.get('start',ubx.start)
    # create temp dir for correction files
    tempdir = name+'.d'
    if not os.path.exists(tempdir):
        os.mkdir(tempdir)
    try:
        # copy broadcast, ephemeris and clock files to temp dir
        # TODO: could use os.symlink() here?
        for fname in get_broadcast_files(start):
            shutil.copy(fname, tempdir)
        for fname in get_ephemeres_files(start):
            shutil.copy(fname, tempdir)
            
        command = ['rnx2rtkp', '-t', '-s', ',', '-p', '7', '-c', '-o', pos, obs, nav, sbs, tempdir+'/*']
        logger.debug('Running {}'.format(' '.join(command)))
        ret = subprocess.call(command)
        if ret:
            logger.error('rnx2rtkp failed. Exit code = %d' % ret)
        else:
            logger.debug('Postprocessing completed')
            return pos
    finally:
        # remove temp dir with correction files
        shutil.rmtree(tempdir, ignore_errors=True)    
    return None
