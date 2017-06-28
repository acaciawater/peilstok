from django.contrib import admin
from peil.models import Device, Sensor,\
    UBXFile, RTKConfig, ECSensor, PressureSensor,\
    BatterySensor, AngleSensor, LoraMessage, ECMessage, PressureMessage,\
    InclinationMessage, StatusMessage, LocationMessage
from peil.actions import create_pvts, calcseries, rtkpost
from peil.sensor import create_sensors, copy_messages
from polymorphic.admin import PolymorphicChildModelFilter, PolymorphicChildModelAdmin, PolymorphicParentModelAdmin

def createsensors(modeladmin, request, queryset):
    for d in queryset:
        create_sensors(d)
        copy_messages(d)

   
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    model = Device
    list_display = ('serial', 'devid', 'last_seen')
    list_filter = ('serial','devid',)
    fields = ('devid', 'serial', 'cal')
    actions=[calcseries, createsensors]
    
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
    child_models = (ECSensor, PressureSensor, BatterySensor, AngleSensor)
    list_filter = (PolymorphicChildModelFilter, 'position', 'device')
    list_display = ('__unicode__', 'device', 'position', 'message_count')
    
@admin.register(ECSensor)
class ECSensorAdmin(PolymorphicChildModelAdmin):
    base_model = ECSensor

@admin.register(PressureSensor)
class PressureSensorAdmin(PolymorphicChildModelAdmin):
    base_model = PressureSensor

@admin.register(BatterySensor)
class BatterySensorAdmin(PolymorphicChildModelAdmin):
    base_model = BatterySensor
    
@admin.register(AngleSensor)
class AngleSensorAdmin(PolymorphicChildModelAdmin):
    base_model = AngleSensor
    
@admin.register(LoraMessage)
class LoraAdmin(PolymorphicParentModelAdmin):
    base_model = LoraMessage
    child_models = (ECMessage, PressureMessage, InclinationMessage, StatusMessage, LocationMessage)
    list_filter = (PolymorphicChildModelFilter, 'time', 'sensor__device')
    list_display = ('__unicode__', 'time', 'device')
    
@admin.register(ECMessage)
class ECMessageAdmin(PolymorphicChildModelAdmin):
    base_model = ECMessage

@admin.register(PressureMessage)
class PressureMessageAdmin(PolymorphicChildModelAdmin):
    base_model = PressureMessage
    
@admin.register(InclinationMessage)
class InclinationMessageAdmin(PolymorphicChildModelAdmin):
    base_model = InclinationMessage
    
@admin.register(StatusMessage)
class StatusMessageAdmin(PolymorphicChildModelAdmin):
    base_model = StatusMessage
    
@admin.register(LocationMessage)
class LocationMessageAdmin(PolymorphicChildModelAdmin):
    base_model = LocationMessage
    
