# Rúbrica: rendimiento y base de datos

Junta las búsquedas activas de rendimiento (heredadas del antiguo agente de revisión de
desarrollo, ya retirado) con las trampas del ORM que se midieron en el banco MySQL con volumen real y que los tests sobre
SQLite no reproducen. En producción (ECOM, MariaDB) la conexión tiene `read_timeout` de **10 s**:
una consulta lenta no es una pantalla lenta, es un **500**.

## Severidad

| Situación | Modo `pr` | Modo `completa` |
|---|---|---|
| Consulta que crece con el volumen en un camino caliente (listado, link público, dashboard, export) | `[MAJOR]` | ALTA |
| Lo anterior dentro de un `select_for_update()` o en el link público | `[BLOCKER]` | CRÍTICA |
| N+1 acotado por la paginación (≤ 25 filas) | `[MINOR]` | MEDIA |
| Optimización sin medición que la respalde | no se reporta | INFO, con la medición que haría falta |

No pidas micro-optimizaciones sin un número que las justifique.

## Búsquedas activas

No alcanza con leer: buscá estos patrones en el código del alcance.

- `list(` sobre querysets en vistas, templates o reportes.
- `.count()` repetido o dentro de un loop.
- `for … in qs` seguido de acceso a relaciones sin `select_related`/`prefetch_related`.
- `prefetch_related` en reportes donde alcanza `values().annotate()`.
- Filtros `__date`, `icontains` o funciones sobre columnas calientes.
- `|length` en templates sobre querysets no acotados.
- Endpoints o listados sin `paginate_by`, `Paginator` o límite explícito.
- Datos, permisos o contadores calculados en el template en vez de la vista o el selector.
- Solapas con listados grandes precargados aunque el usuario no las abra.
- Exportaciones o reportes sin streaming ni paginación.

## Trampas medidas en Chaco

Cada una ya costó un 500 o una pantalla de minutos. Estas cinco no están todas en la skill
`mysql-mariadb`, así que van acá completas:

1. **`Exists(campo_fk=OuterRef("pk"))` sobre una FK casi toda `NULL`** (p. ej. `duplicado_de_id`):
   MySQL le asigna cardinalidad 1, descarta el índice y hace un scan completo **por fila** (131 M
   filas leídas en el banco). Un índice compuesto no lo arregla. Solución: resolver por lote con
   `IN` sobre los ids de la página.
2. **`.only("pk")`/`.defer()` sobre un manager relacionado** (`relevamiento.formularios.only(...)`):
   Django empareja cada fila con el padre leyendo la FK; si está diferida, hace una consulta por
   fila. Solución: `Modelo.objects.filter(padre=...)`. Al revés, sin `defer` el manager relacionado
   conviene: deja el padre apuntado y los `__str__` no lo vuelven a leer.
3. **`TruncDate` también sobre un `DateField`** emite `DATE(CONVERT_TZ(...))`, que en ECOM da
   `NULL` (no hay tablas de timezone). `TruncMonth` sobre `DateField` no lo hace. Solución: agrupar
   por la columna, o en Python.
4. **Paginar con `select_related` en la consulta paginada:** MySQL arranca por la tabla chica,
   materializa todo y recorta al final. Solución: elegir la página con `only("pk")` y rehidratar
   con `pk__in` y los `select_related`.
5. **Función sobre la columna en el `WHERE`** (`REPLACE(CAST(client_uuid))`, `JSON_EXTRACT` con
   `OR`): anula el índice y recorre todas las filas del relevamiento o la convocatoria. Con un
   `select_for_update()` tomado, además arma cola y el que espera más de 10 s recibe el 500
   (Cambio 91: 165 errores en el link público).

Y las de la skill `mysql-mariadb` (§*Trampas conocidas*, §*Consultas*, §*Transacciones y
bloqueos*): `IN` anidados y decodificar JSON en Python sobre miles de filas (el 500 del
dashboard), `OFFSET` profundo, `KeyTransform` con claves numéricas, transacciones largas con
llamadas externas adentro, bloqueos en distinto orden.

## Cómo medir (y qué ya mide el CI)

| Herramienta | Qué da | ¿Lo corre el CI? |
|---|---|---|
| `zeal` (activo con `PYTEST_RUNNING`, `ZEAL_RAISE = True`) | N+1 en la suite | sí: no lo repitas |
| Tests `@tag("performance")` + `scripts/perf_budgets.json` | presupuesto de consultas por ruta | sí, y `check_perf_budgets.py` frena subir un presupuesto sin justificar |
| `scripts/perf_audit.py --scale 200 --output <archivo>` | consultas y tiempos de las superficies clave sobre SQLite, sin base | no: sirve como línea de base del modo `completa` |
| Banco MySQL `scripts/perf_mysql/` (`bench_mysql.py`, `perfil_ruta.py`; receta en su `README.md`) | tiempos reales con 20.000 casos y las `OPTIONS` de producción; `EXPLAIN ANALYZE` | no: pedirlo cuando un hallazgo depende del plan de ejecución |

Los conteos del CI (SQLite, pocos datos) y los tiempos del banco (MySQL, volumen real) miden cosas
distintas: un presupuesto en verde dice cuántas consultas hay, no que cada una escale.

## Qué devolver

Por hallazgo: el patrón, la ruta o pantalla afectada, la estimación de filas o consultas que
crece (y con qué crece: casos, inscriptos, programas), la solución concreta y cómo verificarla
(test con `assertNumQueries`, entrada en `perf_budgets.json` o medición en el banco).
