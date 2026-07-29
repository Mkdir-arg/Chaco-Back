"""Datos sintéticos e idempotentes para aceptar Dispositivos y Merenderos."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Admision,
    Cama,
    CampoTipoDispositivo,
    Dispositivo,
    EntregaMercaderia,
    Merendero,
    RegistroDiario,
    TipoDispositivo,
)


class Command(BaseCommand):
    help = "Siembra datos sintéticos de aceptación para indicadores y reportes de Programas."

    @transaction.atomic
    def handle(self, *args, **options):
        usuario, creado = get_user_model().objects.get_or_create(
            username="aceptacion_plan_183",
            defaults={"is_active": True, "is_staff": True},
        )
        if creado:
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])

        tipo, _ = TipoDispositivo.objects.update_or_create(
            codigo="ACEP-183",
            defaults={"nombre": "Aceptación Plan 183", "maneja_camas": True, "activo": True},
        )
        campo, _ = CampoTipoDispositivo.objects.update_or_create(
            tipo_dispositivo=tipo,
            seccion="Aceptación",
            nombre="Documento de prueba",
            defaults={"tipo_campo": "STRING", "obligatorio": True, "orden": 1},
        )
        dispositivo, _ = Dispositivo.objects.update_or_create(
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
        cama_ocupada, _ = Cama.objects.update_or_create(
            dispositivo=dispositivo,
            codigo="ACEP-01",
            defaults={"estado": Cama.Estado.OCUPADA},
        )
        Cama.objects.update_or_create(
            dispositivo=dispositivo,
            codigo="ACEP-02",
            defaults={"estado": Cama.Estado.DISPONIBLE},
        )
        ciudadano, _ = Ciudadano.objects.update_or_create(
            dni="99000183",
            defaults={"nombre": "Persona", "apellido": "Aceptación"},
        )
        Admision.objects.update_or_create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            defaults={
                "cama": cama_ocupada,
                "fecha_ingreso": timezone.now(),
                "estado": Admision.Estado.ALOJADO,
                "respuestas_f00": {str(campo.pk): "Completo"},
            },
        )
        RegistroDiario.objects.update_or_create(
            dispositivo=dispositivo,
            fecha=timezone.localdate(),
            turno=RegistroDiario.Turno.MANIANA,
            defaults={"firmado_por": usuario},
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
