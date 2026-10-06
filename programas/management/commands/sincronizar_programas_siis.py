"""Sincroniza contra SIIS el estado de los programas vinculados.

Idempotente: solo escribe los programas cuyo estado cambió. Pensado para correr
a diario (cron del host) y también en el arranque del contenedor, igual que
``procesar_vencimientos``.

    python manage.py sincronizar_programas_siis
    python manage.py sincronizar_programas_siis --dry-run
    # baja masiva confirmada con ECOM:
    python manage.py sincronizar_programas_siis --forzar --motivo "ECOM dio de baja el plan X" --usuario jperez

Falla —sin escribir nada— si SIIS devuelve un catálogo vacío o si quedarían
bloqueados todos los programas vinculados o más de la mitad (SIIS-06): a las
04:00 no hay nadie mirando, y marcar todo ``DESCONOCIDO`` por un error del
servicio deja Becas bloqueada entera. El ``CommandError`` deja el CronJob en
rojo, que es la forma de que se entere alguien.

``--forzar`` saltea esa guarda, así que **exige ``--motivo``** y deja rastro en
el log, igual que ``--ignorar-corrida`` en los comandos que hablan con SIIS caso
por caso. El CronJob de ``docker/k8s/cronjobs.yaml`` corre sin el flag y no
cambia.
"""

from django.core.management.base import BaseCommand, CommandError

from programas.models import ProgramaSiis
from programas.services.siis import SiisCatalogError
from programas.services.siis_sync import sincronizar_estado_programas

AYUDA_FORZAR = (
    "Escribe aunque quedaran bloqueados todos los programas vinculados (o más de la mitad). "
    "Es para una baja masiva confirmada con ECOM: sin esto, una ausencia así se trata como un "
    "error de SIIS y no se escribe. Exige --motivo."
)
AYUDA_MOTIVO = "Por qué se fuerza la escritura. Obligatorio con --forzar; queda en el log del pod."
AYUDA_USUARIO = "Quién lo corre. Queda en el log junto al motivo."
FALTA_MOTIVO = (
    "--forzar necesita --motivo: es la única guarda de este comando que se puede saltear a mano, "
    "y deja bloqueada media Becas o más, así que tiene que quedar escrito quién lo hizo y por qué."
)


class Command(BaseCommand):
    help = "Actualiza el estado (ACTIVO/INACTIVO) de los programas SIIS vinculados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No modifica nada; solo informa qué programas cambiarían de estado.",
        )
        parser.add_argument("--forzar", action="store_true", help=AYUDA_FORZAR)
        parser.add_argument("--motivo", default="", help=AYUDA_MOTIVO)
        parser.add_argument("--usuario", default=None, help=AYUDA_USUARIO)

    def handle(self, *args, **options):
        dry = options.get("dry_run")
        forzar = options.get("forzar")
        motivo = (options.get("motivo") or "").strip()
        if forzar and not motivo:
            raise CommandError(FALTA_MOTIVO)
        try:
            cambios = sincronizar_estado_programas(
                dry_run=dry,
                forzar=forzar,
                motivo=motivo,
                usuario=options.get("usuario"),
            )
        except SiisCatalogError as exc:
            raise CommandError(str(exc)) from exc

        if not cambios:
            self.stdout.write("Sin cambios: todos los programas SIIS vinculados siguen igual.")
            return

        prefijo = "[dry-run] " if dry else ""
        for programa, anterior, nuevo in cambios:
            linea = (
                f"{prefijo}{programa.nombre} (programa SIIS #{programa.siis_programa_id}): {anterior or '—'} → {nuevo}"
            )
            if nuevo in ProgramaSiis.ESTADOS_SIIS_BLOQUEANTES:
                self.stdout.write(self.style.WARNING(f"{linea} — el programa y sus segmentos quedan bloqueados."))
            else:
                self.stdout.write(self.style.SUCCESS(linea))

        verbo = "a actualizar" if dry else "actualizado(s)"
        self.stdout.write(self.style.SUCCESS(f"Listo. {len(cambios)} programa(s) {verbo}."))
