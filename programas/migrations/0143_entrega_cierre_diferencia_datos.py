from django.db import migrations


def cerrar_las_ya_repuestas(apps, schema_editor):
    """Marca ``REPUESTA`` a las entregas recibidas con diferencias que ya tienen una reposición (Cambio 586).

    Antes de este cambio «Reponer» se podía repetir; ahora es una sola vez, y sin este paso esas entregas
    aparecerían como «diferencia sin cerrar» y dejarían reponer de nuevo. Toma la **primera** reposición (la que
    cerró la diferencia): su fecha y quien la armó. Una reposición **cancelada** no cuenta: no se repuso nada. Idempotente: solo toca las que siguen sin cierre, así que si se
    corta y se reintenta retoma donde quedó. Se recorre en Python y no con un ``UPDATE`` con subconsulta sobre la misma
    tabla, que MySQL y MariaDB rechazan (error 1093); son pocas filas.
    """

    EntregaKit = apps.get_model("programas", "EntregaKit")
    primera = {}
    reposiciones = (
        EntregaKit.objects.filter(repone_a__isnull=False)
        .exclude(estado="CANCELADA")
        .order_by("creado", "id")
        .values_list("repone_a_id", "creado", "armada_por_id")
    )
    for original, creado, armada_por in reposiciones:
        primera.setdefault(original, (creado, armada_por))
    for original, (creado, armada_por) in primera.items():
        EntregaKit.objects.filter(
            pk=original, estado="RECIBIDA_CON_DIFERENCIAS", cierre_diferencia__isnull=True
        ).update(cierre_diferencia="REPUESTA", cierre_diferencia_en=creado, cierre_diferencia_por_id=armada_por)


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0142_entrega_cierre_diferencia"),
    ]

    operations = [
        # REVERSA-NOOP: al revertir solo este paso las columnas siguen existiendo con las marcas puestas; no es una
        # inconsistencia (el código anterior no las lee). Al revertir 0142 las columnas se borran con ellas.
        migrations.RunPython(cerrar_las_ya_repuestas, migrations.RunPython.noop),
    ]
