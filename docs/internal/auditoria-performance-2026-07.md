# Auditoría de performance — repo completo (2026-07-12)

Barrido de todo el código Python y templates del repo (sin `migrations/` ni tests), en 4 particiones
auditadas en paralelo. Cada hallazgo fue verificado contra su queryset/código de origen antes de
reportarse. Contexto verificado: prod corre `ENVIRONMENT=prd` + `config.settings_production`, con
cache default **y** sesiones compartiendo el mismo Redis DB 1.

## Temas transversales (lo que más duele)

1. **Invalidación de cache rota a nivel sitio.** `core/services/cache.py:44` usa `conn.keys("*patrón*")`
   (bloquea Redis entero, O(N) del keyspace que incluye las sesiones) y ante cualquier excepción cae a
   `cache.clear()` (FLUSHDB → borra sesiones = logout masivo). Se dispara en cada mensaje de chat
   (×2), cada asignación/cierre de conversación… y no hay ninguna clave `conversaciones:*` cacheada:
   es costo puro sin beneficio. Además `legajos/signals/core.py` hace `cache.clear()` directo en cada
   save/delete de `Ciudadano`.
2. **Polling agresivo sin cache ni delta.** Chat ciudadano: historial completo cada 2 s (portal cada
   4 s, endpoint público sin rate-limit). Poller global del backoffice cada 5 s con filtros
   `fecha_inicio__month=` → `EXTRACT()` no-sargable → full scan por poll. Navbar de alertas cada 10 s.
   Métricas: fetch + `location.reload()` de la página entera cada 30 s.
3. **Falta de paginación en pantallas de trabajo.** Lista de conversaciones (con reload completo por
   evento WS), listado de usuarios (paginación falsa "1 de 1"), hub Ñachec (todos los casos de la
   base), prestaciones Ñachec, beneficiarios de convocatoria, API de contactos del legajo.
4. **Trabajo de batch en el request path.** Generación completa de alertas (con escrituras +
   WebSocket) en cada GET del detalle de ciudadano y en cada save de `LegajoAtencion`; escaneo y
   decodificación de TODAS las sesiones de `django_session` por cada conversación creada;
   `psutil.cpu_percent(interval=1)` = sleep de 1 s por request en las APIs de monitoreo.
5. **RENAPER.** Cliente/token nuevos por request (2 round-trips HTTP externos por consulta), sin cache
   por DNI, con **dos endpoints públicos** sin autenticación ni rate-limit
   (`legajos/api_views/__init__.py:93` con `AllowAny`, `conversaciones/views/public.py:46`).
   Los timeouts sí están bien (10 s / 20 s).
6. **N+1 estructural en legajos.** `LegajoAtencion.ciudadano`/`programa`/`dispositivo` son properties
   con query (`legajos/models/base.py:269-292`): imposible de arreglar con `select_related`; ya existe
   `annotate_legajo_link_data()` en `legajos/services/linking.py:52` para usar en los querysets.

---

## SEVERIDAD ALTA

### Cache / Redis
| # | Ubicación | Problema | Fix |
|---|-----------|----------|-----|
| A1 | `core/services/cache.py:44` + `core/signals/cache.py:13-23` | `KEYS *patrón*` bloqueante en Redis por cada save/delete de `Conversacion` y `Mensaje` (mensajes lo disparan ×2) | Claves determinísticas + `delete_many`, o `delete_pattern` (SCAN) de django-redis; nunca `KEYS` en request path |
| A2 | `core/services/cache.py:53-55` | Fallback `cache.clear()` = FLUSHDB del Redis que también guarda sesiones → logout masivo | En el `except`: loguear y no invalidar |
| A3 | `legajos/signals/core.py` (receiver `invalidate_ciudadano_cache`) | `cache.clear()` global en cada save/delete de `Ciudadano` | Invalidar por claves puntuales como el receiver hermano |

