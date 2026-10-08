"""`upload_to` con UUID y lista blanca en los adjuntos del legajo (SEC-09/SEC-15).

**Sin DDL, a propósito.** Lo único que cambia es Python: `upload_to` decide la
ruta del archivo *nuevo* y `validators` corre en `full_clean()`; la columna sigue
siendo el mismo `varchar(100)`. Django no lo sabe —`validators` está en
`non_db_attrs` pero `upload_to` no—, así que un `AlterField` suelto le manda a
MariaDB un `MODIFY COLUMN` idéntico sobre `legajos_ciudadano`, que son cien mil
filas y el `read_timeout` de ECOM son 10 s: el mismo molde que cortó
`legajos.0007` por la mitad (RED-58). Por eso va dentro de
`SeparateDatabaseAndState` con `database_operations=[]`.

Los archivos **ya guardados no se renombran** y se siguen viendo y descargando:
`core.views.media` resuelve el dueño por el nombre que tiene la fila, no por el
formato del nombre.
"""

import core.rutas_media
import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("legajos", "0009_fechas_locales_bec18"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="adjunto",
                    name="archivo",
                    field=models.FileField(upload_to=core.rutas_media.ruta_adjunto_legajo),
                ),
                migrations.AlterField(
                    model_name="ciudadano",
                    name="foto",
                    field=models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=core.rutas_media.ruta_foto_ciudadano,
                        verbose_name="Foto",
                    ),
                ),
                migrations.AlterField(
                    model_name="historialcontacto",
                    name="archivo_adjunto",
                    field=models.FileField(
                        blank=True,
                        help_text="Grabación, foto, documento relacionado (PDF o imagen, hasta 5 MB)",
                        null=True,
                        upload_to=core.rutas_media.ruta_contacto,
                        validators=[core.validators.validar_adjunto],
                    ),
                ),
            ],
        ),
    ]
