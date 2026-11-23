"""Cambio 586: cómo se cerró la diferencia de una entrega recibida con diferencias.

Expand: cuatro columnas nuevas, todas ``NULL`` (el código viejo no las conoce y puede seguir dando de alta sin
ellas). Nada se rellena acá: de las entregas que ya se repusieron se ocupa ``0143``.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0141_linea_entrega_nombre_datos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="entregakit",
            name="cierre_diferencia",
            field=models.CharField(
                blank=True,
                choices=[("REPUESTA", "Repuesta"), ("ACEPTADA", "Aceptada")],
                editable=False,
                max_length=10,
                null=True,
                verbose_name="Cierre de la diferencia",
            ),
        ),
        migrations.AddField(
            model_name="entregakit",
            name="cierre_diferencia_en",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Diferencia cerrada"),
        ),
        migrations.AddField(
            model_name="entregakit",
            name="cierre_diferencia_motivo",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=200,
                null=True,
                verbose_name="Motivo de la diferencia aceptada",
            ),
        ),
        migrations.AddField(
            model_name="entregakit",
            name="cierre_diferencia_por",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entregas_de_kits_con_diferencia_cerrada",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Diferencia cerrada por",
            ),
        ),
    ]
