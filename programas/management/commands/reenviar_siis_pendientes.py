"""Reintenta el alta en SIIS de los beneficiarios cuyo último envío fue un
error técnico (401/5xx/red/catálogo caído). Los ``INCOMPLETO`` y ``RECHAZADO``
necesitan corrección humana y no se tocan. Pensado para un cron o para correr
a mano después de una caída del legacy de SIIS."""

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from programas.models import EnvioSIIS, Formulario
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis


class Command(BaseCommand):
    help = "Reintenta los envíos a SIIS que fallaron por error técnico."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Lista sin enviar.")
        parser.add_argument("--limite", type=int, default=200, help="Máximo de casos por corrida.")

    def handle(self, *args, **options):
        ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado").values("estado")[:1]
        casos = list(
            Formulario.objects.filter(estado=Formulario.Estado.APROBADO)
            .annotate(ultimo_estado=Subquery(ultimo))
            .filter(ultimo_estado=EnvioSIIS.Estado.ERROR)
            .select_related("ciudadano", "relevamiento__convocatoria__segmento__programa", "apoderado_ciudadano")
            .order_by("pk")[: options["limite"]]
        )
        if not casos:
            self.stdout.write("Sin envíos pendientes de reintento.")
            return
        if options["dry_run"]:
            for f in casos:
                dni = f.ciudadano.dni if f.ciudadano_id else "-"
                self.stdout.write(f"[dry-run] caso #{f.pk} · DNI {dni}")
            self.stdout.write(f"{len(casos)} caso(s) a reintentar.")
            return
        catalogos = Catalogos()
        resumen = {}
        for f in casos:
            envio = enviar_beneficiario_a_siis(f, None, catalogos=catalogos)
            resumen[envio.estado] = resumen.get(envio.estado, 0) + 1
            self.stdout.write(f"caso #{f.pk}: {envio.get_estado_display()}")
        detalle = ", ".join(f"{n} {estado.lower()}" for estado, n in sorted(resumen.items()))
        self.stdout.write(self.style.SUCCESS(f"{len(casos)} reintentado(s): {detalle}."))
