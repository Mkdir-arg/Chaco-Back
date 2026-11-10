"""Borra el programa Merenderos entero (decisión del PM, 10-nov-2026; Cambio 452).

No hay ningún dato de Merenderos en ningún ambiente, así que se retiran en la misma
release las tablas, los roles atados al programa y la fila `Programa(MERENDEROS)`.
Rompe a propósito la regla expand/contract: lo eligió el PM.

La parte de datos va primero y es idempotente (filtra por el estado de origen): borra los
roles (`RolMeta` + `Group`) y lo que cuelgue del `Programa` antes de sacarlo, porque
`RolMeta.programa` y las inscripciones/derivaciones son `PROTECT`.
"""

from django.db import migrations

PROGRAMA = {
    "codigo": "MERENDEROS",
    "nombre": "Merenderos",
    "tipo": "MERENDEROS",
    "descripcion": "Programa de merenderos y prestaciones alimentarias.",
    "icono": "restaurant",
    "color": "#ea580c",
    "orden": 21,
    "naturaleza": "PERSISTENTE",
    "estado": "ACTIVO",
}


def borrar_programa(apps, schema_editor):
    Programa = apps.get_model("programas", "Programa")
    InscripcionPrograma = apps.get_model("programas", "InscripcionPrograma")
    DerivacionPrograma = apps.get_model("programas", "DerivacionPrograma")
    RolMeta = apps.get_model("users", "RolMeta")
    Group = apps.get_model("auth", "Group")
    programa = Programa.objects.filter(codigo="MERENDEROS").first()
    if programa is None:
        return
    # Sin ningún dato (decisión del PM): se borran igual por si algún ambiente tuviera filas.
    DerivacionPrograma.objects.filter(programa_destino=programa).delete()
    DerivacionPrograma.objects.filter(programa_origen=programa).update(programa_origen=None)
    InscripcionPrograma.objects.filter(programa=programa).delete()
    grupos = list(RolMeta.objects.filter(programa=programa).values_list("grupo_id", flat=True))
    RolMeta.objects.filter(programa=programa).delete()
    Group.objects.filter(pk__in=grupos).delete()
    programa.delete()


def restituir_programa(apps, schema_editor):
    # Solo la fila del programa; los roles y los datos que tenía no se reconstruyen.
    Programa = apps.get_model("programas", "Programa")
    if not Programa.objects.filter(codigo=PROGRAMA["codigo"]).exists():
        Programa.objects.create(**PROGRAMA)


class Migration(migrations.Migration):

    dependencies = [
        ('programas', '0114_sector_edificio_datos'),
        ('users', '0046_retirar_merenderos'),
    ]

    operations = [
        # REVERSA-NOOP: la reversa recrea la fila Programa(MERENDEROS) pero no los roles ni los datos
        # que tenía: no existían en ningún ambiente.
        migrations.RunPython(borrar_programa, restituir_programa),
        # Hijas primero: cada DeleteModel baja la tabla entera con sus FKs e índices.
        # CONTRACT: borrado en la misma release por decisión del PM (10-nov-2026), sin datos en ningún ambiente
        migrations.DeleteModel(
            name='PrestacionDiaria',
        ),
        # CONTRACT: borrado en la misma release por decisión del PM (10-nov-2026), sin datos en ningún ambiente
        migrations.DeleteModel(
            name='PrestacionMensual',
        ),
        # CONTRACT: borrado en la misma release por decisión del PM (10-nov-2026), sin datos en ningún ambiente
        migrations.DeleteModel(
            name='EntregaMercaderia',
        ),
        # CONTRACT: borrado en la misma release por decisión del PM (10-nov-2026), sin datos en ningún ambiente
        migrations.DeleteModel(
            name='SolicitudMerendero',
        ),
        # CONTRACT: borrado en la misma release por decisión del PM (10-nov-2026), sin datos en ningún ambiente
        migrations.DeleteModel(
            name='Merendero',
        ),
    ]
