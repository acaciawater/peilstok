'''
Created on Apr 25, 2017

@author: theo
'''
import struct
import datetime, pytz

def gps2time(week,ms):
    ''' convert gps tow and week to python datetime '''
    gpst0 = datetime.datetime(1980,1,6,0,0,0)
    if ms < -1e9 or ms > 1e9: ms = 0
    delta1 = datetime.timedelta(weeks=week)
    delta2 = datetime.timedelta(seconds=ms/1000.0)
    return gpst0 + delta1 + delta2

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

                
if __name__ == '__main__':
    #readubx('/home/theo/peilstok/ubx/0000C9F4BBB8131B-0002.ubx')
    readubx('/home/theo/peilstok/ubx/0000E13748EBA25A-0001.ubx')