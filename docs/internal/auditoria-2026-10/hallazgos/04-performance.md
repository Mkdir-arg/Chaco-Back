# 4.4 Performance (PERF, G1b-11, G1c-09/11, G3-03)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. Mediciones y método: `../anexo-mediciones-performance.md`
y `poc/perf_harness/`.

**Cómo se midió (V4).** Docker estaba apagado: todo se midió en **SQLite en memoria** con la forma de datos del banco
(`seed_perf --scale 200` + `scripts/perf_mysql/escalar_bench.py::main(20000)`: un relevamiento público de 20.000 casos).
SQLite da conteos exactos de sentencias (`execute_wrapper`), el SQL generado y el costo en Python. **No** da el plan de
MariaDB ni la latencia de ida y vuelta: esos puntos quedan **NO-MEDIDO en MariaDB** y se miden en el banco
`scripts/perf_mysql/` (contenedor 3308, base `chaco_perf_ci`) antes de cerrar cada ítem. Presupuestos de consultas:
`scripts/perf_budgets.json` + `scripts/perf_audit.py::build_targets` (los dos en el mismo PR: `core/tests/test_performance_budgets.py`
exige que coincidan).

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| PERF-04 | Carga de padrón: cruce caso por caso (13.942 sentencias) | ALTA | CONF. medido; prototipo listo | 4 | M | ✅ |
| PERF-02 | Cupo y beneficiarios: páginas anchas con join | ALTA | CONF. medido en MariaDB (8,99 s de SQL) | 4 | S | ✅ |
| PERF-01 | `armar_payload` por candidato y `hidratar()` con JSON que nadie lee | MEDIA | CONF. ajustado | 4 | S | ✅ |
| PERF-03 | Excel de respuestas por persona: 8,9 s de CPU en el request | MEDIA (baja desde ALTA) | CONF. ajustado | 4 | S-M | ⬜ |
| PERF-07 | Pantalla del masivo: `count()` con 15.532 literales cada 5 s | MEDIA | CONF. ajustado | 4 | S | ✅ |
| PERF-11 | La foto `definicion` en cada caso (88 % de los bytes) | MEDIA (estructural) | CONF. medido | 7 | L | ⬜ |
| PERF-20 | `generar_alertas` recorre todos los ciudadanos activos cada hora | MEDIA | CONF. medido | 4 | S | ✅ |
| G1b-11 | Export del dashboard: un `JSON_EXTRACT` por pregunta sobre todo el recorte | MEDIA | PLAUSIBLE | 4 | M | ⬜ |
| G1c-09 | Admin: fichas de Formulario y Derivación que crecen con la tabla | MEDIA | CONF. test | 4 | S | ⬜ |
| PERF-06 | `validar_casos_siis` trae todo con JSON en una consulta | BAJA | CONF. código | 4 | S | ✅ |
| PERF-08 | `CONN_MAX_AGE = 60` bajo daphne no reutiliza conexiones | BAJA | CONF. ajustado (sonda) | 4 | S | ⬜ |
| PERF-10 | Redis compartido (sesiones + cache, `allkeys-lru`) y sesión por visita pública | BAJA | CONF. ajustado | 4 | S | ⬜ |
| PERF-12 | `COUNT(*)` del cupo del link | BAJA | CONF. ajustado | 4 | — (medir) | ⬜ |
| PERF-13 | Bandeja filtrada por estado raro sin índice combinado | BAJA | PLAUSIBLE | 4 | S (medir) | ⬜ |
| PERF-15 | Conteos de padrón en cada detalle | BAJA | CONF. código | 4 | S (medir) | ⬜ |
| PERF-16 | Señal de `Ciudadano`: 4 DEL de Redis por save | BAJA | CONF. medido | 4 | S | ✅ |
| PERF-17 | Listados operativos sin paginar (Dispositivos/Merenderos/convocatorias) | BAJA | CONF. código | v2 (criterio) | S | ⬜ |
| PERF-18 | Ocupación de Dispositivos con `Count(distinct)` sobre camas × admisiones | BAJA | CONF. código | v2 (criterio) | S | ⬜ |
| PERF-19 | «Último intento» sin índice y subconsulta evaluada dos veces | BAJA | CONF. ajustado | 4 | S | ✅ |
| G1c-11 | Admin: N+1 en listados | BAJA | CONF. lectura | 4 | S | ⬜ |
| G3-03 | `alertas_websocket.js` cargado para todos, con 5 reintentos inútiles | BAJA | CONF. lectura | 2 | S | ✅ |

Refutado: **A4-15 / PERF-14** (GZip sobre xlsx): ver README §8.

---

## ALTA

### PERF-04 · Carga de padrón: cruce caso por caso dentro de una transacción y un request
**Severidad:** ALTA · **Estado:** CONFIRMADO (medido) con prototipo · **Origen:** A4-04, V4-NEW-01, A1-16 (= BEC-12) · **Ola:** 4 · **Esfuerzo:** M
- **Ubicación:** `programas/services/padron.py:413-512` (`validar_casos_pendientes`; `registrar_traza` y `ciudadano.save` por caso, `:459-500`; `bulk_update` con `CASE WHEN`, `:507`), `:282-333` (`@transaction.atomic` del request); `programas/services/becas.py:221` (`bulk_create` de a 1 por traza).
- **Medición (SQLite, 20k casos, 6.667 pendientes, padrón de 50.000 filas):** **13.942 sentencias** (6.667 `UPDATE legajos_ciudadano`, 6.667 `INSERT programas_tracaformulario`, 556 `INSERT` de padrón —en MySQL es un solo INSERT—, 47 `UPDATE` de formulario) + **26.668 `cache.delete`** (4 por ciudadano, PERF-16); 18,4-27 s en SQLite. cProfile: el `bulk_update` de formularios (Cambio 93) es la pieza más cara en Python (13,7 s de 36 s: `CASE WHEN` de 200 ramas × 5 campos × 34 lotes). INSERT único del padrón: ~161 B/fila → 8,06 MB para 50k; con 2 columnas entran ~150k filas (15-18 MB), en el límite de `max_allowed_packet` (16 MB por defecto en MariaDB): PLAUSIBLE.
- **Ajuste:** el «500 en el portal por lock» de A4 es poco probable (READ COMMITTED: el paso 1 lee el padrón viejo sin bloquear). El riesgo real es el **504 de nginx (60 s)** en el request que sube el archivo.
- **Propuesta (mismo resultado funcional):**
  1. Iterar pendientes con `.iterator(chunk_size=2000)`.
  2. Acumular `TracaFormulario(...)` y **un** `bulk_create(trazas, batch_size=1000)` al final (`registrar_traza` sigue para otros llamadores; RN-14/29: una fila por cambio).
  3. Ciudadanos agrupados por tupla de campos completados → `Ciudadano.objects.bulk_update(lista, [*campos, "modificado"], batch_size=500)`; como no dispara la señal, `transaction.on_commit(lambda: cache.delete_many(["contar_ciudadanos", "contar_usuarios", *[f"ciudadano_{id}" for id in ids]]))`.
  4. Formularios: constantes (`validado_renaper=True`, `origen_validacion=PADRON`, `modificado=now`) con `Formulario.objects.filter(pk__in=chunk_1000).update(...)`; `bulk_update` **solo** para los que cambian `datos_identificacion` o `dni_titular`.
  5. `PadronHabilitado.objects.bulk_create(objetos, batch_size=2000)`.
  - **Prototipo medido** (`validar_casos_pendientes_v4` en `poc/perf_harness/tests.py`): **de 13.942 a 676 sentencias**, 0 señales, mismos 6.667 validados y mismas 22.266 trazas; SQLite 18,4 → 13,6 s.
  - Opcional (M): partir en dos transacciones (reemplazo del padrón; cruce en lotes de 1.000 con commit; idempotente). Solo si con 1-5 sigue pasando 30 s en el banco.
