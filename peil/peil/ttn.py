'''
Created on Apr 25, 2017

@author: theo
'''
import json
TTNFILE = '/home/theo/peilstok/ttn.txt'
DATA = '{"app_id":"peilstok","dev_id":"peilstok_test","hardware_serial":"0000C8F09A96BABE","port":1,"counter":0,"is_retry":true,"payload_raw":"BgADgg2aAgIA","payload_fields":{"angle":2,"battery":3458,"position":0,"pressure":666,"total":3,"type":6},"metadata":{"time":"2017-04-25T19:22:23.492105282Z","frequency":868.1,"modulation":"LORA","data_rate":"SF7BW125","coding_rate":"4/5","gateways":[{"gtw_id":"eui-0000024b0805024f","timestamp":2202028659,"time":"2017-04-25T19:22:23.371582Z","channel":0,"rssi":-41,"snr":8.8,"rf_chain":1,"latitude":52.02153,"longitude":4.71009,"altitude":15},{"gtw_id":"eui-008000000000b8b6","timestamp":1871264851,"time":"2017-04-25T19:22:23.393749Z","channel":0,"rssi":-93,"snr":9,"rf_chain":1,"latitude":52.0182,"longitude":4.7084384,"altitude":25}]},"downlink_url":"https://integrations.thethingsnetwork.org/ttn-eu/api/v2/down/peilstok/fiware?key=ttn-account-v2.f_Z0n5hPjNnwgskA0PCa_4_wQIYNQpE-NEVZfitjZuc"}'
def readttn(fname):
    with open(fname) as ttn:
        for line in ttn:
            data = json.loads(line)
            print len(data)

def postttn(url,data):
        
if __name__ == '__main__':
    postttn(DATA)
    #readttn(TTNFILE)
    