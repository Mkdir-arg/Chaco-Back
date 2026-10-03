# Anexo · Mediciones de performance (verificación V4)

Datos crudos: `poc/perf_harness/v4_mediciones.json`. Harness: `poc/perf_harness/tests.py`. Sonda de conexiones:
`poc/perf_harness/asgi_conn_probe.py`.

## Método y límites
- Base `origin/development @ 917e583`, `.venv312` (Python 3.12 + Django 5.2.17, igual al CI).
- El contenedor MySQL/MariaDB del banco (`chaco-mysql-dash`, puerto 3308) no estaba disponible (Docker apagado). Todo se
  midió en **SQLite en memoria** con la misma forma de datos que el banco: `seed_perf --scale 200` +
  `scripts/perf_mysql/escalar_bench.py::main(20000)` = un relevamiento público de 20.000 casos con foto, respuestas,
  trazas, validaciones y adjuntos.
- SQLite da: conteos exactos de sentencias (`connection.execute_wrapper`; no `CaptureQueriesContext`, que corta en
  9.000), el SQL generado y el costo en Python (cProfile, tracemalloc).
- **No** da el plan de MariaDB ni la latencia de ida y vuelta: esos puntos quedan **NO-MEDIDO en MariaDB** y se razonan con
  las mediciones de los Cambios 66, 91, 92 y 93. Antes de cerrar un ítem de performance, medir en el banco
  `scripts/perf_mysql/` (contenedor 3308, base `chaco_perf_ci`; receta en su README) con `EXPLAIN ANALYZE`.
- El JSON tiene además una corrida chica (5.000 casos) en las claves sin sufijo; las cifras de 20k están en las claves
  `*-exacto`, `*-perfil`, `*-antes-despues` y en el texto de V4.

## Tabla de mediciones

