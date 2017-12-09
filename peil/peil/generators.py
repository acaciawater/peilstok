'''
Created on Dec 7, 2017

@author: theo
'''
from acacia.data.generators.generator import Generator
import pandas as pd
import datetime

#url = 'http://getij.rws.nl/export.cfm?format=txt&from=01-11-2017&to=26-11-2017&uitvoer=1&interval=30&lunarphase=yes&location=OUDSD&Timezone=MET_DST&refPlane=NAP&graphRefPlane=NAP'
def_url = 'http://getij.rws.nl/export.cfm?format=txt&from={start}&to={stop}&uitvoer=1&interval={interval}&lunarphase=yes&location={loc}&Timezone=MET_DST&refPlane=NAP&graphRefPlane=NAP'
class Tide(Generator):
    
    def download(self, **kwargs):
        url = kwargs.get('url')
        loc = kwargs.get('location','OUDSD')
        interval = kwargs.get('interval',30)
        start = kwargs.get('start','01-06-2017')
        stop = kwargs.get('stop',datetime.date.today().strftime('%d-%m-%Y'))
        url = url.format(loc=loc,start=start,stop=stop,interval=interval)
        kwargs['url'] = url
        if not 'filename' in kwargs:
            kwargs['filename'] = 'getij_{}_{}.txt'.format(loc,stop)
        return Generator.download(self, **kwargs)

    def get_data(self, f, **kwargs):
        for i in range(15):
            line = f.readline()
        recs = []
        while line:
            words = line.split()
            if len(words) == 4:
                date = datetime.datetime.strptime(words[0] + ' ' + words[1], '%d/%m/%Y %H:%M')
                level = int(words[2])
                recs.append((date,level))
            line = f.readline()
        df = pd.DataFrame.from_records(recs)
        df.set_index(0,drop=True,inplace=True)
        df.columns=['level']
        df.index.name = 'date'
        return df
    
    def get_parameters(self, fil):
        return {'level':{'description': 'waterpeil', 'unit': 'cm tov NAP'}}

# if __name__ == '__main__':
#     tide = Tide()
#     df = tide.get_data('/home/theo/git/peil/peil/data/getij_export.txt')
#     print df
    