- **Tests a agregar:** `programas/tests/test_padron_identidad.py`: con 5 y con 25 casos cruzados, `assertNumQueries(K)` **igual** (hoy crece 2 por caso); mantener los tests de «no pisa JSON» y «traza por cambio» del Cambio 93.
- **Verificación:** V-STD + banco: en la convocatoria del relevamiento público de 20k, subir por `cargar_padron` el xlsx de los pendientes (el harness `test_a404_perfil` muestra cómo) y cronometrar/contar antes y después.
- **Dependencias:** PERF-16 (señal), DAT-05 (Excel viejo), BEC-15 (concurrencia), G1-12 (fechas): mismo módulo.

**Resolución:** ✅ Resuelto en #632 (Cambio 182, Ola 4 PR 1-2), 08-oct-2026 — `validar_casos_pendientes` recorre los
pendientes con `.iterator(chunk_size=2000)` y acumula: las trazas en un `bulk_create(batch_size=1000)`, los ciudadanos
agrupados por tupla de campos completados en `bulk_update(batch_size=500)` y los formularios partidos en dos —los que
solo mueven las tres constantes van por `UPDATE … WHERE pk IN (1.000)` y solo los que tocan `datos_identificacion` o
`dni_titular` pagan el `CASE WHEN` del `bulk_update`—. `cargar_padron` inserta el padrón en lotes de 2.000 (el INSERT
único de 50.000 filas son ~8 MB y con las seis columnas de identidad se acerca a los 16 MB de `max_allowed_packet`).
**Medido en el banco MariaDB 10.11** (`scripts/perf_mysql`, 20.000 casos, 6.667 pendientes, padrón de 50.000 filas,
`OPTIONS` de producción), con los legajos vacíos —el peor caso, que es el que dispara el `UPDATE` de ciudadano—:
**13.376 → 74 sentencias y 55,93 → 21,84 s**; con los legajos ya cargados, **6.709 → 46 sentencias y 37,39 → 14,96 s**.
Los 6.667 validados y las trazas son los mismos en las cuatro corridas. Queda debajo de los 30 s del criterio y lejos
de los 60 s de nginx. **Desvío de la ficha:** el prototipo usaba `.exclude(nombre="").exclude(apellido="")`; el código
real ya pasa por `q_con_identidad()` (RED-77) y se conservó.
**Test permanente:** `programas.tests.test_padron_performance.ConsultasConstantesTests.test_el_cruce_no_crece_con_la_cantidad_de_casos`
y `programas.tests.test_padron_performance.MismosCasosEnElMismoOrdenTests` — este último corre la copia congelada del
algoritmo viejo (`_cruce_por_caso_referencia`) y la versión nueva sobre datasets gemelos y compara, caso por caso, lo
validado, lo escrito en el legajo, el `datos_identificacion` y la lista de trazas.

### PERF-02 · Cupo y beneficiarios: páginas anchas con join y ORDER BY sobre filas de ~8 KB
**Severidad:** ALTA · **Estado:** CONFIRMADO (forma medida; tiempo en MariaDB NO-MEDIDO) · **Origen:** A4-02 · **Ola:** 4 · **Esfuerzo:** S
- **Ubicación:** `programas/views/cupo.py:79-137`. El SQL de la página trae **todas** las columnas de `programas_formulario` incluidas `respuestas`, `definicion` y `datos_siis` (el `defer` solo saca `data` y `datos_identificacion`), más `programas_relevamiento`, `programas_convocatoria` y `legajos_ciudadano`; `WHERE programas_convocatoria.segmento_id = X`; `ORDER BY modificado ASC LIMIT 50 OFFSET 2450` / `ORDER BY creado ASC …`. Es la forma que el Cambio 93 midió en MySQL en el detalle de convocatoria: 4,4 s en frío y 2,1 s en caliente.
- **Medición:** 16 consultas en la página 1 y 13 en la 50; 226 y 540 ms en SQLite.
- **Ajuste:** **no hace falta índice sobre `modificado`** (lo caro es materializar y ordenar filas anchas; con la proyección angosta `(pk, modificado)` el filesort es de tuplas de 16 bytes, y `(relevamiento, estado)` ya existe). Se evita una migración sobre la tabla más grande.
- **Propuesta (reescritura):**
  ```python
  rel_ids = list(Relevamiento.objects.filter(convocatoria__segmento=segmento).values_list("pk", flat=True))
  en_espera = ListaEspera.objects.filter(segmento=segmento, promovido=False).values("formulario_id")
  base = Formulario.objects.filter(relevamiento_id__in=rel_ids)
  conteos = base.aggregate(
      ocupado=Count("pk", filter=Q(estado=APROBADO)),                                   # = get_cupo_stats
      beneficiarios=Count("pk", filter=Q(estado=APROBADO, ciudadano__isnull=False)),
      pendientes=Count("pk", filter=Q(estado=ENVIADO, ciudadano__isnull=False) & ~Q(pk__in=en_espera)),
  )
  benef_ids = base.filter(estado=APROBADO, ciudadano__isnull=False).only("pk").order_by("modificado", "pk")
  pend_ids  = base.filter(estado=ENVIADO, ciudadano__isnull=False).exclude(pk__in=en_espera).only("pk").order_by("creado", "pk")
  beneficiarios = PaginadorConConteo(benef_ids, 50, total=conteos["beneficiarios"]).get_page(...)
  pendientes    = PaginadorConConteo(pend_ids, 50, total=conteos["pendientes"]).get_page(...)
  # hidratar cada página por pk, en el mismo orden:
  Formulario.objects.filter(pk__in=pks).select_related("ciudadano", "relevamiento__convocatoria") \
      .defer("data", "respuestas", "definicion", "datos_siis", "datos_identificacion")
  # lista de espera: el mismo defer de los 5 JSON con prefijo formulario__
  ```
  Reusar `PaginadorConConteo` (`programas/views/relevamientos.py:66`) y el reordenamiento de `_pagina_hidratada` (`programas/views/revision.py:193-212`), movido a un selector compartido. `stats` sale de `conteos["ocupado"]`; `get_cupo_stats` sigue para `promover_lista_espera` y `aprobar_o_poner_en_espera`. Resultado esperado: de 3 COUNT con join + `get_cupo_stats` a un `aggregate` sin join.
