"""DAT-01 · `AdjuntoFormulario` deja de borrarse en cascada con el catálogo.

**Es una migración solo de estado: no emite una sola línea de DDL.** `on_delete` vive
en Python —es lo que el ORM hace *antes* del `DELETE`—, no en el esquema: la foreign
key de MySQL y MariaDB ya estaba creada sin `ON DELETE CASCADE` (Django nunca lo
delega al motor) y sigue igual. Se puede comprobar con
`manage.py sqlmigrate programas 0078`, que sale vacío, y lo mide
`programas/tests/test_contrato_migraciones.py`.

Por eso tampoco tiene costo en producción ni ventana de bloqueo sobre
`programas_adjuntoformulario`, y el rolling de la release no la nota: el código viejo
sigue leyendo y escribiendo la misma tabla con el mismo esquema. Lo único que cambia
es que, desde que la release nueva está arriba, borrar una `PreguntaGlobal` o un
`RequisitoNativo` con adjuntos levanta `ProtectedError` en vez de llevarse los
documentos del ciudadano.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0077_catalogo_siis_local"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adjuntoformulario",
            name="pregunta_global",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="adjuntos_formulario",
                to="programas.preguntaglobal",
                verbose_name="Pregunta global",
            ),
        ),
        migrations.AlterField(
            model_name="adjuntoformulario",
            name="requisito_nativo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="adjuntos_formulario",
                to="programas.requisitonativo",
                verbose_name="Requisito nativo",
            ),
        ),
    ]
