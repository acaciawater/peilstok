"""peil URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from tastypie.api import Api
from .views import ttn, ubx
from peil.views import DeviceListView, MapView, json_locations,\
    PopupView, PeilView, chart_as_json, data_as_json, DeviceDetailView,\
    chart_as_csv, data_as_csv, PhotoView, PostView, select_photo
from django.views.decorators.cache import cache_page
from peil.api import DeviceResource, SensorResource, MessageResource

v1 = Api(api_name='v1')
v1.register(DeviceResource())
v1.register(SensorResource())
v1.register(MessageResource())

urlpatterns = [
    url(r'^$', cache_page(60)(MapView.as_view()), name='home'), # Keep mapview up-to-date
    url(r'^admin/', admin.site.urls),
    url(r'^ttn/', ttn),
    url(r'^ubx/', ubx),
    url(r'^map/', cache_page(60)(MapView.as_view()), name='device-map'),
    url(r'^chart/(?P<pk>\d+)/data/csv', chart_as_csv, name='chart-csv'),
    url(r'^chart/(?P<pk>\d+)/data', chart_as_json, name='chart-json'),
    url(r'^chart/(?P<pk>\d+)/raw/csv', data_as_csv, name='data-csv'),
    url(r'^chart/(?P<pk>\d+)/raw', data_as_json, name='data-json'),
    url(r'^chart/(?P<pk>\d+)', PeilView.as_view(), name='chart-detail'),
    url(r'^post/(?P<pk>\d+)', PostView.as_view(), name='post-detail'),
    url(r'^device/(?P<pk>\d+)', DeviceDetailView.as_view(), name='device-detail'),
    url(r'^device/', DeviceListView.as_view(), name='device-list'),
    url(r'^locs/', json_locations),
    url(r'^photos/(?P<pk>\d+)', PhotoView.as_view(), name='device-photos'),
    url(r'^photos/select/(?P<pk>\d+)', select_photo, name='select-photo'),
    url(r'^pop/(?P<pk>\d+)', PopupView.as_view()),
    url(r'^api/', include(v1.urls)),
    url(r'^accounts/', include('registration.backends.hmac.urls')),    
]

from django.conf.urls.static import static
from django.conf import settings
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = 'Beheerpagina'

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