- **Presupuesto:** ruta en `scripts/perf_audit.py::build_targets` (segmento de `seed_perf`, actor admin) y en `scripts/perf_budgets.json`: `"becas_cupo_segmento": {"route": "becas:cupo_segmento", "max_queries": <medido después + 1>, "max_duplicate_queries": 1}`, con justificación en `adjustments`. Hoy 16; se esperan ~12.
- **Tests a agregar:** regresión: mismos pks y mismo orden en la página N antes y después (segmento con 2 relevamientos y casos en espera).
- **Verificación:** V-STD + `manage.py test --tag performance`; banco: `/becas/cupo/segmento/<seg>/?pendientes_page=50&beneficiarios_page=50` en `bench_mysql.py` + `EXPLAIN ANALYZE` (deben desaparecer `Using temporary` y la materialización de `programas_relevamiento`).
- **Dependencias:** SEC-21 y SEC-22 tocan los mismos querysets (filtros de alcance): coordinar o hacer en el mismo PR.

**Resolución:** ✅ Resuelto en #632 (Cambio 182, Ola 4 PR 1-2), 08-oct-2026 — las tres condiciones de alcance (segmento,
convocatorias visibles y RN-P13) son todas sobre el **relevamiento**, así que se resuelven una vez en una lista de ids y
las tablas quedan con `WHERE relevamiento_id IN (…)`: desaparecen los joins con `programas_convocatoria` y
`programas_relevamiento`. Beneficiarios y pendientes se eligen proyectando **solo el pk** (`order_by("modificado","pk")`
y `("creado","pk")`) y se hidratan por pk con `select_related` + `defer` de los **cinco** JSON; los dos totales salen de
un `aggregate` en vez de dos COUNT. `PaginadorConConteo` y la hidratación por pk se mudaron a
`programas/services/listados.py`, con lo que **se cae la arista `revision → relevamientos`** del ratchet de RED-79 (7 → 6).
**Medido en el banco MariaDB 10.11** (20.000 casos en el segmento, `OPTIONS` de producción): página 1 de **9.239 ms en
frío / 8.890 ms en caliente y 8.991 ms de SQL** a **305 / 189 ms y 167 ms de SQL**; página 50, de 9.149 / 8.971 y 8.973 ms
a 232 / 248 y 167 ms. El `EXPLAIN` pasa de arrancar en `programas_convocatoria` con **«Using temporary; Using filesort»**
más la materialización de `programas_relevamiento`, a un solo acceso a `programas_formulario` con `Using index condition`.
**Desvíos de la ficha:** (1) el `ocupado` no puede salir del mismo `aggregate` que `beneficiarios` —SEC-21 dejó la bandeja
acotada al alcance del usuario y el cupo es del segmento entero—, así que `get_cupo_stats` se conserva; (2) la pantalla
pasa de 16 a **18** consultas en MariaDB (15 en SQLite): +1 por los ids del alcance y +2 por las dos hidrataciones,
contra −1 por unir los dos COUNT. Es el canje que RED-62 pide justificar y está escrito en `adjustments` de
`scripts/perf_budgets.json`; (3) el orden suma el desempate por `pk`, sin el cual la página profunda puede repetir o
saltear un caso cuando dos comparten `modificado`.
**Presupuesto:** `becas_cupo_segmento` en `scripts/perf_audit.py::build_targets` y en `scripts/perf_budgets.json`
(`max_queries: 16` = medido 15 + 1, `max_duplicate_queries: 1`).
**Test permanente:** `programas.tests.test_cupo_performance.LaPaginaNoAbreLosJsonTests.test_ninguna_consulta_de_la_pantalla_pide_los_cinco_json`
y `programas.tests.test_cupo_performance.MismosCasosEnElMismoOrdenTests.test_beneficiarios_pagina_2_igual_que_con_la_consulta_ancha`.

## MEDIA

### PERF-01 · `armar_payload` por candidato: consultas repetidas; `hidratar()` trae `definicion` y `respuestas` que nadie lee
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (6 consultas por llamada, 8 con `ProvinciaSiis` cargado; no 8-10) · **Origen:** A4-07, A4-01 (parte perf), V4-NEW-02 · **Ola:** 4 · **Esfuerzo:** S

**⚠ Actualizar (03-oct-2026):** `hidratar()` hoy en `proceso_masivo.py:232` (sigue sin `defer`); `procesar_casos_siis.py:202` pasó a `:251`. Con #513, `correr_alta_siis` manda por tandas de 500 y acota la consulta de `hidratar`, pero `procesar_casos_siis --total N` a mano sigue trayendo N de una. `ids_de` ya pide por rangos de pk (`PAGINA_IDS = 2000`, #513).
- **Ubicación:** `programas/services/siis_envio.py:293-330` (`respuestas_por_destino` consulta `PreguntaGlobal` y `RequisitoNativo` en cada caso), `:172-224` (`Catalogos.provincia_id` / `localidad_id`: 1 a 3 consultas por campo, dos domicilios), `:605` (vuelve a armar el payload); `programas/services/proceso_masivo.py:192` (`hidratar` sin `defer`); `procesar_casos_siis.py:202` (hidrata hasta 5.000 casos en **una** consulta, ~35 MB).
- **Medición:** `elegir_completos` sobre 200 casos = 1.200 consultas, 2,5 ms/caso; cProfile: lo caro es armar el SQL (`compiler.as_sql` 1,2 de 3,0 s). Con 7.496 candidatos: 45-60 mil consultas, ~40-65 s antes del primer latido (insumo de SIIS-03). `definicion` + `respuestas` ≈ 88 % de los bytes por caso; `armar_payload`, `validacion_siis`, `cupo` y `avisos_resolucion` no las leen y todos los `save()` usan `update_fields`.
- **Propuesta:**
  1. `Catalogos._destinos = {}` con clave `(segmento_id, subsegmento_id, programa_id)` → `(list(preguntas_pk_destino), list(requisitos_pk_destino))`; `respuestas_por_destino(formulario, catalogos=None)` lo usa si viene `catalogos` (2 SELECT por combinación en vez de por caso).
  2. `self._prov = {}` por `clave` y `self._loc = {}` por `(clave, provincia_id)`, memo incluido `None`, mismo orden de resolución (alias → catálogo propio → API).
  3. `_buscar`: índice `{clave_nombre(nombre): [items]}` armado una vez por catálogo en `_items`.
  4. (Opcional) `enviar_beneficiario_a_siis(..., catalogos=None, payload=None)` para reusar el payload de `elegir_completos`; solo si se confirma que aprobar no cambia ningún campo del payload (si hay duda, los puntos 1-3 ya bajan el segundo armado a 0 consultas).
  5. `hidratar()`: `Formulario.objects.select_related(*SELECT_RELATED_CASOS).defer("respuestas", "definicion").filter(pk__in=ids)`; en `procesar_casos_siis.py:202`, `hidratar_por_lotes`.
- **Tests a agregar:** `test_proceso_masivo.py`: `assertNumQueries(K)` para `elegir_completos(hidratar(ids_10), cat, 99, Cuenta())` y el **mismo** K (± lotes) con 50 casos del mismo segmento (hoy 6×N); el SQL de `hidratar` no contiene `"definicion"`; `procesar_caso` con SIIS mockeado no suma consultas por campo diferido.
- **Verificación:** V-STD; banco: `procesar_casos_siis --solo-completos --total 5000` en ensayo contra `chaco_perf_ci` (tabla `aprobados_materias` desde `scripts/Aprobados.sql`), cronometrar «Armando el payload…».
- **Dependencias:** G1-08 cambia de dónde sale el destino (foto): coordinar el memo.