### Legajos / Ñachec
| # | Ubicación | Problema | Fix |
|---|-----------|----------|-----|
| A4 | `legajos/views/programas.py:107-116` | Hub Ñachec (destino de ~25 redirects) carga TODOS los `CasoNachec` sin filtro/paginación + 1 query `TareaNachec` por caso; el template itera la lista 9 veces | `Exists(OuterRef(...))` anotado, filtrar estados activos en DB, paginar solapas |
| A5 | `legajos/selectors/ciudadanos.py:99-105` (+ `legajos/views/contactos_api.py:100`) | `AlertasService.generar_alertas_ciudadano()` (UPDATE masivo + queries por legajo + INSERTs + `group_send`) corre en cada GET del detalle de ciudadano | Mover a tarea periódica/asíncrona; la vista solo lee |
| A6 | `legajos/signals/alertas.py` (`verificar_alertas_legajo`) | Cada `LegajoAtencion.save()` dispara el pipeline completo de alertas del ciudadano, sincrónico y duplicado con A5 | Regenerar solo lo del legajo tocado o despachar a cola |
| A7 | `legajos/views/nachec_operacion.py:182-189` | 1 COUNT por cada usuario activo en el GET del modal de asignación; ya existe la versión con `annotate(Count)` en `legajos/services/nachec.py:551-565` | Usar `get_territoriales_con_carga()` |

### Conversaciones / Portal
| # | Ubicación | Problema | Fix |
|---|-----------|----------|-----|
| A8 | `conversaciones/templates/conversaciones/lista.html:219,310` + `conversaciones/selectors/conversaciones.py:16-34` | `mensajes.count` por fila ×2 (render desktop + mobile) sin anotación | `total_mensajes=Count("mensajes")` en la anotación existente |
| A9 | `conversaciones/views/backoffice.py:57-74` + `static/custom/js/conversaciones_lista_ws.js:158` | Lista de conversaciones sin `Paginator` (histórico completo por request) y `window.location.reload()` por cada evento WS | Paginar 25-50, default sin cerradas, inserción incremental de filas |
| A10 | `conversaciones/templates/conversaciones/chat_ciudadano.html:645` + `conversaciones/views/public.py:171-186` (+ `portal/.../consulta_detalle.html:215`) | Polling público cada 2 s (portal 4 s) devolviendo TODOS los mensajes en cada poll; sin auth ni rate-limit | Parámetro `?since=<last_id>` + `filter(id__gt=since)[:50]` |
| A11 | `conversaciones/services/core.py:23-30` | Carga y **decodifica en Python** todas las filas de `django_session` por cada conversación creada (endpoint público) y N veces en la asignación automática | Presencia de operadores en cache (login/logout signal o heartbeat TTL) |
| A12 | `templates/includes/base.html:497` + `conversaciones_tiempo_real_global.js:76` + `conversaciones/selectors/conversaciones.py:140-161` | Poller cada 5 s en TODO el backoffice; filtro `fecha_inicio__month=` → `EXTRACT()` → full scan por poll por pestaña | Rango sargable (`__gte=date(y,m,1)`) + `cache.get_or_set` 30-60 s |

### Dashboard / Users / Programas
| # | Ubicación | Problema | Fix |
|---|-----------|----------|-----|
| A13 | `dashboard/api_views/__init__.py:65` + `templates/inicio.html:526` | Typeahead de la home: triple `LIKE '%q%'` sobre `Ciudadano` por CADA tecla, sin debounce | `istartswith`/FULLTEXT + `@input.debounce.300ms` |
| A14 | `programas/api/views.py:98` + `legajos/services/consulta_renaper.py:373,198-204` | RENAPER: cliente/token nuevos por request → 2 HTTP externos por validación de DNI; sin cache de resultados; worker bloqueado hasta ~30-60 s | Token en `django.core.cache` (TTL=expiration), cache por `(dni,sexo)` unos minutos |
| A15 | `users/views/admin.py:40-46` + `user_list.html:91-159` | Listado de usuarios sin paginación (paginación estática "1 de 1") con 4 prefetches materializando toda la tabla | `paginate_by = 25` + paginación real |

---

## SEVERIDAD MEDIA

### core / config / dashboard
- **M1** `core/context_processors.py:24-27` — COUNT de conversaciones pendientes en TODOS los requests del backoffice, sin cache. Fix: cachear 30-60 s (invalidar con la señal existente).
- **M2** `core/middleware.py:82-87` + `conversaciones/context_processors.py` + `core/context_processors.py:20` — ~4 queries fijas por request autenticado; el middleware evalúa la query de grupos ANTES de los checks baratos de path (corre hasta en `/static/`). Fix: invertir orden de condiciones, cachear grupos/flags en sesión.
- **M3** `dashboard/api_views/__init__.py:20-49` — `metricas_dashboard` duplica los contadores del dashboard SIN el cache que ya existe en `dashboard/utils.py:40-95`. Fix: reusar los `contar_*()` cacheados.
- **M4** `core/api_views/__init__.py:45,76` — N+1 en acciones `municipios`/`localidades`: serializers anidados → 1-2 queries por ítem, sin paginar. Fix: `select_related` en la relación + paginar.
- **M5** `core/views/performance.py:156,174` + `core/performance/monitoring.py:28,112-124` — `psutil.cpu_percent(interval=1)` bloquea el worker 1 s por request + counts sin cache; accesible a cualquier autenticado. Fix: `interval=None`, cache 30-60 s, restringir a admin.
- **M6** `core/views/performance.py:273-464` — `run_phase2_tests_api`: análisis de índices/particiones/optimización completo en un POST. Fix: mover a comando/tarea asíncrona, restringir a superusuario.

