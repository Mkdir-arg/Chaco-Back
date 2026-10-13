# Relevamiento edilicio (MVP v2, etapa 4 · #700): `InspeccionEdificio` y `FotoInspeccion`.
# Solo tablas nuevas: no hay columna agregada a una tabla existente ni datos que migrar.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import core.rutas_media
import core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0090_turno_bitacora"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InspeccionEdificio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("ASIGNADA", "Asignado · en campo"),
                            ("REALIZADA", "Completado"),
                            ("CANCELADA", "Cancelado"),
                        ],
                        default="ASIGNADA",
                        max_length=12,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "criticidad",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("BAJA", "Baja · en buen estado"),
                            ("MEDIA", "Media · estado regular"),
                            ("ALTA", "Alta · requiere intervención"),
                        ],
                        max_length=12,
                        verbose_name="Criticidad",
                    ),
                ),
                ("observaciones", models.TextField(blank=True, verbose_name="Observaciones")),
                ("indicaciones", models.TextField(blank=True, verbose_name="Indicaciones para el agente")),
                ("fecha_vencimiento", models.DateField(verbose_name="Vence")),
                ("realizada_en", models.DateTimeField(blank=True, null=True, verbose_name="Fecha de realización")),
                (
                    "motivo_cancelacion",
                    models.CharField(blank=True, max_length=200, verbose_name="Motivo de la cancelación"),
                ),
                (
                    "asignado_a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inspecciones_asignadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Agente asignado",
                    ),
                ),
                (
                    "creado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inspecciones_creadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "edificio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inspecciones",
                        to="programas.edificio",
                        verbose_name="Edificio",
                    ),
                ),
                (
                    "realizada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Realizado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Relevamiento edilicio",
                "verbose_name_plural": "Relevamientos edilicios",
                "ordering": ["-fecha_vencimiento", "-id"],
            },
        ),
        migrations.CreateModel(
            name="FotoInspeccion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                (
                    "archivo",
                    models.FileField(
                        upload_to=core.rutas_media.ruta_foto_inspeccion,
                        validators=[core.validators.validar_foto],
                        verbose_name="Foto",
                    ),
                ),
                ("descripcion", models.CharField(blank=True, max_length=120, verbose_name="Descripción")),
                (
                    "cargada_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Cargada por",
                    ),
                ),
                (
                    "inspeccion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fotos",
                        to="programas.inspeccionedificio",
                        verbose_name="Relevamiento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Foto de relevamiento edilicio",
                "verbose_name_plural": "Fotos de relevamientos edilicios",
                "ordering": ["creado", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="inspeccionedificio",
            index=models.Index(fields=["edificio", "estado", "realizada_en"], name="programas_i_edifici_d6e2fe_idx"),
        ),
        migrations.AddIndex(
            model_name="inspeccionedificio",
            index=models.Index(fields=["asignado_a", "estado"], name="programas_i_asignad_ffa65e_idx"),
        ),
        migrations.AddConstraint(
            model_name="inspeccionedificio",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("estado", "REALIZADA"), _negated=True),
                    models.Q(
                        models.Q(("criticidad", ""), _negated=True),
                        ("realizada_en__isnull", False),
                        ("realizada_por__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="inspeccion_realizada_con_resultado",
            ),
        ),
        migrations.AddConstraint(
            model_name="inspeccionedificio",
            constraint=models.CheckConstraint(
                condition=models.Q(("estado", "REALIZADA"), ("criticidad", ""), _connector="OR"),
                name="inspeccion_sin_realizar_sin_criticidad",
            ),
        ),
        migrations.AddConstraint(
            model_name="inspeccionedificio",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("estado", "CANCELADA"), _negated=True),
                    models.Q(("motivo_cancelacion", ""), _negated=True),
                    _connector="OR",
                ),
                name="inspeccion_cancelada_con_motivo",
            ),
        ),
    ]
