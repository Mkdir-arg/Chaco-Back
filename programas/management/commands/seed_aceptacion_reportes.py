"""Datos sintéticos e idempotentes para aceptar Dispositivos y Merenderos.

De Dispositivos queda el **padrón**: el tipo y el legajo institucional. La parte de
camas, admisión y parte diario se fue con los modelos que la sostenían (MVP v2,
release A) y vuelve con `Plaza`, `Estadia` y `Turno`.
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from programas.models import (
    Dispositivo,
    EntregaMercaderia,
    Merendero,
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
            defaults={"nombre": "Aceptación Plan 183", "maneja_camas": True, "activo": True},
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
        merendero, _ = Merendero.objects.update_or_create(
            codigo="ACEP-183-MER",
            defaults={
                "nombre": "Merendero sintético de aceptación",
                "domicilio": "Calle de prueba 184",
                "responsable_nombre": "Equipo de aceptación",
                "estado": Merendero.Estado.ACTIVO,
            },
        )
        EntregaMercaderia.objects.update_or_create(
            merendero=merendero,
            fecha=timezone.localdate(),
            defaults={"cantidad_kits": 10, "servicio": "Merienda", "responsable_receptor": "Equipo de aceptación"},
        )
        self.stdout.write(self.style.SUCCESS("Datos sintéticos de aceptación para Plan 183 listos."))
