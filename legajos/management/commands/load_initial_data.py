from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga todos los datos iniciales del sistema"

    def handle(self, *args, **options):
        self.stdout.write("Cargando datos iniciales...")

        # 1. Cargar programas ciudadanos
        try:
            self.stdout.write("  → Cargando programas ciudadanos...")
            call_command("loaddata", "legajos/fixtures/programas_initial.json", verbosity=0)
            self.stdout.write(self.style.SUCCESS("    ✓ Programas ciudadanos cargados"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    ⚠ Programas ciudadanos ya existen o error: {e}"))

        # 1b. Crear programas institucionales
        try:
            self.stdout.write("  → Creando programas institucionales...")
            call_command("crear_programas", verbosity=0)
            self.stdout.write(self.style.SUCCESS("    ✓ Programas institucionales creados"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    ⚠ Programas institucionales: {e}"))

        # 2. Otros fixtures si existen
        try:
            self.stdout.write("  → Cargando contactos iniciales...")
            call_command("loaddata", "contactos_initial_data", verbosity=0)
            self.stdout.write(self.style.SUCCESS("    ✓ Contactos cargados"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    ⚠ Contactos: {e}"))

        self.stdout.write(self.style.SUCCESS("\n✓ Datos iniciales cargados correctamente"))
