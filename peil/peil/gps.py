'''
Created on Apr 25, 2017
Functions and utilities to test GPS stuff, final versions in peil.util
@author: theo
'''
import struct
import datetime, pytz
from csv import DictReader
from django.conf import settings
from datetime import timedelta

# GPS time=0
GPST0 = datetime.datetime(1980,1,6,0,0,0)

def gps2time(week,ms):
    ''' convert gps tow and week to python datetime '''
    if ms < -1e9 or ms > 1e9: ms = 0
    delta1 = datetime.timedelta(weeks=week)
    delta2 = datetime.timedelta(seconds=ms/1000.0)
    return GPST0 + delta1 + delta2

def time2gps(time):
    ''' convert python datetime to gps week and tow '''
    delta = time - GPST0
    sec = delta.total_seconds()
    week = int(sec/(86400*7))
    tow = sec - week * 86400*7 + delta.seconds # time of week
    dow = int(tow / 86400)-1 # day of week
    return week, dow, tow

def checksum(bufr):
    ''' return 2 checksum bytes '''
    cka = 0
    ckb = 0
    for c in bufr:
        cka = (cka + ord(c)) & 255
        ckb = (ckb + cka) & 255
    return (cka, ckb)

def ubxpack(cid, data):
    ''' pack data as ublox UBX message width class and id '''
    a = bytes(UBX_HEADER)
    b = bytes(cid)
    c = struct.pack('<H',len(data)) # little endian unsigned short
    package = a+b+c+data
    a,b = checksum(package[2:])
    return package+chr(a)+chr(b)
    
def ubx_raw(data):
    rcvTow, week, numSV, reserved1 = struct.unpack('<IHBB',data[:8])
    raw_data = data[8:] # 24 * numSV
    return rcvTow, week, numSV, bytes(raw_data)

def ubx_sfrb(data):
    return struct.unpack('<BB10f',data)

def ubx_nav_posllh(data):
    iTOW, lon, lat, height, hMSL, hAcc, vAcc = struct.unpack('<IiiiiII', data)
    return iTOW, lon, lat, height, hMSL, hAcc, vAcc

def ubx_nav_pvt(data):
    iTOW, year, month, day, hour, min, sec, valid, tAcc, nano, fixType, flags, reserved1, \
        numSV, lon, lat, height, hMSL, hAcc, vAcc, velN, velE, velD, gSpeed, heading, sAcc, \
        headingAcc, pDOP, reserved2, reserved3 = struct.unpack('<IHBBBBBbIiBbBBiiiiIIiiiiiIIHHI', data)
    dt = datetime.datetime(year, month, day, hour, min, sec, tzinfo = pytz.utc)
    return iTOW, str(dt), fixType, numSV, lon, lat, height, hMSL, hAcc, vAcc

UBX_HEADER = 0x62B5
UBX_RXM_RAW = 0x1002
UBX_RXM_SFRB = 0x1102
UBX_NAV_POSLLH = 0x0102
UBX_NAV_PVT = 0x0701

def readubx(ubxfile):
    with open(ubxfile,'rb') as ubx:
        while True:
            data=ubx.read(6)
            if len(data) != 6:
                break
            hdr, msgid, length = struct.unpack('<HHH',data)
            print hex(msgid), 
            if hdr != UBX_HEADER:
                raise ValueError('UBX header tag expected')
            data = ubx.read(length)
            checksum = ubx.read(2)
            if msgid == UBX_RXM_RAW:
                print 'UBX-RXM-RAW', ubx_raw(data)
            elif msgid == UBX_RXM_SFRB:
                print 'UBX-RXM-SFRB', ubx_sfrb(data)
            elif msgid == UBX_NAV_POSLLH:
                print 'UBX-NAV-POSLLH', ubx_nav_posllh(data)
            elif msgid == UBX_NAV_PVT:
                print 'UBX-NAV-PVT', ubx_nav_pvt(data)
            else:
                raise ValueError('Message not supported: %x' % msgid)

def readpos(posfile):
    """ read rnx2rtkp solution file """ 
    with open(posfile) as fpos:
        names = None
        for line in fpos:
            if line.startswith('%  GPST'):
                names = [h.strip() for h in line.split(',')]
                break
        if not names:
            return {}
        reader = DictReader(fpos,fieldnames=names)
        minsdu = 1e10
        best = {}
        for row in reader:
            #%  GPST                , latitude(deg),longitude(deg), height(m),  Q, ns,  sdn(m),  sde(m),  sdu(m), sdne(m), sdeu(m), sdun(m),age(s), ratio
            sdu = float(row['sdu(m)'])
            if sdu < minsdu:
                best = row
                minsdu = sdu                 
#         lat = float(best['latitude(deg)'])
#         lon = float(best['longitude(deg)'])
#         alt = float(best['height(m)'])
#         q = int(best['Q'])
#         ns = int(best['ns'])
#         sdn = float(best['sdn(m)'])
#         sde = float(best['sde(m)'])
#         sdu = float(best['sdu(m)'])
        return best
    
