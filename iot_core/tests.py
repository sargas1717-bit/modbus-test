from django.contrib.auth import get_user_model
from django.test import TestCase
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
                "modbus_address": 2,
                "location": "Planta",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Device.objects.filter(name="PLC autorizado").exists())