### legajos
- **M7** `legajos/models/base.py:269-292` — `ciudadano`/`programa`/`dispositivo` como properties con query → N+1 estructural (confirmado en `AlertaCiudadanoSerializer`, `services/alertas.py:57`, `HistorialContacto.__str__`). Fix: `annotate_legajo_link_data()` en los querysets que alimentan listados.
- **M8** `legajos/views/programas.py:155-168` + `legajos/views/nachec_dashboard.py:94-109` — cumplimiento de SLA calculado en Python materializando todas las prestaciones entregadas históricas. Fix: comparación en DB (`filter(fecha_entregada__lte=TruncDate("sla_hasta")).count()`).
- **M9** `legajos/views/programas.py:96-184` + `legajos/views/nachec_dashboard.py:42-159` — ~20 COUNTs secuenciales en el hub, ~40 en el dashboard Ñachec. Fix: `aggregate(Count(filter=Q(...)))` / `values().annotate()`.
- **M10** `legajos/views/programas.py:208-216` — `prestaciones_nachec` sin slice hacia el template (crece con las entregas autogeneradas). Fix: filtrar activas + `[:50]`/paginar.
- **M11** `legajos/views/historial_contactos.py:29-64` — `contactos_api` serializa todos los contactos del legajo sin paginar. Fix: paginar como el ViewSet DRF equivalente.
- **M12** `legajos/views/alertas.py:71-79` + `legajos/services/filtros_usuario.py:22-42` — endpoint polled del navbar materializa listas de IDs para cláusulas `IN` gigantes en cada poll. Fix: subqueries directas + cache 30-60 s por usuario.
- **M13** `legajos/services/alertas.py:27-32` vs `:98,113` — prefetch de `historial_contactos` completo que luego se ignora re-consultando. Fix: anotaciones (`Max(...)`) o usar el prefetch.
- **M14** `legajos/services/consulta_renaper.py:111-143,372-374` — mismo problema RENAPER que A14 desde legajos (2 round-trips por consulta, sesión HTTP no reutilizada).
- **M15** `legajos/selectors/contactos.py:241` — 1 query por legajo del ciudadano en el timeline (N acotado). Fix: una query `legajo__in=` + agrupar en Python.

### conversaciones / portal / configuracion
- **M16** `conversaciones/templates/conversaciones/metricas.html:143-155` — fetch a la API + `location.reload()` cada 30 s → paga API y render completo dos veces; `calcular_metricas_globales` usa `__date` no-sargable. Fix: actualizar DOM con el JSON, cache 30 s en servidor.
- **M17** `conversaciones/services/core.py:104-107` + `models/__init__.py:188-193` — `actualizar_todas_las_colas`: COUNT + save por cada cola en cada asignación. Fix: UPDATE único con subquery o tocar solo las 2 colas afectadas.
- **M18** `conversaciones/services/chat.py:165-180` — asignación automática: escaneo de sesiones + 2 saves + get_or_create + COUNT **por conversación pendiente**. Fix: resolver operadores/colas una vez fuera del loop, `bulk_update`.
- **M19** `conversaciones/services/chat.py:111,152` → `core/services/cache.py` — invalidación `KEYS`/`clear()` (A1/A2) llamada en cada asignación y cierre… sobre claves que nunca se cachean. Fix: eliminar la llamada.
- **M20** `portal/selectors/public.py:5-28` — home pública: 4 queries por visita anónima (incluye `Ciudadano.objects.count()` full scan) para datos casi estáticos. Fix: `cache.get_or_set(..., 300)`.
- **M21** `portal/selectors/ciudadano.py:18-25` + `portal/views/ciudadano_consultas.py:34` — `prefetch_related("mensajes")` + `mensajes.order_by(...)` en la vista → el order_by descarta el prefetch: doble lectura completa. Fix: `mensajes.all()` (el Meta.ordering ya ordena).
- **M22** `conversaciones/signals/alertas.py:36-58,197` + `api_views/__init__.py:18-23` — alertas fan-out (fila por operador por conversación/mensaje) que NUNCA se marcan vistas ni se purgan: counts monótonamente crecientes consultados por polling cada 10 s. Fix: `vista=True` al abrir + purga programada.
- **M23** `conversaciones/signals/alertas.py:70-93` — `pre_save` relee la fila en cada save y compara `"CERRADA"` vs estado `"cerrada"` → query extra por save que nunca hace nada (código muerto). Fix: eliminar el receiver.
- **M24** `conversaciones/views/public.py:46-96` — RENAPER síncrono en endpoint público sin cache ni rate-limit (worker bloqueado hasta 30 s). Fix: cache por (dni,sexo) + rate-limit por IP.

