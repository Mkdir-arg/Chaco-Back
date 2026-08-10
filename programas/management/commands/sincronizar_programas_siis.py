"""Sincroniza contra SIIS el estado de los programas vinculados a segmentos.

Idempotente: solo escribe los segmentos cuyo estado cambió. Pensado para correr
a diario (cron del host) y también en el arranque del contenedor, igual que
``procesar_vencimientos``.

    python manage.py sincronizar_programas_siis
    python manage.py sincronizar_programas_siis --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from programas.models import Segmento
from programas.services.siis import SiisCatalogError
from programas.services.siis_sync import sincronizar_estado_programas


class Command(BaseCommand):
    help = "Actualiza el estado (ACTIVO/INACTIVO) de los programas SIIS vinculados a los segmentos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No modifica nada; solo informa qué segmentos cambiarían de estado.",
        )

    def handle(self, *args, **options):
        dry = options.get("dry_run")
        try:
            cambios = sincronizar_estado_programas(dry_run=dry)
        except SiisCatalogError as exc:
            raise CommandError(str(exc)) from exc

        if not cambios:
            self.stdout.write("Sin cambios: todos los programas SIIS vinculados siguen igual.")
            return

        prefijo = "[dry-run] " if dry else ""
        for segmento, anterior, nuevo in cambios:
            linea = f"{prefijo}{segmento.nombre} (programa SIIS #{segmento.siis_programa_id}): {anterior or '—'} → {nuevo}"
            if nuevo in Segmento.ESTADOS_SIIS_BLOQUEANTES:
                self.stdout.write(self.style.WARNING(f"{linea} — el segmento queda bloqueado para operar."))
            else:
                self.stdout.write(self.style.SUCCESS(linea))

        verbo = "a actualizar" if dry else "actualizado(s)"
        self.stdout.write(self.style.SUCCESS(f"Listo. {len(cambios)} segmento(s) {verbo}."))
