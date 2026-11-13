# Módulo Emergencia, PR 2: el caso y la mesa. Ocho tablas nuevas y ninguna columna sobre
# una tabla existente, así que no hay nada que el código de la release anterior lea o
# escriba: es EXPAND puro y la reversa borra las tablas.
#
# * `CasoEmergencia.uuid_cliente` nace anulable y único, y se amplía a `char(36)` en
#   MySQL/MariaDB: con MariaDB 10.7+ Django 5 manda el UUID **con guiones** y una columna
#   `char(32)` —la que queda tras un restore desde MySQL— da «Data too long» (patrón de
#   programas.0093, Cambio 99). Se busca con `core.db.q_uuid_en_texto`.
# * `Derivacion.clave_vigente` es la exclusión «a lo sumo una vigente por caso»: columna
#   anulable con un UNIQUE **común**, como `Estadia.clave_alojamiento`. Un
#   `UniqueConstraint(condition=…)` MySQL y MariaDB no lo crean.
# * Las columnas con valor de fábrica llevan `db_default`: el DEFAULT queda en el esquema.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import core.rutas_media
import core.validators
from core.migraciones import modificar_columna

TABLA_CASO = "programas_casoemergencia"


def ampliar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # Tabla recién creada: no hay filas que normalizar. `modificar_columna` mira el tipo
    # real en `information_schema`, así que repetir el paso no hace nada.
    modificar_columna(schema_editor, TABLA_CASO, "uuid_cliente", "char(36)", "NULL")


