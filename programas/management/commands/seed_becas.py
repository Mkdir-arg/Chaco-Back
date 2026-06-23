"""Seed idempotente del Programa Becas.

Crea/asegura, sin duplicar al repetirse:
1. La instancia genérica ``Programa(codigo="BECAS")`` que ancla el alcance del
   RBAC (roles de categoría "Programa") y la futura solapa del legajo.
2. Los adjuntos obligatorios fijos del formulario, modelados como
   ``PreguntaGlobal`` tipo ARCHIVO (#73 / §7.1 del análisis).

Ejecutar tras ``migrate`` (y tras ``seed_rbac`` si se quieren los roles)::

    python manage.py seed_becas
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from programas.models import PreguntaGlobal, Programa, TipoCampo

PROGRAMA_BECAS_CODIGO = "BECAS"

# Adjuntos obligatorios fijos (no configurables). El CUIL lo autocompleta RENAPER
# y el CBU es opcional, por eso no se precargan acá.
ADJUNTOS_OBLIGATORIOS = [
    ("Foto DNI - Frente", 101),
    ("Foto DNI - Dorso", 102),
    ("Certificado de domicilio", 103),
    ("Constancia de estudios", 104),
    ("Convenio de confidencialidad / uso de imagen", 105),
]


def asegurar_programa_becas():
    """Devuelve la instancia genérica del Programa Becas (la crea si falta)."""
    programa, _ = Programa.objects.get_or_create(
        codigo=PROGRAMA_BECAS_CODIGO,
        defaults={
            "nombre": "Becas",
            "tipo": "BECAS",
            "descripcion": "Programa de Becas: relevamiento territorial y asignación de cupos.",
            "naturaleza": Programa.Naturaleza.PERSISTENTE,
            "estado": Programa.Estado.ACTIVO,
            "icono": "school",
            "color": "#0ea5e9",
        },
    )
    return programa


def asegurar_adjuntos_obligatorios():
    """Crea las PreguntaGlobal tipo ARCHIVO obligatorias fijas (idempotente)."""
    creados = 0
    for texto, orden in ADJUNTOS_OBLIGATORIOS:
        _, created = PreguntaGlobal.objects.get_or_create(
            texto=texto,
            defaults={
                "tipo": TipoCampo.ARCHIVO,
                "opciones": None,
                "activo": True,
                "obligatorio": True,
                "orden": orden,
            },
        )
        creados += int(created)
    return creados


class Command(BaseCommand):
    help = "Siembra el Programa Becas (programa genérico + adjuntos obligatorios). Idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Becas ===\n"))

        programa = asegurar_programa_becas()
        self.stdout.write(self.style.SUCCESS(f"  ✓ Programa: {programa.nombre} ({programa.codigo})"))

        creados = asegurar_adjuntos_obligatorios()
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Adjuntos obligatorios asegurados ({creados} nuevos, "
                f"{len(ADJUNTOS_OBLIGATORIOS)} totales)"
            )
        )

        self.stdout.write(self.style.SUCCESS("\nSeed Becas completo."))
