# Módulo Emergencia, PR 9: entregas de kits. Tres tablas nuevas (`EntregaKit`,
# `LineaEntrega`, `TrazaEntrega`) y ninguna columna sobre una tabla existente, así que no
# hay nada que el código de la release anterior lea o escriba: es EXPAND puro y la reversa
# borra las tablas.
#
# * `EntregaKit.uuid_cliente_recepcion` nace anulable y único, y se amplía a `char(36)` en
#   MySQL/MariaDB: con MariaDB 10.7+ Django 5 manda el UUID **con guiones** y una columna
#   `char(32)` —la que queda tras un restore desde MySQL— da «Data too long» (patrón de
#   programas.0119, Cambio 99). Se busca con `core.db.q_uuid_en_texto`.
# * Ninguna exclusión condicional: los únicos son comunes (`numero`, `(entrega, item)`).
# * Las columnas con valor de fábrica llevan `db_default`: el DEFAULT queda en el esquema.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import core.rutas_media
import core.validators
from core.migraciones import modificar_columna

TABLA_ENTREGA = "programas_entregakit"


def ampliar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # Tabla recién creada: no hay filas que normalizar. `modificar_columna` mira el tipo
    # real en `information_schema`, así que repetir el paso no hace nada.
    modificar_columna(schema_editor, TABLA_ENTREGA, "uuid_cliente_recepcion", "char(36)", "NULL")


def restaurar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # RED-18: se normaliza a hex antes de achicar, o MariaDB trunca los UUID con guiones.
    # Después la reversa del `CreateModel` borra la tabla entera.
    schema_editor.execute(
        f"UPDATE {TABLA_ENTREGA} SET uuid_cliente_recepcion = REPLACE(uuid_cliente_recepcion, '-', '') "
        "WHERE uuid_cliente_recepcion IS NOT NULL AND CHAR_LENGTH(uuid_cliente_recepcion) = 36"
    )
    schema_editor.execute(f"ALTER TABLE {TABLA_ENTREGA} MODIFY uuid_cliente_recepcion char(32) NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0120_reserva_plaza_derivacion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EntregaKit",
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
                    "numero",
                    models.CharField(
                        editable=False,
                        max_length=20,
                        unique=True,
                        verbose_name="N.° de entrega",
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("PREPARADA", "Preparada"),
                            ("EN_CAMINO", "En camino"),
                            ("RECIBIDA", "Recibida"),
                            ("RECIBIDA_CON_DIFERENCIAS", "Recibida con diferencias"),
                            ("CANCELADA", "Cancelada"),
                        ],
                        db_default="PREPARADA",
                        default="PREPARADA",
                        max_length=30,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "observacion_mesa",
                    models.TextField(blank=True, verbose_name="Observación de la mesa"),
                ),
                (
                    "transporte",
                    models.CharField(
                        blank=True,
                        db_default="",
                        default="",
                        max_length=120,
                        verbose_name="Transporte",
                    ),
                ),
                (
                    "despachada_en",
                    models.DateTimeField(blank=True, null=True, verbose_name="En camino desde"),
                ),
                (
                    "recibida_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Recibida"),
                ),
                (
                    "observacion_dispositivo",
                    models.TextField(blank=True, verbose_name="Observación del dispositivo"),
                ),
                (
                    "remito",
                    models.FileField(
                        blank=True,
                        upload_to=core.rutas_media.ruta_remito_entrega,
                        validators=[core.validators.validar_foto],
                        verbose_name="Foto del remito",
                    ),
                ),
                (
                    "motivo_cancelacion",
                    models.CharField(
                        blank=True,
                        db_default="",
                        default="",
                        max_length=200,
                        verbose_name="Motivo de la cancelación",
                    ),
                ),
                (
                    "uuid_cliente_recepcion",
                    models.UUIDField(
                        blank=True,
                        editable=False,
                        null=True,
                        unique=True,
                        verbose_name="Identificador de la recepción (app)",
                    ),
                ),
                (
                    "armada_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="entregas_de_kits_armadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Armada por",
                    ),
                ),
                (
                    "dispositivo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="entregas_de_kits",
                        to="programas.dispositivo",
                        verbose_name="Dispositivo destino",
                    ),
                ),
                (
                    "recibida_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="entregas_de_kits_recibidas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Recibida por",
                    ),
                ),
                (
                    "repone_a",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reposiciones",
                        to="programas.entregakit",
                        verbose_name="Repone a",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrega de kits",
                "verbose_name_plural": "Entregas de kits",
                "ordering": ["-creado", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LineaEntrega",
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
                ("unidad", models.CharField(max_length=30, verbose_name="Unidad")),
                (
                    "cantidad_enviada",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Cantidad enviada",
                    ),
                ),
                (
                    "cantidad_recibida",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Cantidad recibida"),
                ),
                (
                    "entrega",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lineas",
                        to="programas.entregakit",
                        verbose_name="Entrega",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lineas_de_entrega",
                        to="programas.tipokit",
                        verbose_name="Ítem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Línea de entrega de kits",
                "verbose_name_plural": "Líneas de entregas de kits",
                "ordering": ["entrega_id", "id"],
            },
        ),
        migrations.CreateModel(
            name="TrazaEntrega",
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
                (
                    "creado_en",
                    models.DateTimeField(auto_now_add=True, verbose_name="Fecha"),
                ),
                ("accion", models.CharField(max_length=40, verbose_name="Acción")),
                (
                    "estado_anterior",
                    models.CharField(blank=True, max_length=30, verbose_name="Estado anterior"),
                ),
                (
                    "estado_nuevo",
                    models.CharField(blank=True, max_length=30, verbose_name="Estado nuevo"),
                ),
                ("detalle", models.TextField(blank=True, verbose_name="Detalle")),
                (
                    "entrega",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trazas",
                        to="programas.entregakit",
                        verbose_name="Entrega",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trazas_entregas_de_kits",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "Traza de entrega de kits",
                "verbose_name_plural": "Trazas de entregas de kits",
                "ordering": ["creado_en", "id"],
                "base_manager_name": "objects",
                "default_manager_name": "objects",
            },
        ),
        migrations.AddIndex(
            model_name="entregakit",
            index=models.Index(fields=["dispositivo", "estado"], name="programas_e_disposi_2ba7af_idx"),
        ),
        migrations.AddConstraint(
            model_name="lineaentrega",
            constraint=models.UniqueConstraint(fields=("entrega", "item"), name="linea_entrega_item_unico_por_entrega"),
        ),
        migrations.AddConstraint(
            model_name="lineaentrega",
            constraint=models.CheckConstraint(
                condition=models.Q(("cantidad_enviada__gte", 1)),
                name="linea_entrega_enviada_positiva",
            ),
        ),
        # `atomic=False`: en MySQL/MariaDB Django envuelve un RunPython de una migración atómica en
        # una transacción, y el `ALTER TABLE … MODIFY` de adentro muere con TransactionManagementError
        # (mismo caso que la 0119, que cazó el job «Motor real (mariadb:10.11)»). El paso es
        # idempotente: `modificar_columna` mira el tipo real de la columna antes de tocarla.
        migrations.RunPython(ampliar_uuid_mysql, restaurar_uuid_mysql, atomic=False),
    ]
