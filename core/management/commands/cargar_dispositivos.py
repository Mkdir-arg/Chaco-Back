from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga los dispositivos desde los fixtures"

    def handle(self, *args, **options):
        self.stdout.write("Cargando dispositivos desde fixtures...")

        try:
            # Cargar fixtures en orden
            call_command("loaddata", "localidad_municipio_provincia.json")
            call_command("loaddata", "dispositivos.json")

            self.stdout.write(self.style.SUCCESS("Dispositivos cargados exitosamente"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al cargar dispositivos: {e}"))
