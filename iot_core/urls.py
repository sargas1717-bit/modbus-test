from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    AdministratorDeviceCreateView,
    AdministratorDeviceDeleteView,
    AdministratorDeviceUpdateView,
    DashboardView,
    dashboard_data_view,
    DeviceAnalyticsView,
    DeviceExportView,
    DeviceScanAPIView,
    DataRecordCreateAPIView,
    DataRecordListView,
    DeviceListView,
)


urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("api/dashboard-data/", dashboard_data_view, name="dashboard_data"),
    path("devices/", DeviceListView.as_view(), name="device_list"),
    path("devices/<int:pk>/analytics/", DeviceAnalyticsView.as_view(), name="device_analytics"),
    path("devices/<int:pk>/export/", DeviceExportView.as_view(), name="device_export"),
    path("devices/create/", AdministratorDeviceCreateView.as_view(), name="device_create"),
    path("devices/<int:pk>/edit/", AdministratorDeviceUpdateView.as_view(), name="device_update"),
    path("devices/<int:pk>/delete/", AdministratorDeviceDeleteView.as_view(), name="device_delete"),
    path("records/", DataRecordListView.as_view(), name="record_list"),
    path("api/token/", obtain_auth_token, name="api_token"),
    path("api/records/", DataRecordCreateAPIView.as_view(), name="api_record_create"),
    path("api/devices/scan/", DeviceScanAPIView.as_view(), name="api_device_scan"),
]