### programas / users
- **M25** `users/views/roles.py:44-46` — pipeline completo de roles (JOIN + COUNT DISTINCT) ejecutado 3 veces por render. Fix: computar una vez y derivar.
- **M26** `programas/models/__init__.py:363-375` + `segmento_detail.html` (13 accesos) — properties de cupo con `aggregate(Sum)` sin cache → ~13 SUMs idénticos por render. Fix: calcular una vez en contexto / `cached_property`.
- **M27** `programas/api/serializers.py:28-29` — `formularios.count()` por ítem en la API de sync de campo. Fix: `annotate(formularios_count=Count(...))`.
- **M28** `programas/views/relevamientos.py:211-221` — export CSV con COUNT por fila. Fix: anotar el conteo.
- **M29** `programas/forms.py:87,224,259,297-323` — forms de Becas materializan catálogos dos veces y se instancian en vistas que no los usan (SegmentoDetailView instancia 4 forms). Fix: `list(qs)` reusado en map + choices.
- **M30** `programas/views/relevamientos.py:90-115` — counts redundantes sobre querysets que el template itera completos + beneficiarios sin paginar. Fix: materializar y usar `len()`, paginar.

---

## SEVERIDAD BAJA

- **B1** `core/views/public.py:67-68`, `dashboard/views/home.py:41-45` — counts sin cache en la home (`last_login` sin índice). Fix: helpers cacheados.
- **B2** `core/performance/cache_utils.py:50-53` — cada login (update de `last_login`) invalida el cache del dashboard. Fix: ignorar `update_fields={"last_login"}`.
- **B3** `legajos/context_processors.py` — CP muerto que hace `cache.get`+`set` por request para devolver lista vacía. Fix: quitarlo de settings.
- **B4** `core/templatetags/custom_filters.py:41-43` — filtro `getattr` que materializa managers relacionados (N+1 latente en loops). Fix: quitar la rama M2M.
- **B5** `core/middleware.py:107-115` + `config/settings.py:367-370` — 1 log INFO por request a través de 5 file handlers síncronos en root. Fix: un handler dedicado.
- **B6** `dashboard/models/__init__.py:17-19` — `aumentar_cantidad` read-modify-write no atómico (código muerto). Fix: `F()` o eliminar.
- **B7** `config/settings.py:224-257` — QA usa LocMemCache por proceso (invalidación cross-proceso invisible) y sesiones en DB sin `clearsessions`. Fix: incluir `qa` en la rama Redis.
- **B8** `legajos/views/programas.py:53-62` — el mismo `Programa` se consulta 3 veces (`get_object()` repetido). Fix: `self.object`.
- **B9** `legajos/admin/nachec.py` — changelists sin `list_select_related` → N+1 por fila en admin.
- **B10** `programa_nachec_detail.html:815-836` — conteos por prioridad iterando la lista completa 4 veces en template (y el output es incorrecto: imprime "111"). Se resuelve con A4.
- **B11** `legajos/selectors/ciudadanos.py:73-90` — 6 COUNTs globales en cada página del listado de ciudadanos. Fix: cache 1-5 min.
- **B12** `legajos/api_views/__init__.py:93-101` — endpoint RENAPER con `AllowAny` sin throttling (además de performance, es un riesgo de abuso del upstream). Fix: auth + throttle DRF.
- **B13** `conversaciones/models/__init__.py:90-97` — doble `save()` completo en `asignar_operador` (2 UPDATEs + 2 rondas de señales). Fix: un solo `save(update_fields=...)`.
- **B14** `conversaciones/api_views/extra.py:31`, `views/backoffice.py:244` — COUNT extra por conversación en el detalle "en vivo" (por evento WS). Fix: anotar.
- **B15** `conversaciones/selectors/conversaciones.py:64-85` — duplica `get_estadisticas_tiempo_real` (con `datetime.now()` naive) y suma 3 agregados no-sargables al render de la lista. Fix: unificar + rango sargable + cache.
- **B16** `conversaciones/selectors/conversaciones.py:55` — `id__icontains` fuerza `CAST(id AS CHAR) LIKE` → full scan al buscar. Fix: `Q(id=int(term))` si es numérico.
- **B17** `configuracion/.../localidad_list.html:132-212`, `municipio_list.html:134-216` — catálogo completo repetido en un modal por fila (20 × N opciones de HTML). Fix: modal único poblado por JS.
- **B18** `conversaciones/context_processors.py:8-21` — ~2 queries fijas por request para datos estables por sesión. Fix: memoizar en sesión.
- **B19** `configuracion/views/geografia.py` y `secretaria.py` (`form_invalid`) — re-render de listados sin paginar ante error de validación. Fix: reusar queryset paginado.
- **B20** `programas/services/autorizacion.py:41-45` — `programa_becas()` repetido 4-5 veces por vista. Fix: memoizar por request.
- **B21** `programas/models/__init__.py:548-552` — nombre autogenerado con `COUNT(*)` de toda la tabla + carrera de duplicados. Fix: `Max("id")+1` o secuencia.
- **B22** `programas/views/relevamientos.py:280-304` — detalle sin `select_related` → ~4 queries lazy. Fix: queryset con `select_related`.
- **B23** `users/selectors/usuarios.py:8-11` — prefetches (`groups__meta`, `user_permissions`) que el template no consume. Fix: quitarlos.
- **B24** `users/signals/profiles.py:8-16` — doble escritura de Profile por cada `User.save()`; hoy latente (las señales no están conectadas: `users/apps.py` sin `ready()`).
- **B25** `users/forms/__init__.py:55-73` — 2 queries con JOINs por instanciación del form de usuario. Fix: cachear ids de grupos territoriales.
- **B26** `users/forms/roles.py:74-76` — `count()` + `first()` = 2 queries donde alcanza `list()`.
- **B27** `users/api_views/__init__.py:159-166` — action `users` de GroupViewSet sin `paginate_queryset`.
- **B28** `users/management/commands/verificar_usuarios.py:43-62` — N+1 doble (solo comando offline).
- **B29** `programas/models/__init__.py:870-894` — `ListaEspera` sin índice compuesto `(segmento, promovido)` (relevante solo si crece).
- **B30** `users/serializers/__init__.py:69-81` — alta por API con INSERT + UPDATE. Fix: pasar password a `create_user`.

