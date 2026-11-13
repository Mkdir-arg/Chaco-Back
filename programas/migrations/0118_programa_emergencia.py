"""Crea el programa EMERGENCIA (módulo Emergencia, PR 1).

Va por migración y no solo por el seed por el mismo motivo que `programas.0012`: en ECOM
el bootstrap del arranque no corre, y sin la fila `Programa` las capacidades
`emergencia.*` —que se evalúan con alcance sobre este programa— no se pueden ni otorgar
(el ABM de Roles no tiene programa que ofrecer) ni evaluar.

Idempotente: se identifica por `codigo`. Si el programa ya existe no se le toca nada
(Cambio 104: nombre, estado, color y orden son de Configuración → Programas). Los
literales repiten `PROGRAMA_EMERGENCIA_DEFAULTS` de `seed_emergencia` a propósito: una
migración no importa código vivo.

La fila de `SLAEmergencia` no se crea acá: la crea `sla_vigente()` con los `DEFAULT` del
modelo la primera vez que alguien la lee, y el seed en los ambientes donde corre.
"""

import logging

from django.db import migrations

CODIGO = "EMERGENCIA"
DATOS = {
    "nombre": "Emergencia",
    "tipo": "EMERGENCIA",
    "descripcion": "Mesa de Emergencia: relevamiento de familias, derivación a dispositivos y entrega de kits.",
    "naturaleza": "PERSISTENTE",
    "estado": "ACTIVO",
    "icono": "life-ring",
    "color": "#dc2626",
    "orden": 30,
}

logger = logging.getLogger(__name__)


def crear_programa(apps, schema_editor):
    Programa = apps.get_model("programas", "Programa")

    if Programa.objects.filter(codigo=CODIGO).exists():
        return
    conflicto = Programa.objects.filter(nombre=DATOS["nombre"]).values_list("codigo", flat=True).first()
    if conflicto is not None:
        raise RuntimeError(
            f'No se puede crear Programa(codigo="{CODIGO}"): el nombre "{DATOS["nombre"]}" '
            f'pertenece al código "{conflicto}".'
        )
    Programa.objects.create(codigo=CODIGO, **DATOS)


def borrar_programa_si_esta_vacio(apps, schema_editor):
    """Reversa: borra el programa **solo si no le cuelga nada**.

    Mira todas las relaciones que apuntan a `Programa` en el estado de esta migración
    (roles con `RolMeta.programa`, trazas de configuración, inscripciones…). Con una sola
    fila colgando el programa queda donde está y se avisa por log: borrarlo arrastraría por
    CASCADE lo cargado debajo, o chocaría con un PROTECT a mitad de la reversa. La única
    excepción es su fila de `SLAEmergencia`, que es configuración del propio programa y se
    va con él (sin trazas no tiene nada que no sean los valores de fábrica).
    """
    Programa = apps.get_model("programas", "Programa")
    SLAEmergencia = apps.get_model("programas", "SLAEmergencia")

    programa = Programa.objects.filter(codigo=CODIGO).first()
    if programa is None:
        return
    ocupadas = []
    for relacion in Programa._meta.related_objects:
        if relacion.related_model is SLAEmergencia:
            continue
        if relacion.related_model._base_manager.filter(**{relacion.field.name: programa.pk}).exists():
            ocupadas.append(relacion.related_model._meta.label)
    if ocupadas:
        logger.warning(
            "programas.0118 (reversa): el programa %s no se borra, tiene filas en %s.",
            CODIGO,
            ", ".join(sorted(ocupadas)),
        )
        return
    SLAEmergencia.objects.filter(programa=programa).delete()
    programa.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0117_emergencia_base"),
        # `users.RolMeta.programa` ya está en el estado (lo trae `programas.0115`), así que
        # la reversa ve los roles del programa sin declarar otra dependencia.
    ]

    operations = [
        migrations.RunPython(crear_programa, borrar_programa_si_esta_vacio),
    ]
