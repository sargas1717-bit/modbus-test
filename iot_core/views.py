import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated

from accounts.mixins import AdministratorRequiredMixin
from .models import DataRecord, Device
from .serializers import DataRecordSerializer


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "iot_core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recent_records = list(
            DataRecord.objects.select_related("device")
            .order_by("-timestamp")[:100]
        )
        chart_records = reversed(recent_records)
        chart_series = {}
        for record in chart_records:
            series = chart_series.setdefault(
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
        context.update(
            {
                "devices": Device.objects.all(),
                "records": recent_records,
                "chart_data": json.dumps(
                    list(chart_series.values())
                ),
                "active_device_count": Device.objects.filter(is_active=True).count(),
                "record_count": DataRecord.objects.count(),
            }
        )
        return context


class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = "iot_core/device_list.html"
    context_object_name = "devices"


class AdministratorDeviceCreateView(AdministratorRequiredMixin, CreateView):
    model = Device
    fields = ("name", "modbus_address", "location", "is_active")
    template_name = "generic_form.html"
    success_url = reverse_lazy("device_list")
    extra_context = {"page_title": "Registrar dispositivo"}

    def form_valid(self, form):
        messages.success(self.request, "Dispositivo creado correctamente.")
        return super().form_valid(form)


class AdministratorDeviceUpdateView(AdministratorRequiredMixin, UpdateView):
    model = Device
    fields = ("name", "modbus_address", "location", "is_active")
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
