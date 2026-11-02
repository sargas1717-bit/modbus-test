from rest_framework import serializers

from .models import DataRecord, Device


class DataRecordSerializer(serializers.ModelSerializer):
    device = serializers.PrimaryKeyRelatedField(
        queryset=Device.objects.filter(is_active=True),
    )

    class Meta:
        model = DataRecord
        fields = ("id", "device", "value", "timestamp")
        read_only_fields = ("id", "timestamp")
