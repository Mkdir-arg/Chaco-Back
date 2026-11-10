"""Datos sintéticos e idempotentes para aceptar Dispositivos.

De Dispositivos queda el **padrón**: el tipo y el legajo institucional. La parte de
camas, admisión y parte diario se fue con los modelos que la sostenían (MVP v2,
release A) y vuelve con `Plaza`, `Estadia` y `Turno`.
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from programas.models import (
    Dispositivo,
    Programa,
    TipoDispositivo,
)

ACCEPTANCE_DATABASE_NAME = "chaco_acceptance"


def _es_base_aceptacion():
    if connection.vendor != "mysql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        return cursor.fetchone()[0] == ACCEPTANCE_DATABASE_NAME


class Command(BaseCommand):
    help = "Siembra datos sintéticos de aceptación para los reportes de Programas."

    @transaction.atomic
    def handle(self, *args, **options):
        if os.environ.get("CHACO_ACCEPTANCE_SEED") != "1" or not _es_base_aceptacion():
            raise CommandError("Este seed solo se puede ejecutar desde el entorno de aceptación aislado.")
        Programa.objects.get_or_create(
            codigo=Programa.TipoPrograma.DISPOSITIVOS,
            defaults={"nombre": "Dispositivos", "estado": Programa.Estado.ACTIVO},
        )

        tipo, _ = TipoDispositivo.objects.update_or_create(
            codigo="ACEP-183",
            defaults={
                "nombre": "Aceptación Plan 183",
                "maneja_camas": True,
                "tipos_plaza_admitidos": ["CAMA"],
                "activo": True,
            },
        )
        Dispositivo.objects.update_or_create(
            codigo="ACEP-183-DIS",
            defaults={
                "nombre": "Dispositivo sintético de aceptación",
                "tipo": tipo,
                "domicilio": "Calle de prueba 183",
                "localidad": "Resistencia",
                "responsable_nombre": "Equipo de aceptación",
                "estado": Dispositivo.Estado.ACTIVO,
            },
        )
        self.stdout.write(self.style.SUCCESS("Datos sintéticos de aceptación para Plan 183 listos."))
