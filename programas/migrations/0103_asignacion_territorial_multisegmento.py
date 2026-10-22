"""Un territorial puede tener varios segmentos (expand).

``AsignacionTerritorial.territorial`` pasa de OneToOne a ForeignKey, con un UNIQUE
(segmento, territorial) no condicional (existe en MySQL y en MariaDB) y la columna de
auditoría ``asignado_por``.

Son cuatro sentencias DDL sobre una tabla chica (cientos de filas). Si el proceso se
corta a mitad, el reintento vuelve a correr el archivo y falla con 1061 (índice
duplicado) o 1091 (no se puede borrar: no existe). Recuperación a mano:
  1. mirar en ``information_schema`` qué quedó aplicado (índice
     ``uniq_asignacion_territorial_segmento``, columna ``asignado_por_id``);
  2. quitar lo que quedó a medias (``DROP INDEX`` / ``DROP COLUMN``) o, si el esquema
     ya está completo, ``migrate programas 0103 --fake`` solo después de verificarlo.

Reversa (``migrate programas 0102``): ``dedup_reversa`` deja UNA fila por territorial
(la de menor pk, el segmento dueño) para que se pueda recrear el UNIQUE del OneToOne.
Se pierden los segmentos extra y ``asignado_por``.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def dedup_reversa(apps, schema_editor):
    """Deja la asignación más antigua de cada territorial. Idempotente."""
    Asignacion = apps.get_model("programas", "AsignacionTerritorial")
    vistos = set()
    sobrantes = []
    for pk, territorial_id in Asignacion.objects.order_by("pk").values_list("pk", "territorial_id"):
        if territorial_id in vistos:
            sobrantes.append(pk)
        else:
            vistos.add(territorial_id)
    if sobrantes:
        Asignacion.objects.filter(pk__in=sobrantes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0102_relevamiento_cierre_automatico_en"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="asignacionterritorial",
            name="territorial",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="segmentos_territoriales",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Territorial",
            ),
        ),
        migrations.AddConstraint(
            model_name="asignacionterritorial",
            constraint=models.UniqueConstraint(
                fields=("segmento", "territorial"), name="uniq_asignacion_territorial_segmento"
            ),
        ),
        migrations.AddField(
            model_name="asignacionterritorial",
            name="asignado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Asignado por",
            ),
        ),
        # Va al final: al desaplicar corre PRIMERO, antes de que la reversa del
        # AlterField recree el UNIQUE de territorial.
        migrations.RunPython(migrations.RunPython.noop, dedup_reversa),
    ]
