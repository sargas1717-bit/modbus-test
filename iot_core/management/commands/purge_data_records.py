from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from iot_core.models import DataRecord


class Command(BaseCommand):
    help = "Elimina registros de telemetría anteriores al periodo de retención."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Antigüedad máxima de los registros en días (por defecto: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuántos registros coinciden sin eliminarlos.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days debe ser un entero mayor que cero.")

        cutoff = timezone.now() - timedelta(days=days)
        old_records = DataRecord.objects.filter(timestamp__lt=cutoff)

        if options["dry_run"]:
            self.stdout.write(
                f"Registros que se eliminarían: {old_records.count()} "
                f"(anteriores a {cutoff.isoformat()})."
            )
            return

        deleted_count, _ = old_records.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Registros eliminados: {deleted_count} "
                f"(anteriores a {cutoff.isoformat()})."
            )
        )
