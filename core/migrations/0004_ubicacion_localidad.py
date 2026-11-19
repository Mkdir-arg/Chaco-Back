"""Cambio 498 (E-2 del análisis 009) · Tabla nueva `core_ubicacionlocalidad`.

Solo *expand*: crea una tabla vacía y no toca `core_localidad` (8.779 filas de todo el
país compartidas con el domicilio). La release vieja no la nombra, así que convive con
ella durante el rolling; la reversa es el `DROP TABLE` que Django arma solo. Los datos los
carga después `manage.py cargar_ubicaciones_localidades`, no esta migración.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_retirar_django_health_check"),
    ]

    operations = [
        migrations.CreateModel(
            name="UbicacionLocalidad",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                (
                    "latitud",
                    models.DecimalField(decimal_places=6, max_digits=9, verbose_name="Latitud"),
                ),
                (
                    "longitud",
                    models.DecimalField(decimal_places=6, max_digits=9, verbose_name="Longitud"),
                ),
                (
                    "departamento",
                    models.CharField(blank=True, max_length=255, verbose_name="Departamento"),
                ),
                ("fuente", models.CharField(max_length=50, verbose_name="Fuente")),
                (
                    "id_fuente",
                    models.CharField(max_length=32, verbose_name="Id en la fuente"),
                ),
                (
                    "localidad",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ubicacion",
                        to="core.localidad",
                        verbose_name="Localidad",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ubicación de localidad",
                "verbose_name_plural": "Ubicaciones de localidades",
            },
        ),
    ]
