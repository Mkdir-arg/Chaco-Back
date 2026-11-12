"""Siembra el programa EMERGENCIA y su fila de SLA. Idempotente (apto bootstrap).

Reglas de siembra (Cambio 104, igual que ``seed_becas`` y ``seed_dispositivos``):

* El programa se identifica por ``codigo``. Si ya existe **no se le toca nada**: nombre,
  estado, color y orden se editan desde Configuración → Programas y el arranque no los
  revierte.
* La fila de ``SLAEmergencia`` nace con los valores de fábrica del modelo. Si ya existe
  tampoco se toca: lo que el supervisor guardó en E7 sobrevive al arranque.
* No siembra roles: los de la mesa los arma el PM desde el ABM de Roles con las
  capacidades ``emergencia.*``.

Lo llaman ``seed_datos_base`` y ``crear_programas``. La misma fila la crea la migración
``programas.0117`` en los ambientes donde el bootstrap no corre (ECOM).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programas.models import Programa, SLAEmergencia
from programas.services.emergencia_programa import PROGRAMA_EMERGENCIA_CODIGO
from programas.services.programa_cache import invalidar_programa

# Única fuente viva de los datos con que nace el programa. ``programas.0117`` repite los
# literales porque una migración no importa código vivo.
PROGRAMA_EMERGENCIA_DEFAULTS = {
    "nombre": "Emergencia",
    "tipo": Programa.TipoPrograma.EMERGENCIA,
    "descripcion": "Mesa de Emergencia: relevamiento de familias, derivación a dispositivos y entrega de kits.",
    "naturaleza": Programa.Naturaleza.PERSISTENTE,
    "estado": Programa.Estado.ACTIVO,
    "icono": "life-ring",
    "color": "#dc2626",
    "orden": 30,
}


def asegurar_programa_emergencia():
    """Devuelve ``(programa, creado, sla_creada)``. No pisa nada de lo que ya existe.

    Si el programa falta y el nombre «Emergencia» ya lo usa otro, frena con
    ``CommandError``: ``Programa.nombre`` es único, y crear el programa con otro nombre
    taparía en silencio un ambiente con datos inconsistentes.
    """
    programa = Programa.objects.filter(codigo=PROGRAMA_EMERGENCIA_CODIGO).first()
    creado = False
    if programa is None:
        nombre = PROGRAMA_EMERGENCIA_DEFAULTS["nombre"]
        conflicto = Programa.objects.filter(nombre=nombre).values_list("codigo", flat=True).first()
        if conflicto is not None:
            raise CommandError(
                f"No se puede crear el programa «{PROGRAMA_EMERGENCIA_CODIGO}»: el nombre «{nombre}» ya lo usa el "
                f"programa de código «{conflicto}». Corregí el código o el nombre de ese programa y volvé a correr "
                "el arranque."
            )
        programa = Programa.objects.create(codigo=PROGRAMA_EMERGENCIA_CODIGO, **PROGRAMA_EMERGENCIA_DEFAULTS)
        creado = True
    _sla, sla_creada = SLAEmergencia.objects.get_or_create(programa=programa)
    # Quien escribe —o puede haber recreado— un ``Programa`` borra su clave (RED-80). Tolera
    # un cache caído: esto corre en el arranque del contenedor.
    invalidar_programa(PROGRAMA_EMERGENCIA_CODIGO)
    return programa, creado, sla_creada


class Command(BaseCommand):
    help = "Siembra el programa EMERGENCIA y su fila de SLA con los valores de fábrica. Idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        programa, creado, sla_creada = asegurar_programa_emergencia()
        self.stdout.write(("  ✓ " if creado else "  · ") + f"Programa {programa.nombre}")
        self.stdout.write(("  ✓ " if sla_creada else "  · ") + "SLA de Emergencia")
