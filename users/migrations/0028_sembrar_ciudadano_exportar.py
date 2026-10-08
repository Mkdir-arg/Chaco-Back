# SEC-20 / D-20 (auditoría oct-2026): quién arranca con `ciudadano.exportar`.
#
# DECISIÓN CLIENTE (D-20, README §2 de la auditoría): la exportación masiva del padrón
# es una capacidad propia, sembrada a los roles que ya tienen `ciudadano.editar`.
#
# La migración **solo agrega** filas en `auth_group_permissions`: no le quita ninguna
# capacidad a nadie y no puede dejar a un rol con menos acceso del que tenía. Lo que sí
# cambia —y es el objetivo de la ficha— es que la vista pasa a exigir la capacidad
# nueva: un rol con `ciudadano.ver` y sin `ciudadano.editar` (el «Operador de
# backoffice» sembrado, que ni siquiera da altas) deja de poder bajarse el padrón
# completo. Si el organismo quiere devolvérselo, es un tilde en el ABM de Roles, sin
# deploy: por eso la migración **lista en el log** los roles en esa situación.
#
# Va por migración y no por seed porque el entrypoint del contenedor corre `migrate`
# en todos los ambientes y los seeds solo bajo variable de entorno (mismo motivo que
# `users.0025`).
import logging

from django.db import migrations

CODENAME_NUEVA = "ciudadano_exportar"
NOMBRE_NUEVA = "Exportar el padrón de ciudadanos"
CODENAME_ORIGEN = "ciudadano_editar"
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
    con_alta = list(Group.objects.filter(permissions__codename=CODENAME_ORIGEN).distinct())
    for grupo in con_alta:
        grupo.permissions.add(permiso)

    solo_lectura = (
        Group.objects.filter(permissions__codename=CODENAME_LECTURA)
        .exclude(permissions__codename=CODENAME_ORIGEN)
        .distinct()
    )
    nombres = list(solo_lectura.values_list("name", flat=True))
    if nombres:
        logger.warning(
            "SEC-20: estos roles ven ciudadanos pero no los editan, así que NO reciben "
            "«%s» y pierden la exportación del padrón: %s. Si alguno tiene que seguir "
            "exportando, tildale la capacidad en el ABM de Roles.",
            NOMBRE_NUEVA,
            ", ".join(nombres),
        )


def quitar(apps, schema_editor):
    """Reversa real: la capacidad se va de todos los roles.

    Al desaplicar, el código que la exige ya no está y la capacidad queda inerte, así
    que dejarla tildada solo ensucia el ABM. Lo que no se puede distinguir es un tilde
    hecho a mano después del deploy: si alguien se la dio a un rol que no tiene
    `ciudadano.editar`, al revertir se pierde y hay que volver a tildarla (al reaplicar,
    la siembra vuelve a salir de `ciudadano.editar`).
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