---

## Verificados y descartados (para no re-reportar)

- `config/middlewares/` (`PerformanceMiddleware`, `QueryCountMiddleware`) NO están registrados en `MIDDLEWARE`.
- Los hilos de `core/performance/*` solo arrancan vía comando `initialize_phase2`.
- Silk queda fuera de prod (`config/settings_production.py:9`).
- Índices correctos confirmados: `Conversacion(estado, operador_asignado)`, `InscripcionPrograma.fecha_inscripcion`, `Mensaje.leido` y compuestos, índices de `CasoNachec`/`TareaNachec`/`AlertaCiudadano`/`HistorialContacto` alineados con los filtros.
- `dashboard/utils.py` cachea bien; `calcular_metricas_globales` y `MetricasOperador` usan `aggregate`; `registrar_traza` usa `bulk_create`; `services/cupo.py` usa `select_for_update` + `update_fields`.
- `core.rbac.puede` cachea capacidades por request (`_caps_activas_cache`).
- Los templates de Becas no tienen N+1 (querysets de origen con prefetch correcto).
- `portal/views/public.py:18-25` (`get_municipios`/`get_localidades`) no está ruteado (código muerto).
- Managers "optimizados" de `legajos/models/managers.py` sin asignar a ningún modelo (código muerto; si se usan, sus `Count` múltiples sin `distinct=True` multiplican filas).

## Orden de remediación sugerido

1. **Cache/Redis (A1-A3, M19)** — riesgo de caída/logout masivo en prod; fix chico y aislado.
2. **Polling (A10, A12, M16, M22)** — `?since=`, rango sargable + cache 30-60 s, marcar alertas vistas.
3. **Paginación (A9, A15, A4)** — lista de conversaciones, usuarios, hub Ñachec.
4. **Alertas legajos (A5, A6)** — sacar la generación del request path.
5. **RENAPER (A14, M24, B12)** — cache de token/resultados + rate-limit en los endpoints públicos.
6. El resto (medias/bajas) a medida que se toque cada módulo.
