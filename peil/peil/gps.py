'''
Created on Apr 25, 2017

@author: theo
'''
import struct
import datetime, pytz

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
    
if __name__ == '__main__':
    from ftplib import FTP_TLS as FTP
    pem = '/home/theo/peilstok/acacia.pem'
    ftp = FTP('130.206.127.42',user='ubuntu',keyfile=pem)
    ftp.login('ubuntu')
    
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