"""Pasada periódica de generación de alertas de ciudadanos.

Reemplaza la generación on-the-fly que corría en cada GET del detalle de
ciudadano (con escrituras y WebSocket en el request path). Pensado para cron
(p. ej. cada hora): cubre las alertas por tiempo transcurrido (sin contacto,
sin evaluación) y el cierre de las alertas MEDIA/BAJA que ya no aplican.

El trabajo está en :meth:`AlertasService.reconciliar_alertas`, que **reconcilia** en
vez de recrear (LEG-01) y recorre los legajos enlazados, no los 20.000 ciudadanos sin
legajo (PERF-20). El comando solo informa el resultado.
"""

from django.core.management.base import BaseCommand

from legajos.services.alertas import AlertasService


class Command(BaseCommand):
    help = "Reconcilia las alertas de los legajos enlazados a ciudadanos activos"

    def handle(self, *args, **options):
        resumen = AlertasService.reconciliar_alertas()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas activas tras la pasada: {resumen['vigentes']} "
                f"({resumen['creadas']} nuevas, {resumen['refrescadas']} con el mensaje al día, "
                f"{resumen['cerradas']} cerradas, {resumen['legajos']} legajos revisados)"
            )
        )
