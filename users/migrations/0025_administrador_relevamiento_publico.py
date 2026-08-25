from django.db import migrations

# El rol `Administrador` recibe `becas.relevamiento.publico` (Cambio 41).
#
# El gate del formulario público (RN-P13) deja la capacidad fuera de los seeds a
# propósito: se enciende tildándola en la pantalla de Roles, sin deploy. Pero el
# `Administrador` es un rol **protegido** (`RolMeta.protegido`) y esa pantalla
# rechaza su edición ("El rol está protegido y no puede editarse"), así que para
# él no existía camino manual. El único mecanismo que corre en cada despliegue es
# una migración: el entrypoint del contenedor ejecuta `migrate`, no los seeds.
#
# Decisión del PM (25/08/2026): el Administrador la tiene en todos los entornos.
# Es coherente con `seed_rbac`, que ya le asigna **todas** las capacidades del
# catálogo, y no cambia nada para el cliente: `seed_becas` sigue excluyéndola de
# los roles de Becas, que se encienden a mano cuando el programa lo pida.
CODENAME = "becas_relevamiento_publico"
NOMBRE = "Crear y ver relevamientos de formulario público (link de inscripción)"
ROL = "Administrador"


def otorgar_al_administrador(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    grupo = Group.objects.filter(name=ROL).first()
    if grupo is None:
        # Base nueva: los roles todavía no existen (los crea `seed_rbac`, que ya
        # le da todas las capacidades al Administrador). Nada que otorgar.
        return

    # `get_or_create` y no `filter`: en una corrida donde la `0024` recién creó
    # la capacidad, el `post_migrate` que materializa los permisos todavía no
    # pasó, así que la fila puede no existir cuando esta migración corre.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    permiso, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=CODENAME,
        defaults={"name": NOMBRE},
    )
    grupo.permissions.add(permiso)


def revertir(apps, schema_editor):
    """No-op deliberado: la vuelta atrás no quita la capacidad.

    No hay forma de distinguir si el Administrador la tiene por esta migración,
    porque alguien corrió `seed_rbac` (que le asigna todo el catálogo) o porque
    se tildó a mano, y quitarla revocaría un acceso legítimo. Al revertir el
    código del formulario público la capacidad queda inerte: sin la superficie
    no habilita nada.
    """
    return


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0024_capacidad_relevamiento_publico"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(otorgar_al_administrador, revertir),
    ]
