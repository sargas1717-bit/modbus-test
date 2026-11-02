from datetime import datetime, time, timedelta
from io import BytesIO
import json

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Avg, Max, Min, StdDev
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView
from openpyxl.styles import Font
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import AdministratorRequiredMixin
from .forms import DateRangeForm
from .models import DataRecord, Device
from .serializers import DataRecordSerializer, DeviceScanSerializer


def get_period_records(device, form):
    records = DataRecord.objects.filter(device=device).order_by("timestamp")
    if not form.is_valid():
        return records.none()

    start = form.cleaned_data["fecha_inicio"]
    end = form.cleaned_data["fecha_fin"]
    current_timezone = timezone.get_current_timezone()
    if start:
        start_datetime = timezone.make_aware(
            datetime.combine(start, time.min),
            current_timezone,
        )
        records = records.filter(timestamp__gte=start_datetime)
    if end:
        end_exclusive = timezone.make_aware(
            datetime.combine(end + timedelta(days=1), time.min),
            current_timezone,
        )
        records = records.filter(timestamp__lt=end_exclusive)
    return records


def get_record_metrics(records):
    aggregate = records.aggregate(
        average=Avg("value"),
        maximum=Max("value"),
        minimum=Min("value"),
        standard_deviation=StdDev("value"),
    )
    standard_deviation = aggregate["standard_deviation"]
    aggregate["variance"] = (
        standard_deviation**2 if standard_deviation is not None else None
    )
    return aggregate


def get_dashboard_data():
    recent_records = list(
        DataRecord.objects.select_related("device")
        .order_by("-timestamp")[:100]
    )
    chart_groups = {
        sensor_type: {
            "key": sensor_type,
            "label": label,
            "unit": Device.SENSOR_UNITS[sensor_type],
            "active_device_count": 0,
            "latest_value": None,
            "latest_timestamp": None,
            "series": {},
        }
        for sensor_type, label in Device.SensorType.choices
    }

    for device in Device.objects.filter(is_active=True):
        chart_groups[device.sensor_type]["active_device_count"] += 1

    for record in reversed(recent_records):
        group = chart_groups[record.device.sensor_type]
        series = group["series"].setdefault(
            record.device_id,
            {
                "name": (
                    f"{record.device.name} · Modbus "
                    f"{record.device.modbus_address}"
                ),
                "labels": [],
                "values": [],
            },
        )
        series["labels"].append(record.timestamp.isoformat())
        series["values"].append(record.value)

    for sensor_type, _ in Device.SensorType.choices:
        latest_record = (
            DataRecord.objects.filter(device__sensor_type=sensor_type)
            .order_by("-timestamp")
            .first()
        )
        if latest_record:
            chart_groups[sensor_type]["latest_value"] = latest_record.value
            chart_groups[sensor_type]["latest_timestamp"] = (
                latest_record.timestamp
            )

    sensor_charts = [
        {
            **group,
            "series": list(group["series"].values()),
        }
        for group in chart_groups.values()
    ]
    return {
        "sensor_charts": sensor_charts,
        "active_device_count": Device.objects.filter(is_active=True).count(),
        "record_count": DataRecord.objects.count(),
        "sensor_type_count": (
            Device.objects.filter(is_active=True)
            .values("sensor_type")
            .distinct()
            .count()
        ),
        "records": [
            {
                "timestamp": record.timestamp.isoformat(),
                "device_name": record.device.name,
                "sensor_type": record.device.get_sensor_type_display(),
                "value": record.value,
                "unit": record.device.sensor_unit,
            }
            for record in recent_records
        ],
    }


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "iot_core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard_data = get_dashboard_data()
        context.update(
            {
                **dashboard_data,
                "devices": Device.objects.all(),
                "chart_data": dashboard_data,
            }
        )
        return context


@login_required
def dashboard_data_view(request):
    return JsonResponse(get_dashboard_data())


class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = "iot_core/device_list.html"
    context_object_name = "devices"


class AdministratorDeviceCreateView(AdministratorRequiredMixin, CreateView):
    model = Device
    fields = ("name", "sensor_type", "modbus_address", "location", "is_active")
    template_name = "generic_form.html"
    success_url = reverse_lazy("device_list")
    extra_context = {"page_title": "Registrar dispositivo"}

    def form_valid(self, form):
        messages.success(self.request, "Dispositivo creado correctamente.")
        return super().form_valid(form)


class AdministratorDeviceUpdateView(AdministratorRequiredMixin, UpdateView):
    model = Device
    fields = ("name", "sensor_type", "modbus_address", "location", "is_active")
    template_name = "generic_form.html"
    success_url = reverse_lazy("device_list")
    extra_context = {"page_title": "Editar dispositivo"}

    def form_valid(self, form):
        messages.success(self.request, "Dispositivo actualizado correctamente.")
        return super().form_valid(form)


class AdministratorDeviceDeleteView(AdministratorRequiredMixin, DeleteView):
    model = Device
    template_name = "generic_confirm_delete.html"
    success_url = reverse_lazy("device_list")
    extra_context = {"page_title": "Eliminar dispositivo"}

    def form_valid(self, form):
        messages.success(self.request, "Dispositivo eliminado correctamente.")
        return super().form_valid(form)