**Resolución:** ✅ Resuelto en #639 (Cambio 186, Ola 4 PR 3), 08-oct-2026 — los puntos 1 a 3 de la propuesta,
como **memo de instancia** de `Catalogos`: `destinos_del_catalogo` por `(segmento, subsegmento, programa)`,
`provincia_id` por clave, `localidad_id` por `(clave, provincia_id)` —memorizando también el `None`, que era la
respuesta del 38 % de los casos— y un índice `{clave: [items]}` por catálogo en vez de normalizar la lista entera
por llamada. `respuestas_por_destino(formulario, catalogos=None)` usa el memo si se lo pasan; sin él se comporta
igual que antes. Medido en el banco MariaDB 10.11 (20.000 casos, 22.000 DNI en `aprobados_materias`):
`elegir_completos` sobre 200 candidatos pasa de **1.201 sentencias y 4.132 ms** a **8 sentencias y 329 ms**.
El punto 4 **no** se hizo: reusar el payload entre `elegir_completos` y el alta exige confirmar que aprobar no
mueve ningún campo, y con los puntos 1-3 el segundo armado ya no consulta nada.
**El punto 5 se contradice con el código y no se aplicó** (ver V4-NEW-02, abajo): en `procesar_casos_siis` sí se
cambió `hidratar(...)` por `hidratar_por_lotes(...)` en la rama sin `--solo-completos`, que era la que traía hasta
5.000 casos (~35 MB) en una sola consulta.

**V4-NEW-02 — corrección code-first.** La ficha pedía `hidratar()` con `defer("respuestas", "definicion")`.
`armar_payload` **las lee**: `respuestas_por_destino` abre `definicion` y `data`, `cuil_del_caso` abre `respuestas`
y las correcciones salen de `datos_siis`. Diferirlas no ahorra bytes: los vuelve a pedir de a uno, una consulta por
campo y por caso. El `defer` se agregó como parámetro de `hidratar`/`hidratar_por_lotes` (`JSON_DEL_CASO`) y lo usa
**el llamador que no los lee**, que es `validar_casos_siis` (PERF-06). Quien quiera sacarle los bytes al circuito de
alta necesita PERF-11, que es Ola 7.
**Test permanente:** `programas.tests.test_circuito_siis_performance.PayloadSinConsultasPorCasoTests`
(`test_las_consultas_no_crecen_con_la_cantidad_de_casos`, `test_el_memo_no_cambia_el_payload` y
`test_hidratar_trae_los_json_que_el_payload_lee`).

### PERF-03 · Excel de respuestas por persona: CPU con el GIL tomado dentro del request
**Severidad:** MEDIA (baja desde ALTA; vuelve a ALTA si ECOM confirma un timeout de ingress < 30 s o hay convocatorias > 40k casos) · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A4-03 · **Ola:** 4 · **Esfuerzo:** S-M · **Decisión:** pregunta ECOM (timeout del ingress)
- **Medición (20.000 × 22 columnas):** `respuestas_por_persona` 1,22 s; `respuesta_libro` (openpyxl) **9,24 s**; request **8,92 s**; xlsx 1,99 MB; pico **37,2 MB** (no 150-250 MB; ~84 B/celda → ~90 MB con 40k × 26). cProfile: casi todo `et_xmlfile` (serializador XML en Python puro, sin `lxml`); `celda_segura` ~6 %.
- **Propuesta (en orden de retorno):** (1) **`lxml` en `requirements.txt`** (openpyxl lo detecta solo; el Cambio 93 estimó 2-3× más rápido; pasa por `pip-audit`); (2) **botón «CSV»** en la misma pantalla (`respuesta_reporte(reporte, "csv", ...)` ya existe; ~10× según el Cambio 93; es UI: V-UI); (3) solo si 1 y 2 no alcanzan: exportación fuera del request (`ExportacionPendiente` + CronJob/worker + link). **Descartado:** reescribir fila a fila (ahorra ~37 MB y no mueve el tiempo) y sacar GZip (A4-15 refutado).
- **Criterio:** `perfil_ruta.py /becas/config/programas/<p>/dashboard/respuestas/<c>/xlsx/ 1` con 20k casos debe bajar de 5,7 s (Cambio 93) a < 3 s en el banco.
- **Dependencias:** G2-01 (el mismo export cambia de fuente de datos: hacer G2-01 con `lxml` ya instalado).

