from datetime import timedelta

from datetime import datetime, time, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import DataRecord, Device


User = get_user_model()


class DataRecordAPITests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="PLC de prueba",
            modbus_address=1,
            location="Banco de pruebas",
        )
        self.user = User.objects.create_user(
            username="gateway",
            password="test-password-123",
            role=User.Role.OPERATOR,
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def test_post_requires_token_authentication(self):
        response = self.client.post(
            "/api/records/",
            {"device": self.device.pk, "value": 21.5},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(DataRecord.objects.count(), 0)

    def test_authenticated_post_creates_record(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/records/",
            {"device": self.device.pk, "value": 21.5},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DataRecord.objects.get().value, 21.5)
        self.assertEqual(response.data["device"], self.device.pk)
        self.assertIn("timestamp", response.data)

    def test_authenticated_post_rejects_unknown_device(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post(
            "/api/records/",
            {"device": 9999, "value": 21.5},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DataRecord.objects.count(), 0)


class DeviceScanAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="scanner-admin",
            password="test-password-123",
            role=User.Role.ADMINISTRATOR,
        )
        self.operator = User.objects.create_user(
            username="scanner-operator",
            password="test-password-123",
            role=User.Role.OPERATOR,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.operator_token = Token.objects.create(user=self.operator)
        self.api_client = APIClient()
        self.existing_device = Device.objects.create(
            name="Dispositivo existente",
            modbus_address=1,
            location="Planta",
        )

    def test_scan_creates_only_missing_addresses_inactive(self):
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}"
        )
        response = self.api_client.post(
            "/api/devices/scan/",
            {"discovered_ids": [1, 2, 5]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["already_registered"], [1])
        self.assertEqual(
            [device["modbus_address"] for device in response.data["created"]],
            [2, 5],
        )
        discovered_devices = Device.objects.filter(modbus_address__in=[2, 5])
        self.assertEqual(discovered_devices.count(), 2)
        self.assertFalse(discovered_devices.filter(is_active=True).exists())
        self.assertTrue(
            discovered_devices.filter(
                name="Sensor Autodetectado 2",
                location="Pendiente de configuración",
            ).exists()
        )

    def test_operator_cannot_scan_network(self):
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.operator_token.key}"
        )
        response = self.api_client.post(
            "/api/devices/scan/",
            {"discovered_ids": [5]},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Device.objects.filter(modbus_address=5).exists())

    def test_scan_requires_token(self):
        response = self.api_client.post(
            "/api/devices/scan/",
            {"discovered_ids": [5]},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_scan_validates_modbus_addresses_and_duplicates(self):
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}"
        )
        for discovered_ids in ([0], [248], [2, 2], []):
            with self.subTest(discovered_ids=discovered_ids):
                response = self.api_client.post(
                    "/api/devices/scan/",
                    {"discovered_ids": discovered_ids},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)


class RoleAccessTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="operator",
            password="test-password-123",
            role=User.Role.OPERATOR,
        )
        self.administrator = User.objects.create_user(
            username="admin",
            password="test-password-123",
            role=User.Role.ADMINISTRATOR,
        )

    def test_operator_can_view_dashboard_and_records(self):
        self.client.force_login(self.operator)

        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/records/").status_code, 200)

    def test_operator_cannot_create_device(self):
        self.client.force_login(self.operator)

        response = self.client.post(
            "/devices/create/",
            {
                "name": "PLC no autorizado",
                "modbus_address": 2,
                "location": "Planta",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Device.objects.count(), 0)

    def test_administrator_can_create_device(self):
        self.client.force_login(self.administrator)

        response = self.client.post(
            "/devices/create/",
            {
                "name": "PLC autorizado",
                "sensor_type": Device.SensorType.VOLTAGE,
                "modbus_address": 2,
                "location": "Planta",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Device.objects.filter(name="PLC autorizado").exists())


class DashboardSensorChartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard",
            password="test-password-123",
            role=User.Role.OPERATOR,
        )
        self.voltage_device = Device.objects.create(
            name="Voltímetro",
            sensor_type=Device.SensorType.VOLTAGE,
            modbus_address=10,
            location="Banco",
        )
        self.temperature_device = Device.objects.create(
            name="Termómetro",
            sensor_type=Device.SensorType.TEMPERATURE,
            modbus_address=11,
            location="Banco",
        )
        self.valve_device = Device.objects.create(
            name="Válvula",
            sensor_type=Device.SensorType.VALVE_POSITION,
            modbus_address=12,
            location="Banco",
        )
        DataRecord.objects.create(device=self.voltage_device, value=220.0)
        DataRecord.objects.create(device=self.temperature_device, value=38.5)
        DataRecord.objects.create(device=self.valve_device, value=75.0)

    def test_dashboard_groups_series_by_sensor_type_and_unit(self):
        self.client.force_login(self.user)
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="chart-voltage"')
        self.assertContains(response, 'id="chart-temperature"')
        self.assertContains(response, 'id="chart-valve_position"')
        charts = {
            chart["key"]: chart
            for chart in response.context["sensor_charts"]
        }
        self.assertEqual(charts["voltage"]["unit"], "V")
        self.assertEqual(charts["voltage"]["series"][0]["values"], [220.0])
        self.assertEqual(charts["temperature"]["unit"], "°C")
        self.assertEqual(charts["temperature"]["series"][0]["values"], [38.5])
        self.assertEqual(charts["valve_position"]["unit"], "%")
        self.assertEqual(charts["valve_position"]["series"][0]["values"], [75.0])
        self.assertEqual(charts["other"]["series"], [])

    def test_dashboard_data_endpoint_requires_login(self):
        response = self.client.get("/api/dashboard-data/")

        self.assertEqual(response.status_code, 302)

    def test_dashboard_data_endpoint_returns_latest_records(self):
        self.client.force_login(self.user)
        first_response = self.client.get("/api/dashboard-data/")
        first_record_count = first_response.json()["record_count"]

        DataRecord.objects.create(device=self.voltage_device, value=221.0)
        response = self.client.get("/api/dashboard-data/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["record_count"], first_record_count + 1)
        voltage_chart = next(
            chart
            for chart in response.json()["sensor_charts"]
            if chart["key"] == Device.SensorType.VOLTAGE
        )
        self.assertEqual(voltage_chart["latest_value"], 221.0)
        self.assertEqual(len(response.json()["records"]), 4)


class DeviceAnalyticsAndExportTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="analytics-operator",
            password="test-password-123",
            role=User.Role.OPERATOR,
        )
        self.admin = User.objects.create_user(
            username="analytics-admin",
            password="test-password-123",
            role=User.Role.ADMINISTRATOR,
        )
        self.device = Device.objects.create(
            name="Sensor analítico",
            sensor_type=Device.SensorType.TEMPERATURE,
            modbus_address=22,
            location="Laboratorio",
        )
        self.start_date = timezone.localdate()
        midnight = datetime.combine(self.start_date, time.min)
        midnight = timezone.make_aware(midnight, timezone.get_current_timezone())
        self.first_record = DataRecord.objects.create(
            device=self.device,
            value=10.0,
        )
        self.second_record = DataRecord.objects.create(
            device=self.device,
            value=20.0,
        )
        DataRecord.objects.filter(pk=self.first_record.pk).update(
            timestamp=midnight + timedelta(hours=8)
        )
        DataRecord.objects.filter(pk=self.second_record.pk).update(
            timestamp=midnight + timedelta(hours=20)
        )

    def test_operator_can_see_date_filtered_analytics(self):
        self.client.force_login(self.operator)
        response = self.client.get(
            f"/devices/{self.device.pk}/analytics/",
            {
                "fecha_inicio": self.start_date.isoformat(),
                "fecha_fin": self.start_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["record_count"], 2)
        self.assertEqual(response.context["metrics"]["average"], 15.0)
        self.assertEqual(response.context["metrics"]["maximum"], 20.0)
        self.assertEqual(response.context["metrics"]["minimum"], 10.0)
        self.assertAlmostEqual(response.context["metrics"]["variance"], 25.0)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, "Plotly.newPlot")

    def test_analytics_rejects_reversed_date_range(self):
        self.client.force_login(self.operator)
        response = self.client.get(
            f"/devices/{self.device.pk}/analytics/",
            {
                "fecha_inicio": (self.start_date + timedelta(days=1)).isoformat(),
                "fecha_fin": self.start_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["record_count"], 0)
        self.assertTrue(response.context["form"].non_field_errors())

    def test_export_contains_metrics_and_history_sheets(self):
        self.client.force_login(self.operator)
        response = self.client.get(
            f"/devices/{self.device.pk}/export/",
            {"fecha_inicio": self.start_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response["Content-Type"],
        )
        workbook = load_workbook(BytesIO(response.content), read_only=False)
        self.assertEqual(
            workbook.sheetnames,
            ["Métricas", "Registro Histórico"],
        )
        self.assertEqual(workbook["Métricas"]["B2"].value, 15.0)
        self.assertEqual(workbook["Métricas"]["B5"].value, 25.0)
        self.assertTrue(workbook["Métricas"]["A1"].font.bold)
        self.assertTrue(workbook["Registro Histórico"]["A1"].font.bold)
        self.assertEqual(workbook["Registro Histórico"].max_row, 3)

    def test_export_rejects_invalid_date_range(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/devices/{self.device.pk}/export/",
            {
                "fecha_inicio": (self.start_date + timedelta(days=1)).isoformat(),
                "fecha_fin": self.start_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_analytics_and_export_require_login(self):
        self.assertEqual(
            self.client.get(
                f"/devices/{self.device.pk}/analytics/"
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.get(f"/devices/{self.device.pk}/export/").status_code,
            302,
        )


class PurgeDataRecordsCommandTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="PLC de retención",
            modbus_address=3,
            location="Banco de pruebas",
        )

    def test_purge_removes_records_older_than_retention_period(self):
        old_record = DataRecord.objects.create(device=self.device, value=10)
        recent_record = DataRecord.objects.create(device=self.device, value=20)
        DataRecord.objects.filter(pk=old_record.pk).update(
            timestamp=timezone.now() - timedelta(days=31)
        )

        call_command("purge_data_records")

        self.assertFalse(DataRecord.objects.filter(pk=old_record.pk).exists())
        self.assertTrue(DataRecord.objects.filter(pk=recent_record.pk).exists())

    def test_dry_run_does_not_delete_records(self):
        record = DataRecord.objects.create(device=self.device, value=10)
        DataRecord.objects.filter(pk=record.pk).update(
            timestamp=timezone.now() - timedelta(days=31)
        )

        call_command("purge_data_records", dry_run=True)

        self.assertTrue(DataRecord.objects.filter(pk=record.pk).exists())

    def test_days_must_be_positive(self):
        with self.assertRaises(CommandError):
            call_command("purge_data_records", days=0)
