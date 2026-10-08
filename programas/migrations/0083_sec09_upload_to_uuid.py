"""`upload_to` con UUID y lista blanca en F-00 y merenderos (SEC-09/SEC-15).

**Sin DDL, a propósito.** Ver el comentario de `legajos.0010`, que es la otra
mitad del mismo cambio: la columna sigue siendo el mismo `varchar(100)` y lo
único que se mueve es Python (`upload_to`, `validators`). Va dentro de
`SeparateDatabaseAndState` para que MariaDB no reciba un `MODIFY COLUMN` que no
cambia nada y puede pasarse del `read_timeout`.

La lista blanca **no revalida lo guardado**: `core.validators.validar_adjunto`
se sale ante un `FieldFile` ya commiteado, así que una solicitud de merendero
vieja con un `.docx` adjunto se sigue editando y su archivo se sigue bajando.
"""

import core.rutas_media
import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0082_indices_ultimo_intento_siis"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="archivoadmision",
                    name="archivo",
                    field=models.FileField(
                        upload_to=core.rutas_media.ruta_archivo_admision,
                        validators=[core.validators.validar_adjunto],
                    ),
                ),
                migrations.AlterField(
                    model_name="solicitudmerendero",
                    name="documentacion",
                    field=models.FileField(
                        upload_to=core.rutas_media.ruta_solicitud_merendero,
                        validators=[core.validators.validar_adjunto],
                        verbose_name="Documentación respaldatoria",
                    ),
                ),
            ],
        ),
    ]
