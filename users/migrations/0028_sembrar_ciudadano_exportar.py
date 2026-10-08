# SEC-20 / D-20 (auditoría oct-2026): quién arranca con `ciudadano.exportar`.
#
# DECISIÓN CLIENTE (D-20, decidida por el PM el 08-oct-2026): la exportación masiva del
# padrón es una capacidad propia, sembrada a **todo rol que tenga `ciudadano.ver`**. El
# «Operador de backoffice» conserva la exportación: nadie pierde nada el día del deploy.
# Lo que cambia es que la capacidad queda separada del ver, así que de acá en adelante se
# puede quitar rol por rol desde el ABM de Roles, sin deploy.
#
# La migración **solo agrega** filas en `auth_group_permissions`: no le quita ninguna
# capacidad a nadie y, con este criterio, tampoco deja a ningún rol con menos acceso del
# que tenía (la vista exige la capacidad nueva, y la tienen todos los que antes
# alcanzaban con `ciudadano.ver`).
#
# Va por migración y no por seed porque el entrypoint del contenedor corre `migrate`
# en todos los ambientes y los seeds solo bajo variable de entorno (mismo motivo que
# `users.0025`).
import logging

from django.db import migrations

CODENAME_NUEVA = "ciudadano_exportar"
NOMBRE_NUEVA = "Exportar el padrón de ciudadanos"
CODENAME_LECTURA = "ciudadano_ver"

logger = logging.getLogger(__name__)


def _permiso(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    # `get_or_create` y no `get`: en una base donde la 0027 recién declaró la
    # capacidad, el `post_migrate` que materializa los permisos todavía no corrió.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    permiso, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=CODENAME_NUEVA,
        defaults={"name": NOMBRE_NUEVA},
    )
    return permiso


def sembrar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    permiso = _permiso(apps)
    con_lectura = list(Group.objects.filter(permissions__codename=CODENAME_LECTURA).distinct())
    for grupo in con_lectura:
        grupo.permissions.add(permiso)

    if con_lectura:
        logger.info(
            "SEC-20 / D-20: «%s» quedó tildada en los roles que ven ciudadanos, así que "
            "ninguno pierde la exportación: %s. Para sacársela a alguno, destildala en el "
            "ABM de Roles (no hace falta deploy).",
            NOMBRE_NUEVA,
            ", ".join(grupo.name for grupo in con_lectura),
        )


def quitar(apps, schema_editor):
    """Reversa real: la capacidad se va de todos los roles.

    Al desaplicar, el código que la exige ya no está y la capacidad queda inerte, así
    que dejarla tildada solo ensucia el ABM. Lo que no se puede distinguir es un tilde
    hecho a mano después del deploy: si alguien se la dio a un rol que no tiene
    `ciudadano.ver`, al revertir se pierde y hay que volver a tildarla (al reaplicar,
    la siembra vuelve a salir de `ciudadano.ver`).
    """
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    permiso = Permission.objects.filter(content_type__app_label="users", codename=CODENAME_NUEVA).first()
    if permiso is None:
        return
    for grupo in Group.objects.filter(permissions=permiso).distinct():
        grupo.permissions.remove(permiso)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0027_capacidad_ciudadano_exportar"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
