# Campo «Firma» del constructor de formularios (Cambio 480): `TipoCampo.FIRMA`.
#
# Solo cambian los `choices` de `tipo` en el catálogo (preguntas globales y requisitos nativos):
# Django no escribe SQL para eso (`sqlmigrate` sale vacío), la columna sigue `varchar(20)` y el
# código anterior lee una fila «FIRMA» como un valor fuera de la lista, sin fallar. Ida y vuelta
# sin datos que tocar.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0122_plaza_activa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="preguntaglobal",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("STRING", "Texto"),
                    ("INT", "Número entero"),
                    ("SELECTOR", "Selector (una opción)"),
                    ("SELECTOR_MULTIPLE", "Selector múltiple"),
                    ("DATE", "Fecha"),
                    ("ARCHIVO", "Archivo adjunto"),
                    ("FIRMA", "Firma"),
                ],
                max_length=20,
                verbose_name="Tipo de campo",
            ),
        ),
        migrations.AlterField(
            model_name="requisitonativo",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("STRING", "Texto"),
                    ("INT", "Número entero"),
                    ("SELECTOR", "Selector (una opción)"),
                    ("SELECTOR_MULTIPLE", "Selector múltiple"),
                    ("DATE", "Fecha"),
                    ("ARCHIVO", "Archivo adjunto"),
                    ("FIRMA", "Firma"),
                ],
                max_length=20,
                verbose_name="Tipo de campo",
            ),
        ),
    ]