### PERF-07 · Pantalla del proceso masivo: `candidatos().count()` con 15.532 literales, recalculado cada 5 s
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A4-08, V4-NEW-03 · **Ola:** 4 · **Esfuerzo:** S
- **Medición:** la lista real (`scripts/Aprobados.sql`: 15.531 DNI) da un set de 15.532 literales; el `count()` lleva **188 KB de SQL**; el GET hace 13 consultas (el `SELECT dni` de toda la tabla, 1 `table_names()` y el `count()` con dos subconsultas correlacionadas por fila, PERF-19). Con una corrida en curso, `proceso_masivo.html:196-206` recarga **cada 5 s**, en el mismo proceso que el hilo de la corrida.
- **Ajuste:** `aprobados_materias` ya tiene índice (`idx_dni`, #506); en MariaDB, un IN > 1.000 literales se convierte en tabla derivada (`in_predicate_conversion_threshold`), no en scan: costo real pero moderado (NO-MEDIDO).
- **Propuesta:** (1) en `ProcesoMasivoView.get_context_data`, si `ctx["en_curso"]` no calcular `pendientes`; si no hay corrida, `cache.get_or_set(f"masivo_pendientes_{programa.pk}", lambda: ...count(), 60)`; (2) `dnis_aprobados_materias()`: memo por proceso con TTL 5 min (variable de módulo `(momento, set)`) y `table_names()` cacheado en la misma memo; (3) la tabla administrada por Django que proponía A4 no hace falta para performance.
- **Presupuesto:** `becas_proceso_masivo` en `build_targets` y `perf_budgets.json` (hoy 13; después medido + 1); el `setUp` crea `aprobados_materias` como `crear_tabla_aprobados_materias` de `test_proceso_masivo.py`.

**Resolución:** ✅ Resuelto en #639 (Cambio 186, Ola 4 PR 3), 08-oct-2026 — los puntos 1 y 3 de la propuesta, y el 2
**descartado a propósito**. Con `en_curso` la vista no calcula ninguno de los dos números (la plantilla muestra el
progreso, no los conteos) y la existencia de `aprobados_materias` se pregunta al catálogo con
`proceso_masivo.hay_aprobados_materias()` en vez de leer la planilla entera para enterarse. Sin corrida, los dos
conteos salen juntos de `proceso_masivo.conteos_de_la_pantalla()` —comparten `Insumos`, así que la planilla, la lista
de exclusión y los casos agotados se leen **una** vez— y se cachean 60 s bajo `masivo_conteos_<pk>`.
**El memo con TTL de 5 minutos del punto 2 no se hizo**: `dnis_aprobados_materias` decide quién va a SIIS, el alta no
tiene baja, y servir una lista de hace cinco minutos a una corrida lanzada justo después de cargar la planilla es un
riesgo que no paga una pantalla. Con el punto 1, esa lectura ya no está en el camino de los 5 s.
Medido en el banco MariaDB 10.11 (20.000 casos, 22.000 DNI habilitados):

| Pantalla | Antes | Después |
|---|---|---|
| sin corrida, primera visita | 1.403 ms · SQL 999 ms · 20 consultas | 1.235 ms · SQL 937 ms · 17 |
| sin corrida, visita siguiente | 1.562 ms · SQL 1.140 ms · 18 | **41 ms · SQL 16 ms · 9** |
| **con corrida en curso (relee cada 5 s)** | 720-794 ms · SQL 484-578 ms · 14-16 | **45-50 ms · SQL 16-31 ms · 10-12** |

**Presupuesto:** `becas_proceso_masivo` agregado a `build_targets` y a `perf_budgets.json` en 18 (medido 17 + 1) con
2 duplicadas, justificado en `adjustments`. `seed_perf` crea el `ProgramaSiis` sintético y la tabla
`aprobados_materias` con los DNI del seed.
**Test permanente:** `programas.tests.test_circuito_siis_performance.PantallaDelMasivoTests`
(`test_con_una_corrida_en_curso_no_se_cuentan_los_candidatos`,
`test_sin_corrida_el_conteo_se_calcula_una_vez_y_se_cachea`,
`test_los_dos_conteos_leen_los_insumos_una_sola_vez` y
`test_sin_la_tabla_de_materias_la_pantalla_lo_dice_sin_leerla`).

### PERF-11 · La foto `definicion` (~5,3 KB) se copia en cada caso
**Severidad:** MEDIA (estructural) · **Estado:** CONFIRMADO (medido: 5,3 de 6,0 KB de JSON por caso, 88 %; todos los casos del banco comparten la misma foto) · **Origen:** A4-12 · **Ola:** 7 (plan propio) · **Esfuerzo:** L
- **Raíz de** PERF-02, PERF-01 (V4-NEW-02) y los `defer` de los Cambios 66, 91, 92 y 93.
- **Propuesta:** tabla `FotoDefinicion` deduplicada por huella + FK desde `Formulario`, rellenada por lotes (migración de datos larga sobre la tabla más grande: ver README §0, gotchas de MariaDB). **No** recomendado: un queryset por defecto que difiera `definicion` (cualquier lector que la toque en un bucle se vuelve N+1 sin aviso). En su lugar, ya en Ola 4: método explícito `Formulario.objects.listado()` = `defer` de los 4 JSON, usado en todo listado nuevo, y un test que recorra las vistas paginadas de `programas/views/` y falle si el SQL de la página contiene `"definicion"` (estilo `pagina_trae_definicion` del harness).

### PERF-20 · `generar_alertas` recorre todos los ciudadanos activos cada hora
**Severidad:** MEDIA (escala con el volumen de Becas y corre contra PRD; BAJA si ECOM no tiene el CronJob) · **Estado:** CONFIRMADO (medido) · **Origen:** V3-NEW-03, A8-10 (= OPS-08) · **Ola:** 4 (con LEG-01) · **Esfuerzo:** S
- **Ubicación:** `legajos/management/commands/generar_alertas.py:21-22`; `LegajoAtencion` no se crea en ningún camino productivo. Cron: `docker/k8s/cronjobs.yaml:18` (`0 * * * *`) y crontab de icore.
- **Medición:** 20.200 activos, 200 con legajo: **61.821 sentencias por corrida** (20.201 `SELECT legajos_ciudadano`, 20.200 `UPDATE legajos_alertaciudadano`, 20.200 `SELECT legajos_legajoatencion` con IN vacío), 38 s en SQLite; con 40k ciudadanos, ~122k sentencias por hora (1-2 min de carga continua).
- **Propuesta:**
  ```python
  # antes: for ciudadano_id in Ciudadano.objects.filter(activo=True).values_list("id", flat=True).iterator(): ...
  legajo_ids = (InscripcionPrograma.objects.filter(legajo_id__isnull=False, ciudadano__activo=True)
                .values_list("legajo_id", flat=True).distinct())
  legajos = (LegajoAtencion.objects.filter(pk__in=legajo_ids).select_related("responsable", "evaluacion")
             .annotate(ultimo_contacto=Max("historialcontacto__fecha_contacto"),
                       fallidos=Count("historialcontacto", filter=Q(historialcontacto__estado="NO_CONTESTA",
                                                                     historialcontacto__fecha_contacto__gte=hace_30))))
  existentes = set(AlertaCiudadano.objects.filter(activa=True, legajo_id__in=legajo_ids).values_list("legajo_id", "tipo"))
  # _generar_alertas_legajo(legajo, existentes) con los datos anotados; altas en bulk_create; notificación por alta
  ```
  Ajustar los `related_name` reales (`historialcontacto`, `evaluacion`); traer `legajo.ciudadano` con `annotate_legajo_link_data` (`legajos/services/linking.py:50`). El `UPDATE` global de hoy desaparece con la reconciliación de LEG-01; **si PERF-20 saliera sin LEG-01**, hay que conservar un único `AlertaCiudadano.objects.filter(activa=True, prioridad__in=["MEDIA", "BAJA"], ciudadano__activo=True).update(activa=False)` antes de regenerar, para no cambiar la semántica actual. Esperado: de 61.821 a ~5 consultas + las altas, constante respecto de los ciudadanos sin legajo. Alternativa: retirar el CronJob si Legajos de atención no se usa (decidir con LEG-01).
- **Tests a agregar:** `legajos/tests`: `call_command("generar_alertas")` dentro de `assertNumQueries(K)` con 10 y con 200 ciudadanos sin legajo → **el mismo K**; dos corridas seguidas no crean alertas (LEG-01).

**Resolución:** ✅ Resuelto en el PR 4 de la Ola 4 (Cambio 187), 08-10-2026 — con LEG-01 en el mismo PR, como pedía la
ficha. El universo de la pasada ya no es el padrón sino los legajos: `AlertasService.reconciliar_alertas` arranca de
`InscripcionPrograma.filter(legajo_id__isnull=False, ciudadano__activo=True).values_list("legajo_id").distinct()` y
reconcilia **por lotes de 500 legajos**, con cuatro lecturas fijas por lote —las inscripciones del lote (que resuelven
en una sola consulta el ciudadano y los `programa_ids` del ruteo), los legajos con `Max(fecha_contacto)` y el
`Count` filtrado de fallidos anotados sobre el mismo `JOIN`, las alertas activas del lote y, solo si hay algo que
crear, los ciudadanos—, más un `INSERT` por alta y **un** `UPDATE` de cierre. Desaparecen las tres consultas por
ciudadano activo y el `UPDATE` global, que LEG-01 reemplaza por el cierre selectivo. **Medido** en banco sintético
equivalente (2.000 activos / 20 con legajo, SQLite en memoria, Django 5.2.17, mismo `execute_wrapper` del harness):
**6.181 → 45 sentencias** en la pasada en frío (40 de las 45 son los `INSERT` de las altas) y **6.141 → 4** en la
pasada en régimen, que es la que corre 23 de las 24 veces por día; 6,6 s → 0,53 s. **Desvío de la ficha, code-first:**
las altas van de a una y no con `bulk_create`, porque en MySQL 8 (icore) `bulk_create` no devuelve el `pk` y el aviso
por WebSocket lo necesita —el dashboard dibuja `data-alerta-id` y el cierre se entrega por ese id (Cambio 179)—; en
régimen son cero, así que el término no se paga. El ruteo del WebSocket se calcula **una vez por lote** y se le pasa a
`_enviar_notificacion_alerta`, en vez de una vez por alerta.
**Test permanente:** `legajos.tests.test_generar_alertas_performance.PasadaDeAlertasPerformanceTests.test_las_consultas_no_crecen_con_los_ciudadanos_sin_legajo`
(+ `test_la_pasada_en_regimen_cuesta_lo_mismo_con_3_que_con_9_legajos`).

### G1b-11 · Export del dashboard de Becas: una consulta `JSON_EXTRACT` + `GROUP BY` por pregunta sobre todo el recorte
**Severidad:** MEDIA · **Estado:** PLAUSIBLE (sin medir en MariaDB) · **Origen:** G1b-11 (verificado en G2) · **Ola:** 4 · **Esfuerzo:** M
- **Ubicación:** `programas/views/dashboard_becas.py:142-144` → `distribuciones_respuestas(claves=None)` sin caché (`programas/services/dashboard_becas.py:826`, `:854-873`). Cada consulta queda < 10 s, pero el request completo escala con preguntas × 20k casos de filas anchas. El banco validado fue MySQL 8, no MariaDB.
- **Propuesta:** una sola pasada con todas las claves + conteo en Python, o reusar `distribucion_cacheada`; medir primero en `scripts/perf_mysql/` (`chaco_perf_ci`, 20k casos) **en MariaDB**.
- **Tests a agregar:** `@tag("performance")` con consultas constantes respecto de la cantidad de preguntas.
- **Dependencias:** G2-01 (agrega claves `cp-` al mismo cálculo).

### G1c-09 · Admin: fichas de Formulario y de Derivación que crecen con la tabla
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`poc/test_repro_admin_cron_renaper.py::G1c09AdminNmas1Tests`: ficha de `Formulario` 19 → 46 consultas con 5 → 35 casos; alta de `DerivacionPrograma` 21 → 80 con 5 → 35 inscripciones; zeal corta con `NPlusOneError` en `Formulario.__str__`, `models:2683`) · **Origen:** G1c-09 · **Ola:** 4 · **Esfuerzo:** S
- **Escenario:** con 40k casos, decenas de miles de consultas y `<select>` de decenas de miles de opciones: la ficha choca con el `read_timeout`.
- **Propuesta:** `raw_id_fields` (o `autocomplete_fields` con `search_fields`) en `FormularioAdmin` (`ciudadano`, `apoderado_ciudadano`, `duplicado_de`, `created_by`, `relevamiento`), `InscripcionProgramaAdmin` (`ciudadano`, `responsable`), `DerivacionProgramaAdmin` (`ciudadano`, `inscripcion_creada`, `derivado_por`, `respondido_por`), `ListaEsperaAdmin` (`formulario`), `VinculoFamiliarAdmin`, `HistorialContactoAdmin` (`programas/admin.py:131`, `:298-307`).
- **Tests:** el de la PoC con tope fijo (`assertNumQueries` igual con 5 y con 35 casos).

