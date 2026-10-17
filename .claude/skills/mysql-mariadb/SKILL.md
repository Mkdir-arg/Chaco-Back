---
name: mysql-mariadb
description: Patrones de MySQL 8 y MariaDB para Chaco — esquema, índices, consultas, transacciones, migraciones y diagnóstico — con las trampas que ya cobraron en ECOM (UUID con guiones, CONVERT_TZ, UniqueConstraint condicional, read_timeout de 10 s). Usala al diseñar un modelo o índice, al escribir una migración sobre una tabla grande, o cuando una consulta, un bloqueo o un 500 aparece solo en producción.
---

# MySQL y MariaDB en Chaco

Adaptada de la skill `mysql-patterns` de [ECC](https://github.com/affaan-m/ECC)
(MIT, © 2026 Affaan Mustafa), reducida a lo que aplica a un Django sobre los dos motores.

## Primero: qué motor y qué versión

Chaco corre en **dos motores a la vez** y el código tiene que andar en los dos:

| Ambiente | Motor |
|---|---|
| Local, CI efímero, icore-srv (DEV) | MySQL 8 (icore-srv pineado en 8.0.32) |
| ECOM testing y PRD | **MariaDB** (testing: 10.11) |
| Tests (`PYTEST_RUNNING=1`) | SQLite en memoria — **no** prueba nada de lo de abajo |

```sql
SELECT VERSION();
SHOW VARIABLES LIKE 'version_comment';
```

Un test verde en SQLite no demuestra que la regla exista en MySQL/MariaDB. Si la
corrección depende del motor, se mide en el banco de `scripts/perf_mysql/` (ver su README)
o en el job `Ephemeral MySQL Redis Contract` del CI.

## Trampas conocidas (leer antes de diseñar)

1. **`UUIDField` en MariaDB 10.7+ viaja con guiones** (36 caracteres). Una columna
   `char(32)` da *"Data too long"* y `campo=uuid` no encuentra filas guardadas en hex.
   Todo `UUIDField` nuevo lleva su migración a `char(36)` (patrón de `programas.0073`) y
   se busca con `q_uuid_en_texto` (`programas/services/becas.py`). Cambio 99.
2. **La base de ECOM no tiene tablas de timezone.** `TruncDate`/`TruncWeek`/`Trunc*` sobre
   un `DateTimeField` con `USE_TZ` se traduce a `CONVERT_TZ`, que devuelve `NULL`: rompe
   **solo en producción**. Agrupar en Python (`programas/services/dashboard_becas.py`).
3. **`UniqueConstraint(condition=...)` no existe en MySQL/MariaDB.** Django la descarta en
   silencio, pero en SQLite sí la crea: el CI pasa y la regla no está en prod. Usar
   `select_for_update()` en el servicio o un `UNIQUE` sobre una columna anulable.
4. **`read_timeout` y `write_timeout` son de 10 s** (`config/settings.py`). Una consulta
   lenta no es "lenta": es un 500. Los `IN` anidados y decodificar JSON en Python sobre
   miles de filas fueron la causa del 500 del dashboard.
5. **JSON:** `KeyTransform` trata una clave numérica como índice de array. Para claves
   como `"12"`, usar `JSON_EXTRACT` con la ruta explícita (`'$."12"'`).
6. **`Exists()` sobre una FK casi siempre `NULL`** termina en un scan por fila. Resolver
   antes el alcance a una lista de ids.
7. **Función sobre una columna en el `WHERE` + `select_for_update()`** bloquea filas de más
   y arma cola (Cambio 91). El predicado de un lock tiene que poder usar índice.
8. Restaurar un dump de PRD sobre una base que tuvo el constructor deja tablas huérfanas y
   el deploy muere con *"Table already exists"*: se borran, **nunca** `--fake`.

## Esquema

| Caso | Preferir | Evitar |
|---|---|---|
| Texto visible | `utf8mb4` (es el charset de las conexiones) | `utf8`/`utf8mb3` |
| Montos y cantidades exactas | `DecimalField` | `FloatField` |
| Fechas | `DateTimeField` en UTC con `USE_TZ`; agrupar por día en Python | `Trunc*` en SQL (trampa 2) |
| Estados que cambian | `CharField` con `choices` | `ENUM` nativo |
| Datos de extensión | `JSONField` | `JSONField` para lo que se filtra, se une o tiene FK |
| Unicidad condicional | servicio con `select_for_update()` | `UniqueConstraint(condition=…)` (trampa 3) |

Si un camino JSON se filtra seguido, conviene subirlo a una columna real con índice.

## Índices

El orden de un índice compuesto suele ser: igualdades primero, después rango u orden.

```python
class Meta:
    indexes = [models.Index(fields=["relevamiento", "estado", "creado"])]
```

Antes de agregar o cambiar un índice, `EXPLAIN` contra datos de tamaño real (banco
`chaco_perf_ci`, no SQLite):

| Campo | Señal de riesgo |
|---|---|
| `type` | `ALL` sobre una tabla grande |
| `key` | `NULL` con un predicado selectivo |
| `rows` | estimación muy alta en un camino interactivo |
| `Extra` | `Using temporary`, `Using filesort`, `Using where` amplio |

Cada índice suma costo de escritura, tiempo de migración y tamaño de backup: no agregar a
ciegas. Los presupuestos de consultas del CI viven en `scripts/perf_budgets.json`.

## Consultas

- **Columnas explícitas** en caminos calientes: `.only()`/`.values()` en vez de traer el
  modelo entero. Ojo: `.only("pk")` sobre un manager relacionado puede abrir un N+1.
- **Paginación profunda con `OFFSET`** escanea y descarta filas. En listados grandes,
  paginar por clave (`WHERE (creado, id) < (%s, %s) ORDER BY creado DESC, id DESC`)
  con un índice que coincida con el cursor.
- **Upsert** compatible con los dos motores: `ON DUPLICATE KEY UPDATE col = VALUES(col)`.
  La forma con alias de fila (`AS new`) es solo MySQL. Desde el ORM,
  `bulk_create(update_conflicts=True, ...)` ya lo resuelve.
- **SQL crudo**, siempre con parámetros (`cursor.execute(sql, [valor])`), nunca f-strings.

## Transacciones y bloqueos

- Transacciones cortas. Las llamadas externas (RENAPER, SIIS, correo) van **fuera** de
  `transaction.atomic()`: con `read_timeout` de 10 s, una integración lenta adentro de un
  lock deja filas tomadas.
- Bloquear filas siempre en el mismo orden (`select_for_update().order_by("pk")`).
- El predicado de `select_for_update()` tiene que usar índice (trampa 7).
- Ante un deadlock: rollback y reintento de la transacción entera, con tope de reintentos.
  `SHOW ENGINE INNODB STATUS\G` enseguida: el siguiente evento lo pisa.
- `SKIP LOCKED` solo para trabajo tipo cola, donde saltear una fila tomada es aceptable.

## Migraciones sobre MySQL/MariaDB

El contrato de Chaco manda (`CLAUDE.md` y `scripts/check_migraciones.py`): columna nueva
`null=True` o con `DEFAULT` real en la base, `# CONTRACT:` en los borrados y renombres,
reversa declarada en todo `RunPython`/`RunSQL`. Además, por el motor:

- **El DDL de MySQL/MariaDB no es transaccional.** Una migración con varias operaciones
  que falla a la mitad deja la base a mitad: Django no la revierte. Preferir una operación
  de esquema por migración cuando la tabla es grande, y separar esquema de datos.
- **Expandir y contraer** para renombres y borrados: agregar lo nuevo, escribir en los
  dos lados, rellenar, leer de lo nuevo y recién dos releases después borrar lo viejo.
  `SeparateDatabaseAndState` saca el campo del modelo sin tocar la columna.
- **Rellenos en lotes**, no un `UPDATE` de toda la tabla:

  ```python
  def rellenar(apps, schema_editor):
      Caso = apps.get_model("programas", "Formulario")
      pendientes = Caso.objects.filter(nuevo_campo__isnull=True).values_list("pk", flat=True)
      while ids := list(pendientes[:2000]):
          Caso.objects.filter(pk__in=ids).update(nuevo_campo=...)
  ```

- Las migraciones sin vuelta están en el paso D.4 de `docs/internal/processes.md`: si la
  tuya entra en esa lista, se dice antes de mergear.

## Diagnóstico

```sql
SHOW FULL PROCESSLIST;
SHOW ENGINE INNODB STATUS\G
EXPLAIN SELECT ...;
```

`EXPLAIN ANALYZE` ejecuta la consulta: solo en el banco local, nunca en ECOM.

## Qué devolver cuando se usa para revisar

1. Motor y versión que se asumen, y si la recomendación cambia entre MySQL y MariaDB.
2. Riesgos más altos: corrección, bloqueos, trampas de la lista, migración.
3. El cambio concreto (modelo, consulta o migración).
4. Cómo se valida: `EXPLAIN` o banco `scripts/perf_mysql/`, presupuesto de consultas,
   `check_migraciones.py` y criterio de reversa.
