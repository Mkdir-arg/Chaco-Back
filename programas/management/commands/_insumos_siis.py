"""Los `.sql` del organismo que alimentan el alta en SIIS, y de dónde salen.

Son tres volcados con datos personales reales —la respuesta de RENAPER para 10.321
personas con domicilio, los DNI de aprobados y las localidades por DNI—. Hasta el
04/10/2026 estaban versionados en el repositorio, que es público, y viajaban dentro
de la imagen de producción por el `COPY . .` del `Dockerfile` (RED-01).

Ahora viven fuera del código: en el directorio que apunta ``settings.DATOS_SIIS_DIR``,
montado como volumen o secret en el pod y como bind mount en icore. Este módulo
centraliza la lista y los mensajes de error para que los tres comandos que dependen
de ellos digan lo mismo y nombren la variable.

El guión bajo del nombre no es decorativo: Django no lo toma como un comando
(``find_commands`` saltea lo que empieza con ``_``).
"""

# (tabla que carga, archivo que la carga, para qué sirve)
INSUMOS = (
    ("aprobados_materias", "Aprobados.sql", "decide quién va a SIIS"),
    ("localidades_corregidas", "Localidades.sql", "localidades del organismo"),
    ("ciudadanos_renaper", "DatosPersonas.sql", "CUIL y fechas de RENAPER"),
)

FALTA_DIRECTORIO = (
    "No existe el directorio de insumos {base}. Los .sql del organismo ya no viajan en la imagen: "
    "tienen datos personales reales y no pueden estar en el código (RED-01). Montá el directorio en "
    "el pod y apuntá DATOS_SIIS_DIR ahí, o pasá --scripts <dir> en esta corrida. De dónde salen los "
    "volcados y quién los genera: scripts/README-datos-siis.md."
)


def falta_tabla(tabla, archivo):
    """Mensaje único para «la tabla no está cargada», nombrando la variable."""
    return (
        f"No existe la tabla `{tabla}`. Cargala primero con {archivo}, que está en el directorio que "
        "apunta DATOS_SIIS_DIR (ver scripts/README-datos-siis.md), o corré `manage.py correr_alta_siis`, "
        "que la carga sola."
    )
