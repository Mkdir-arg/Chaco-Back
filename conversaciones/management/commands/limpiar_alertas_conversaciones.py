"""Purga de alertas de conversaciones viejas.

Las alertas se generan con fan-out (una fila por operador por conversación /
mensaje) y sin purga las tablas crecen sin límite. Pensado para cron diario.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from conversaciones.models import HistorialAlertaConversacion, NuevaConversacionAlerta


class Command(BaseCommand):
    help = "Elimina alertas de conversaciones con más de N días (default 30)"

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=30)

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=options["dias"])
        nuevas, _ = NuevaConversacionAlerta.objects.filter(creado__lt=limite).delete()
        historial, _ = HistorialAlertaConversacion.objects.filter(creado__lt=limite).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Purgadas {nuevas} alertas de nueva conversación y {historial} de historial")
        )
