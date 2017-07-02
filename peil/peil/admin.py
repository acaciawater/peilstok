from django.contrib import admin
from peil.models import Device, Sensor,\
    UBXFile, RTKConfig, ECSensor, PressureSensor,\
    BatterySensor, AngleSensor, LoraMessage, ECMessage, PressureMessage,\
    InclinationMessage, StatusMessage, LocationMessage, GNSS_Sensor, Survey
from peil.actions import create_pvts, rtkpost
from peil.sensor import create_sensors, load_offsets,\
    load_distance, load_survey
from polymorphic.admin import PolymorphicChildModelFilter, PolymorphicChildModelAdmin, PolymorphicParentModelAdmin

def createsensors(modeladmin, request, queryset):
    for d in queryset:
        create_sensors(d)
    filename = '/media/sf_C_DRIVE/Users/theo/Documents/projdirs/peilstok/offsets.csv'
    load_offsets(filename)
    filename = '/media/sf_C_DRIVE/Users/theo/Documents/projdirs/peilstok/afstanden.csv'
    load_distance(filename)
    filename='/media/sf_C_DRIVE/Users/theo/Documents/projdirs/peilstok/survey.csv'
    load_survey(filename)
    
def test_ecsensors(modeladmin, request, queryset):
    x1 = [3839,3723,3666,3613,3574,3537,3518,3498,3484,3469,3459,3446,3438,3430,3425,3420,3411,3407,3392,3379,3370,3366,3360,3355,3350,3347,3345,3344,3341,3340,3337,3336,3334,3333,3333,3332,3330,3330,3328,3329,3328,3328,3327,3302,3295]
    x2 = [4095,4095,4095,4095,4095,4095,4095,4095,4095,4095,4095,4095,4093,4088,4085,4079,4076,4070,4048,4022,3984,3967,3931,3914,3890,3852,3835,3817,3803,3787,3774,3749,3730,3735,3713,3688,3689,3674,3668,3663,3654,3638,3645,3348,3303]
    for s in queryset:
        for raw1,raw2 in zip(x1,x2):
            print raw1, raw2, s.EC(raw1,raw2,2500)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    model = Device
    list_display = ('serial', 'devid', 'last_seen')
    list_filter = ('serial','devid',)
    fields = ('devid', 'serial', 'cal')
    actions=[createsensors]
    
@admin.register(UBXFile)
class UBXFileAdmin(admin.ModelAdmin):
    model = UBXFile
    actions = [create_pvts, rtkpost]
    list_filter = ('device', 'created')
    list_display = ('__unicode__','device','created', 'start', 'stop')
        
@admin.register(RTKConfig)
class RTKAdmin(admin.ModelAdmin):
    model = RTKConfig
    list_display = ('name',)

@admin.register(Sensor)
class SensorAdmin(PolymorphicParentModelAdmin):
    base_model = Sensor
    child_models = (ECSensor, PressureSensor, BatterySensor, AngleSensor, GNSS_Sensor)
    list_filter = (PolymorphicChildModelFilter, 'position', 'device')
    list_display = ('ident', 'device', 'position', 'distance', 'message_count')
    
@admin.register(ECSensor)
class ECSensorAdmin(PolymorphicChildModelAdmin):
    base_model = ECSensor
    actions = [test_ecsensors,]
    
@admin.register(PressureSensor)
class PressureSensorAdmin(PolymorphicChildModelAdmin):
    base_model = PressureSensor
    list_filter = ('ident', 'device')
    list_display = ('ident', 'device', 'offset', 'scale')
    
@admin.register(BatterySensor)
class BatterySensorAdmin(PolymorphicChildModelAdmin):
    base_model = BatterySensor
    
@admin.register(AngleSensor)
class AngleSensorAdmin(PolymorphicChildModelAdmin):
    base_model = AngleSensor

@admin.register(GNSS_Sensor)
class GNSS_SensorAdmin(PolymorphicChildModelAdmin):
    base_model = GNSS_Sensor
    
@admin.register(LoraMessage)
class LoraAdmin(PolymorphicParentModelAdmin):
    base_model = LoraMessage
    child_models = (ECMessage, PressureMessage, InclinationMessage, StatusMessage, LocationMessage)
    list_filter = (PolymorphicChildModelFilter, 'time', 'sensor__device')
    list_display = ('__unicode__', 'time', 'device')
    
@admin.register(ECMessage)
class ECMessageAdmin(PolymorphicChildModelAdmin):
    base_model = ECMessage
    list_display = ('device','sensor','time','adc1','adc2', 'temperature')
    list_filter = ('sensor__device','time',)
    show_in_index = True
    
@admin.register(PressureMessage)
class PressureMessageAdmin(PolymorphicChildModelAdmin):
    base_model = PressureMessage
    list_display = ('adc',)
    
@admin.register(InclinationMessage)
class InclinationMessageAdmin(PolymorphicChildModelAdmin):
    base_model = InclinationMessage
    
@admin.register(StatusMessage)
class StatusMessageAdmin(PolymorphicChildModelAdmin):
    base_model = StatusMessage
    
@admin.register(LocationMessage)
class LocationMessageAdmin(PolymorphicChildModelAdmin):
    base_model = LocationMessage
    
@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    model = Survey
    list_display=('device','time','surveyor','location','altitude','vacc','hacc')
    list_filter=('device','time','surveyor')
    