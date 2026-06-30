from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crear grupos necesarios para el sistema de legajos"

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name="Responsable")
        if created:
            self.stdout.write(self.style.SUCCESS('Grupo "Responsable" creado exitosamente'))
        else:
            self.stdout.write(self.style.WARNING('Grupo "Responsable" ya existe'))
