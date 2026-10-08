"""Esquema de la Ola 2 PR 1: la clave estable de los roles sembrados y el registro de
capacidades revocadas.

**Expand puro, las dos.** ``RolMeta.clave`` nace ``NULL`` (el código viejo no la escribe
y la fila sigue entrando), con índice único que admite varios ``NULL`` en MySQL y
MariaDB. ``users_capacidadrevocada`` es una tabla nueva: nadie la lee todavía salvo la
``0031``, y su reversa.

Las dos tablas son chicas (``users_rolmeta`` tiene una fila por rol: decenas), así que
el ``ALTER`` es instantáneo en los dos motores.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("users", "0028_sembrar_ciudadano_exportar"),
    ]

    operations = [
        migrations.AddField(
            model_name="rolmeta",
            name="clave",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="Identificador estable de los roles que crea el arranque. Vacío en los roles creados a mano.",
                max_length=50,
                null=True,
                unique=True,
                verbose_name="Clave del rol sembrado",
            ),
        ),
        migrations.CreateModel(
            name="CapacidadRevocada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codename", models.CharField(max_length=100, verbose_name="Capacidad (codename)")),
                ("migracion", models.CharField(max_length=100, verbose_name="Migración que la quitó")),
                ("creado", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                (
                    "grupo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="capacidades_revocadas",
                        to="auth.group",
                        verbose_name="Rol",
                    ),
                ),
            ],
            options={
                "verbose_name": "Capacidad revocada por una migración",
                "verbose_name_plural": "Capacidades revocadas por migraciones",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("grupo", "codename", "migracion"), name="users_capacidadrevocada_unica"
                    )
                ],
            },
        ),
    ]
