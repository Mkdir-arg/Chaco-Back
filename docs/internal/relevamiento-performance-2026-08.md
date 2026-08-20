# Relevamiento profundo de performance — 2026-08-19 (tasks #262 y #264)

> **Clasificación: medición en entorno DEDICADO local con datos sintéticos.**
> No representa rendimiento de producción, no es una prueba de carga de producción
> y no habilita conclusiones de capacidad. Es la segunda línea de base de la épica
> #222, posterior a la optimización de #261.

Tasks: #262 (relevamiento profundo) · #264 (línea de base con métricas reales) · Épica: #222 · Análisis de origen: #259 · Relevamiento previo: #219

## 1. Contexto de validez

| Dato | Valor |
|---|---|
| Fecha de la ventana | 2026-08-19 |
| SHA medido | `f80a7c54bb9c28f2ebe5b2f22ca7a80529275ef5` (rama `claude/perf-optimization-261-262-c05caf`, con #261 aplicada) |
| Ambiente | Docker Compose **dedicado y descartable** en la máquina de desarrollo, aislado del stack de otro worktree |
| Base de datos | MySQL 8.0.44 (contenedor propio, volumen propio) |
| Cache y métricas | Redis 7.4.9 (contenedor propio). Con `PERFORMANCE_CI=1` el cache `default` es Redis, como en producción |
| Runtime | `manage.py runserver` (Django 5.2.17, Python 3.12.14) |
| Datos | Sintéticos de `manage.py seed_perf`. **Ningún dato funcional de un entorno compartido fue creado, modificado ni eliminado** |
| Volumen medido | Dos escalas: **200** y **2000** entidades principales |
| Volumen final | 2006 ciudadanos · 2000 conversaciones · 2204 relevamientos · 2200 formularios · 200 segmentos · 4000 inscripciones |
| Rol de prueba | `perf_admin` (grupos `Administrador` y `Becas — Administrador`), más identidades sintéticas dedicadas para concurrencia y para leer métricas |
| Nivel de concurrencia | **8** sesiones simultáneas con **identidades distintas**, 5 rondas por worker |
| Fuentes de métricas | `/performance-api/` (instrumentación por request) + medición HTTP externa (TTFB y tiempo total) + auditoría determinista `scripts/perf_audit.py` |

**Servicios externos:** el stack corrió **sin credenciales** de SIIS, Personas y RENAPER. No se
hizo ninguna llamada real a servicios externos.

## 2. Procedencia de las métricas

Tomado de `/performance-api/`, verificado antes de usar cualquier medición:

| Campo | Valor |
|---|---|
| `metrics_source` | `measured` |
| `scope` | `shared_fixed_window` (Redis compartido, sin namespace de corrida) |
| `window.kind` / `window.seconds` | `fixed` / 3600 |
| Retención | 86400 s |
| Tasa de muestreo | **1.0 (no existe muestreo en este SHA)** — ver §3.2 |

Las métricas se reinician (`FLUSHALL` del Redis dedicado) antes de cada fase, así que los
agregados por fase no se contaminan entre sí.

Los artefactos conservan únicamente rutas normalizadas y agregados: **sin SQL, parámetros, URLs,
usuarios, payloads, tokens ni credenciales.**

## 3. Sesgos declarados

### 3.1 La instrumentación subcuenta sistemáticamente

`QueryCountMiddleware` se agrega al final de `MIDDLEWARE` (`config/settings.py`), así que es el
**más interno** y no ve las consultas de sesión, autenticación, grupos ni del control de sesión
única de Backoffice.

#219 lo reportó como un caso puntual («13 medidas contra 16 reales» en `/inicio/`). Acá queda
cuantificado sobre las 16 rutas del manifiesto determinista, comparando el total real capturado
con `CaptureQueriesContext` contra lo que el middleware reporta:

| Ruta | Consultas reales | Ve el middleware | Ocultas | % oculto |
|---|---:|---:|---:|---:|
| `inicio` | 19 | 14 | 5 | 26 % |
| `dashboard_redirect` | 4 | 0 | 4 | **100 %** |
| `dashboard_metricas` | 9 | 5 | 4 | 44 % |
| `legajos_lista` | 12 | 8 | 4 | 33 % |
| `legajo_detalle` | 20 | 16 | 4 | 20 % |
| `conversaciones_lista` | 14 | 10 | 4 | 29 % |
| `conversacion_detalle` | 12 | 8 | 4 | 33 % |
| `portal_perfil` | 11 | 7 | 4 | 36 % |
| `portal_programas` | 9 | 6 | 3 | 33 % |
| `portal_consultas` | 8 | 5 | 3 | 38 % |
| `becas_segmentos` | 14 | 10 | 4 | 29 % |
| `becas_convocatorias` | 11 | 7 | 4 | 36 % |
| `becas_relevamientos` | 15 | 11 | 4 | 27 % |
| `becas_relevamiento_detalle` | 14 | 10 | 4 | 29 % |
| **Total** | **175** | **120** | **55** | **31 %** |

**Regla de lectura:** todo `max_queries` de este informe y del dashboard es un **piso**, no el
costo real. Para una ruta autenticada de backoffice hay que sumarle ~4 consultas fijas.

### 3.2 El muestreo todavía no existe en este SHA

El análisis #259 advierte que con muestreo 0.2 en producción, `max_queries` es el peor caso
**entre las requests muestreadas**, no el peor real, y que hay que leer `sampling_rate`.

**Hecho medido:** en este SHA no hay muestreo. `sampling_rate` no existe en el código (una
búsqueda sobre todo el repo no encuentra la clave) porque lo introduce #260, cuya **PR #263 sigue
abierta y sin mergear**. La instrumentación mide el **100 %** de las requests, así que los
máximos de este informe son máximos reales de la ventana.

**Consecuencia:** cuando #260 se mergee y producción quede en 0.2, este informe deja de ser
comparable con producción sin corregir por muestreo. La advertencia de #259 aplica a futuro,
no a estos números.

### 3.3 Desvíos del entorno respecto de producción

Declarados para que nadie lea estos tiempos como producción:

- **Runtime distinto:** `runserver`, no Daphne/ASGI. Los resultados de concurrencia no
  representan el pool de threads de Daphne.
- **Sesiones en base de datos:** producción usa sesiones en cache (`ENVIRONMENT == "prd"`).
- **Sin red:** la medición es contra `localhost`; no incluye latencia de red, TLS ni nginx.
- **Volumen sintético:** distribución uniforme de `seed_perf`, no la distribución real.

## 4. Comparación con la línea de base de #219

#219 midió 5 flujos de solo lectura, 5 repeticiones, un usuario, contra el TEST remoto
`relevamiento-deshum.ecomdev.ar`, con SHA de contraste `9beda837`.

### 4.1 Lo que sí es comparable: el tamaño del documento

| Flujo | #219 (TEST remoto) | Este relevamiento (gzip) | Δ |
|---|---:|---:|---:|
| `/inicio/` | 28.2 KB | 28.8 KB | +2 % |
| `/legajos/ciudadanos/` | 24.9 KB | 25.4 KB | +2 % |
| `/legajos/reportes/` | 23.1 KB | 22.6 KB | −2 % |
| `/legajos/ciudadanos/nuevo/` | 22.8 KB | 22.2 KB | −3 % |
| `/configuracion/programas/` | 24.6 KB | 24.1 KB | −2 % |

Las cinco coinciden dentro de ±3 %. Eso ancla la comparabilidad: **ambos entornos renderizan
páginas equivalentes y no hay regresión de payload**. También confirma que las cifras de #219
eran tamaño transferido (comprimido): sin gzip estas mismas páginas pesan 152–204 KB.

### 4.2 Lo que NO es comparable: el TTFB

| Flujo | #219 mediana | Este relev. escala 200 | Este relev. escala 2000 |
|---|---:|---:|---:|
| `/inicio/` | 95 ms | 27.1 ms | 45.6 ms |
| `/legajos/ciudadanos/` | 81 ms | 21.1 ms | 27.8 ms |
| `/legajos/reportes/` | 90 ms | 20.7 ms | 30.6 ms |
| `/legajos/ciudadanos/nuevo/` | 84 ms | 19.9 ms | 24.6 ms |
| `/configuracion/programas/` | 90 ms | 19.4 ms | 27.5 ms |

**No se concluye ninguna mejora de esta tabla.** Los números de #219 incluyen ida y vuelta por
internet hasta un host remoto; los de acá son `localhost` sin red. La diferencia mide sobre todo
el camino de red, no el código. Presentar esto como «bajamos de 95 ms a 45 ms» sería incorrecto.

### 4.3 Lo que #219 no pudo medir y ahora sí

#219 declaró «sin telemetría SQL válida» y `query_count: 0`. Ahora hay conteo real por request
(§5, §6, §8). Ese es el avance concreto entre ambas líneas de base.

## 5. Flujos de lectura (los 5 de #219)

Procedimiento equivalente al de #219: 1 pasada de calentamiento descartada + 5 repeticiones
secuenciales, usuario autenticado de backoffice.

Escala 2000, TTFB en ms, y consultas por request medidas por la instrumentación:

| Flujo | Ruta | HTTP | TTFB mediana | TTFB p95 | TTFB máx | `max_queries` |
|---|---|---:|---:|---:|---:|---:|
| Inicio | `core:inicio` | 5/5 × 200 | 45.6 | 52.1 | 52.1 | 15 |
| Ciudadanos | `legajos:ciudadanos` | 5/5 × 200 | 27.8 | 30.4 | 30.4 | 7 |
| Reportes | `legajos:reportes` | 5/5 × 200 | 30.6 | 32.6 | 32.6 | 10 |
| Nuevo legajo | `legajos:ciudadano_nuevo` | 5/5 × 200 | 24.6 | 33.5 | 33.5 | 2 |
| Config. programas | `configuracion:programas` | 5/5 × 200 | 27.5 | 36.2 | 36.2 | 4 |

Sin consultas duplicadas y sin N+1 detectado en ninguno de los cinco.

## 6. Flujos de escritura (lo que #219 no cubrió)

Cuatro flujos de escritura, 3 repeticiones cada uno, sobre datos sintéticos.

| Flujo | Ruta | Resultado | TTFB mediana | `max_queries` | `max_duplicate_queries` |
|---|---|---|---:|---:|---:|
| Alta de ciudadano | `legajos:ciudadano_manual` | 302 → `/legajos/ciudadanos/` | 24.5 ms | 4 | 0 |
| Carga de relevamiento | `becas:relevamiento_crear` | 302 → `/becas/relevamientos/` | 27.9 ms | **13** | **1** |
| Edición en Becas | `becas:convocatoria_editar` | 302 → `/becas/convocatorias/1/` | 30.1 ms | 6 | **1** |
| Envío en conversaciones | `conversaciones:enviar_mensaje_operador` | 200 (JSON) | 25.1 ms | 4 | 0 |

Ruta auxiliar que el recorrido atravesó: `conversaciones:detalle` (7), al leer el CSRF.

**Sobre `conversaciones:asignar`:** el recorrido intentó un POST de asignación previa que devolvió
**404** y quedó registrado con 3 consultas. No es un fallo del producto: la vista exige
`estado="activa"` (`conversaciones/views/backoffice.py:114`) y la conversación sembrada está en
`pendiente`, así que el 404 es la respuesta correcta. El paso además era innecesario:
`enviar_mensaje_operador` no exige asignación previa y creó los mensajes igual. Sus 3 consultas
corresponden al camino 404, **no** a una asignación medida, y por eso no se informa como flujo de
escritura.

**Validación de que son escrituras reales.** Dos controles independientes:

1. Cada respuesta se verificó contra su `Location`. Un 302 hacia `/` sería el redirect al login, no
   una escritura; el harness lo detecta y lo marca. Durante la construcción esto ocurrió y se
   corrigió (ver O-1).
2. Conteo de filas en la base al cerrar el relevamiento: 9 ciudadanos con apellido `Escritura*`,
   7 relevamientos con observaciones sintéticas, `Convocatoria` 1 con nombre
   `PERF Convocatoria 000 rev2` y descripción reemplazada, 9 mensajes sintéticos, y la
   conversación 1 con operador asignado. Las escrituras persistieron.

**Nota sobre el alta de ciudadano:** se midió el formulario **manual**
(`/legajos/ciudadanos/manual/`), que no consulta RENAPER. La variante que sí lo consulta
(`/legajos/ciudadanos/nuevo/`) no se usó para medir costo propio porque en este entorno
`RENAPER_TEST_MODE=True` inserta un `time.sleep(2)` fijo (ver H-7).

## 7. Concurrencia

| Parámetro | Valor |
|---|---|
| Nivel de concurrencia | **8 sesiones simultáneas, identidades distintas** |
| Rondas por worker | 5 (× 5 flujos) |
| Requests totales | 200 |
| Errores | 0 |
| Wall clock | 3.52 s |
| Throughput observado | **56.8 req/s** |

Comparación secuencial vs concurrente (escala 2000, TTFB en ms):

| Flujo | Secuencial mediana | Concurrente mediana | Concurrente p95 | Concurrente máx | Degradación |
|---|---:|---:|---:|---:|---:|
| `core:inicio` | 45.6 | 163.9 | 240.6 | 262.9 | **3.6×** |
| `legajos:reportes` | 30.6 | 131.3 | 164.6 | 223.5 | **4.3×** |
| `legajos:ciudadanos` | 27.8 | 104.3 | 156.4 | 176.4 | **3.8×** |
| `configuracion:programas` | 27.5 | 92.3 | 138.8 | 176.2 | **3.4×** |
| `legajos:ciudadano_nuevo` | 24.6 | 91.3 | 144.3 | 188.5 | **3.7×** |

El bucket de latencia de `core:inicio` pasa de ≤50 ms a ≤250 ms. Con 8 clientes la degradación es
aproximadamente proporcional a la concurrencia, que es el comportamiento esperado de un servidor
que no escala dentro del proceso: **no hay evidencia de contención anómala, bloqueo ni errores**.
Los `max_queries` no cambian bajo concurrencia.

**Este resultado no se traslada a producción**: `runserver` no es Daphne (§3.3).

## 8. Peor caso por ruta

Máximos por request y buckets de latencia, no promedios. Escala 2000.

| Ruta | `max_queries` | `max_duplicate_queries` | Bucket p95 secuencial | Bucket p95 concurrente |
|---|---:|---:|---:|---:|
| `core:inicio` | 15 | 0 | ≤50 ms | ≤250 ms |
| `users:login` (POST) | 10 | 0 | ≤250 ms | ≤500 ms |
| `legajos:reportes` | 10 | 0 | ≤50 ms | ≤100 ms |
| `becas:relevamiento_crear` | 13 | 1 | ≤50 ms | — |
| `legajos:ciudadanos` | 7 | 0 | ≤50 ms | ≤100 ms |
| `conversaciones:detalle` | 7 | 0 | ≤50 ms | — |
| `becas:convocatoria_editar` | 6 | 1 | ≤50 ms | — |
| `configuracion:programas` | 4 | 0 | ≤50 ms | ≤100 ms |
| `legajos:ciudadano_manual` | 4 | 0 | ≤50 ms | — |
| `conversaciones:enviar_mensaje_operador` | 4 | 0 | ≤50 ms | — |
| `conversaciones:asignar` (404) | 3 | 0 | ≤50 ms | — |
| `legajos:ciudadano_nuevo` (GET) | 2 | 0 | ≤50 ms | ≤100 ms |

Recordar §3.1: sumarle ~4 consultas por ruta autenticada para obtener el costo real.

## 9. Costo de servicios externos (SIIS, Personas, RENAPER)

**No se pudo medir. Dato no disponible, no «costo cero».**

La instrumentación de dependencias existe y funciona: `instrument_external_call` está aplicado en
`programas/services/siis.py`, `programas/services/personas.py` y
`legajos/services/consulta_renaper.py`. En este relevamiento el campo `dependencies` de todas las
rutas quedó **vacío**, por tres causas concretas y medidas:

1. **Sin credenciales.** El stack corrió deliberadamente sin claves de SIIS, Personas ni RENAPER
   para no llamar a servicios externos reales.
2. **`RENAPER_TEST_MODE` no pasa por la instrumentación.** En
   `legajos/services/consulta_renaper.py:376` el modo test devuelve datos sintéticos y corta
   **antes** de `instrument_external_call`. Probado: un alta por `/legajos/ciudadanos/nuevo/`
   respondió 302 y registró `dependencies = {}`.
3. **El catálogo SIIS está vacío.** `ProgramaSiis.objects.count() == 0`, así que el alta/edición
   de segmentos de Becas no es utilizable (el `select` de programa no tiene opciones) y por lo
   tanto no ejercita SIIS. Por eso la edición en Becas se midió sobre convocatoria.

Separar costo externo de costo propio requiere un modo de simulación que **sí** atraviese
`instrument_external_call`. Derivado como H-6.

## 10. Sensibilidad al volumen

Se midió todo a escala 200 y a escala 2000 (10×).

| Fase | Requests | Consultas escala 200 | Consultas escala 2000 |
|---|---:|---:|---:|
| Lecturas | 32 | 178 | **178** |
| Escrituras | 26 | 154 (6 duplicadas) | **154 (6 duplicadas)** |
| Concurrencia | 216 | 1139 | **1139** |

**Hecho medido: el conteo de consultas es idéntico a 10× de volumen, y el `max_queries` de cada
ruta no cambió en ninguna.** No hay N+1 dependiente del volumen de datos en los flujos
relevados: la paginación y los selectors se sostienen.

La latencia sí crece, de forma sublineal (10× datos → 1.2×–1.7× TTFB):

| Flujo | Escala 200 | Escala 2000 | Factor |
|---|---:|---:|---:|
| `/inicio/` | 27.1 ms | 45.6 ms | 1.68× |
| `/legajos/reportes/` | 20.7 ms | 30.6 ms | 1.48× |
| `/configuracion/programas/` | 19.4 ms | 27.5 ms | 1.42× |
| `/legajos/ciudadanos/` | 21.1 ms | 27.8 ms | 1.32× |
| `/legajos/ciudadanos/nuevo/` | 19.9 ms | 24.6 ms | 1.24× |

## 11. Contraste con los presupuestos versionados

`scripts/perf_budgets.json` cubre 16 rutas, **todas de lectura**. Contraste de lo medido:

| Ruta medida | Medido (`max_queries`) | Presupuesto | Margen |
|---|---:|---:|---|
| `core:inicio` | 15 | 20 | 5 |
| `legajos:ciudadanos` | 7 | 13 | 6 |
| `conversaciones:detalle` | 7 | 14 | 7 |
| `users:login` | 10 | **0** | **ver H-4** |
| `legajos:reportes` | 10 | — | **sin presupuesto** |
| `configuracion:programas` | 4 | — | **sin presupuesto** |
| `legajos:ciudadano_nuevo` | 2 | — | **sin presupuesto** |
| `legajos:ciudadano_manual` | 4 | — | **sin presupuesto** |
| `becas:relevamiento_crear` | 13 | — | **sin presupuesto** |
| `becas:convocatoria_editar` | 6 | — | **sin presupuesto** |
| `conversaciones:enviar_mensaje_operador` | 4 | — | **sin presupuesto** |
| `conversaciones:asignar` (404, ver §6) | 3 | — | **sin presupuesto** |

Los valores medidos por el middleware quedan **por debajo** de los presupuestos en todas las rutas
que tienen uno, lo cual es esperable por §3.1: el presupuesto se fija con el conteo total de
`perf_audit` y el middleware ve menos. **Ningún presupuesto se modifica en esta task.**

## 12. Hallazgos priorizados

Cada hallazgo indica si es **hecho medido** o **hipótesis**.

### H-1 · Ningún flujo de escritura tiene presupuesto — severidad MEDIA

- **Evidencia (medida):** las 4 rutas de escritura medidas (§6) —y las auxiliares que el recorrido
  atraviesa— no están en `scripts/perf_budgets.json`, que cubre 16 rutas, todas de lectura.
- **Impacto:** una regresión de consultas en un alta, una edición o un envío de mensaje no la
  detecta ninguna guarda de CI.
- **Causa:** el manifiesto de `scripts/perf_audit.py::build_targets` sólo hace GET.
- **Recomendación:** extender manifiesto y presupuestos a los flujos de escritura.

### H-2 · Dos rutas de escritura tienen una consulta duplicada — severidad MEDIA

- **Evidencia (medida):** `becas:relevamiento_crear` y `becas:convocatoria_editar` reportan
  `max_duplicate_queries = 1`, estable en ambas escalas.
- **Causa probable (hipótesis, no verificada sobre estas dos rutas):** la misma colisión de
  fingerprint documentada en #261. `programa_becas()` lee `Programa WHERE codigo='BECAS'` y el tag
  de sidebar `programa_dispositivos()` lee `codigo='DISPOSITIVOS'`; `sql_fingerprint` reemplaza el
  literal por `?` y las agrupa. Confirmarlo requiere capturar el SQL con su call-site como se hizo
  en #261.
- **Recomendación:** diagnosticar con captura de call-site y confirmar o descartar.

### H-3 · Tres de los cinco flujos de #219 no tienen presupuesto — severidad MEDIA

- **Evidencia (medida):** `legajos:reportes` (10 consultas por request, el segundo más alto de las
  lecturas), `configuracion:programas` (4) y `legajos:ciudadano_nuevo` (2) no están en el
  manifiesto ni en los presupuestos.
- **Impacto:** los flujos que la propia línea de base considera representativos quedan sin guarda.
- **Recomendación:** incorporarlos al manifiesto determinista y fijarles presupuesto.

### H-4 · El presupuesto de `login` sólo cubre el GET — severidad BAJA

- **Evidencia (medida):** el presupuesto de `login` es `max_queries: 0` porque el manifiesto hace
  GET de la página. El **POST** de autenticación mide `max_queries = 10`.
- **Impacto:** el costo real del login no está protegido; el 0 da una falsa sensación de cobertura.
- **Recomendación:** medir el POST como entrada propia, o documentar que el presupuesto es del GET.

### H-5 · La instrumentación subcuenta 31 % — severidad MEDIA

- **Evidencia (medida):** §3.1, 55 de 175 consultas invisibles; 100 % en `dashboard_redirect`.
- **Impacto:** el dashboard y las APIs informan un piso. Comparar contra presupuestos fijados con
  el conteo total lleva a creer que hay más margen del que hay.
- **Recomendación:** evaluar mover `QueryCountMiddleware` hacia afuera de la cadena, o exponer el
  desvío conocido junto a la métrica para que el consumidor lo corrija.

### H-6 · El costo de SIIS, Personas y RENAPER no es medible — severidad MEDIA

- **Evidencia (medida):** §9. `dependencies` vacío en todas las rutas;
  `consulta_renaper.py:376` corta antes de `instrument_external_call`;
  `ProgramaSiis.objects.count() == 0`.
- **Impacto:** no se puede separar costo externo de costo propio, que es justamente uno de los
  objetivos de este ciclo.
- **Recomendación:** modo de simulación que atraviese `instrument_external_call` con latencia
  configurable, usable en relevamientos y en CI sin llamar a los servicios reales.

### H-7 · `RENAPER_TEST_MODE` mete un `time.sleep(2)` en el request path — severidad MEDIA

- **Evidencia (medida):** `legajos/services/consulta_renaper.py:377`, `time.sleep(2)` incondicional
  dentro de `_consultar_datos_renaper` cuando el modo test está activo.
- **Impacto:** en cualquier entorno con el flag encendido, cada alta por RENAPER agrega 2 s de
  latencia y retiene un thread del pool. Bajo Daphne, con el pool acotado, 2 s por request de alta
  es contención real.
- **Recomendación:** hacer la demora configurable y por defecto 0, o simularla sin bloquear.

### H-8 · Degradación esperada bajo concurrencia 8, sin anomalías — severidad INFORMATIVA

- **Evidencia (medida):** §7. Mediana ×3.4–4.3, p95 ≤250 ms, 0 errores, 56.8 req/s.
- **Impacto:** ninguno accionable hoy. **No es un resultado de producción**: `runserver` ≠ Daphne.
- **Recomendación:** repetir bajo Daphne antes de sacar conclusiones de capacidad.

### H-9 · Los defaults de `docker-compose.yml` no arrancan sin `.env` — severidad BAJA

- **Evidencia (medida):** el servicio `mysql` crea la base con
  `MYSQL_DATABASE=${DATABASE_NAME:-chaco}` / `MYSQL_USER=${DATABASE_USER:-chaco}` / `chaco123`,
  mientras `app` conecta con `${DATABASE_NAME:-chaco_db}` / `${DATABASE_USER:-chaco_user}` /
  `chaco_secure_pass`. Sin un `.env` que defina las tres variables, el entrypoint queda en
  «Esperando base de datos...» indefinidamente. Reproducido en este relevamiento.
- **Impacto:** fricción de onboarding; un `docker compose up` limpio no levanta.
- **Recomendación:** alinear los defaults entre ambos servicios, o documentar el `.env` requerido.

### O-1 · Hallazgo operativo: el control de sesión única impide medir concurrencia con un mismo usuario

- **Evidencia (medida):** con 8 logins concurrentes del mismo `perf_admin`,
  `BackofficeSingleSessionMiddleware` invalida todas las sesiones menos la última y las requests
  pasan a redirigir al login (302). El primer intento de este relevamiento produjo 302 en toda la
  fase concurrente y en las escrituras, con métricas artificialmente bajas (10 consultas en 27
  requests) por ese motivo.
- **Consecuencia para futuros relevamientos:** la concurrencia exige **una identidad por worker**, y
  la sesión que lee `/performance-api/` debe usar un usuario distinto del que ejecuta los flujos.
  Es comportamiento correcto del producto, no un defecto; se documenta como requisito de método.
  Ya está resuelto en el harness usado acá.

## 13. Cobertura adicional de la task #264

Este mismo corte completa la línea de base verificable solicitada por #264. La
relación no cambia la naturaleza del entregable: sigue siendo un relevamiento,
sin optimizaciones ni cambios de presupuesto.

| Criterio de #264 | Evidencia en este informe |
|---|---|
| Contexto de la ventana y procedencia de las métricas | §1 y §2: SHA, ambiente, volumen, `shared_fixed_window`, ventana, retención y tasa de muestreo |
| Flujos del manifiesto con calentamiento y repeticiones | §5 y §8: lecturas del manifiesto, 1 calentamiento y 5 repeticiones por flujo |
| Máximos, duplicadas, latencia y dependencias por ruta | §6, §8 y §9, tomados de `/performance-api/` y de la sonda HTTP |
| Contraste contra presupuestos y rutas sin margen | §11, sin modificar `scripts/perf_budgets.json` |
| Sin carga ni servicios externos reales | §1 y §9: Docker dedicado, datos sintéticos y sin credenciales externas |
| Artefacto sin datos sensibles | §2: no conserva SQL, parámetros, URLs, usuarios, payloads, tokens ni credenciales |
| Continuidad de los hallazgos | Task derivada #268: alcance, requisitos y criterios verificables para H-1 a H-9 |

H-8 no es una optimización pendiente: es un resultado informativo que pide repetir
la medición bajo Daphne antes de concluir sobre capacidad. O-1 queda incorporado
como requisito del método de concurrencia, porque describe un control funcional
correcto y no un defecto.

## 14. Qué NO es este informe

- No es una medición de producción ni una prueba de carga de producción.
- No permite concluir mejora ni empeoramiento de TTFB contra #219 (§4.2).
- No mide costo de servicios externos (§9).
- No representa el comportamiento de Daphne bajo concurrencia (§3.3).
- No introduce optimizaciones ni modifica presupuestos: es un relevamiento.