## BAJA

### PERF-06 · `validar_casos_siis` trae todos los casos con sus JSON en una consulta
**Severidad:** BAJA (baja desde MEDIA: comando manual, sin cron) · **Origen:** A4-06 · **Ola:** 4 · **Esfuerzo:** S
- **Ubicación:** `programas/management/commands/validar_casos_siis.py:93-112` (`select_related` de 4 niveles, `annotate(Subquery)`, `list(casos)` sin `defer`; con `--reintentar-errores` la subconsulta aparece dos veces, PERF-19).
- **Propuesta:** `ids = list(casos.values_list("pk", flat=True))` → `proceso_masivo.hidratar_por_lotes(ids)` con `defer("respuestas", "definicion")`; `sin_programa` y `sin_dni` con dos `count()`.
- **Test:** `--dry-run` con N=10 y N=30: las consultas crecen por lote de 200, no por caso.

**Resolución:** ✅ Resuelto en #639 (Cambio 186, Ola 4 PR 3), 08-oct-2026 — la propuesta tal cual. `_casos` devuelve
el **queryset** y el comando se queda con los ids (`proceso_masivo.ids_de`, por rangos de pk) y los hidrata lote por
lote con `defer` de los cuatro JSON (`JSON_DEL_CASO`): la validación de compatibilidad solo manda DNI, programa y
fecha de nacimiento. `sin_programa` y `sin_dni` salen de dos `count()` en la base; con `--limite`, el recorte se
reproduce **exacto** acotando por el último pk de la lista de ids, sin un `IN` de miles. Medido en el banco MariaDB
10.11, ensayo sobre los 20.000 casos: de **3 sentencias y 22.917 ms** —una sola consulta de decenas de MB, que
contra ECOM muere por `read_timeout` a los 10 s— a **11 sentencias y 431 ms**.
**Test permanente:** `programas.tests.test_circuito_siis_performance.ValidarCasosSiisTests`
(`test_el_ensayo_no_pide_los_json_del_caso`, `test_el_aplicar_hidrata_por_lote_y_no_por_caso` y
`test_el_ensayo_cuenta_los_salteados_en_la_base`).

### PERF-08 · `CONN_MAX_AGE = 60` bajo daphne no reutiliza conexiones
**Severidad:** BAJA (baja desde MEDIA) · **Estado:** CONFIRMADO-AJUSTADO (sonda `poc/perf_harness/asgi_conn_probe.py`: 200 requests → 200 hilos y 200 conexiones nuevas, ninguna reutilizada; 9 quedan abiertas hasta el GC cíclico; con 0 → 0) · **Origen:** A4-09 · **Ola:** 4 · **Esfuerzo:** S
- **Propuesta:** `config/settings.py:295`: `"CONN_MAX_AGE": 0 if os.environ.get("APP_RUNTIME") == "daphne" else 60`. Reutilizar de verdad exige WSGI (gunicorn), decisión de despliegue (`docker/k8s/README.md:61`). Medir en ECOM `SHOW STATUS LIKE 'Threads_connected'` antes y después.

