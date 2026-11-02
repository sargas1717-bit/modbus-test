from django.contrib import admin

from .models import DataRecord, Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "sensor_type", "modbus_address", "location", "is_active")
    list_filter = ("sensor_type", "is_active")
    search_fields = ("name", "location")


@admin.register(DataRecord)
class DataRecordAdmin(admin.ModelAdmin):
    list_display = ("device", "value", "timestamp")
    list_filter = ("device",)
    date_hierarchy = "timestamp"
    readonly_fields = ("timestamp",)