class DataRecordListView(LoginRequiredMixin, ListView):
    model = DataRecord
    template_name = "iot_core/record_list.html"
    context_object_name = "records"
    paginate_by = 50

    def get_queryset(self):
        return DataRecord.objects.select_related("device").order_by("-timestamp")


class DataRecordCreateAPIView(CreateAPIView):
    queryset = DataRecord.objects.all()
    serializer_class = DataRecordSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)


class AdministratorScanPermission(BasePermission):
    message = "Solo los administradores pueden registrar dispositivos detectados."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_admin_access


class DeviceScanAPIView(APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated, AdministratorScanPermission)

    def post(self, request):
        serializer = DeviceScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discovered_ids = serializer.validated_data["discovered_ids"]

        with transaction.atomic():
            existing_addresses = set(
                Device.objects.filter(
                    modbus_address__in=discovered_ids
                ).values_list("modbus_address", flat=True)
            )
            new_addresses = [
                address
                for address in discovered_ids
                if address not in existing_addresses
            ]
            created_devices = Device.objects.bulk_create(
                [
                    Device(
                        name=f"Sensor Autodetectado {address}",
                        modbus_address=address,
                        location="Pendiente de configuración",
                        is_active=False,
                        sensor_type=Device.SensorType.OTHER,
                    )
                    for address in new_addresses
                ]
            )

        return Response(
            {
                "created": [
                    {
                        "id": device.pk,
                        "modbus_address": device.modbus_address,
                        "name": device.name,
                        "is_active": device.is_active,
                    }
                    for device in created_devices
                ],
                "already_registered": sorted(existing_addresses),
            },
            status=status.HTTP_201_CREATED,
        )


class DeviceAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "iot_core/device_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = get_object_or_404(Device, pk=self.kwargs["pk"])
        form = DateRangeForm(data=self.request.GET or None)
        records = get_period_records(device, form)
        metrics = (
            get_record_metrics(records)
            if form.is_valid()
            else {
                "average": None,
                "maximum": None,
                "minimum": None,
                "standard_deviation": None,
                "variance": None,
            }
        )
        chart_records = list(records.values_list("timestamp", "value"))

        context.update(
            {
                "device": device,
                "form": form,
                "metrics": metrics,
                "chart_data": json.dumps(
                    {
                        "labels": [
                            timestamp.isoformat()
                            for timestamp, _ in chart_records
                        ],
                        "values": [value for _, value in chart_records],
                        "unit": device.sensor_unit,
                    }
                ),
                "record_count": len(chart_records),
            }
        )
        return context


class DeviceExportView(LoginRequiredMixin, View):
    def get(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        form = DateRangeForm(data=request.GET or None)
        if not form.is_valid():
            return HttpResponseBadRequest(
                "Rango de fechas inválido. Use fecha_inicio y fecha_fin con "
                "formato AAAA-MM-DD; fecha_inicio no puede ser posterior a fecha_fin."
            )

        records = get_period_records(device, form)
        metrics = get_record_metrics(records)
        metric_rows = [
            {
                "Métrica": "Promedio",
                "Valor": metrics["average"],
                "Unidad": device.sensor_unit,
            },
            {
                "Métrica": "Máximo",
                "Valor": metrics["maximum"],
                "Unidad": device.sensor_unit,
            },
            {
                "Métrica": "Mínimo",
                "Valor": metrics["minimum"],
                "Unidad": device.sensor_unit,
            },
            {
                "Métrica": "Varianza (poblacional)",
                "Valor": metrics["variance"],
                "Unidad": (
                    f"{device.sensor_unit}²" if device.sensor_unit else ""
                ),
            },
        ]
        record_rows = [
            {
                "Fecha y hora": timezone.localtime(record.timestamp).replace(
                    tzinfo=None
                ),
                "Dispositivo": device.name,
                "Tipo de sensor": device.get_sensor_type_display(),
                "Dirección Modbus": device.modbus_address,
                "Valor": record.value,
                "Unidad": device.sensor_unit,
            }
            for record in records
        ]
        metrics_dataframe = pd.DataFrame(
            metric_rows,
            columns=("Métrica", "Valor", "Unidad"),
        )
        records_dataframe = pd.DataFrame(
            record_rows,
            columns=(
                "Fecha y hora",
                "Dispositivo",
                "Tipo de sensor",
                "Dirección Modbus",
                "Valor",
                "Unidad",
            ),
        )

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            metrics_dataframe.to_excel(writer, sheet_name="Métricas", index=False)
            records_dataframe.to_excel(
                writer,
                sheet_name="Registro Histórico",
                index=False,
            )
            for worksheet in writer.book.worksheets:
                worksheet.freeze_panes = "A2"
                worksheet.auto_filter.ref = worksheet.dimensions
                for cell in worksheet[1]:
                    cell.font = Font(bold=True)
                for column_cells in worksheet.columns:
                    width = max(
                        (
                            len(str(cell.value))
                            for cell in column_cells
                            if cell.value is not None
                        ),
                        default=0,
                    )
                    worksheet.column_dimensions[
                        column_cells[0].column_letter
                    ].width = min(width + 2, 50)

        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="dispositivo_{device.pk}_reporte.xlsx"'
        )
        return response
