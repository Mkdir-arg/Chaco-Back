"""Pasada periódica de generación de alertas de ciudadanos.

Reemplaza la generación on-the-fly que corría en cada GET del detalle de
ciudadano (con escrituras y WebSocket en el request path). Pensado para cron
(p. ej. cada hora): cubre las alertas por tiempo transcurrido (sin contacto,
sin evaluación) y la desactivación de alertas MEDIA/BAJA que ya no aplican.
"""

from django.core.management.base import BaseCommand

from legajos.models import Ciudadano
from legajos.services.alertas import AlertasService


class Command(BaseCommand):
    help = "Genera/reconcilia las alertas de todos los ciudadanos activos"

    def handle(self, *args, **options):
        total_alertas = 0
        ciudadanos = Ciudadano.objects.filter(activo=True).values_list("id", flat=True)
        for ciudadano_id in ciudadanos.iterator():
            total_alertas += len(AlertasService.generar_alertas_ciudadano(ciudadano_id))
        self.stdout.write(self.style.SUCCESS(f"Alertas activas tras la pasada: {total_alertas}"))
