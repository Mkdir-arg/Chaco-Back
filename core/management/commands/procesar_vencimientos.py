"""Aplica las reglas de vencimiento por fecha (cierres y cambios de estado).

Idempotente: cada regla filtra por "vencido y todavía por procesar", así que
re-ejecutarlo no repite trabajo. Pensado para correr a diario (cron del host)
y también en el arranque del contenedor, para que un deploy ponga al día lo
vencido.

    python manage.py procesar_vencimientos
    python manage.py procesar_vencimientos --dry-run
    python manage.py procesar_vencimientos --solo becas.convocatoria
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.services.vencimientos import REGLAS


class Command(BaseCommand):
    help = "Corre las reglas de vencimiento por fecha (cierres y cambios de estado automáticos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No modifica nada; solo informa cuántos registros se afectarían.",
        )
        parser.add_argument(
            "--solo",
            metavar="SLUG",
            help="Corre únicamente la regla con ese slug (ej. becas.convocatoria).",
        )

    def handle(self, *args, **options):
        reglas = list(REGLAS)
        solo = options.get("solo")
        if solo:
            reglas = [r for r in reglas if r.slug == solo]
            if not reglas:
                disponibles = ", ".join(r.slug for r in REGLAS) or "(ninguna)"
                raise CommandError(f"No existe la regla '{solo}'. Disponibles: {disponibles}")

        if not reglas:
            self.stdout.write("No hay reglas de vencimiento registradas.")
            return

        dry = options.get("dry_run")
        total = 0
        for regla in reglas:
            pendientes = regla.pendientes().count()
            if dry:
                self.stdout.write(f"[dry-run] {regla.slug}: {pendientes} pendiente(s) — {regla.descripcion}")
                total += pendientes
                continue

            if pendientes:
                with transaction.atomic():
                    afectados = regla.aplicar(regla.pendientes())
                self.stdout.write(self.style.SUCCESS(f"{regla.slug}: {afectados} procesado(s) — {regla.descripcion}"))
                total += afectados
            else:
                self.stdout.write(f"{regla.slug}: sin pendientes.")

        verbo = "a procesar" if dry else "procesado(s)"
        self.stdout.write(self.style.SUCCESS(f"Listo. {total} registro(s) {verbo}."))
