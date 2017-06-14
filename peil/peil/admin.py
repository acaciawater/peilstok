from django.contrib import admin
from .models import ECModule, PressureModule, MasterModule
from peil.models import GNSSModule, Device, CalibrationSeries, CalibrationData,\
    AngleMessage, UBXFile

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    model = Device
    list_display = ('serial', 'devid', 'last_seen')
    list_filter = ('serial','devid',)
    fields = ('devid', 'serial', 'cal')
    
@admin.register(MasterModule)
class MasterModuleAdmin(admin.ModelAdmin):
    model = MasterModule
    list_display = ('device','time','angle','battery','air')
    list_filter = ('device','time')

@admin.register(ECModule)
class ECModuleAdmin(admin.ModelAdmin):
    model = ECModule
    list_display = ('device','time','position', 'adc1','adc2','temperature')
    list_filter = ('device','time','position')
    
@admin.register(PressureModule)
class PressureModuleAdmin(admin.ModelAdmin):
    model = PressureModule
    list_display = ('device','time','position', 'adc')
    list_filter = ('device','time','position')
    
@admin.register(GNSSModule)
class GNSSModuleAdmin(admin.ModelAdmin):
    model = GNSSModule
    list_display = ('device','time','lat','lon','alt','hacc','vacc','msl')
    list_filter = ('device','time')

class CalibDataInline(admin.TabularInline):
    model = CalibrationData
    extra = 0
    
@admin.register(CalibrationSeries)
class CalibAdmin(admin.ModelAdmin):
    model = CalibrationSeries
    list_display = ('name','created','modified')
    inlines = [CalibDataInline]
    class Media:
        css = {"all": ('css/hide_admin_original.css',)}

@admin.register(AngleMessage)
class AngleAdmin(admin.ModelAdmin):
    model = AngleMessage
    list_display = ('device','time','angle',)
        
@admin.register(UBXFile)
class UBXFileAdmin(admin.ModelAdmin):
    model = UBXFile
    list_display = ('device','ubxfile','created')
        