def create_pvts(modeladmin, request, queryset):
    '''Create pvty messages from ubx file '''
    for u in queryset:
        #sf.get_dimensions()
        u.create_pvts()
create_pvts.short_description='UBX-NAV-PVT messages aanmaken'
