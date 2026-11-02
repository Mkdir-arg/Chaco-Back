"""Cambio 410: el Equipo nace de las asignaciones de rol vigentes.

Por cada ``AsignacionDispositivo`` activa se crea un ``MiembroEquipoDispositivo`` para cada
usuario que tiene ese rol, para que nadie pierda acceso. Se **saltea** el rol de agente de
relevamiento (``RolMeta.clave == dispositivos.agente_relevamiento``): los agentes siguen con la
asignación de siempre (``programas.services.inspecciones``) y no son parte del Equipo.

Idempotente: ``get_or_create`` sobre la clave única. La asignación vieja no se toca.
"""

from django.db import migrations

CLAVE_ROL_AGENTE = "dispositivos.agente_relevamiento"


def crear_equipo(apps, schema_editor):
    Asignacion = apps.get_model("programas", "AsignacionDispositivo")
    Miembro = apps.get_model("programas", "MiembroEquipoDispositivo")
    User = apps.get_model("auth", "User")

    asignaciones = (
        Asignacion.objects.filter(activo=True).exclude(rol__meta__clave=CLAVE_ROL_AGENTE).select_related("rol")
    )
    for asignacion in asignaciones:
        for usuario in User.objects.filter(groups=asignacion.rol):
            Miembro.objects.get_or_create(
                dispositivo_id=asignacion.dispositivo_id,
                usuario=usuario,
                rol_id=asignacion.rol_id,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0110_miembro_equipo_dispositivo"),
        ("users", "0044_sembrar_rol_agente_dispositivos"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            crear_equipo,
            # REVERSA-NOOP: deshacerla dejaría filas del Equipo que no se pueden distinguir de las
            # cargadas a mano después; son inocuas (la asignación vieja sigue vigente) y volver
            # atrás la 0110 borra la tabla entera.
            migrations.RunPython.noop,
        ),
    ]
