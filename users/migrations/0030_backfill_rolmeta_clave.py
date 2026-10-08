"""OPS-06 fase 2: le pone su clave estable a los roles que ya sembró el arranque.

Hasta acá los seeds reconocían «su» rol por ``Group.name``, que el ABM deja renombrar.
Un rol renombrado dejaba de ser reconocido y el arranque siguiente creaba **otro** con
el nombre canónico: un rol fantasma, sin usuarios y con todas las capacidades, al lado
del que la gente usa (escenario 3 de la ficha).

La clave se asigna por el nombre canónico porque es lo único que hay para hacer el
empate **esta vez**; de acá en adelante el empate lo hace la clave y el nombre queda
libre. Un rol que ya fue renombrado antes de este deploy no se puede reconocer
retroactivamente: queda sin clave, el seed crea el canónico y el PM los une a mano
(está en «Pasos para el PM»).

El mapa va escrito acá y no importado de los seeds a propósito: una migración se
congela y los seeds cambian.
"""

from django.db import migrations

#: Clave estable → nombre con el que el seed creó el rol hasta hoy.
#: ``sistema.*`` los siembra ``users.seed_rbac``; ``becas.*``, ``programas.seed_becas``.
#: Los cinco ``menu.*`` de ``seed_datos_base`` van en ``users.0032``.
CLAVES = {
    "sistema.administrador": "Administrador",
    "sistema.operador_backoffice": "Operador de backoffice",
    "becas.administrador": "Becas — Administrador",
    "becas.coordinador": "Becas — Coordinador",
    "becas.coordinador_regional": "Becas — Coordinador Regional",
    "becas.referente": "Becas — Referente",
    "becas.territorial": "Becas — Territorial",
}


def sembrar_claves(apps, schema_editor):
    RolMeta = apps.get_model("users", "RolMeta")
    for clave, nombre in CLAVES.items():
        # Por ``filter().update()`` y no ``get()``: un rol que no existe en esta base
        # (p. ej. Becas sin sembrar) simplemente no se toca, y una base donde ya corrió
        # no cambia nada. ``clave__isnull=True`` deja fuera el caso imposible de que
        # otro rol ya la tenga, que el índice único rechazaría.
        RolMeta.objects.filter(grupo__name=nombre, clave__isnull=True).update(clave=clave)


def borrar_claves(apps, schema_editor):
    """Reversa real: las claves que esta migración puso vuelven a ``NULL``.

    No es un noop: deja la columna como estaba. Lo que no se puede distinguir es una
    clave puesta a mano después del deploy sobre uno de estos siete roles —no hay
    pantalla que lo permita, así que no debería existir—; al reaplicar, la migración la
    vuelve a poner con el mismo valor.

    Los **cinco roles de menú** no están acá: su backfill es ``users.0032``, que se sumó
    después de que esta migración ya pudiera estar aplicada.
    """
    RolMeta = apps.get_model("users", "RolMeta")
    RolMeta.objects.filter(clave__in=list(CLAVES)).update(clave=None)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0029_esquema_rolmeta_clave_y_capacidad_revocada"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(sembrar_claves, borrar_claves),
    ]
