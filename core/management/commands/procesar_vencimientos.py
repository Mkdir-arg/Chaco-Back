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

# Por el módulo y no `from … import REGLAS`: `registrar()` **rebindea** la lista
# global, así que una copia del nombre importada al cargar el comando se queda
# con la lista de antes del último registro (RED-81).
from core.services import vencimientos as registro


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
        reglas = list(registro.REGLAS)
        if not reglas:
            # RED-81: con el registro vacío el comando salía con éxito y no
            # procesaba nada. Como lo corre un cron (03:10) y el arranque del
            # contenedor, «nada que hacer» y «el import de `ready()` se perdió»
            # eran indistinguibles: las convocatorias vencidas dejaban de
            # cerrarse en silencio. Registro vacío = falla, no éxito.
            raise CommandError(
                "No hay reglas de vencimiento registradas: revisá que el `ready()` de cada app "
                "importe su `services/vencimientos.py` (el import lleva `# noqa: F401` y parece sin uso)."
            )

        solo = options.get("solo")
        if solo:
            reglas = [r for r in reglas if r.slug == solo]
            if not reglas:
                disponibles = ", ".join(r.slug for r in registro.REGLAS)
                raise CommandError(f"No existe la regla '{solo}'. Disponibles: {disponibles}")

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
