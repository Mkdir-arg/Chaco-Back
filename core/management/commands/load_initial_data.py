"""
Carga los catálogos de referencia base del sistema.

Uso:
    python manage.py load_initial_data

Carga los siguientes fixtures de datos de referencia (idempotente por PK):
    - core/fixtures/sexo.json                          → core.Sexo
    - core/fixtures/dia.json                            → core.Dia
    - core/fixtures/mes.json                            → core.Mes
    - core/fixtures/localidad_municipio_provincia.json  → core.Localidad
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga los catálogos de referencia base (sexo, día, mes, localidades)."

    FIXTURES = [
        "core/fixtures/sexo.json",
        "core/fixtures/dia.json",
        "core/fixtures/mes.json",
        "core/fixtures/localidad_municipio_provincia.json",
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Cargando catálogos de referencia..."))
        for fixture in self.FIXTURES:
            try:
                call_command("loaddata", fixture, verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"  ✓ {fixture}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ {fixture}: {e}"))
        self.stdout.write(self.style.SUCCESS("Catálogos de referencia cargados."))
