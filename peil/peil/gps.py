'''
Created on Apr 25, 2017

@author: theo
'''
import json
import struct
import datetime

GPSFILE = '/home/theo/peilstok/gps.txt'
UBXFILE = '/home/theo/peilstok/gps.ubx'
UBX_RXM_RAW = b'\x02\x10'
UBX_RXM_SFRB = b'\x02\x11'
UBX_HEADER = b'\xB5\x62'

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
    
def testpack():
    package = ubxpack(UBX_RXM_RAW, 'ABCDEFG')
    print ' '.join('{:02X}'.format(ord(x)) for x in package)
    
def readgps(fname):
    mes = 0
    with open(fname,'rb') as gps:
        gps.read(764)
        while True:
            timestamp = gps.readline()
            if not timestamp: 
                break
            print timestamp[:-1]
            
            for i in range(32):
                # 32 messages per chunk?
                header = gps.read(2)
                if header != '42':
                    raise Exception('Format error')
        
                header = gps.read(8)
                rcvTow, week, numSV, reserved1 = struct.unpack('<IHBB',header)
                if numSV > 0:
                    mes += 1
                    print mes, gps2time(week, rcvTow), numSV
                    for j in range(numSV):
                        data = gps.read(24)
                        #cpMes, prMes, doMes, sv, mesQI, cno, lli = struct.unpack('<ddfBbbB',data)
                        #print cpMes, prMes, doMes, mesQI, cno, lli
                eoln = gps.read(2)
                if eoln != '\r\n':
                    raise Exception('Format error')

def readgps2(fname,ubxfile):
    total = 0
    batch = 0
    with open(fname,'rb') as gps:
        with open(ubxfile,'wb') as ubx:
            gps.seek(598793)
            while True:
                timestamp = gps.readline()
                if not timestamp: 
                    break
                serial = gps.readline()
                if not serial: 
                    break
                print serial[:-2], timestamp[:-2]
                
                batch += 1
                for i in range(32):
                    total += 1
                    header = gps.read(2)
                    if header != '42':
                        raise Exception('Format error')
            
                    header = gps.read(8)
                    rcvTow, week, numSV, reserved1 = struct.unpack('<IHBB',header)
                    print i+1, total, gps2time(week, rcvTow), numSV
                    if numSV > 0:
                        data = gps.read(24 * numSV)
                        ubx.write(ubxpack(UBX_RXM_RAW, header+data))
                    eoln = gps.read(2)
                    if eoln != '\r\n':
                        offset = gps.tell()
                        raise Exception('Format error at offset %d' % offset)
                
def checkgps(gpsfile):
    with open(gpsfile,'rb') as f:
        data = f.read()
        pos = 0
        count = 0
        while True:
            pos1 = data.find('42',pos)
            if pos1 >= 0:
                count += 1
                size = (pos1-pos)
                tow, week = struct.unpack_from('<IH',data,pos1+2)
                print count, pos1, size, week, tow, gps2time(week,tow)
                pos = pos1 + 2
            else:
                break
            
            
if __name__ == '__main__':
    readgps2(GPSFILE,UBXFILE)
    