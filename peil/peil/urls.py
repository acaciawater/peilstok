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
from .api import ECResource, PressureResource, MasterResource, GNSSResource, DeviceResource
from .views import ttn
from peil.views import DeviceView, DeviceListView, MapView, json_locations,\
    PopupView

v1 = Api(api_name='v1')
v1.register(DeviceResource())
v1.register(ECResource())
v1.register(PressureResource())
v1.register(MasterResource())
v1.register(GNSSResource())

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ttn/', ttn),
    url(r'^map/', MapView.as_view(), name='device-map'),
    url(r'^device/(?P<pk>\d+)', DeviceView.as_view(), name='device-detail'),
    url(r'^device/', DeviceListView.as_view(), name='device-list'),
    url(r'^locs/', json_locations),
    url(r'^pop/(?P<pk>\d+)', PopupView.as_view()),
    url(r'^api/', include(v1.urls)),
]
