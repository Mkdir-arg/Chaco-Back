"""OPS-06 fase 2, ronda 2: la clave estable también para los **cinco roles de menú**.

``users.0030`` le puso la clave a los siete roles de ``seed_rbac`` y ``seed_becas``, pero
el arranque siembra doce: faltaban los cinco de ``seed_datos_base._ROLES_MENU``
(Dashboard, Gestión de Ciudadanos, Reportes, Configuración y Administración), que seguían
reconociéndose por ``Group.name``. Medido: renombrar «Gestión de Ciudadanos» y
«Administración» desde el ABM y correr ``seed_datos_base`` dejaba **dos roles más**, y el
«Administración» duplicado nace con ``usuario.administrar`` + ``rol.administrar`` y cero
usuarios al lado del que la gente usa. Es el escenario 3 de la ficha.

Va en una migración **nueva** y no ampliando la ``0030``: la rama ya se pudo haber
desplegado en testing, y una ``0030`` ya aplicada no vuelve a correr. Mismo mecanismo y
misma reversa que aquella.
"""

from django.db import migrations

#: Clave estable → nombre con el que ``seed_datos_base`` creó el rol hasta hoy.
CLAVES = {
    "menu.dashboard": "Dashboard",
    "menu.ciudadanos": "Gestión de Ciudadanos",
    "menu.reportes": "Reportes",
    "menu.configuracion": "Configuración",
    "menu.administracion": "Administración",
}


def sembrar_claves(apps, schema_editor):
    RolMeta = apps.get_model("users", "RolMeta")
    for clave, nombre in CLAVES.items():
        # Igual que la 0030: por ``filter().update()``, así una base donde el rol no
        # existe o donde esto ya corrió no cambia nada, y ``clave__isnull=True`` deja
        # fuera el caso que el índice único rechazaría.
        RolMeta.objects.filter(grupo__name=nombre, clave__isnull=True).update(clave=clave)


def borrar_claves(apps, schema_editor):
    """Reversa real: las cinco claves que esta migración puso vuelven a ``NULL``."""
    RolMeta = apps.get_model("users", "RolMeta")
    RolMeta.objects.filter(clave__in=list(CLAVES)).update(clave=None)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0031_quitar_becas_de_roles_de_otros_programas"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(sembrar_claves, borrar_claves),
    ]
