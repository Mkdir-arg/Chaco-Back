# El rol protegido «Administrador» recibe `inspeccion.asignar` y `becas.revision.identidad`.
#
# Va por migración porque el rol es protegido (el ABM de Roles no lo deja editar) y en ECOM
# el `seed_rbac` del arranque no corre: las migraciones `users.0037` y `users.0038`
# declararon las capacidades y delegaron la siembra al seed, así que el Administrador
# quedó sin ellas (mismo motivo que `users.0025` y `users.0035`). Síntoma: no veía
# «Programas → Dispositivos → Relevamientos».
#
# Solo esas dos, a propósito:
# - `inspeccion.relevar` NO: es capacidad de la app de campo; un Administrador global nunca
#   es asignable a un relevamiento (`agentes_asignables` exige un rol del programa) y solo
#   le sumaría poder sacar token de la app.
# - No se realinea con todo el catálogo: es un arreglo puntual.
# No toca ningún otro rol.
import logging

from django.db import migrations

ROL_ADMINISTRADOR = "Administrador"
CLAVE_ADMINISTRADOR = "sistema.administrador"
CAPACIDADES = (
    ("inspeccion_asignar", "Crear, asignar, reasignar y cancelar relevamientos edilicios"),
    (
        "becas_revision_identidad",
        "Validar la identidad de un caso: revalidar RENAPER, forzar identidad, validar padrón y corregir género",
    ),
)

logger = logging.getLogger(__name__)


def _permisos(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    # `get_or_create` y no `get`: en una base que migra de corrido el `post_migrate` que
    # materializa las capacidades todavía no corrió.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    return [
        Permission.objects.get_or_create(content_type=content_type, codename=codename, defaults={"name": nombre})[0]
        for codename, nombre in CAPACIDADES
    ]


def _administrador(apps):
    """El grupo del Administrador: por su clave estable y, si nadie la tiene, por el nombre."""
    Group = apps.get_model("auth", "Group")
    RolMeta = apps.get_model("users", "RolMeta")

    meta = RolMeta.objects.filter(clave=CLAVE_ADMINISTRADOR).select_related("grupo").first()
    if meta is not None:
        return meta.grupo
    return Group.objects.filter(name=ROL_ADMINISTRADOR).first()


def sembrar(apps, schema_editor):
    administrador = _administrador(apps)
    if administrador is None:
        # Base nueva: `seed_rbac` crea el Administrador con todo el catálogo.
        return

    permisos = _permisos(apps)
    tiene = set(administrador.permissions.values_list("pk", flat=True))
    faltan = [permiso for permiso in permisos if permiso.pk not in tiene]
    if faltan:
        administrador.permissions.add(*faltan)
    logger.info(
        "Administrador «%s»: sumó %s; ya tenía %s.",
        administrador.name,
        ", ".join(permiso.codename for permiso in faltan) or "ninguna",
        ", ".join(permiso.codename for permiso in permisos if permiso.pk in tiene) or "ninguna",
    )


def quitar(apps, schema_editor):
    """Reversa real: las dos capacidades salen **solo** del Administrador.

    No borra las filas de `Permission` (son de `users.0037`/`users.0038`) ni toca otros
    roles, que las conservan. Lo que no se distingue: en una base donde `seed_rbac` ya se
    las había dado, revertir se las saca hasta el próximo `seed_rbac` del arranque, que las
    devuelve; en ECOM, donde no corre, se vuelve exactamente al estado anterior.
    """
    administrador = _administrador(apps)
    if administrador is None:
        return
    Permission = apps.get_model("auth", "Permission")
    codenames = [codename for codename, _ in CAPACIDADES]
    permisos = list(Permission.objects.filter(content_type__app_label="users", codename__in=codenames))
    administrador.permissions.remove(*permisos)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0039_etiqueta_becas_convocatoria_ver"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
