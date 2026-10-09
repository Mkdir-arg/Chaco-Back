# Notificaciones (análisis 007, RNF-007-01): el rol «Comunicaciones» con las tres
# capacidades del módulo, y las mismas tres para el «Administrador».
#
# Va por migración y no solo por seed porque el entrypoint del contenedor corre `migrate`
# en todos los ambientes y los seeds solo bajo variable de entorno (mismo motivo que
# `users.0025` y `users.0028`). `seed_rbac` crea el mismo rol en una base nueva, donde
# esta migración corre antes de que exista ningún rol.
#
# El rol lleva su clave estable (`RolMeta.clave`, OPS-06 fase 2): el seed lo reconoce
# por la clave y no por el nombre, así renombrarlo desde el ABM no crea un duplicado. Se
# siembra **solo al crearlo**: si ya existía un «Comunicaciones» armado a mano, se le pone
# la clave (si no tenía) y no se le tocan las capacidades ni el estado.
from django.db import migrations

ROL = "Comunicaciones"
CLAVE = "notificaciones.comunicaciones"
ROL_ADMINISTRADOR = "Administrador"
CLAVE_ADMINISTRADOR = "sistema.administrador"
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
    # `get_or_create` y no `get`: en una base donde la 0034 recién declaró las
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
    if not RolMeta.objects.filter(clave=CLAVE).exists():
        grupo, creado = Group.objects.get_or_create(name=ROL)
        meta, _ = RolMeta.objects.get_or_create(
            grupo=grupo,
            defaults={
                "descripcion": DESCRIPCION,
                "categoria": "Backoffice",
                "protegido": False,
                "activo": True,
                "clave": CLAVE,
            },
        )
        if meta.clave is None:
            meta.clave = CLAVE
            meta.save(update_fields=["clave"])
        if creado:
            grupo.permissions.add(*permisos)

    # Rol protegido: la pantalla de Roles no lo deja editar, así que la migración es el
    # único camino para que tenga el módulo nuevo (mismo criterio que `users.0025`). Se lo
    # busca por su clave y, si todavía no la tiene, por el nombre canónico.
    meta_admin = RolMeta.objects.filter(clave=CLAVE_ADMINISTRADOR).select_related("grupo").first()
    administrador = meta_admin.grupo if meta_admin else Group.objects.filter(name=ROL_ADMINISTRADOR).first()
    if administrador is not None:
        administrador.permissions.add(*permisos)


def quitar(apps, schema_editor):
    """Reversa real: las tres capacidades salen de todos los roles.

    Al desaplicar, el módulo ya no está y las capacidades quedan inertes. El rol
    «Comunicaciones» se borra si nadie lo tiene asignado; con usuarios adentro se deja
    (vacío de capacidades y sin la clave) para no sacarle un rol a nadie sin avisar.
    """
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    RolMeta = apps.get_model("users", "RolMeta")

    codenames = [codename for codename, _ in CAPACIDADES]
    permisos = list(Permission.objects.filter(content_type__app_label="users", codename__in=codenames))
    for grupo in Group.objects.filter(permissions__in=permisos).distinct():
        grupo.permissions.remove(*permisos)
    meta = RolMeta.objects.filter(clave=CLAVE).select_related("grupo").first()
    if meta is None:
        return
    if meta.grupo.user_set.exists():
        RolMeta.objects.filter(pk=meta.pk).update(clave=None)
    else:
        meta.grupo.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0034_capacidades_notificaciones"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
