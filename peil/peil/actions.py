def create_pvts(modeladmin, request, queryset):
    '''Create pvty messages from ubx file '''
    for u in queryset:
        #sf.get_dimensions()
        u.create_pvts()
create_pvts.short_description='UBX-NAV-PVT messages aanmaken'

def calcseries(modeladmin, request, queryset):
    for d in queryset:
        #sf.get_dimensions()
        df = d.calc()
        df = df.dropna(how='all')
        df.to_csv('/home/theo/peilstok/testdata.csv')
        
calcseries.short_description='Tijdreeksen  berekenen'
