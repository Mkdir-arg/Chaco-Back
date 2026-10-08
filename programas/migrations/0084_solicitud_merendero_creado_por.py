"""SEC-09: quién creó la solicitud de merendero, para acotarle `/media/` a `merendero.crear`.

**Expand puro:** columna nueva `NULL`, así que el código de la release anterior sigue
dando de alta solicitudes sin tocarla. Las filas existentes quedan en `NULL` y nadie las
abre por `merendero.crear`: las leen `merendero.ver` y `merendero.validar`, que no
cambian.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0083_sec09_upload_to_uuid"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudmerendero",
            name="creado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="solicitudes_merendero_creadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Creada por",
            ),
        ),
    ]
