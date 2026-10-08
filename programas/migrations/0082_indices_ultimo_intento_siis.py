"""Dos índices para «el último intento de este caso» (PERF-19).

``proceso_masivo.candidatos`` y ``validar_casos_siis`` deciden qué reintentar con una
subconsulta correlacionada —``WHERE formulario_id = ? ORDER BY creado DESC, id DESC
LIMIT 1``— que el motor resuelve **por fila** del recorte. Con solo el índice de la
clave foránea tiene que juntar todos los intentos del caso y ordenarlos; con
``(formulario, creado, id)`` lee una sola entrada hacia atrás y corta.

**Online en los dos motores.** Son índices secundarios sobre tablas chicas al lado de
``programas_formulario`` (decenas de miles de filas): InnoDB los crea con
``ALGORITHM=INPLACE, LOCK=NONE``, sin reescribir la tabla y sin bloquear escrituras.
Django no escribe las cláusulas, las elige el motor; el job «Migrate ida y vuelta» las
aplica y desaplica contra MariaDB 10.11 y MySQL 8.0.

**Expand puro y reversible.** Un índice no cambia ningún resultado: la release anterior
sigue funcionando con él puesto, y ``RemoveIndex`` lo deshace. No hay contrato que
cumplir con ``scripts/check_migraciones.py`` (no agrega columnas, no borra nada y no
corre datos), pero la reversa existe y es exacta.
"""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0081_formulario_version_capturada"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="enviosiis",
            index=models.Index(fields=["formulario", "creado", "id"], name="idx_enviosiis_ultimo"),
        ),
        migrations.AddIndex(
            model_name="validacionsis",
            index=models.Index(fields=["formulario", "creado", "id"], name="idx_validacionsis_ult"),
        ),
    ]
