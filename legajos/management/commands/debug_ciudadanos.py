from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Q

from legajos.models import Ciudadano


class Command(BaseCommand):
    help = "Debug ciudadanos en la base de datos"

    def handle(self, *args, **options):
        self.stdout.write("=== DEBUG CIUDADANOS ===")

        # Contar todos los ciudadanos
        total = Ciudadano.objects.count()
        self.stdout.write(f"Total ciudadanos: {total}")

        # Contar ciudadanos activos
        activos = Ciudadano.objects.filter(activo=True).count()
        self.stdout.write(f"Ciudadanos activos: {activos}")

        # Ciudadanos que deberían aparecer en la lista
        visibles = (
            Ciudadano.objects.filter(activo=True)
            .exclude(Q(dni="00000000") | Q(apellido__icontains="Institución") | Q(nombre__icontains="Institución"))
            .count()
        )
        self.stdout.write(f"Ciudadanos visibles en lista: {visibles}")

        # Últimos 3 ciudadanos
        self.stdout.write("\n=== ÚLTIMOS 3 CIUDADANOS ===")
        for c in Ciudadano.objects.order_by("-creado")[:3]:
            self.stdout.write(f"- {c.dni}: {c.nombre} {c.apellido} (activo: {c.activo})")

        # Limpiar cache
        self.stdout.write("\nLimpiando cache...")
        cache.clear()
        self.stdout.write("Cache limpiado")