| ID | Qué se midió | Resultado |
|---|---|---|
| PERF-01 | `armar_payload` por llamada | **6 consultas** (2 catálogo + 2 `provinciasiis` + 2 `localidadsiis`); 8 con `ProvinciaSiis` cargado (+2 `AliasLocalidadSiis`) |
| PERF-01 | `elegir_completos` sobre 200 casos | 1.200 consultas; 554 ms en SQLite; 2,53 ms/caso sin profiler; cProfile: `compiler.as_sql` 1,2 de 3,0 s |
| PERF-01 | Proyección a 7.496 candidatos | 45-60 mil consultas → ~40-65 s con 0,5-1 ms de RTT a MariaDB, antes del primer latido (SIIS-03) |
| PERF-01 / V4-NEW-02 | `hidratar()` | 1 consulta por lote; trae `definicion` y `respuestas`: 5.981 B de JSON por caso, 5.292 B de `definicion` (88 %) |
| PERF-02 | Página de cupo (20k; 9.151 ENVIADO y 8.932 APROBADO en el segmento) | página 1: 16 consultas, 226 ms; página 50: 13 consultas, 540 ms (SQLite). SQL con todas las columnas de `programas_formulario` (incluye `respuestas`, `definicion`, `datos_siis`) + 3 joins, `ORDER BY modificado ASC LIMIT 50 OFFSET 2450`. MariaDB NO-MEDIDO (forma idéntica a la que el Cambio 93 midió en 4,4 s frío / 2,1 s caliente) |
| PERF-03 | Excel de respuestas, 20.000 × 22 columnas | `respuestas_por_persona` 1,22 s; `respuesta_libro` 9,24 s; request 8,92 s; xlsx 1,99 MB; pico 37,2 MB (tracemalloc); cProfile: casi todo `et_xmlfile` (sin `lxml`); `celda_segura` ~6 % |
| PERF-03 | GZip del xlsx (A4-15, refutado) | comprime al 43 % (1,99 → 0,86 MB) en 0,12 s = 1,3 % del request |
| PERF-04 | Cruce de padrón: 6.667 pendientes, padrón de 50.000 filas | **13.942 sentencias**: 6.667 `UPDATE legajos_ciudadano`, 6.667 `INSERT programas_tracaformulario`, 556 `INSERT programas_padronhabilitado` (SQLite parte el lote; MySQL = 1 INSERT), 47 `UPDATE programas_formulario`; **26.668 `cache.delete`**; 18,4-27 s en SQLite; 36 s con profiler (13,7 s en el `bulk_update` con `CASE WHEN`, 10,7 s en 6.668 `bulk_create` de a 1, 3,9 s en `save()`) |
| PERF-04 | Prototipo `validar_casos_pendientes_v4` | **676 sentencias** (556 INSERT padrón, 81 INSERT traza, 27 UPDATE ciudadano, 7 UPDATE formulario), 0 señales, mismos 6.667 validados y 22.266 trazas; 13,6 s en SQLite |
| PERF-04 | Tamaño del INSERT único del padrón | ~161 B/fila → 8,06 MB para 50k; con 2 columnas ~150k filas = 15-18 MB (límite `max_allowed_packet` 16 MB por defecto en MariaDB) |
| PERF-07 | `candidatos().count()` con la lista real de `Aprobados.sql` | set de 15.532 literales; **188 KB de SQL** (193 KB el GET entero); 72 ms en SQLite; GET = 13 consultas (1 `SELECT dni` de toda la tabla, 1 `table_names()`); recarga cada 5 s con corrida en curso |
| PERF-08 | Sonda ASGI (Django puro, `ASGIHandler`) con `CONN_MAX_AGE=60` | 200 requests → 200 hilos distintos y 200 conexiones nuevas, ninguna reutilizada; 9 abiertas al final hasta `gc.collect()` (50 de 50 con GC apagado); con `CONN_MAX_AGE=0`, 0 abiertas |
| PERF-10 | Presión de sesiones del link público | 350 MB con sesiones de 0,5-1 KB = 350-700 mil visitas únicas en 24 h (10-20× el objetivo de 40k) |
| PERF-11 | Peso de la foto | `definicion` = 5,3 de 6,0 KB de JSON por caso (88 %); todos los casos del banco comparten la misma foto |
| PERF-12 | Paso 1 GET del link público | 6 consultas, una `SELECT COUNT(*) FROM programas_formulario WHERE relevamiento_id = X` |
| PERF-16 | Señal de `Ciudadano.save()` | 4 `cache.delete` por save (`contar_ciudadanos` dos veces) |
| PERF-19 | SQL de `candidatos()` | `WHERE ((SELECT estado … LIMIT 1) IS NULL OR NOT ((SELECT estado …) = 'ENVIADO'))`: dos subconsultas correlacionadas por fila |
| PERF-20 | `generar_alertas`, 20.200 ciudadanos activos (200 con legajo) | **61.821 sentencias** (20.201 `SELECT legajos_ciudadano`, 20.200 `UPDATE legajos_alertaciudadano`, 20.200 `SELECT legajos_legajoatencion`, 400 `SELECT historialcontacto`, 310 SELECT + 310 INSERT de alertas, 200 `SELECT inscripcionprograma`); 38 s en SQLite; corrida 2: 61.611; alertas en la tabla 200 → 510 → 610 |

## Criterios de cierre en el banco (MariaDB)
| Ítem | Criterio |
|---|---|
| PERF-04 | Subir por `cargar_padron` el xlsx de los pendientes de la convocatoria del relevamiento público de 20k: el request baja de forma clara y queda < 30 s; conteo con `execute_wrapper` ≈ prototipo |
| PERF-02 | `EXPLAIN ANALYZE` de las dos consultas de página: desaparecen `Using temporary` y la materialización de `programas_relevamiento`; presupuesto en `perf_budgets.json` = medido + 1 |
| PERF-03 | `perfil_ruta.py /becas/config/programas/<p>/dashboard/respuestas/<c>/xlsx/ 1` con 20k: de 5,7 s (Cambio 93) a < 3 s |
| PERF-07 | `EXPLAIN ANALYZE` del `count()` antes y después de PERF-19; presupuesto `becas_proceso_masivo` = medido + 1 |
| PERF-13 | `EXPLAIN ANALYZE` de `/becas/revision/?estado=BAJA&page=10` antes de decidir el índice |
| G1b-11 / G2-01 | Export del dashboard y segunda pasada de `respuestas` con 20k casos en MariaDB (no MySQL 8) |
| PERF-08 | En ECOM, `SHOW STATUS LIKE 'Threads_connected'` antes y después |
