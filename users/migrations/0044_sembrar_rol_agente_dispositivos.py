"""Siembra el rol «Dispositivos — Agente de relevamiento» (Cambio 395).

El rol lo necesita el botón «Crear agente», y en ECOM el arranque (`seed_datos_base`) no corre; en una
base nueva además corre antes que `crear_programas`. Por eso va también por migración de datos, como
`users.0040` y `users.0043`. `seed_dispositivos` queda como red para los ambientes que sí lo corren.

Idempotente y respetuosa del Cambio 104: el rol se busca por `RolMeta.clave` (un rol renombrado sigue
siendo el mismo y no se duplica); si existe, solo se asegura `inspeccion.relevar` y no se toca nada más.
Sin el programa DISPOSITIVOS no hace nada.
"""

from django.db import migrations

CLAVE = "dispositivos.agente_relevamiento"
NOMBRE = "Dispositivos — Agente de relevamiento"
DESCRIPCION = "Releva edificios en campo: carga el resultado de los relevamientos edilicios que se le asignan."
CODENAME = "inspeccion_relevar"
ETIQUETA = "Cargar el resultado de los relevamientos edilicios asignados"


def sembrar(apps, schema_editor):
    Programa = apps.get_model("programas", "Programa")
    programa = Programa.objects.filter(codigo="DISPOSITIVOS").first()
    if programa is None:
        return
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    RolMeta = apps.get_model("users", "RolMeta")

    meta = RolMeta.objects.filter(clave=CLAVE).select_related("grupo").first()
    if meta is not None:
        grupo = meta.grupo
    else:
        grupo, _ = Group.objects.get_or_create(name=NOMBRE)
        meta = RolMeta.objects.filter(grupo=grupo).first()
        if meta is None:
            RolMeta.objects.create(
                grupo=grupo,
                clave=CLAVE,
                categoria="Programa",
                programa=programa,
                descripcion=DESCRIPCION,
                protegido=False,
                activo=True,
            )
        elif meta.clave is None:
            meta.clave = CLAVE
            meta.save(update_fields=["clave"])
    # `get_or_create`: en una base que migra de corrido el `post_migrate` aún no materializó la capacidad.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    permiso, _ = Permission.objects.get_or_create(
        content_type=content_type, codename=CODENAME, defaults={"name": ETIQUETA}
    )
    grupo.permissions.add(permiso)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("programas", "0012_crear_programas_dispositivos_merenderos"),
        ("users", "0043_administrador_inspeccion_agente_crear"),
    ]

    operations = [
        # REVERSA-NOOP: el rol queda con sus usuarios y su capacidad; borrarlo desharía las altas hechas con
        # el botón y no hay forma de saber si lo creó esta migración o el seed. Es un dato inofensivo.
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
