'''
Created on Dec 6, 2017

@author: theo
'''
import binascii
import struct

def decode(payload):
    ''' decode hex payload '''
    payload = binascii.a2b_hex(payload)
    type, position = struct.unpack('<BB',payload[:2])
    result = {'type': type, 'position': position}
    data = payload[2:]

    if type == 1:
        # gps
        lat,lon,height,hmsl,hacc,vacc = struct.unpack('<IIIIII',data)
        result.update({
            'latitude': lat,
            'longitude': lon,
            'height': height,
            'hMSL': hmsl,
            'hAcc': hacc,
            'vAcc': vacc
            })
    elif type == 5:
        # inclinometer
        angle = struct.unpack('<H',data)
        result.update({'angle': angle[0]})
    elif type == 6:
        # main sensor
        count, bat, pressure, angle = struct.unpack('<BHHH',data)
        result.update({
            'total': count,
            'battery': bat,
            'pressure': pressure,
            'angle': angle
            })
    elif type == 2:
        # EC
        temp, adc1, adc2 = struct.unpack('<HHH',data)
        result.update({
            'temperature': temp,
            'ec1': adc1,
            'ec2': adc2
            })
    elif type == 3:
        # pressure
        adc = struct.unpack('<H',data)
        result.update({
            'pressure': adc[0]
            })
    return result

if __name__ == '__main__':
    print decode('0303a907')
    