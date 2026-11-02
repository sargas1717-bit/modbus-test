from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Device(models.Model):
    class SensorType(models.TextChoices):
        VOLTAGE = "voltage", "Voltaje"
        TEMPERATURE = "temperature", "Temperatura"
        VALVE_POSITION = "valve_position", "Posición de válvula"
        OTHER = "other", "Otro"

    SENSOR_UNITS = {
        SensorType.VOLTAGE: "V",
        SensorType.TEMPERATURE: "°C",
        SensorType.VALVE_POSITION: "%",
        SensorType.OTHER: "",
    }

    name = models.CharField("nombre", max_length=120)
    sensor_type = models.CharField(
        "tipo de sensor",
        max_length=20,
        choices=SensorType.choices,
        default=SensorType.OTHER,
    )
    modbus_address = models.PositiveSmallIntegerField(
        "dirección Modbus",
        validators=[MinValueValidator(1), MaxValueValidator(247)],
    )
    location = models.CharField("ubicación", max_length=200)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "dispositivo"
        verbose_name_plural = "dispositivos"

    def __str__(self):
        return f"{self.name} (Modbus {self.modbus_address})"

    @property
    def sensor_unit(self):
        return self.SENSOR_UNITS[self.sensor_type]


class DataRecord(models.Model):
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name="dispositivo",
    )
    value = models.FloatField("valor")
    timestamp = models.DateTimeField("marca de tiempo", auto_now_add=True)

    class Meta:
        ordering = ("-timestamp",)
        verbose_name = "registro"
        verbose_name_plural = "registros"

    def __str__(self):
        return f"{self.device}: {self.value} ({self.timestamp:%Y-%m-%d %H:%M:%S})"
