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


class DeviceScanSerializer(serializers.Serializer):
    discovered_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=247),
        allow_empty=False,
    )

    def validate_discovered_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "La lista no puede contener direcciones Modbus repetidas."
            )
        return value
