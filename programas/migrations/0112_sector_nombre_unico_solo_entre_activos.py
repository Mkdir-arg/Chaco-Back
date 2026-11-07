from django.db import migrations


class Migration(migrations.Migration):
    """El nombre del sector deja de ser único en la base: lo es solo entre los ACTIVOS.

    MySQL y MariaDB no tienen índice único condicional (Django descarta la `condition` en
    silencio y SQLite sí la crea, así que el CI pasaría en verde sin que la regla exista en
    producción). La regla vive en `programas.services.plazas._exigir_nombre_libre`, bajo el
    bloqueo de la fila del dispositivo.

    Es expand para el código viejo: sin el UNIQUE, la release anterior sigue dando de alta (ella
    misma pregunta por el nombre antes de crear), así que no hace falta marca de CONTRACT.

    REVERSA: `migrate programas 0111` vuelve a crear el UNIQUE (dispositivo, nombre). Falla si
    para entonces hay un sector inactivo y uno activo del mismo dispositivo con el mismo nombre
    (justo lo que esta migración permite). Antes de volver atrás hay que renombrar esos
    duplicados:
        SELECT dispositivo_id, nombre, COUNT(*) FROM programas_sector
        GROUP BY dispositivo_id, nombre HAVING COUNT(*) > 1;
    """

    dependencies = [
        ("programas", "0111_preguntaglobal_fuente_opciones_depende_de"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="sector",
            name="sector_nombre_unico_por_dispositivo",
        ),
    ]