class TransNAP:
    ''' transform 3D coordinates from WGS84 to RDNAP '''
  
    def __init__(self):
        import osr

        wgs = osr.SpatialReference()
        #wgs.ImportFromProj4('+init=epsg:4326')
        #wgs.ImportFromEPSG(4979)
        wgs.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        rd = osr.SpatialReference()
        rd.ImportFromProj4('+init=rdnap:rdnap')
        self.fwd = osr.CoordinateTransformation(wgs,rd)
        self.inv = osr.CoordinateTransformation(rd,wgs)
    
    def to_rdnap(self,x,y,z):
        return self.fwd.TransformPoint(x,y,z)

    def to_wgs84(self,x,y,z):
        return self.inv.TransformPoint(x,y,z)

def showpos(posfile):
    """ read rnx2rtkp solution file and show rdnap 3D-coordinates """ 
    with open(posfile) as fpos:
        names = None
        for line in fpos:
            if line.startswith('%  GPST'):
                line = line[1:]
                names = [h.strip() for h in line.split(',')]
                break
        if not names:
            return {}
        reader = DictReader(fpos,fieldnames=names)
        minsdu = 1e10
        best = {}
        trans = TransNAP()
        for row in reader:
            #%  GPST                , latitude(deg),longitude(deg), height(m),  Q, ns,  sdn(m),  sde(m),  sdu(m), sdne(m), sdeu(m), sdun(m),age(s), ratio
            sdu = float(row['sdu(m)'])
            if sdu < minsdu:
                best = row
                minsdu = sdu
            time = row['GPST']
            lat = float(row['latitude(deg)'])
            lon = float(row['longitude(deg)'])
            alt = float(row['height(m)'])
            q = int(row['Q'])
            ns = int(row['ns'])
            sdn = float(row['sdn(m)'])
            sde = float(row['sde(m)'])
            sdu = float(row['sdu(m)'])
            nap = trans.to_rdnap(lon,lat,alt)
            print time,lat,lon,alt,q,ns,sdn,sde,sdu,nap 
                             
        return best
"""
RINEX filename:
ssssdddf.yyt

   |   |  | | |
   |   |  | | +--  t:  file type:
   |   |  | |          O: Observation file
   |   |  | |          N: GPS Navigation file
   |   |  | |          M: Meteorological data file
   |   |  | |          G: GLONASS Navigation file
   |   |  | |          L: Future Galileo Navigation file
   |   |  | |          H: Geostationary GPS payload nav mess file
   |   |  | |          B: Geo SBAS broadcast data file
   |   |  | |                        (separate documentation)
   |   |  | |          C: Clock file (separate documentation)
   |   |  | |          S: Summary file (used e.g., by IGS, not a standard!)
   |   |  | |
   |   |  | +---  yy:  two-digit year
   |   |  |
   |   |  +-----   f:  file sequence number/character within day
   |   |               daily file: f = 0
   |   |               hourly files:
   |   |               f = a:  1st hour 00h-01h; f = b: 2nd hour 01h-02h; ...
   |   |               f = x: 24th hour 23h-24h
   |   |
   |   +-------  ddd:  day of the year of first record
   |
   +----------- ssss:  4-character station name designator
"""
RINEX_FILE_TYPES = (
    ('o', 'Observation'),
    ('d', 'Observation Hatanaka compressed'),
    ('n', 'GPS Navigation'),
    ('m', 'Meteorological'),
    ('g', 'GLONASS Navigation'),
    ('l', 'Galileo Navigation'),
    ('h', 'Geostationary GPS'),
    ('b', 'SBAS broadcast'),
    ('c', 'Clock'),
    ('s', 'Summary')
)

def download(url,dest):
    import os,ftplib
    from urlparse import urlparse
    res = urlparse(url)
    ftp = ftplib.FTP(res.hostname)
    ftp.login()
    destdir = os.path.dirname(dest)
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    try:
        with open(dest,"wb") as f:
            def save(data):
                f.write(data)
            response = ftp.retrbinary("RETR "+res.path, callback=save, blocksize=1024)
            return True
    except:
        os.remove(dest)
        return False

def getfile(local,path,remote):
    """ get local file local/path. Download from remote if file does not exist """ 
    local_file = os.path.join(local,path)
    if not os.path.exists(local_file):
        local_dir = os.path.dirname(local_file)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        if not download(remote + path, local_file):
            return None
    return local_file

def rinex_filename(station,date,filetype):
    """ return hourly rinex filenames at gnss1.tudelft.nl for specified station and time """
    ssss = station[:4].lower()
    ddd = '%03d' % date.timetuple().tm_yday
    f = 'a' + date.hour
    yy = date.year - 2000
    t = filetype.lower()
    return ssss+ddd+f+yy+t+'.Z'

def get_rinex_files(station, time, types='odnhbc'):
    url = 'gnss.tudelft.nl/rinex/'
    station = station[:4].lower()
    year = time.year
    day = time.timetuple().tm_yday
    yy = year - 2000
    hour = 'a' + time.hour
    files = []
    for _type in types:
        path = '{year}/{doy:03}/{station}{day:03}{yy:02}{type}.Z'.format(year=year,day=day,yy=yy,station=station,type=_type)
        local_file = getfile(settings.MEDIA_ROOT, path, url)
        if local_file is None:
            continue
        file.append(local_file)
        break
    return files

