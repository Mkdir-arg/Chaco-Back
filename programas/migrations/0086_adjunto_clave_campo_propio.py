"""#637: referencia estable para adjuntos de campos propios.

El DEFAULT SQL vacío conserva los INSERT de la release anterior. La nueva
restricción admite exactamente una referencia: catálogo o clave cp-.
La reversa conserva adjuntos legacy; solo puede ejecutarse antes de recibir
adjuntos cp-, que el esquema anterior no puede representar. No se borran esos
documentos automáticamente para permitir un rollback.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programas', '0085_indices_redundantes_red83'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='adjuntoformulario',
            name='adjunto_formulario_una_sola_referencia',
        ),
        migrations.AddField(
            model_name='adjuntoformulario',
            name='clave',
            field=models.CharField(blank=True, db_default='', default='', max_length=60, verbose_name='Clave del campo propio'),
        ),
        migrations.AddConstraint(
            model_name='adjuntoformulario',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('clave', ''), ('pregunta_global__isnull', False), ('requisito_nativo__isnull', True)), models.Q(('clave', ''), ('pregunta_global__isnull', True), ('requisito_nativo__isnull', False)), models.Q(('pregunta_global__isnull', True), ('requisito_nativo__isnull', True), ('clave__startswith', 'cp-')), _connector='OR'), name='adjunto_formulario_una_sola_referencia'),
        ),
    ]
