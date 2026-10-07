from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.management.guardas import exigir_entorno_demo
from programas.models import AsignacionTerritorial, Convocatoria, Relevamiento, Segmento


class Command(BaseCommand):
    help = "Crea dos relevamientos locales para probar períodos desde Mobile."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="territorial_demo")
        parser.add_argument("--password", default="demo1234")

    @transaction.atomic
    def handle(self, *args, **options):
        exigir_entorno_demo("seed_relevamientos_periodo_demo")
        call_command("seed_becas", verbosity=0)
        hoy = timezone.localdate()

        segmento, _ = Segmento.objects.get_or_create(
            nombre="Demo períodos Mobile",
            defaults={"descripcion": "Datos locales de prueba", "cupo_maximo": 100, "activo": True},
        )
        convocatoria, _ = Convocatoria.objects.update_or_create(
            nombre="Convocatoria demo — períodos Mobile",
            defaults={
                "segmento": segmento,
                "fecha_inicio": hoy - timedelta(days=7),
                "fecha_fin": hoy + timedelta(days=14),
                "descripcion": "Convocatoria local para verificar relevamientos de uno y varios días.",
                "activo": True,
            },
        )

        User = get_user_model()
        username = options["username"]
        password = options["password"]
        territorial, creado = User.objects.get_or_create(username=username, defaults={"is_active": True})
        if creado:
            territorial.set_password(password)
            territorial.save(update_fields=["password"])
        else:
            # OPS-02: pisarle la clave (y reactivar) a una cuenta que ya existe es
            # justo el daño del comando que este PR borró. Si el usuario ya está,
            # el seed siembra los relevamientos y deja la cuenta como está.
            self.stdout.write(
                self.style.WARNING(f"El usuario «{username}» ya existía: no se le toca la clave ni el estado.")
            )
        grupo = Group.objects.filter(name__icontains="Becas").filter(name__icontains="Territorial").first()
        if grupo:
            territorial.groups.add(grupo)
        AsignacionTerritorial.objects.update_or_create(territorial=territorial, defaults={"segmento": segmento})

        ejemplos = (
            ("Zona Centro — operativo de varios días", hoy - timedelta(days=1), hoy + timedelta(days=2)),
            ("Barrio Norte — operativo de un día", hoy + timedelta(days=3), hoy + timedelta(days=3)),
        )
        for zona, desde, hasta in ejemplos:
            Relevamiento.objects.update_or_create(
                convocatoria=convocatoria,
                territorial=territorial,
                zona=zona,
                defaults={
                    "fecha_asignada": desde,
                    "fecha_hasta": hasta,
                    "estado": Relevamiento.Estado.ASIGNADO,
                    "observaciones": "Ejemplo local creado para probar Mobile.",
                    "fecha_finalizado": None,
                },
            )

        self.stdout.write(self.style.SUCCESS(f"Ejemplos creados. Usuario: {username} | 2 relevamientos"))