IGS_SATCODES = (
    ('G', 'GPS'),
    ('R', 'GLONASS'),
    ('E', 'Galileo'),
    ('C', 'Beidou'),
    ('M', 'Mixed'),
)
    
def get_broadcast_files(time, satcodes='G'):
    """ Gets broadcast files for given time. Possible satellite codes are:
        G GPS
        R GLONASS
        E Galileo
        C Beidou
        M Mixed
    """
    url = 'ftp://igs.bkg.bund.de/IGS/'
    year = time.year
    doy = time.timetuple().tm_yday
    files = []
    for sat in satcodes:
        path = 'BRDC/{year}/{doy:03}/BRDC00WRD_R_{year}{doy:03}0000_01D_{sat}N.rnx.gz'.format(year=year,doy=doy,sat=sat)
        local_file = getfile(settings.GNSS_ROOT,path,url)
        if local_file is None:
            continue
        files.append(local_file)
    return files

IGS_PRODUCTS = (
    ('u', 'ultra'), #3-9 hrs
    ('r', 'rapid'), #17-41 hrs
    ('s', 'final')  #12-18 days
)

IGS_FILE_TYPES = (
    ('clk', 'clock'),
    ('sp3', 'ephemeris'),
    ('erp', 'orbits')
)

def get_igs_files(time, types = ['clk','sp3','erp'], products='sru'):
    """ get pathnames of local igs files for postprocessing and try to download if they do not exist """
    week, dow, _tow = time2gps(time)

    delta = datetime.datetime.utcnow() - time
    secs = delta.total_seconds()
    if secs < (3*60*60):
        # ultra not available
        products = products.replace('u','')
    if secs < (17*60*60):
        # rapid not available
        products = products.replace('r','')
    if delta.days < 12:
        # final not available
        products = products.replace('s','')
    
    files = []
    url = 'ftp://ftp.igs.org/pub/product/'
    for _type in types:
        for product in products:
            if product == 'u':
                hour = (time.hour // 6) * 6 # 0, 6, 12, 18
                path = '{week}/ig{product}{week}{dow}_{hour:02}.{type}.Z'.format(week=week,dow=dow,hour=hour,product=product,type=_type)
            else:
                path = '{week}/ig{product}{week}{dow}.{type}.Z'.format(week=week,dow=dow,product=product,type=_type)
            local_file = getfile(settings.GNSS_ROOT,path,url)
            if not local_file:
                continue
            files.append(local_file)
            break
    return files

if __name__ == '__main__':
    import os
    time = datetime.datetime.utcnow()
    yesterday = time - timedelta(days=1)
    print get_broadcast_files(yesterday, 'GRECM')
    time = datetime.datetime(2017,8,31,17,40,44)
    print get_igs_files(time)
    yesterday = time - timedelta(days=1)
    print get_igs_files(yesterday)
    
    pos = '/media/sf_C_DRIVE/Users/theo/Documents/projdirs/GNSS/peilstok/ubx/gps/0000DA2DC61F7064-0003.pos'
    best = showpos(pos)
    if best:
        print best
                    
# if __name__ == '__main__':
#     import os
#     pos = '/home/theo/git/peil/peil/media/ubx/0000FAB6A3EE43F8-0002.pos'
#     posdir = '/home/theo/git/peil/peil/media/ubx'
#     for path,dirs,files in os.walk(posdir):
#         for pos in files:
#             if pos.endswith('.pos'):
#                 best = readpos(os.path.join(path,pos))
#                 if best:
#                     print pos, best
    
# if __name__ == '__main__':
#     from ftplib import FTP_TLS as FTP
#     pem = '/home/theo/peilstok/acacia.pem'
#     ftp = FTP('130.206.127.42',user='ubuntu',keyfile=pem)
#     ftp.login('ubuntu')
    
# if __name__ == '__main__':
#     t = TransNAP()
#     y = 53.3374355750
#     x = 7.0274954167
#     z = 56.9441
#     print t.to_rdnap(x, y, z)
#     print (264259.0348,595802.0442,16.4567)
#     y = 52.0213500    
#     x = 4.7104886
#     z = 45.349
#     print 'gouda', t.to_rdnap(x, y, z)

# if __name__ == '__main__':
#     print time2gps(datetime.datetime(2017,6,10))
#     print time2gps(datetime.datetime(2017,6,10,12))
#     print time2gps(datetime.datetime(2017,6,11,12))
#     print time2gps(datetime.datetime(2017,6,12,12))
#     print time2gps(datetime.datetime(2017,6,13,12))
#     print time2gps(datetime.datetime(2017,6,14,12))
#     print time2gps(datetime.datetime(2017,6,15,12))
#     print time2gps(datetime.datetime.now())
#     #readubx('/home/theo/peilstok/ubx/0000C9F4BBB8131B-0002.ubx')
#     #readubx('/home/theo/peilstok/ubx/0000E13748EBA25A-0001.ubx')
#     