def restaurar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # RED-18: se normaliza a hex antes de achicar, o MariaDB trunca los UUID con guiones.
    # Después la reversa del `CreateModel` borra la tabla entera.
    schema_editor.execute(
        f"UPDATE {TABLA_CASO} SET uuid_cliente = REPLACE(uuid_cliente, '-', '') "
        "WHERE uuid_cliente IS NOT NULL AND CHAR_LENGTH(uuid_cliente) = 36"
    )
    schema_editor.execute(f"ALTER TABLE {TABLA_CASO} MODIFY uuid_cliente char(32) NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_retirar_django_health_check"),
        ("legajos", "0011_indices_redundantes_red83"),
        ("programas", "0118_programa_emergencia"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GrupoFamiliar",
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
                    "traslado",
                    models.CharField(
                        choices=[
                            ("BOMBEROS", "Bomberos"),
                            ("EJERCITO", "Ejército"),
                            ("DEFENSA_CIVIL", "Defensa Civil"),
                            ("POLICIA", "Policía"),
                            ("MUNICIPIO", "Municipio"),
                            ("AUTOEVACUADO", "Autoevacuado"),
                            ("OTRA", "Otra"),
                        ],
                        max_length=20,
                        verbose_name="Fuerza que traslada",
                    ),
                ),
                (
                    "traslado_otro",
                    models.CharField(
                        blank=True,
                        max_length=120,
                        verbose_name="Otra fuerza que traslada",
                    ),
                ),
                (
                    "menores_f",
                    models.PositiveSmallIntegerField(db_default=0, default=0, verbose_name="Menores de 16 · femenino"),
                ),
                (
                    "menores_m",
                    models.PositiveSmallIntegerField(
                        db_default=0,
                        default=0,
                        verbose_name="Menores de 16 · masculino",
                    ),
                ),
                (
                    "adultos_f",
                    models.PositiveSmallIntegerField(
                        db_default=0,
                        default=0,
                        verbose_name="Adultos (16 a 59) · femenino",
                    ),
                ),
                (
                    "adultos_m",
                    models.PositiveSmallIntegerField(
                        db_default=0,
                        default=0,
                        verbose_name="Adultos (16 a 59) · masculino",
                    ),
                ),
                (
                    "mayores_f",
                    models.PositiveSmallIntegerField(db_default=0, default=0, verbose_name="Mayores (60+) · femenino"),
                ),
                (
                    "mayores_m",
                    models.PositiveSmallIntegerField(
                        db_default=0,
                        default=0,
                        verbose_name="Mayores (60+) · masculino",
                    ),
                ),
                (
                    "dependientes",
                    models.PositiveSmallIntegerField(db_default=0, default=0, verbose_name="Personas con dependencia"),
                ),
                (
                    "mayores_dependientes",
                    models.PositiveSmallIntegerField(db_default=0, default=0, verbose_name="Mayores dependientes"),
                ),
                (
                    "lactantes",
                    models.PositiveSmallIntegerField(db_default=0, default=0, verbose_name="Lactantes"),
                ),
                (
                    "total_declarado",
                    models.PositiveSmallIntegerField(verbose_name="Total de personas declarado"),
                ),
                (
                    "responsable",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="grupos_emergencia",
                        to="legajos.ciudadano",
                        verbose_name="Responsable",
                    ),
                ),
            ],
            options={
                "verbose_name": "Grupo familiar de Emergencia",
                "verbose_name_plural": "Grupos familiares de Emergencia",
                "ordering": ["-creado", "-id"],
            },
        ),
        migrations.CreateModel(
            name="CasoEmergencia",
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
                        max_length=16,
                        unique=True,
                        verbose_name="N.° de caso",
                    ),
                ),
                (
                    "origen",
                    models.CharField(
                        choices=[
                            ("TERRITORIO", "Territorio"),
                            ("MESA", "Mesa"),
                            ("DISPOSITIVO", "Ingreso directo"),
                        ],
                        max_length=12,
                        verbose_name="Origen",
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("NUEVO", "Nuevo"),
                            ("EN_GESTION", "En gestión"),
                            ("DERIVADO", "Derivado"),
                            ("INGRESO_EN_CURSO", "Ingreso en curso"),
                            ("ALOJADO", "Alojado"),
                            ("CERRADO", "Cerrado"),
                        ],
                        db_default="NUEVO",
                        default="NUEVO",
                        max_length=20,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "prioridad",
                    models.CharField(
                        choices=[
                            ("ALTA", "Alta"),
                            ("MEDIA", "Media"),
                            ("BAJA", "Baja"),
                        ],
                        max_length=6,
                        verbose_name="Prioridad",
                    ),
                ),
                (
                    "latitud",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Latitud",
                    ),
                ),
                (
                    "longitud",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Longitud",
                    ),
                ),
                (
                    "precision_m",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Precisión del GPS (m)"),
                ),
                (
                    "direccion",
                    models.CharField(max_length=240, verbose_name="Dirección"),
                ),
                (
                    "necesidades",
                    models.JSONField(blank=True, default=dict, verbose_name="Necesidades"),
                ),
                (
                    "situacion",
                    models.JSONField(blank=True, default=dict, verbose_name="Situación"),
                ),
                ("relevado_en", models.DateTimeField(verbose_name="Relevado")),
                (
                    "tomado_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Tomado"),
                ),
                (
                    "derivado_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Derivado"),
                ),
                (
                    "aceptado_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Aceptado"),
                ),
                (
                    "alojado_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Alojado"),
                ),
                (
                    "cerrado_en",
                    models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Cerrado"),
                ),
                (
                    "motivo_cierre",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("NO_REQUIERE", "No requiere alojamiento"),
                            ("SIN_CONTACTO", "Sin contacto con la familia"),
                            ("ASISTIDO_DOMICILIO", "Asistido en domicilio"),
                            ("POR_SU_CUENTA", "Se alojó por su cuenta"),
                            ("OTRO", "Otro"),
                            ("TODOS_EGRESADOS", "Todos egresados"),
                        ],
                        max_length=20,
                        verbose_name="Motivo del cierre",
                    ),
                ),
                (
                    "observacion_cierre",
                    models.TextField(blank=True, verbose_name="Observación del cierre"),
                ),
                (
                    "total_alojado",
                    models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Personas alojadas"),
                ),
                (
                    "uuid_cliente",
                    models.UUIDField(
                        blank=True,
                        editable=False,
                        null=True,
                        unique=True,
                        verbose_name="Identificador del envío (app)",
                    ),
                ),
                (
                    "localidad",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="casos_emergencia",
                        to="core.localidad",
                        verbose_name="Localidad",
                    ),
                ),
                (
                    "relevado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="casos_emergencia_relevados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Relevado por",
                    ),
                ),
                (
                    "tomado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="casos_emergencia_tomados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Tomado por",
                    ),
                ),
                (
                    "grupo",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="caso",
                        to="programas.grupofamiliar",
                        verbose_name="Grupo familiar",
                    ),
                ),
            ],
            options={
                "verbose_name": "Caso de Emergencia",
                "verbose_name_plural": "Casos de Emergencia",
                "ordering": ["-creado", "-id"],
            },
        ),
        migrations.CreateModel(
            name="ContactoCaso",
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
                    "canal",
                    models.CharField(
                        choices=[
                            ("LLAMADA", "Llamada"),
                            ("WHATSAPP", "WhatsApp"),
                            ("SMS", "SMS"),
                            ("PRESENCIAL", "Presencial"),
                        ],
                        max_length=12,
                        verbose_name="Canal",
                    ),
                ),
                (
                    "resultado",
                    models.CharField(
                        choices=[
                            ("ATENDIO", "Atendió"),
                            ("NO_ATENDIO", "No atendió"),
                            ("NUMERO_ERRONEO", "Número erróneo"),
                            ("OTRO", "Otro"),
                        ],
                        max_length=16,
                        verbose_name="Resultado",
                    ),
                ),
                (
                    "observacion",
                    models.TextField(blank=True, verbose_name="Observación"),
                ),
                ("momento", models.DateTimeField(verbose_name="Momento del contacto")),
                (
                    "caso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contactos",
                        to="programas.casoemergencia",
                        verbose_name="Caso",
                    ),
                ),
                (
                    "por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contactos_emergencia",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contacto con la familia",
                "verbose_name_plural": "Contactos con la familia",
                "ordering": ["-momento", "-id"],
            },
        ),
        migrations.CreateModel(
            name="IntegranteGrupo",
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
                    "orden",
                    models.PositiveSmallIntegerField(verbose_name="N.° dentro del grupo"),
                ),
                (
                    "parentesco",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("JEFE", "Jefe/a de hogar"),
                            ("CONYUGE", "Cónyuge/pareja"),
                            ("HIJO", "Hijo/a"),
                            ("OTRO", "Otro"),
                        ],
                        max_length=10,
                        verbose_name="Parentesco",
                    ),
                ),
                (
                    "parentesco_otro",
                    models.CharField(blank=True, max_length=80, verbose_name="Otro parentesco"),
                ),
                (
                    "ficha",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Ficha individual (Formulario 2)",
                    ),
                ),
                (
                    "ficha_completa",
                    models.BooleanField(db_default=False, default=False, verbose_name="Ficha completa"),
                ),
                (
                    "confirmada_en",
                    models.DateTimeField(blank=True, null=True, verbose_name="Confirmada"),
                ),
                (
                    "egresado_en",
                    models.DateTimeField(blank=True, null=True, verbose_name="Egreso"),
                ),
                (
                    "ciudadano",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="integraciones_emergencia",
                        to="legajos.ciudadano",
                        verbose_name="Persona",
                    ),
                ),
                (
                    "estadia",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="integrantes_emergencia",
                        to="programas.estadia",
                        verbose_name="Estadía",
                    ),
                ),
                (
                    "grupo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="integrantes",
                        to="programas.grupofamiliar",
                        verbose_name="Grupo familiar",
                    ),
                ),
            ],
            options={
                "verbose_name": "Integrante del grupo familiar",
                "verbose_name_plural": "Integrantes del grupo familiar",
                "ordering": ["grupo_id", "orden"],
            },
        ),
        migrations.CreateModel(
            name="NumeradorEmergencia",
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
                    "serie",
                    models.CharField(
                        choices=[("C", "Casos"), ("K", "Entregas de kits")],
                        max_length=1,
                        verbose_name="Serie",
                    ),
                ),
                ("anio", models.PositiveSmallIntegerField(verbose_name="Año")),
                (
                    "ultimo",
                    models.PositiveIntegerField(db_default=0, default=0, verbose_name="Último número asignado"),
                ),
            ],
            options={
                "verbose_name": "Numerador de Emergencia",
                "verbose_name_plural": "Numeradores de Emergencia",
                "ordering": ["anio", "serie"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("serie", "anio"),
                        name="numerador_emergencia_serie_anio_unico",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="TrazaCaso",
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
                    models.CharField(blank=True, max_length=20, verbose_name="Estado anterior"),
                ),
                (
                    "estado_nuevo",
                    models.CharField(blank=True, max_length=20, verbose_name="Estado nuevo"),
                ),
                ("detalle", models.TextField(blank=True, verbose_name="Detalle")),
                (
                    "por_supervisor",
                    models.BooleanField(db_default=False, default=False, verbose_name="Por supervisor"),
                ),
                (
                    "caso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trazas",
                        to="programas.casoemergencia",
                        verbose_name="Caso",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="trazas_casos_emergencia",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "Traza de caso de Emergencia",
                "verbose_name_plural": "Trazas de casos de Emergencia",
                "ordering": ["creado_en", "id"],
                "base_manager_name": "objects",
                "default_manager_name": "objects",
            },
        ),
        migrations.CreateModel(
            name="AdjuntoCaso",
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
                    "archivo",
                    models.FileField(
                        upload_to=core.rutas_media.ruta_adjunto_emergencia,
                        validators=[core.validators.validar_foto],
                        verbose_name="Foto",
                    ),
                ),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("VIVIENDA", "Foto de la vivienda"),
                            ("ACCESO", "Foto del acceso"),
                        ],
                        max_length=10,
                        verbose_name="Tipo",
                    ),
                ),
                (
                    "cargado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Cargado por",
                    ),
                ),
                (
                    "caso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adjuntos",
                        to="programas.casoemergencia",
                        verbose_name="Caso",
                    ),
                ),
            ],
            options={
                "verbose_name": "Foto de un caso de Emergencia",
                "verbose_name_plural": "Fotos de casos de Emergencia",
                "ordering": ["caso_id", "tipo"],
                "constraints": [models.UniqueConstraint(fields=("caso", "tipo"), name="adjunto_caso_uno_por_tipo")],
            },
        ),
        migrations.CreateModel(
            name="Derivacion",
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
                    "estado",
                    models.CharField(
                        choices=[
                            ("PENDIENTE", "Pendiente"),
                            ("ACEPTADA", "Aceptada"),
                            ("RECHAZADA", "Rechazada"),
                            ("VENCIDA", "Vencida"),
                            ("CANCELADA", "Cancelada"),
                        ],
                        db_default="PENDIENTE",
                        default="PENDIENTE",
                        max_length=10,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "plazas_pedidas",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Plazas pedidas",
                    ),
                ),
                ("vence_en", models.DateTimeField(verbose_name="Vence")),
                (
                    "respondida_en",
                    models.DateTimeField(blank=True, null=True, verbose_name="Respondida"),
                ),
                (
                    "motivo",
                    models.CharField(blank=True, max_length=200, verbose_name="Motivo"),
                ),
                (
                    "observacion",
                    models.TextField(blank=True, verbose_name="Observación"),
                ),
                (
                    "clave_vigente",
                    models.PositiveBigIntegerField(
                        blank=True,
                        editable=False,
                        null=True,
                        verbose_name="Clave de vigencia",
                    ),
                ),
                (
                    "caso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derivaciones",
                        to="programas.casoemergencia",
                        verbose_name="Caso",
                    ),
                ),
                (
                    "derivada_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derivaciones_emergencia_hechas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Derivada por",
                    ),
                ),
                (
                    "dispositivo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derivaciones_emergencia",
                        to="programas.dispositivo",
                        verbose_name="Dispositivo",
                    ),
                ),
                (
                    "respondida_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derivaciones_emergencia_respondidas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Respondida por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Derivación de Emergencia",
                "verbose_name_plural": "Derivaciones de Emergencia",
                "ordering": ["-creado", "-id"],
                "indexes": [
                    models.Index(
                        fields=["dispositivo", "estado"],
                        name="programas_d_disposi_6036a2_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("clave_vigente",), name="derivacion_clave_vigente_unica"),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("clave_vigente__isnull", False),
                                ("estado__in", ["PENDIENTE", "ACEPTADA"]),
                            ),
                            models.Q(
                                ("clave_vigente__isnull", True),
                                ("estado__in", ["RECHAZADA", "VENCIDA", "CANCELADA"]),
                            ),
                            _connector="OR",
                        ),
                        name="derivacion_estado_coherente_con_la_clave",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="casoemergencia",
            index=models.Index(fields=["estado", "prioridad"], name="programas_c_estado_a2afe0_idx"),
        ),
        migrations.AddIndex(
            model_name="casoemergencia",
            index=models.Index(fields=["tomado_por", "estado"], name="programas_c_tomado__a4b0ea_idx"),
        ),
        migrations.AddConstraint(
            model_name="casoemergencia",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("estado", "CERRADO"), _negated=True),
                    ("cerrado_en__isnull", False),
                    _connector="OR",
                ),
                name="caso_emergencia_cerrado_con_marca",
            ),
        ),
        migrations.AddConstraint(
            model_name="integrantegrupo",
            constraint=models.UniqueConstraint(fields=("grupo", "orden"), name="integrante_orden_unico_por_grupo"),
        ),
        migrations.AddConstraint(
            model_name="integrantegrupo",
            constraint=models.UniqueConstraint(
                fields=("grupo", "ciudadano"), name="integrante_persona_unica_por_grupo"
            ),
        ),
        migrations.RunPython(ampliar_uuid_mysql, restaurar_uuid_mysql),
    ]
