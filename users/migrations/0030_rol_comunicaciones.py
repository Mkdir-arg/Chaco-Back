# Notificaciones (análisis 007, RNF-007-01): el rol «Comunicaciones» con las tres
# capacidades del módulo, y las mismas tres para el «Administrador».
#
# Va por migración y no solo por seed porque el entrypoint del contenedor corre `migrate`
# en todos los ambientes y los seeds solo bajo variable de entorno (mismo motivo que
# `users.0025` y `users.0028`). `seed_rbac` crea el mismo rol en una base nueva, donde
# esta migración corre antes de que exista ningún rol.
#
# El rol se siembra **solo al crearlo**: si ya existe un «Comunicaciones» armado a mano,
# no se le tocan las capacidades ni el estado.
from django.db import migrations

ROL = "Comunicaciones"
ROL_ADMINISTRADOR = "Administrador"
DESCRIPCION = (
    "Arma, prueba y envía campañas de correo masivo desde Notificaciones: lista de "
    "destinatarios en Excel y cuerpo en HTML."
)
CAPACIDADES = (
    ("notificacion_ver", "Ver campañas de correo y su resultado"),
    ("notificacion_gestionar", "Crear, editar, duplicar y eliminar campañas de correo, y mandar pruebas"),
    ("notificacion_enviar", "Enviar, detener y reanudar campañas de correo"),
)


def _permisos(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    # `get_or_create` y no `get`: en una base donde la 0029 recién declaró las
    # capacidades, el `post_migrate` que materializa los permisos todavía no corrió.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    return [
        Permission.objects.get_or_create(content_type=content_type, codename=codename, defaults={"name": nombre})[0]
        for codename, nombre in CAPACIDADES
    ]


def sembrar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    RolMeta = apps.get_model("users", "RolMeta")

    permisos = _permisos(apps)
    grupo, creado = Group.objects.get_or_create(name=ROL)
    RolMeta.objects.get_or_create(
        grupo=grupo,
        defaults={"descripcion": DESCRIPCION, "categoria": "Backoffice", "protegido": False, "activo": True},
    )
    if creado:
        grupo.permissions.add(*permisos)

    administrador = Group.objects.filter(name=ROL_ADMINISTRADOR).first()
    if administrador is not None:
        # Rol protegido: la pantalla de Roles no lo deja editar, así que la migración es
        # el único camino para que tenga el módulo nuevo (mismo criterio que `users.0025`).
        administrador.permissions.add(*permisos)


def quitar(apps, schema_editor):
    """Reversa real: las tres capacidades salen de todos los roles.

    Al desaplicar, el módulo ya no está y las capacidades quedan inertes. El rol
    «Comunicaciones» se borra si nadie lo tiene asignado; con usuarios adentro se deja
    (vacío de capacidades) para no sacarle un rol a nadie sin avisar.
    """
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    codenames = [codename for codename, _ in CAPACIDADES]
    permisos = list(Permission.objects.filter(content_type__app_label="users", codename__in=codenames))
    for grupo in Group.objects.filter(permissions__in=permisos).distinct():
        grupo.permissions.remove(*permisos)
    grupo = Group.objects.filter(name=ROL).first()
    if grupo is not None and not grupo.user_set.exists():
        grupo.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0029_capacidades_notificaciones"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