### PERF-10 · Redis compartido entre sesiones y cache con `allkeys-lru`; sesión de 24 h por visita del link público
**Severidad:** BAJA (baja desde MEDIA: llenar 350 MB requiere 350-700 mil visitas únicas en 24 h) · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A4-11, A8-11 (= OPS-09) · **Ola:** 4 · **Esfuerzo:** S · **Decisión:** coordinación ECOM (config de su Redis)
- **Ubicación:** `docker-compose.prod.yml:24` (VM: `allkeys-lru 350mb`); `config/settings.py:305-340` (`default` y `sessions` con el mismo `REDIS_URL`; channel layer también, `:381-385`).
- **Propuesta:** `sessions` en otra DB de Redis (`REDIS_SESSIONS_DB`, default 2) con `volatile-lru` o `noeviction`, o `cached_db`; esto además protege las sesiones de un `cache.clear()` (G1c-12). **No** usar `set_expiry(3600)` en el paso 1 del link (contradice `portal/views/inscripcion.py:193-196`: «acortar la sesión entera hacía perder el paso 2»); alternativa compatible: `pregunta_captcha` no crea sesión en el GET si no existe `clave_sesion(relevamiento)` y el desafío se genera en el POST, o `set_expiry(3600)` solo mientras la sesión tenga únicamente las claves del captcha, restaurando `SESSION_COOKIE_AGE` al pasar el paso 1.

### PERF-12 · `COUNT(*)` del cupo del link público
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO (el paso 1 GET hace 6 consultas, una `COUNT(*) … WHERE relevamiento_id = X`; se repite bajo el lock en el envío) · **Origen:** A4-13 · **Ola:** 4 · **Esfuerzo:** — (sin cambio)
- **Decisión vigente:** el Cambio 91 decidió conservar ese `count` bajo el lock, por índice (pocos ms con 40k). **No** denormalizar salvo que el banco muestre > 20 ms con 40k casos.

### PERF-13 · Bandeja de personas filtrada por un estado raro sin índice que combine estado y orden
**Severidad:** BAJA · **Estado:** PLAUSIBLE / NO-MEDIDO · **Origen:** A4-14 · **Ola:** 4 · **Esfuerzo:** S (medir; índice solo si el plan lo pide)
- **Ubicación:** `programas/views/revision.py:398-422` (`relevamiento_id IN (...)` + `estado = X` + `ORDER BY creado DESC, pk DESC`); índices `programas/models/__init__.py:2629-2645`.
- **Propuesta:** **medir antes de migrar** (Cambio 66): `EXPLAIN ANALYZE` de `/becas/revision/?estado=BAJA&page=10` en el banco. Si hace falta: `models.Index(fields=["estado", "creado", "relevamiento"], name="prog_formulario_estado_creado_idx")` (online en MariaDB, `ALGORITHM=INPLACE, LOCK=NONE`; segundos con 40-100k filas).

### PERF-15 · Conteos del padrón en cada vista de detalle
**Severidad:** BAJA · **Estado:** CONFIRMADO (código) / NO-MEDIDO · **Origen:** A4-16 · **Ola:** 4 · **Esfuerzo:** S (medir)
- **Ubicación:** `programas/views/relevamientos.py:298-306`, `:706-711`.
- **Propuesta:** solo si se mide y pesa (padrón > 50k): guardar `padron_total` y `padron_con_identidad` al cargar (todo pasa por `cargar_padron`, PERF-04).

### PERF-16 · La señal de `Ciudadano` borra 4 claves de Redis por save
**Severidad:** BAJA sola; se suma a PERF-04 · **Estado:** CONFIRMADO (medido: 26.668 `cache.delete` para 6.667 saves; `contar_ciudadanos` se borra dos veces) · **Origen:** A4-18 · **Ola:** 4 · **Esfuerzo:** S
- **Ubicación:** `core/performance/cache_utils.py:22-49`; `dashboard/utils.py:50-57`.
- **Propuesta:** `transaction.on_commit(lambda: cache.delete_many([...deduplicadas]))` en la señal; no invalidar `contar_ciudadanos` con `created=False`. El grueso desaparece con PERF-04 (`bulk_update` no dispara la señal).

**Resolución:** ✅ Resuelto en #632 (Cambio 182, Ola 4 PR 1-2), 08-oct-2026 — la señal pasa a un solo `delete_many`
deduplicado dentro de `transaction.on_commit` (`core/performance/cache_utils.invalidar_tras_commit`), y los dos
contadores solo se invalidan cuando el total pudo cambiar: al crear o al borrar (`post_delete` no manda `created`, y ahí
el total sí cambió). Editar un ciudadano deja de borrarlos. `invalidate_dashboard_cache` se conserva tal cual —la
sigue llamando la señal de `User` y la congela el ratchet de RED-51, que la compara con su homónima de
`dashboard/utils.py`—. `invalidate_ciudadano_cache`, en cambio, se **borró en #639 (Cambio 186)**: con el receiver
nuevo no la llamaba nadie (la afirmación de que la llamaba `dashboard/utils.py` era falsa; ese módulo tiene su propia
`invalidate_dashboard_cache` y nunca la importó). El cruce del padrón, que ya
no dispara la señal, avisa con `invalidar_ciudadanos_tras_commit`: en el banco los **26.668 `cache.delete`** del peor
caso quedan en **un** `delete_many`.
**Test permanente:** `dashboard.tests.test_cache_invalidacion.InvalidacionTests.test_editar_un_ciudadano_no_invalida_los_contadores`
y `programas.tests.test_padron_performance.InvalidacionDeCacheTests.test_el_cruce_invalida_el_legajo_de_cada_ciudadano_una_sola_vez`.

### PERF-17 · Listados operativos sin paginar
**Severidad:** BAJA · **Estado:** CONFIRMADO (código; volumen bajo hoy) · **Origen:** A4-19 · **Ola:** v2 · **Esfuerzo:** S · **Tratamiento:** **criterio de aceptación v2** (README §7) para Dispositivos y Merenderos; `ConvocatoriaListView` y el detalle de convocatoria (pendiente del Cambio 92) van con FE-17 (Ola 5)
- **Ubicación:** `programas/views/dispositivos_legajo.py:70-99`, `:160-162` (trazas sin límite); `programas/views/relevamientos.py:198-214`, `:229-232`; `programas/views/merenderos.py:51-76`, `:133-137`.
- **Criterio:** `paginate_by = 25` + `components/_paginacion.html`; `trazas[:50]`; presupuestos `dispositivos:lista`, `merenderos:lista` en `perf_budgets.json`.

### PERF-18 · Reporte de ocupación de Dispositivos con `Count(distinct)` sobre camas × admisiones
**Severidad:** BAJA · **Estado:** CONFIRMADO (código) / NO-MEDIDO · **Origen:** A4-20 · **Ola:** v2 · **Esfuerzo:** S · **Tratamiento:** **criterio de aceptación v2**
- **Ubicación:** `programas/services/reportes.py:73-90`.
- **Criterio:** dos `Subquery` escalares (camas por estado; admisiones ALOJADO con cama) o dos `values("dispositivo_id").annotate(...)` unidos en Python; `assertNumQueries` + `EXPLAIN` con 20 dispositivos × 2.000 admisiones.

