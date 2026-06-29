# Generated manually 2026-06-29: reemplaza CATEGORIA_PROGRAMA por CATEGORIA_NACHEC + CATEGORIA_BECAS.
# No cambia el esquema de la DB; actualiza las choices para validación a nivel de formulario.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_alter_capacidad_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rolmeta',
            name='categoria',
            field=models.CharField(
                choices=[
                    ('Backoffice', 'Backoffice'),
                    ('Institución', 'Institución'),
                    ('Portal', 'Portal'),
                    ('Sistema', 'Sistema'),
                    ('ÑACHEC', 'ÑACHEC'),
                    ('Becas', 'Becas'),
                ],
                default='Backoffice',
                max_length=20,
                verbose_name='Categoría',
            ),
        ),
    ]
