from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de programas.0032 solo se vuelve con restore (RED-57).
# La migración copia ``siis_segmento_id`` del segmento al subsegmento y después borra la
# columna de origen: al revertir, el ``AddField`` automático la recrea vacía y la
# asociación con SIIS de todos los segmentos desaparece sin un solo mensaje.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "programas.0032 es una barrera de reversa (RED-57): revertirla deja a todos los "
    "segmentos sin siis_segmento_id, y esa asociación no se puede reconstruir desde los "
    "subsegmentos. Volver atrás se hace con restore del dump previo al deploy: runbook "
    "D.4 de docs/internal/processes.md. No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de que se borre nada. A diferencia de las barreras de
    # UUID, esta vale en todos los motores: la pérdida de datos no depende del motor.
    raise IrreversibleError(MENSAJE_BARRERA)


def copiar_asociaciones_univocas(apps, schema_editor):
    Segmento = apps.get_model("programas", "Segmento")
    Subsegmento = apps.get_model("programas", "Subsegmento")
    for segmento in Segmento.objects.exclude(siis_segmento_id__isnull=True).iterator():
        subsegmentos = Subsegmento.objects.filter(segmento_id=segmento.pk)
        if subsegmentos.count() == 1:
            subsegmentos.update(siis_segmento_id=segmento.siis_segmento_id)


class Migration(migrations.Migration):
    dependencies = [("programas", "0031_siis_integracion")]

    operations = [
        migrations.AddField(
            model_name="subsegmento",
            name="siis_segmento_id",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de segmento SIIS"),
        ),
        # REVERSA-NOOP: al revertir, los subsegmentos conservan el ``siis_segmento_id``
        # copiado pero los segmentos lo pierden (la columna se recrea vacía).
        migrations.RunPython(copiar_asociaciones_univocas, migrations.RunPython.noop),
        # Expand y contract en la misma migración: es el antipatrón que el Anexo C de la
        # auditoría toma como ejemplo de lo que no hay que repetir. Queda como está —ya
        # corrió en producción—; lo que lo impide de acá en adelante es el gate.
        migrations.RemoveField(model_name="segmento", name="siis_segmento_id"),
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