### PERF-19 · «Último intento por caso» sin índice compuesto y subconsulta evaluada dos veces por fila
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A4-21, V4-NEW-04 · **Ola:** 4 · **Esfuerzo:** S
- **Evidencia:** el SQL de `candidatos()` tiene `WHERE ((SELECT estado … ORDER BY creado DESC, id DESC LIMIT 1) IS NULL OR NOT ((SELECT estado …) = 'ENVIADO'))`: dos subconsultas correlacionadas por fila (la caché de subconsultas de MariaDB no las comparte). Igual en `validar_casos_siis --reintentar-errores`.
- **Propuesta:** `.annotate(ultimo_envio=Coalesce(Subquery(ultimo), Value("")))` + `.exclude(ultimo_envio=EnvioSIIS.Estado.ENVIADO)` (misma semántica); `models.Index(fields=["formulario", "creado", "id"], name=...)` en `ValidacionSIS` y `EnvioSIIS` (tablas de decenas de miles: migración trivial y online). Con SIIS-01, el criterio de «ya informado» pasa a `exclude(envios_sis__vigente=True)`, pero el «último estado» sigue decidiendo qué reintentar.
- **Test:** `str(candidatos(...).query).count("programas_enviosiis") == 1`; `EXPLAIN ANALYZE` del `count()` de PERF-07 antes y después.

**Resolución:** ✅ Resuelto en #639 (Cambio 186, Ola 4 PR 3), 08-oct-2026 — la propuesta tal cual, en los **dos**
lugares: `proceso_masivo.candidatos` y `validar_casos_siis._casos` anotan con
`Coalesce(Subquery(ultimo), Value(""))` y filtran con un solo `exclude` / `__in`. El valor de relleno es la cadena
vacía, que no es ninguno de los tres `choices` de `EnvioSIIS.Estado` ni de `ValidacionSIS.Estado`: «no tiene
intentos» pasa a ser un valor más y deja de necesitar el `Q(isnull=True) | …` que escribía la subconsulta dos veces.
Los dos índices `(formulario, creado, id)` van en `programas.0082`.
`EXPLAIN ANALYZE` del recorte de candidatos en el banco (MariaDB 10.11): antes, **tres** `DEPENDENT SUBQUERY` sobre
`programas_enviosiis` —dos de ellas resolviendo por `uniq_enviosiis_vigente_caso` con `Using filesort`— y la de
`programas_validacionsis` también con `Using filesort`; después, **una** sobre `idx_enviosiis_ultimo` y la de
validaciones sobre `idx_validacionsis_ult`, las dos sin `filesort`. El `count()` de la pantalla baja de 720 a 624 ms
sobre 8.000 envíos y 10.906 validaciones; el ahorro crece con los intentos acumulados por caso.
**Riesgo del índice:** `ALTER TABLE … ADD INDEX …, ALGORITHM=INPLACE, LOCK=NONE` aceptado por MariaDB 10.11 en
**29 ms** y **26 ms** sobre esas dos tablas. Al aplicar, Django **borra** el índice implícito de la clave foránea de
`programas_validacionsis` (`programas_validacion_formulario_id_…`), que el índice nuevo ya cubre, y al desaplicar lo
**recrea** con otro nombre (`programas_validacionsis_formulario_id_bca809bb`): la ida y vuelta por `migrate` es
limpia —probada—, pero un `DROP INDEX` a mano fuera de Django falla con `ERROR 1553` por la FK.
**Test permanente:** `programas.tests.test_circuito_siis_performance.UnaSolaSubconsultaDelUltimoEnvioTests.test_la_subconsulta_del_ultimo_envio_no_se_escribe_dos_veces`
y `programas.tests.test_circuito_siis_performance.LosMismosCandidatosTests`.

### G1c-11 · Admin: N+1 en listados
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1c-11 · **Ola:** 4 (mismo PR que G1c-09) · **Esfuerzo:** S
- **Ubicación:** `list_display` con FK sin `list_select_related`: `ListaEsperaAdmin` (`formulario`→`ciudadano`, `segmento`), `TracaFormularioAdmin`, `HistorialContactoAdmin` (`legajo`, `profesional`), `VinculoFamiliarAdmin` (2 ciudadanos), `RelevamientoAdmin` (`convocatoria`, `territorial`): 100-300 consultas por página. `OptimizedGroupAdmin` prefetchea `user_set` y `CiudadanoAdmin` `inscripciones_programas` sin usarlas.
- **Propuesta:** `list_select_related`; `search_fields=("=formulario__id",)` donde aplique; sacar los prefetch inútiles.

### G3-03 · `alertas_websocket.js` se carga para todo el backoffice y reintenta 5 veces con quien no tiene permiso
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G3-03 · **Ola:** 2 (mismo PR que G1c-04) · **Esfuerzo:** S
- **Ubicación:** `templates/includes/base.html:388-390` (se incluye con `websockets_enabled`, sin mirar capacidades); `static/custom/js/alertas_websocket.js:12-14`, `:335-343` (5 reintentos cada 3 s); `conversaciones/consumers.py:215-217` (cierra con 4403).
- **Escenario:** cada página de un usuario de Becas sin `ciudadano.ver` dispara 1 + 5 handshakes contra el único daphne (300 MB en icore); con cientos de operadores en campaña, miles de handshakes inútiles por minuto, y el indicador muestra «Desconectado».
- **Propuesta:** incluir el script solo si `puede_ver_ciudadanos` (context processor; ya existe el patrón `puede_conversaciones` en la misma plantilla) y no reintentar ante `event.code === 4403` (o 1006 tras un 403 de handshake). Mismo patrón sin medir en `alertas_conversaciones_rt.js` (se va con el apagado de conversaciones, G1-01 fase 2).
- **Test:** `test_base_no_incluye_alertas_ws_sin_capacidad` (render de `/inicio/` sin `ciudadano.ver` → no aparece `alertas_websocket.js`).

**Resolución:** ✅ Resuelto en #629 (Cambio 179), 08-oct-2026 — **un solo guard**, `puede_alertas_sensibles`. La
primera vuelta del PR necesitó dos (`ciudadano.ver` para el script, `ciudadano.sensible` para abrir el socket)
porque la campana del navbar y `/ws/alertas/` pedían capacidades distintas, y subir solo la del consumer habría
**creado** la población que la ficha describe. La ronda 2 eliminó esa población en vez de administrarla: con D-11
la campana, el contador, el preview y el dashboard también piden `ciudadano.sensible`, así que quien no la tiene
no ve campana, ni punto de estado, ni script, y no hay handshake que rechazar. Se fueron con eso la variable
`puede_ver_ciudadanos` y el flag `window.alertasConfig.puedeSocket`. Además, un cierre con código `4403` marca
`rechazado` y **no** se reintenta: es un veredicto de autorización, no una caída de red. La variable sale del
context processor `conversaciones.context_processors.user_groups`, donde `rbac.puede` resuelve sobre el mismo juego
de permisos que ya leía `puede_conversaciones` (sin consultas nuevas; `inicio` conserva su presupuesto).
`alertas_conversaciones_rt.js` queda como estaba: se va con el apagado de conversaciones (G1-01 fase 2).
**Test permanente:** `core.tests.test_alertas_ws_shell` (en particular
`AlertasWebsocketEnElShellTests.test_sin_capacidad_no_se_incluye_el_script`,
`test_con_ciudadano_ver_solo_tampoco_hay_campana_ni_script` y
`AlertasWebsocketReintentosTests.test_el_js_no_reintenta_tras_un_4403`).
