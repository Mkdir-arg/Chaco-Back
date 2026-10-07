"""Aplica las reglas de vencimiento por fecha (cierres y cambios de estado).

Idempotente: cada regla filtra por "vencido y todavía por procesar", así que
re-ejecutarlo no repite trabajo. Pensado para correr a diario (cron del host)
y también en el arranque del contenedor, para que un deploy ponga al día lo
vencido.

    python manage.py procesar_vencimientos
    python manage.py procesar_vencimientos --dry-run
    python manage.py procesar_vencimientos --solo becas.convocatoria
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Por el módulo y no `from … import REGLAS`: `registrar()` **rebindea** la lista
# global, así que una copia del nombre importada al cargar el comando se queda
# con la lista de antes del último registro (RED-81).
from core.services import vencimientos as registro

logger = logging.getLogger(__name__)


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
        fallidas = []
        for regla in reglas:
            # OPS-07: las reglas son independientes entre sí —una la registra Becas, otra
            # la va a registrar Legajos— y el comando corre en el **arranque del
            # contenedor** además del cron de las 03:10. Sin aislar, la primera que
            # explota deja a las demás sin correr y, en el arranque, tira abajo el pod:
            # el entrypoint corre con `set -eu`. Cada regla ya tiene su propia `atomic`,
            # así que lo que falla no deja nada a medias.
            try:
                total += self._correr_regla(regla, dry)
            except Exception as excepcion:
                logger.exception("La regla de vencimiento %s falló", regla.slug)
                self.stderr.write(
                    self.style.ERROR(f"{regla.slug}: falló ({excepcion}). Se sigue con las demás reglas.")
                )
                fallidas.append(regla.slug)

        verbo = "a procesar" if dry else "procesado(s)"
        self.stdout.write(self.style.SUCCESS(f"Listo. {total} registro(s) {verbo}."))

        if fallidas:
            # El cron es la única notificación que hay: tiene que ponerse rojo. Lo que
            # cambió es que ahora se pone rojo **después** de correr todo lo que podía.
            raise CommandError(
                f"{len(fallidas)} regla(s) de vencimiento fallaron: {', '.join(fallidas)}. "
                "El traceback de cada una está en el log; las demás reglas sí se aplicaron."
            )

    def _correr_regla(self, regla, dry):
        """Devuelve cuántos registros contó o procesó. Lo que lance, lo maneja `handle`."""
        pendientes = regla.pendientes().count()
        if dry:
            self.stdout.write(f"[dry-run] {regla.slug}: {pendientes} pendiente(s) — {regla.descripcion}")
            return pendientes

        if not pendientes:
            self.stdout.write(f"{regla.slug}: sin pendientes.")
            return 0

        with transaction.atomic():
            afectados = regla.aplicar(regla.pendientes())
        self.stdout.write(self.style.SUCCESS(f"{regla.slug}: {afectados} procesado(s) — {regla.descripcion}"))
        return afectados
