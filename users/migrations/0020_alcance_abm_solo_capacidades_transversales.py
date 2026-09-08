from django.db import migrations

# `becas.programa.administrar` dejó de conferir alcance sobre los ABM de Usuarios y
# Roles: ese alcance ahora lo dan únicamente las dos capacidades transversales, así
# que se le puede quitar a un rol sin desarmarle el dominio del programa. La paraguas
# se conserva —sigue habilitando reportes, RENAPER, pausas y el alta de coordinadores
# de Becas—, solo pierde ese doble rol.
#
# Los roles que la tenían reciben las dos capacidades para no perder lo que venían
# haciendo. Sin este traspaso el Administrador de Becas no solo perdería los ABM:
# `users.selectors.usuarios.es_gestor_territorial` lo tomaría por gestor territorial
# (define el alcance territorial por exclusión: tiene `becas.usuario.territorial` y
# no administra ningún programa) y el listado le quedaría vacío en silencio, porque
# un administrador no coordina segmentos.
PARAGUAS = "becas_programa_administrar"
TRANSVERSALES = [
    ("programa_usuario_administrar", "Administrar los usuarios de su programa"),
    ("programa_rol_administrar", "Administrar los roles de su programa"),
]


def traspasar_alcance(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    nuevos = []
    for codename, nombre in TRANSVERSALES:
        permiso, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": nombre},
        )
        nuevos.append(permiso)

    paraguas = Permission.objects.filter(
        content_type__app_label="users",
        content_type__model="capacidad",
        codename=PARAGUAS,
    ).first()
    if not paraguas:
        return
    # No se filtra por RolMeta: las capacidades transversales solo confieren alcance
    # en un rol con `programa` seteado, así que en cualquier otro rol quedan inertes.
    for grupo in Group.objects.filter(permissions=paraguas):
        grupo.permissions.add(*nuevos)


def revertir(apps, schema_editor):
    """No-op deliberado: la vuelta atrás no quita capacidades.

    Al revertir el código la paraguas recupera su doble rol, así que las transversales
    quedan redundantes pero inofensivas. Quitarlas sería peor: no hay forma de saber
    si un rol las tenía por esta migración o porque la ``0019`` se las dio por tener
    ``programa.configurar`` —o porque alguien las tildó a mano—, y borrarlas le
    revocaría un acceso legítimo.
    """
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0019_separar_admin_programa_usuarios_roles"),
    ]

    operations = [
        migrations.RunPython(traspasar_alcance, revertir),
    ]
