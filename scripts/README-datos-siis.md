# Los insumos del alta en SIIS (`DATOS_SIIS_DIR`)

El circuito de alta masiva en SIIS necesita tres `.sql` que **no están en este
repositorio y no pueden volver a estarlo**: son volcados con datos personales reales
—nombre, DNI, CUIL, fecha de nacimiento y domicilio de personas, menores incluidos—.
Hasta el 04/10/2026 estaban versionados, viajaban al release de `main`, de ahí al
GitLab de ECOM y, por el `COPY . .` del `Dockerfile`, **dentro de la imagen de
producción**. Eso se cerró con el Cambio 116 (hallazgo RED-01 de la auditoría de
octubre de 2026).

Este archivo es el único que queda versionado: dice qué archivos hacen falta, de
dónde salen y cómo se los ve el sistema. **No contiene ningún dato.**

## Los tres archivos

| Archivo | Tabla que carga | Para qué | Quién lo genera |
|---|---|---|---|
| `Aprobados.sql` | `aprobados_materias` | Decide quién va a SIIS: solo se informan los casos cuyo DNI figure ahí | El organismo, exportando la columna de DNI de su planilla de aprobados. El molde está en [`aprobados_materias_plantilla.sql`](aprobados_materias_plantilla.sql), versionado y sin datos |
| `Localidades.sql` | `localidades_corregidas` | Una fila por persona: DNI y la localidad de su domicilio tal como la tiene el organismo. Reemplaza la localidad de los casos cuyo texto no cruza el catálogo de SIIS | El organismo, desde la misma planilla |
| `DatosPersonas.sql` | `ciudadanos_renaper` | CUIL y fecha de nacimiento que devolvió RENAPER para un lote de DNI | Lo genera el equipo corriendo la consulta a RENAPER sobre el padrón de la convocatoria y volcando la respuesta cruda |

Los tres son `INSERT` sobre tablas que ningún modelo de Django declara: las crea y las
borra el propio `.sql`, y se cruzan en Python, no con un `JOIN` (pueden quedar con otra
intercalación que la de la aplicación, y ahí MariaDB corta con *«Illegal mix of
collations»*).

## Dónde se ponen

En el directorio que apunta la variable de entorno **`DATOS_SIIS_DIR`** (por defecto
`/datos-siis`), montado como volumen o secret en el pod y como bind mount en icore.
Nunca dentro del árbol del repositorio ni en la imagen.

```bash
# icore-srv / docker compose
DATOS_SIIS_DIR=/datos-siis
#   volumes:
#     - /srv/datos-siis:/datos-siis:ro
```

Permisos: solo lectura para el proceso de la aplicación, y el directorio del host
cerrado al resto (`chmod 750`, dueño el usuario del deploy). Son datos del Título VI
de la Ley 25.326.

## Cómo se usan

`manage.py correr_alta_siis` los ejecuta desde el propio pod en su paso 2 —el pod no
trae cliente de base—, en el orden en que están en la tabla de arriba:

```bash
python manage.py correr_alta_siis --solo-precondiciones        # revisa y sale
python manage.py correr_alta_siis                              # ensayo completo
python manage.py correr_alta_siis --aplicar --usuario coord    # para en el caso de prueba
python manage.py correr_alta_siis --aplicar --usuario coord --continuar
```

Para una corrida puntual contra otro directorio, sin tocar el entorno del pod:

```bash
python manage.py correr_alta_siis --scripts /ruta/a/los/sql
```

Si el directorio no existe, el comando **corta antes de tocar nada** y nombra la
variable. `completar_casos_renaper` y `corregir_datos_siis`, que esperan la tabla ya
cargada, dicen lo mismo si no la encuentran.

Si hace falta cargarlos a mano (el cliente de base está afuera del pod):

```bash
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < $DATOS_SIIS_DIR/Aprobados.sql
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < $DATOS_SIIS_DIR/Localidades.sql
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < $DATOS_SIIS_DIR/DatosPersonas.sql
```

## Qué impide que vuelvan al repositorio

Cuatro barreras, todas con test en `core/tests/test_release_sin_datos.py`:

1. **`.gitignore`** — `scripts/*.sql`, con excepción explícita de la plantilla sin datos.
2. **`.gitattributes`** — `export-ignore` sobre `scripts/*.sql`: aunque alguien fuerce
   uno al índice, no sale en el release de `main` ni en el espejo de ECOM.
3. **`.dockerignore`** — `scripts/*.sql`: el `COPY . .` del `Dockerfile` no los mete en
   la imagen.
4. **El gate `Sin datos personales`** ([`scripts/check_datos_personales.py`](check_datos_personales.py))
   — corre en cada PR **y en cada push a `development`** (`.github/workflows/pr-datos.yml`),
   y en `publish-main.yml` dos veces: sobre los archivos versionados **antes** de que
   `git archive` aplique el `export-ignore`, y sobre el árbol del release después.
   Rechaza un archivo por cuatro motivos:

   | | Qué mira |
   |---|---|
   | Techo de tamaño | Más de 512 KB. La red para el formato que no reconocemos (JSON, Parquet, un export binario). Las exenciones son **rutas exactas** de los seis archivos grandes que ya estaban versionados, nunca un glob de directorio |
   | `INSERT` con columnas | La lista de columnas nombra `dni`, `cuil`, `cuit`, `apellido`, `fecha_nac` o `domicilio`, y hay más de 100 filas |
   | `INSERT` sin columnas | Lo que emite `mysqldump` por defecto: más de 100 filas y, en el contenido, más de 100 documentos o más de 50 CUIL distintos |
   | Tabular sin SQL | `.csv`, `.tsv`, `.dump`, `.dat`, `.sql` con más de 100 líneas y más de 100 documentos distintos. Un padrón de 5.000 DNI en CSV pesa 60 KB: no lo atrapa ningún techo |

   La plantilla sin datos pasa a propósito: tiene el `INSERT` con `dni`, pero tres filas
   de ejemplo. Lo que distingue un volcado de una plantilla es el volumen.

   El gate **todavía no bloquea el merge**: eso lo habilita RED-20, que crea los
   rulesets de rama. Mientras tanto, el disparador por `push` es lo que cubre un
   `git push origin development` directo.
