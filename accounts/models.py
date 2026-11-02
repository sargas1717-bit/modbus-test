from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATOR = "admin", "Administrador"
        OPERATOR = "operator", "Operador"

    role = models.CharField(
        "rol",
        max_length=10,
        choices=Role.choices,
        default=Role.OPERATOR,
    )

    @property
    def has_admin_access(self):
        return self.is_superuser or self.role == self.Role.ADMINISTRATOR

    def __str__(self):
        return self.get_full_name() or self.username
