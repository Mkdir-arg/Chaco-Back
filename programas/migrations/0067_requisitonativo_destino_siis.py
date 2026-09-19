# Cambio 80: el marcador «Este dato alimenta a SIIS como» pasa a existir también
# en los requisitos nativos, porque en el catálogo real el domicilio, el estado
# civil y el lugar de nacimiento son requisitos del segmento y no preguntas
# generales. Aditiva: no toca datos.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0066_siis_envio_beneficiarios"),
    ]

    operations = [
        migrations.AddField(
            model_name="requisitonativo",
            name="destino_siis",
            field=models.CharField(
                blank=True,
                choices=[
                    ("prov_actual", "Provincia del domicilio"),
                    ("loc_actual", "Localidad del domicilio"),
                    ("barrio_actual", "Barrio"),
                    ("calle_altura", "Calle y altura (piso, dpto)"),
                    ("est_civil", "Estado civil"),
                    ("prov_nacim", "Provincia de nacimiento"),
                    ("loc_nacim", "Localidad de nacimiento"),
                ],
                db_index=True,
                default="",
                help_text=(
                    "Con qué campo del alta de beneficiarios en SIIS se corresponde la respuesta. "
                    "Un solo requisito por destino dentro del mismo programa, segmento o subsegmento."
                ),
                max_length=20,
                verbose_name="Este dato alimenta a SIIS como",
            ),
        ),
    ]
