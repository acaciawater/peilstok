'''
Created on Jul 1, 2017

@author: theo
'''
# Factor to convert raw ADC-pressure value to hPa for master and slave
ADC_HPAMASTER = 0.8047603298
ADC_HPASLAVE = 0.5532727267

# Factor to convert raw ADC-pressure value to psi for master and slave
ADC_PSIMASTER = 0.01167206175
ADC_PSISLAVE = 0.008024542455

# results from rational function fit June 2017 (15oC and 23 oC) as json string
EC23ADC1= '[-1.24962278e-01,   7.51304212e+02,  -6.42625003e+05,  -3.31128125e+03]'
EC23ADC2= '[-2.72687329e+01,   2.07166387e+05,  -3.88755659e+08,  -3.50129229e+03]'
EC15ADC1= '[-8.29946220e-02,   6.46281398e+02,  -8.20979572e+05,  -3.32036612e+03]'
EC15ADC2= '[-8.91896788e+01,   6.88251396e+05,  -1.32082791e+09,  -3.51902652e+03]'

# final calibration coefficents
ADC1EC = EC23ADC1
ADC2EC = EC23ADC2
ADC1EC_LIMITS = '[3400,4094]' 
ADC2EC_LIMITS = '[3590,4094]'
EC_RANGE = '[700,40000]'
