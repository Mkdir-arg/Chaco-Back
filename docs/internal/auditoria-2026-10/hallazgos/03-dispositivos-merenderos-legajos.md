# 4.3 Dispositivos, Merenderos y Legajos (DIS, MER, LEG, G1c-08, G1c-17)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. PoC:
`poc/test_repro_dispositivos_legajos.py` (salvo indicación). Los hallazgos de seguridad de Legajos (A3-01..04,
A3-08, A3-13, A3-14) están en `01-seguridad.md` (SEC-02, SEC-04, SEC-10, SEC-11, SEC-12, SEC-15, SEC-18, SEC-19).

## Estado de la Versión 2 de Dispositivos y Merenderos (Cambios 69, 72 y 85) — verificado al 01-oct-2026
- **No hay código v2:** ninguna rama tipo `feat/dispositivos-v2`; desde el 08/09 ningún commit tocó `admisiones.py`,
  `registro_diario.py`, `merenderos.py` ni `dispositivos.py`.
- **Solo documentación y backlog:** épica #127 (sección «Versión 2»), análisis #385 a #396 y 45 tasks, todo OPEN en
  Backlog. Ninguna task v2 tiene casos de QA (pendiente 1 del Cambio 69): ninguna puede estar Ready.
- **Cotizada, no aprobada:** el Cambio 85 la recotizó en 827 h (5 etapas, 16 semanas, por tramos). No hay registro
  de aprobación del Ministerio.
- **La v1 está en producción y montada** (`/dispositivos/`, `/merenderos/`), pero según el Cambio 69 «no hay datos
  productivos que migrar»: hoy nadie la opera en PRD.
- **Las 14 tasks de remediación del Cambio 48 (#310-#323) se cerraron sin ejecutar** (Done en el Cambio 69). B2,
  B3 (el parte pisa el turno, `registro_diario.py:64-67`) y B4 (borrar un campo da 500, ver V6-NEW-02) siguen en el
  código y hoy solo figuran como alcance de la v2.
- La propuesta v2 (`docs/client/funcionalidades/propuesta-dispositivos-v2.md`) ya cubre en su texto DIS-02 (§4.3
  l.129), DIS-03 (l.133), DIS-04 (l.107), MER-02 (l.229) y el reemplazo del parte diario por la bitácora.

**Criterio de tratamiento (V3).** Se **parchea la v1** cuando el arreglo es S, sobrevive en la v2 (helpers de fecha,
reportes, Legajos —transversal y fuera de la v2—) o la v1 se va a operar antes de la v2. El resto es **criterio de
aceptación de la v2** (README §7), con el test nombrado para que la task lo herede.
**D-V1 (transversal):** ¿se va a operar Dispositivos/Merenderos v1 en PRD antes de que se apruebe la v2? Default:
**no**. Si es sí, DIS-02, DIS-03, DIS-04 (y DIS-05/06, MER-01 punto a) pasan a «parchear v1», empezando por DIS-03.

| ID | Título | Sev. | Estado | Tratamiento | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|---|
| DIS-01 | `__date` sobre DateTimeField en parte F-01, listado y exports (CONVERT_TZ → NULL) | ALTA (latente) | CONF. test (SQL compilado) | Parchear v1 + criterio v2 | 5 | S | ✅ |
| DIS-02 | Doble estadía ALOJADA de la misma persona en el mismo dispositivo | ALTA | CONF. test (matiz) | Criterio v2 (v1 si D-V1 = sí) | v2 | S / M | ⬜ |
| DIS-03 | Espera de traslado huérfana; traslado pendiente imposible de cancelar | ALTA | CONF. test | Criterio v2 (1er parche si D-V1 = sí) | v2 | M | ⬜ |
| LEG-03 | Solapa «Red Familiar» rota; API de vínculos abierta y sin filtro | ALTA (V5a) / MEDIA (V3) | CONF. test | Parchear v1 | 5 | S / M | ✅ |
| DIS-04 | Cerrar/inactivar con alojados; promover en dispositivo no activo | MEDIA | CONF. test | Criterio v2 | v2 | S | ⬜ |
| DIS-05 | «Alojar» con cama tomada se degrada en silencio a espera | MEDIA | CONF. test | Criterio v2 | v2 | S | ⬜ |
| DIS-06 | El egreso acepta fechas futuras | MEDIA | CONF. test | Criterio v2 | v2 | S | ⬜ |
| LEG-01 | La pasada horaria de alertas recrea y re-notifica | MEDIA | CONF. test | Parchear v1 | 4 | S-M | ⬜ |
| LEG-04 | Endpoints AJAX de legajos tragan excepciones; un blob faltante vacía la lista | MEDIA | CONF. test | Parchear v1 | 5 | S | ✅ |
| G1c-08 | Alta/edición de ciudadano: DNI sin normalizar, confirmación RENAPER alterable | MEDIA | CONF. test | Parchear v1 | 3 | M | ⬜ |
| DIS-07 | Camas RESERVADAS cuentan como libres | BAJA | CONF. test | Criterio v2 | v2 | S | ⬜ |
| DIS-08 | Fechas UTC en indicador y export de movimientos | BAJA | CONF. test | Parchear v1 + criterio v2 | 5 | S | ✅ |
| DIS-09 | El egreso cierra la membresía aunque haya espera en otro dispositivo | BAJA | CONF. test | Criterio v2 | v2 | S | ⬜ |
| DIS-10 | Edición del dispositivo: cambio de tipo con estadías | BAJA | PARCIAL | Criterio v2 | v2 | S | ⬜ |
| V6-NEW-02 | Borrar un campo de tipo con archivos da 500 (Cambio 48 B4) | BAJA | CONF. lectura | Criterio v2 | v2 | S | ⬜ |
| MER-01 | Merendero SUSPENDIDO sin vuelta y grilla no consultable | BAJA | CONF. (conforme spec v1) | Criterio v2 | v2 | S | ⬜ |
| MER-02 | Entregas de mercadería sin anulación ni idempotencia | BAJA | CONF. lectura | Criterio v2 | v2 | S | ⬜ |
| LEG-02 | Reinscribir con una inscripción no activa rompe `unique_together` | BAJA | CONF. test | Parchear v1 | 5 | S | ✅ |
| LEG-05 | Subida múltiple de adjuntos no atómica | BAJA | CONF. test | Parchear v1 | 5 | S | ✅ |
| LEG-06 | Código muerto de legajos y derivaciones sin dónde procesarse | BAJA | CONF. lectura | Parchear v1 | 7 | S | ⬜ |
| G1c-17 | Difusión de alertas críticas es código muerto; channel layer InMemory fuera de prd | BAJA | CONF. lectura | Parchear v1 | 2 | S | ⬜ |

---

## ALTA

### DIS-01 · `__date` sobre DateTimeField en el parte F-01, el listado y los exports de Dispositivos (CONVERT_TZ → NULL en ECOM)
**Severidad:** ALTA por tipo de defecto (el reporte oficial sale mal y en silencio); impacto hoy nulo porque nadie opera la v1 · **Estado:** CONFIRMADO con test (`A305SQL`: el SQL compilado con el backend mysql contiene `DATE(CONVERT_TZ(fecha_ingreso,'UTC','America/Argentina/Buenos_Aires'))`) · **Origen:** A3-05, A4-05 (= PERF-05), V3-NEW-01, V3-NEW-05 · **Tratamiento:** parchear v1 + criterio v2 (M5 bitácora, M9 reportes) · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `programas/services/registro_diario.py:35-36` (`fecha_ingreso__date=`, `fecha_egreso__date=`); `programas/services/reportes.py:36-43` (`_movimientos_en_periodo`, `__date__gte/lte`), que alimenta (a) `DispositivoListView` con `?desde/hasta`, (b) `filtrar_dispositivos` (`programas/views/reportes.py:39`) → los **tres exports** `/dispositivos/export/<padron|ocupacion|movimientos>/<csv|xlsx>/`, (c) `movimientos_dispositivos` (`reportes.py:119`).
- **Escenario:** en ECOM (MariaDB sin tablas de zona horaria) `CONVERT_TZ` devuelve NULL: el parte se guarda con `ingresos=0` y `egresos=0` (campos `editable=False`) y el listado y los exports con período salen vacíos. En SQLite el test de borde (23:30 ART) cuenta bien: **los tests nunca lo detectan**. Mismo mecanismo que rompió `/api/tendencias/` (Cambio 66) y el dashboard de Becas.
- **Propuesta:**
  1. `core/utils_fechas.py` (o `core/services/fechas.py`): `rango_dia_local(fecha) -> (inicio, fin)` = `make_aware(datetime.combine(fecha, time.min))` e `inicio + 1 día`; `rango_periodo_local(desde, hasta)` con extremos opcionales.
  2. `registro_diario.calcular_cantidades`: `fecha_ingreso__gte=inicio, fecha_ingreso__lt=fin` (ídem egreso).
  3. `reportes._movimientos_en_periodo`: `__gte=inicio_desde` y `__lt=inicio(hasta + 1 día)`.
  4. Guardia para que no vuelva: test que recorra el código productivo buscando lookups `__date`, `__year`, `__month`, `__day` y `TruncDate`/`TruncWeek` sobre DateTimeField (grep con allowlist vacía), o una regla en `scripts/design_audit.py` / ruff custom. Variantes que hoy no pegan en PRD pero cubre la guardia (V3-NEW-05): `legajos/models/base.py:325` (sin llamadores), `legajos/api_views/contactos.py:47-49` (router no montado), `core/performance/database_partitioning.py:91` (comando de mantenimiento). **`TruncMonth` sobre un DateField (`legajos/views/dashboard_simple.py:62`) es seguro**: compila a `DATE_FORMAT`, sin CONVERT_TZ.
- **Tests a agregar:** `test_parte_diario_sql_sin_convert_tz` y `test_filtro_periodo_sql_sin_convert_tz` (compilan con el wrapper mysql sin conexión, como la PoC), `test_ingreso_2330_art_cuenta_en_fecha_local`, `test_export_movimientos_con_periodo_no_vacio`. Opcional: contra el banco `scripts/perf_mysql/` con MariaDB.
- **Verificación:** V-STD. Sin migración (los partes guardados no se recalculan; no hay datos en PRD).
- **Dependencias:** DIS-08 en el mismo PR (mismo helper).
- **⚠ Ya hay dos tests esperando (05-oct-2026, PRs R-10 y R-11).** El del SQL compilado
  (`core/tests/test_sql_motor_real.py::SinConvertTZTests.test_ninguna_consulta_de_reporte_usa_convert_tz`, Cambio 125) y
  ahora el **ejecutado contra el motor real**: `core/tests/test_motor_real.py::ParteDiarioEnElMotorRealTests.test_el_parte_diario_cuenta_el_ingreso_de_hoy`
  (Cambio 130) crea un ingreso de hoy y pide el parte contra MariaDB sin tablas de zona horaria → **0 ingresos**. Los dos
  están marcados `@unittest.expectedFailure` con el ID de esta ficha: el PR de la Ola 5 que la arregle **saca los dos
  decoradores** y ahí quedan como regresión. El segundo se saltea contra `mysql:8.0`, que sí trae las tablas cargadas (como
  icore): el bug es de ECOM.

**Resolución:** ✅ Resuelto en el PR #592 (Cambio 140), 06-oct-2026 — helper único `core/utils_fechas.py`
(`rango_dia_local`, `rango_periodo_local`, `q_rango_local`, `fecha_local`, `inicio_del_dia_local`) y los dos usos de la
ficha —`registro_diario.calcular_cantidades` y `reportes._movimientos_en_periodo`, que alimenta el listado y los tres
exports— pasados al rango local `[00:00, 00:00 del día siguiente)`. Se arreglaron **también** los tres «latentes» que
nombra la ficha (`legajos/models/base.py:325`, `legajos/api_views/contactos.py`, `core/performance/database_partitioning.py`)
y **cuatro de Conversaciones** que la ficha no listaba y aparecieron al barrer el repo
(`selectors/conversaciones.py` ×2, `services/core.py` ×2, más un `timezone.now().date()` en las métricas): arreglarlos
costaba lo mismo que excepcionarlos y deja la guardia **sin allowlist**, como la pedía el punto 4. Esa guardia es un test
y no un grep: `core/tests/test_sql_portable.py` parsea con `ast` todo el código productivo de las apps del repo —incluidos
los lookups armados con un f-string, que es como estaba escrito el de los reportes—, resuelve el tipo del campo contra los
modelos y solo reporta los `DateTimeField`; `TruncMonth` sobre un `DateField` (`legajos/views/dashboard_simple.py`) no se
reporta, como pedía la ficha. Hay pragma de escape (`# sql-portable: ok`) y hoy no lo usa nadie. Antes del fix la guardia
encontraba **16** lookups vivos. Se sacaron los dos `@unittest.expectedFailure` (Cambios 125 y 130) y el
`test_hoy_los_reportes_de_dispositivos_si_compilan_convert_tz` —que afirmaba lo contrario y dejó de ser cierto— se
reemplazó por un pin invertido equivalente (`test_un_date_sobre_un_datetimefield_si_compila_convert_tz`). Verificado
contra `mariadb:10.11` con `MARIADB_INITDB_SKIP_TZINFO=1`: `--tag mysql` en verde, 16/16.
**Test permanente:** `core.tests.test_sql_portable.SqlPortableTests.test_ningun_lookup_por_dia_sobre_un_datetimefield`
(+ `core.tests.test_motor_real.ParteDiarioEnElMotorRealTests.test_el_parte_diario_cuenta_el_ingreso_de_hoy` y
`core.tests.test_sql_motor_real.SinConvertTZTests.test_ninguna_consulta_de_reporte_usa_convert_tz`, los dos ya sin
`expectedFailure`, y `programas.tests.test_fechas_locales_dispositivos.ParteDiarioFechaLocalTests.test_ingreso_2330_art_cuenta_en_fecha_local`).

### DIS-02 · Doble estadía ALOJADA de la misma persona en el mismo dispositivo
**Severidad:** ALTA · **Estado:** CONFIRMADO con matiz (`A306DobleAlojamiento`) · **Origen:** A3-06; incluye el gate faltante de `models.W036` · **Tratamiento:** criterio de aceptación v2 (M3, «unicidad residencial en la red»); puntos 1-3 en v1 solo si D-V1 = sí · **Ola:** v2 · **Esfuerzo:** S (1-3) / M (4, dentro de la v2)
- **Causa raíz:** (a) `poner_en_espera` (`admisiones.py:111-116`) solo rechaza un duplicado en LISTA_ESPERA, no a un ALOJADO; (b) `admitir_ciudadano` no consume ni rechaza una espera pendiente. El duplicado se concreta en `promover_espera` (`admisiones.py:227-250`), que hace `save()` **sin `full_clean()`**. El `UniqueConstraint(condition=Q(estado="ALOJADO"))` (`models/__init__.py:776-785`) **no se crea en MySQL ni MariaDB** (`supports_partial_indexes=False`). Matiz: `_crear_admision_alojada` sí llama `full_clean()`, que en Django 5.2 valida la restricción condicional en Python: la vía `admitir` está protegida; **la única abierta es `promover_espera`**.
- **Escenario (reproducido):** en MariaDB, 2 ALOJADO y 2 camas OCUPADAS; el F-01 la cuenta doble y el egreso libera una sola cama. En SQLite (tests y dev), `PromoverEsperaView` solo captura `ValidationError` → **500**.
- **Propuesta:** (1) en `promover_espera`, antes del `save()`, `admision.full_clean(exclude=["respuestas_f00"])` o `Admision.objects.select_for_update().filter(ciudadano, dispositivo, estado=ALOJADO).exists()` → `ValidationError`; (2) `poner_en_espera` rechaza si hay un ALOJADO del ciudadano en ese dispositivo; `admitir_ciudadano` rechaza si hay espera pendiente («tiene una espera pendiente: promovela»); (3) `PromoverEsperaView.post` captura también `IntegrityError`; (4) en la v2, campo real `clave_alojamiento = CharField(null=True, unique=True)` = `f"{ciudadano_id}"` al alojar y NULL al egresar/trasladar (UNIQUE con NULL funciona igual en SQLite, MySQL y MariaDB). **No** usar una columna generada con `RunSQL` por vendor (frágil con `DJANGO_SYNCDB_PROJECT_APPS`). Gate: como el CI corre en SQLite, el warning `models.W036` nunca aparece: test que, para cada `UniqueConstraint` con `condition`, exija el chequeo explícito en el servicio, o prohibir `condition=` nuevas por lint (los tres condicionales del repo están en `models/__init__.py:778, 783, 867`).
- **Tests a agregar:** `test_no_se_puede_poner_en_espera_a_un_alojado`, `test_promover_rechaza_si_ya_esta_alojado`, `test_admitir_con_espera_pendiente_rechaza`, `test_promover_integrityerror_no_da_500`; v2: `test_clave_alojamiento_unica_en_la_red`.
- **⚠ La ilusión ya está caracterizada en el CI (05-oct-2026, PR R-11, Cambio 130).**
  `core/tests/test_motor_real.py::ConstraintCondicionalTests.test_una_uniqueconstraint_con_condicion_no_existe_en_el_motor`
  mete dos admisiones ALOJADO en la **misma cama** contra el motor real y las dos entran: lo que en SQLite parece una
  restricción de base, en MySQL y MariaDB no existe. No reemplaza el gate que pide esta ficha (el chequeo explícito en
  `promover_espera`, o el lint sobre `condition=` nuevas): lo que hace es que el agujero deje de ser invisible mientras la
  v2 llega. El PR de la v2 que lo cierre va a cambiar este test por el de la unicidad real (`clave_alojamiento`).

### DIS-03 · Espera de traslado huérfana y un traslado pendiente que no se puede cancelar
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`A307EsperaHuerfana`); se refuta un sub-punto · **Origen:** A3-07 · **Tratamiento:** criterio v2 (M3, task #410: «tránsito con recepción, rechazo, vencimiento»); si D-V1 = sí, es el **primer** parche · **Ola:** v2 · **Esfuerzo:** M
- **Causa raíz:** no existe operación para cancelar una espera (el único `promovida=True` está en `admisiones.py:246`); la rama con cama de `trasladar_admision` (`:213-224`) no mira esperas pendientes con `origen_traslado=admision`; `egresar_admision` (`:144-145`) bloquea el egreso mientras exista ese traslado pendiente.
- **Escenario (reproducido):** (1) traslado sin cama a D2 y después con cama a D3: la espera de D2 queda para siempre, al promoverla da «La estadía de origen ya no está alojada» y no se puede volver a encolar; (2) **cualquier traslado sin cama cuyo destino nunca libera cama deja a la persona sin poder egresar del origen**, sin salida por UI. Sub-punto refutado: «`_cerrar_origen_por_traslado` con `origen.cama_id is None`» es inalcanzable (toda estadía ALOJADA nace con cama).
- **Propuesta:** (1) `cancelar_espera(*, espera, usuario, motivo)` en `admisiones.py`: `select_for_update` sobre la espera, exige `promovida=False` y `estado=LISTA_ESPERA`, pasa `admision.estado=RECHAZADO` (ya existe, sin migración), `motivo_egreso=motivo`, `responsable_egreso=usuario`, `fecha_egreso=now`, `espera.promovida=True`; vista POST `dispositivos:espera_cancelar` con `dispositivo.admitir` y confirmación SweetAlert2; botón en `admisiones/espera.html` y en el detalle del origen. (2) En la rama con cama de `trasladar_admision`, cancelar en la misma transacción las esperas pendientes con `origen_traslado=admision` («Reemplazada por traslado a X»).
- **Tests a agregar:** `test_traslado_con_cama_cancela_espera_pendiente`, `test_cancelar_espera_libera_egreso_del_origen`, `test_cancelar_espera_ya_promovida_falla`.
- **Relación:** caso límite de B2 del Cambio 48.

### LEG-03 · La solapa «Red Familiar» del legajo está rota y la API de vínculos, si se monta tal cual, expone todo
**Severidad:** ALTA según V5a (FE-03 + V5A-NEW-02) / MEDIA según V3: se adopta ALTA mientras la decisión A/B esté abierta, porque la opción A aplicada como la proponía A6 expone los vínculos de todos los ciudadanos · **Estado:** CONFIRMADO con test (`A316Vinculos`) y en navegador (404 en cada carga del legajo) · **Origen:** A3-16, A3-25 (parte `api_contactos`), A6-03 (= FE-03), V5A-NEW-02 · **Tratamiento:** parchear v1 · **Ola:** 5 · **Esfuerzo:** S (retirar) / M (arreglar) · **Decisión:** D-L03

**Ampliado por RS-R3-11 (04-oct-2026):** el `fetch` roto de `ciudadano_detail.html` a `/api/legajos/contactos/vinculos-familiares/` queda en la allowlist inicial del test `core/tests/test_urls_del_front.py::UrlsDelFrontTests.test_todo_fetch_literal_resuelve` (RED-42, Ola R); cerrar esta ficha (B o A) saca la entrada de la allowlist.

**Reconciliado el 07-oct-2026 (Cambio 160, PR R-18):** el test ya existe y la allowlist **nació sin esta entrada**, porque el Cambio 150 retiró la solapa antes. Nada pendiente por este lado.

- **Ubicación:** `legajos/urls/api_contactos.py` no está incluido en ninguna URL (registrado en el Cambio 66 como decisión aparte); fetch de `ciudadano_detail.html:1265`, `:1443`, `:1482` → 404 (`/api/legajos/contactos/vinculos-familiares/?ciudadano_principal=1`); `legajos/api_views/contactos.py:77-82` (`VinculoFamiliarViewSet.get_queryset` lee `?ciudadano=`, el JS manda `ciudadano_principal`, que no está en `filterset_fields`: la consulta vuelve **sin filtro**; solo `IsAuthenticated`; `buscar_ciudadanos` lista por nombre o DNI); la solapa es estática y siempre visible (`programas/services/solapas.py:25`). El buscador del modal (`:1224`, `?search=`) ignora el texto (SEC-02 / V1-NEW-03).
- **Lo que NO hay que hacer:** `path("contactos/", include("legajos.urls.api_contactos"))` en `api.py` (propuesta de A6): `api_contactos.py:14` ya declara `path("contactos/", include(router.urls))` → `/api/legajos/contactos/contactos/…`; y montarlo sin corregir el filtro lista los vínculos de todos.
- **Propuesta (default D-L03 = B, retirar):** sacar la entrada de `solapas.py`, los bloques `tab-red_familiar` y `modalVinculo`, el contador `total-vinculos`, `cargarVinculos()` y `renderizarGrafoRed` de `ciudadano_detail.html`, y borrar `api_contactos.py`. **Opción A (si se usa):** montar con `path("", include("legajos.urls.api_contactos"))`; `permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]` (escritura con `ciudadano.editar`); filtrar por `ciudadano_principal` (o cambiar el JS a `?ciudadano=`); `SearchFilter` en el buscador; en el JS (`:1265`) `if (!r.ok) throw …` y `window.toast('error', …)`.
- **Tests a agregar:** B: `test_solapa_red_familiar_no_se_ofrece`; A: `test_api_vinculos_filtra_por_ciudadano` (con dos ciudadanos con vínculos, uno no trae los del otro), `test_api_vinculos_sin_capacidad_403`, `test_busqueda_ciudadanos_api_filtra_por_texto`.
- **Verificación:** V-STD + V-UI; Playwright sin 404 en `/legajos/ciudadanos/<id>/`.
- **Dependencias:** SEC-01/SEC-02 (helpers DRF) para la opción A; FE-02 (mismo template).

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — **se aplicó el default D-L03 = B (retirar)**.
Se fueron la entrada `red_familiar` de `SOLAPAS_ESTATICAS`, el bloque `tab-red_familiar`, el modal `modalVinculo`, el
buscador de ciudadanos, el contador `total-vinculos`, `cargarVinculos()`, `renderizarGrafoRed()` y el `<script>` de
`vis-network` (673 KB que la página ya no descarga). Se borraron `legajos/urls/api_contactos.py` **y**
`VinculoFamiliarViewSet`: dejar escrito el ViewSet que lista los vínculos de todos es dejar la trampa armada, y la
receta de la opción A quedó en un comentario de `legajos/api_views/contactos.py` por si el cliente la repone. **El
modelo `VinculoFamiliar` se conserva**: alimenta la línea de tiempo y la actividad reciente, así que no se pierde
ningún dato. **Desvío de la ficha, code-first:** la allowlist de RED-42 (`core/tests/test_urls_del_front.py`) **no
existe todavía** —RED-42 es del PR R-18, abierto—, así que no hubo entrada que sacar; nacerá sin ella.
**Test permanente:** `legajos.tests.test_ciudadano_detail_ola5.RedFamiliarRetiradaTests.test_solapa_red_familiar_no_se_ofrece`
(+ `test_el_detalle_no_consulta_la_api_de_vinculos` y `test_el_router_de_vinculos_ya_no_existe`).

## MEDIA

### DIS-04 · Cerrar o inactivar con alojados y esperas; promover dentro de un dispositivo no activo
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`A309CierreConAlojados`) · **Origen:** A3-09 · **Tratamiento:** criterio v2 (M1: cerrar con gente alojada obliga a egresar o trasladar; asistente de egreso masivo, task #411) · **Ola:** v2 · **Esfuerzo:** S · **Decisión:** D-D04
- **Causa raíz:** `inactivar_dispositivo` y `cerrar_dispositivo` (`services/dispositivos.py:259-280`) solo validan el estado de origen; `promover_espera` no valida `Dispositivo.estado`.
- **Propuesta:** contar `Admision` ALOJADO y `EsperaAdmision` pendientes antes de `_transicionar` → `ValidationError` con los conteos; en `promover_espera`, `Dispositivo.objects.select_for_update().get(pk=admision.dispositivo_id)` y exigir ACTIVO, en el mismo orden de locks que `admitir` (dispositivo → cama). Default D-D04: «inactivo» permite egresos y traslados salientes, no promociones ni ingresos.
- **Tests:** `test_no_se_cierra_con_alojados`, `test_no_se_inactiva_con_esperas`, `test_promover_en_inactivo_falla`.

### DIS-05 · «Alojar» con una cama ya tomada se degrada en silencio a lista de espera
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`A310CamaTomada`: POST `alojar` con cama ocupada → 302 y la persona en LISTA_ESPERA) · **Origen:** A3-10 · **Tratamiento:** criterio v2 (asistente de ingreso M3) · **Ola:** v2 · **Esfuerzo:** S
- **Ubicación:** `views/admisiones.py:100-112` (cama no DISPONIBLE → `cama=None` y `accion="espera"`).
- **Propuesta:** degradar solo si `not cama_id`; si vino `cama_id` y no está disponible, `f00_form.add_error(None, "La cama seleccionada ya no está disponible.")` y re-renderizar con las camas actualizadas.
- **Test:** `test_alojar_con_cama_ocupada_muestra_error_y_no_encola`.

### DIS-06 · El egreso acepta fechas futuras
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`A311EgresoFuturo`: egreso a +3 días, `ocupacion_nocturna=2` con `camas_totales=1`) · **Origen:** A3-11 · **Tratamiento:** criterio v2 (egreso M3, #411) · **Ola:** v2 · **Esfuerzo:** S
- **Ubicación:** `EgresoAdmisionForm` (`forms.py:862-869`, sin `clean_fecha_egreso`); `egresar_admision:142` (solo valida contra el ingreso; la cama se libera en el acto).
- **Propuesta:** rechazar `fecha_egreso > timezone.now() + timedelta(minutes=5)` en el form y en el servicio (fuente de verdad); misma regla en `_cerrar_origen_por_traslado`.
- **Test:** `test_egreso_con_fecha_futura_rechazado` (servicio y vista).

### LEG-01 · La pasada horaria de alertas desactiva y recrea las MEDIA/BAJA y vuelve a notificar
**Severidad:** MEDIA (BAJA si ECOM no tiene el CronJob) · **Estado:** CONFIRMADO con test (`A312Alertas`: 2 corridas → 2 alertas SIN_PLAN y 2 notificaciones; la vieja queda con `fecha_cierre=None`) · **Origen:** A3-12, A8-S5, V4-NEW-05 · **Tratamiento:** parchear v1 (Legajos no es parte de la v2) · **Ola:** 4 (con PERF-20) · **Esfuerzo:** S-M · **Decisión:** pregunta H-02 (¿CronJob en ECOM?)
- **Ubicación:** `legajos/services/alertas.py:36-40` (`update(activa=False)` masivo sin `fecha_cierre` ni `cerrada_por`), `:142-162` (`_crear_alerta` crea otra fila y hace push por WebSocket). Cron horario: `docker/k8s/cronjobs.yaml` (`0 * * * *`); en icore, crontab del host sin snippet versionado (G3-05).
- **Escenario:** cada hora se recrean las MEDIA/BAJA, se re-notifica a todos los conectados (G1c-04) y `legajos_alertaciudadano` crece sin techo (200 → 510 → 610 en dos corridas del seed de V4).
- **Propuesta:** reconciliar en lugar de recrear: en `generar_alertas_ciudadano`, calcular el set vigente `{(legajo_id, tipo)}` con `_generar_alertas_legajo` en modo «dry» (devuelve tuplas sin crear), crear solo las que faltan y cerrar con `fecha_cierre=now`, `cerrada_por=None` las activas MEDIA/BAJA cuyo `(legajo, tipo)` ya no está; notificar solo las creadas. No incluir `MENSAJE_CIUDADANO` en el cierre automático (es de conversaciones, que hoy se cierra cada hora). Con esto desaparece el `UPDATE` global de PERF-20.
- **Tests a agregar:** `test_generar_alertas_dos_veces_no_duplica_ni_notifica`, `test_alerta_que_deja_de_aplicar_se_cierra_con_fecha`.
- **Verificación:** V-STD + `manage.py test legajos`. P-16 (README §3) mide si el cron corre en PRD.
- **Dependencias:** PERF-20 en el mismo PR.

### LEG-04 · Los endpoints AJAX de legajos tragan excepciones y un blob faltante vacía la lista
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`A317A318Adjuntos.test_blob_faltante_vacia_la_lista`: 200, `count=0` y la **ruta absoluta del servidor** en el JSON) · **Origen:** A3-17 · **Tratamiento:** parchear v1 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `legajos/views/contactos_api.py` (`except Exception → JsonResponse(... str(exc))` con 200 y sin log); `legajos/selectors/contactos.py:39` (`_serialize_adjunto` lee `archivo.archivo.size`). Sin `select_related("content_type")`: N+1, y en tests (zeal) cualquier ciudadano con 2+ adjuntos devuelve la lista vacía.
- **Propuesta:** capturar solo `ContactosFilesError` y `Http404`; `logger.exception` + 500 genérico para el resto (coordinar con SEC-10, que toca las mismas vistas); en `_serialize_adjunto`, `try/except OSError` → `tamano=None, faltante=True`; `select_related("content_type")` en los querysets de adjuntos.
- **Tests:** `test_archivos_ciudadano_con_blob_faltante_lista_el_resto`, `test_error_inesperado_no_expone_detalle`, `test_archivos_ciudadano_sin_n_mas_1`.

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — `_serialize_adjunto` lee el peso con
`try/except OSError` y devuelve `tamano: None, faltante: True`: el adjunto con el blob perdido se **sigue listando**,
marcado «Archivo no disponible», en vez de llevarse puesta la lista entera. El queryset de adjuntos suma
`select_related("content_type")`, así que el costo ya no crece con la cantidad de archivos. **Desvío de la ficha,
code-first:** la primera mitad —`except Exception → JsonResponse(str(exc))` con 200 y sin log— **ya estaba resuelta**
por R-19 (#556, Cambio 126), que dejó `logger.exception` + 500 genérico en las siete vistas de `contactos_api.py`;
acá se agregó el test permanente que lo fija.
**Test permanente:** `legajos.tests.test_adjuntos_robustez.AdjuntoBlobFaltanteTests.test_archivos_ciudadano_con_blob_faltante_lista_el_resto`
(+ `test_error_inesperado_no_expone_detalle` y `test_archivos_ciudadano_sin_n_mas_1`).

### G1c-08 · Alta y edición de ciudadano: DNI sin normalizar, confirmación RENAPER alterable, sin procedencia
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`poc/test_repro_admin_cron_renaper.py::G1c08AltaRenaperTests`, 4 escenarios) · **Origen:** G1c-08 (verificado en G3) · **Tratamiento:** parchear v1 (Legajos) · **Ola:** 3 · **Esfuerzo:** M · **Decisión:** D-C08 (alta manual tras «fallecido»)
- **Ubicación:** `legajos/forms/ciudadanos.py:67-92` (`dni` con `readonly` solo de widget), `:149-161` (Manual/Confirmar sin `clean_dni`), `:167-185` (Update con `dni` y `estado_renaper` editables); `legajos/views/ciudadanos.py:93-119` (`exists()` contra el DNI normalizado), `:183-194` (`form_valid` no compara con la sesión ni setea `estado_renaper`); `ciudadano_renaper_form.html:35` («Cargar manualmente» también tras «fallecido»); `Ciudadano.dni` sin validadores (`base.py:23`).
- **Escenario (reproducido):** `12.345.678` por la carga manual crea un **segundo** ciudadano junto a `12345678` (Becas, que usa `normalizar_dni`, nunca lo encuentra); el alta con RENAPER de `87654321` no frena aunque exista `87.654.321`; la confirmación acepta un POST con `dni=99999999, nombre=Inventado` y deja `estado_renaper=''`; la edición cambia el DNI de un titular con caso APROBADO (los reintentos a SIIS usan `ciudadano.dni`) y pone `estado_renaper=REGISTRADO` a mano.
- **Propuesta:** (1) validador común `normalizar_dni` + 7-8 dígitos en `CiudadanoForm.clean_dni` (y en `Ciudadano.save` como red), más un comando/migración de datos que **liste** (sin merge automático) los DNI con no-dígitos y sus colisiones (P-17); (2) `CiudadanoConfirmarForm`: `dni`, `nombre`, `apellido` y `fecha_nacimiento` con `disabled=True` (Django usa el `initial` de la sesión) y `estado_renaper=REGISTRADO` en `form_valid`; (3) `CiudadanoUpdateForm`: `dni` `disabled` salvo `config.administrar` (o `ciudadano.eliminar` mientras exista) y `estado_renaper` fuera del form; (4) D-C08 (default: la vista guarda `estado_renaper=FALLECIDO` si el link manual viene de un resultado «fallecido», con `?fallecido=1`).
- **Tests:** los 4 escenarios de la PoC invertidos.
- **Verificación:** V-STD + V-UI.
- **Dependencias:** SIIS-08 (identidad validada que no corrige el legajo), G1-01, DAT-03 (`dni_titular` desincronizado al cambiar el DNI).

## BAJA

### DIS-07 · Las camas RESERVADAS cuentan como libres
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (2 RESERVADAS de 3 → `libres=3`) · **Origen:** A3-19 · **Tratamiento:** criterio v2 (M2 plazas, estado Prestada y disponibilidad neta) · **Ola:** v2 · **Esfuerzo:** S
- **Ubicación:** `camas.py:13-26` (`libres = operativas - ocupadas`); `registro_diario.py:38`.
- **Propuesta:** contar por estado (`Count` con filtro DISPONIBLE, RESERVADA, OCUPADA, FUERA_SERVICIO) y `libres = DISPONIBLE`.
- **Test:** `test_resumen_no_cuenta_reservadas_como_libres`.

### DIS-08 · Fechas UTC en Python: indicador «última actualización» y fecha del export de movimientos
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (parte de las 22:30 ART al día siguiente da `dias=0`) · **Origen:** A3-20, V3-NEW-02, A1-23 (parte `indicadores.py:201`) · **Tratamiento:** parchear v1 (mismo PR que DIS-01) + criterio v2 (M8, M9) · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `indicadores.py:56`, `:201`; `reportes.py:124-125`, `:141-142` (filtro del período), `:130`, `:146` (`strftime("%d/%m/%Y")` en UTC).
- **Propuesta:** `timezone.localtime(x).date()` y `localtime(x).strftime(...)`; en el indicador, mejor `ultimo_registro.fecha` (la fecha del parte).
- **Tests:** `test_actualizacion_parte_nocturno_cuenta_en_fecha_local`, `test_movimiento_2230_art_se_exporta_con_fecha_local`.

**Resolución:** ✅ Resuelto en el PR #592 (Cambio 140), 06-oct-2026, en el mismo PR que DIS-01 — `movimientos_dispositivos`
filtra el período con la fecha **local** del movimiento (`core.utils_fechas.fecha_local`) y la columna «Fecha» sale con
`timezone.localtime(...).strftime(...)`: el movimiento de las 22:30 ART ya no queda fuera del período pedido ni se exporta
con el día siguiente. El indicador de «última actualización» mide contra la fecha local de `modificado`.
**Dos desvíos de la ficha, los dos code-first:** (a) `indicadores.py:201` no existe —el archivo tiene 93 líneas—; el único
uso es `:56` y es el que se corrigió; (b) **no** se cambió `modificado` por `ultimo_registro.fecha`: miden cosas distintas
(cuándo se tocó el parte vs. de qué día es el parte) y el semáforo de actualización mide la primera, así que alcanzaba con
leerlo en hora local.
**Test permanente:** `programas.tests.test_fechas_locales_dispositivos.ExportMovimientosFechaLocalTests.test_movimiento_2230_art_se_exporta_con_fecha_local`
(+ `IndicadorActualizacionFechaLocalTests.test_actualizacion_parte_nocturno_cuenta_en_fecha_local`).

### DIS-09 · El egreso cierra la membresía aunque haya una espera en otro dispositivo
**Severidad:** BAJA · **Estado:** CONFIRMADO con test · **Origen:** A3-21 · **Tratamiento:** criterio v2 (M3 y trayectoria en la solapa del legajo, §4.10) · **Ola:** v2 · **Esfuerzo:** S
- **Ubicación:** `admisiones.py:160-167` (solo mira ALOJADO).
- **Propuesta:** cerrar la membresía solo si no hay ALOJADO **ni** LISTA_ESPERA con esa membresía.
- **Test:** `test_egreso_no_cierra_membresia_con_espera_pendiente`.

### DIS-10 · Edición del dispositivo: cambio de tipo con estadías (y `IntegrityError` teórico del código)
**Severidad:** BAJA · **Estado:** PARCIAL (la carrera del código es teórica porque `clean_codigo`, `forms.py:670-677`, valida antes; el cambio de tipo con estadías es real) · **Origen:** A3-24 · **Tratamiento:** criterio v2 (M4: ficha por tipo al constructor, se retira `CampoTipoDispositivo`) · **Ola:** v2 · **Esfuerzo:** S
- **Propuesta:** en `DispositivoForm.__init__`, si `instance.pk` y hay admisiones o camas, `fields["tipo"].disabled = True` con help_text; `try/except IntegrityError` en el `save` del Update.
- **Test:** `test_editar_tipo_con_admisiones_deshabilitado`.

### V6-NEW-02 · Dispositivos: borrar un campo de tipo con archivos da 500
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura); ya registrado como hallazgo B4 del Cambio 48, abierto · **Origen:** V6-NEW-02 · **Tratamiento:** criterio v2 (se retira `CampoTipoDispositivo`); parche S si D-V1 = sí · **Ola:** v2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/dispositivos_config.py:214-220` (`CampoTipoDispositivoDeleteView` hace `campo.delete()` sin capturar el `ProtectedError` de `models:877`).
- **Propuesta:** la misma receta que DAT-01 (PROTECT + captura con mensaje + baja lógica, que es lo que decidió el Cambio 48). El mismo producto tiene el patrón opuesto: Becas borra en silencio (DAT-01) y Dispositivos revienta.

### MER-01 · Merendero SUSPENDIDO: no vuelve a ACTIVO y su grilla no se puede consultar
**Severidad:** BAJA · **Estado:** CONFIRMADO, conforme a la spec v1 (#128 RF-09: «Activo→Suspendido/Cerrado» sin vuelta) · **Origen:** A3-22 · **Tratamiento:** criterio v2 (M11); el punto (a) en v1 si hoy se opera Merenderos · **Ola:** v2 · **Esfuerzo:** S · **Decisión:** D-M01
- **Ubicación:** `merenderos.py:112-116`; `views/merenderos.py:264-266` (el GET de `PrestacionMensualView` da 403 para cualquier estado ≠ ACTIVO).
- **Propuesta:** (a) GET en solo lectura para SUSPENDIDO y CERRADO (`solo_lectura=True`, sin «Guardar»; el POST ya bloquea); (b) si D-M01 = reversible (default sí, igual que la «suspendida con vuelta a activa» de la v2 §4.1), transición `SUSPENDIDO → ACTIVO` en `cambiar_estado_merendero` con traza.
- **Tests:** `test_grilla_de_suspendido_es_de_solo_lectura`, `test_reactivar_merendero_suspendido`.

### MER-02 · Entregas de mercadería sin anulación ni idempotencia
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura: nadie escribe `EntregaMercaderia.anulada=True`; `registrar_entrega` siempre hace `create`) · **Origen:** A3-23 · **Tratamiento:** criterio v2 (§4.11: «anulación con motivo»; migración para `motivo_anulacion`, `anulada_por`, `anulada_en`) · **Ola:** v2 · **Esfuerzo:** S
- **Propuesta:** `anular_entrega(entrega, usuario, motivo)` + vista POST con confirmación; deshabilitar el submit al enviar. **No** agregar deduplicación «entrega idéntica en menos de 1 minuto» (rechazaría entregas legítimas del mismo día).
- **Test:** `test_anular_entrega_la_excluye_del_padron`.

### LEG-02 · Reinscribir en un programa con una inscripción previa no activa rompe `unique_together`
**Severidad:** BAJA (baja desde MEDIA: la inscripción directa exige `is_staff` y la aceptación de derivaciones no tiene UI) · **Estado:** CONFIRMADO con test (`A315Reinscripcion`: `IntegrityError`, 500 en la vista) · **Origen:** A3-15, A1-18 (= BEC-13) · **Tratamiento:** parchear v1 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `InscripcionPrograma.unique_together = [ciudadano, programa]` (`models/__init__.py:272`); `DerivarProgramaForm.save` (`legajos/forms/derivacion.py:115-123`, hace `create`; `clean` solo excluye PENDIENTE/ACTIVO/EN_SEGUIMIENTO); `DerivacionPrograma.aceptar` (`:395-419`); `SolapasService.crear_inscripcion_directa` (`programas/services/solapas.py:160-175`, llamada desde `legajos/views/solapas.py`, que no tiene ruta: LEG-06).
- **Propuesta:** `activar_inscripcion(ciudadano, programa, *, via, usuario, notas)` en `programas/services/inscripciones.py` (nuevo): `select_for_update().get_or_create`; si existe en CERRADO, DADO_DE_BAJA o SUSPENDIDO → ACTIVO con `fecha_inicio=localdate`, `fecha_cierre=None`, nueva `via_ingreso` y notas; PENDIENTE → ACTIVO. Usarlo en el form, en `aceptar()` y como base de `_membresia_activa` de Dispositivos. Sacar el `except Exception` de `derivacion_programa.py:27-28`.
- **Tests:** `test_aceptar_derivacion_con_inscripcion_cerrada_la_reactiva`, `test_inscripcion_directa_con_baja_reactiva`.
- **Dependencias:** SEC-12 (permisos).

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — `programas/services/inscripciones.py` con
`activar_inscripcion(ciudadano, programa, *, via, usuario, notas)`: toma la fila bajo
`select_for_update().get_or_create`, tolera la carrera (quien pierde recibe el `IntegrityError` del índice único y
relee ya con el candado) y revive la inscripción CERRADA, SUSPENDIDA, DADA DE BAJA o PENDIENTE con
`fecha_inicio=localdate()`, `fecha_cierre=None`, la vía nueva y las notas. Lo que ya está ACTIVO o EN_SEGUIMIENTO se
devuelve intacto. Pasan por ahí las tres vías de alta (`DerivarProgramaForm.save`, `DerivacionPrograma.aceptar`,
`SolapasService.crear_inscripcion_directa`) **y** `_membresia_activa` de Dispositivos, que tenía la misma lógica
duplicada. Fuera el `except Exception` de `legajos/views/derivacion_programa.py`, que mostraba el `IntegrityError`
como si fuera una validación de negocio.
**Ronda 2 (revisión):** la rama de rescate pedía su `select_for_update` **en autocommit** —`transaction.atomic()`
nuevo— porque el `atomic` de la rama feliz ya se había cerrado; contra `mariadb:10.11` eso es
`TransactionManagementError` (500) para cualquier llamador que no venga envuelto en su propio `atomic`. Los dos
llamadores de hoy sí lo están, así que no había un 500 vivo: lo que se arregló es el contrato de la función.
Se sumaron las dos capas de RED-67: `candados_tomados` (presencia del candado, en SQLite es un no-op) y la
carrera de dos hilos contra el motor real.
**Test permanente:** `programas.tests.test_inscripciones_reactivacion.ReactivarInscripcionTests.test_aceptar_derivacion_con_inscripcion_cerrada_la_reactiva`
(+ `test_inscripcion_directa_con_baja_reactiva`, `test_crear_inscripcion_directa_de_solapas_reactiva_la_suspendida`,
`TomarInscripcionFueraDeAtomicTests.test_la_rama_de_rescate_pide_el_candado_dentro_de_una_transaccion`,
`ContratoDeCandadoTests` y, con `@tag("mysql")`, `TomarInscripcionMotorRealTests` y `CarreraDeReactivacionTests`).

### LEG-05 · Subida múltiple de adjuntos no atómica
**Severidad:** BAJA (baja desde MEDIA: el daño es un adjunto duplicado y un mensaje engañoso) · **Estado:** CONFIRMADO con test (`dni.pdf` + `foto.heic` → excepción y 1 Adjunto persistido) · **Origen:** A3-18 · **Tratamiento:** parchear v1 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `legajos/services/contactos.py:23-44`.
- **Propuesta:** primer loop solo de `_validate_archivo`; segundo loop de creación dentro de `transaction.atomic()`; en el `except`, borrar del storage los archivos ya escritos y re-lanzar.
- **Test:** `test_subida_con_un_archivo_invalido_no_guarda_ninguno`.

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — `subir_archivos_para_objeto` valida la tanda
**completa** antes de tocar la base y crea dentro de `transaction.atomic()`; si algo revienta, además borra del
storage los blobs ya escritos (el storage no participa de la transacción) y re-lanza. Con `dni.pdf` + `foto.heic` ya
no queda un adjunto a medias con el mensaje «Formato no permitido».
**Ronda 2 (revisión):** `FileField.pre_save` escribe el blob **adentro** del `save()`, antes del INSERT; si el
INSERT falla, el archivo queda en `media/` sin fila y el registro para la limpieza —que corría recién con el
objeto ya creado— se lo perdía. El nombre se anota en un `finally` alrededor del `save()`.
**Test permanente:** `legajos.tests.test_adjuntos_robustez.SubidaMultipleAtomicaTests.test_subida_con_un_archivo_invalido_no_guarda_ninguno`
(+ `test_fallo_del_insert_no_deja_la_fila_ni_el_blob_que_ya_se_escribio`).

### LEG-06 · Código muerto de legajos y derivaciones que no tienen dónde procesarse
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A3-25, A5-44, A6-16 (parte templates) · **Tratamiento:** parchear v1 (limpieza); las derivaciones son criterio v2 (M6, #390) · **Ola:** 7 · **Esfuerzo:** S · **Decisión:** D-L06

**Ampliado por RS-R3-11 (04-oct-2026):** además del código muerto, `historial_contactos.html:334` y `:445` hacen dos `fetch` a URLs que no resuelven (`/legajos/<id>/contactos/api/`, `/legajos/contactos/<id>/detalle/`): las vistas existen (`historial_contactos.py:13,21`) pero sin ruta. Quedan en la allowlist de RED-42 hasta que esta ficha borre el template.

**Puesto en el ratchet el 07-oct-2026 (Cambio 160, PR R-18):** las dos entradas ya están en la `ALLOWLIST` de `core/tests/test_urls_del_front.py`, nombrando a LEG-06. Al borrar el template hay que **sacarlas en el mismo diff**: `test_la_allowlist_no_tiene_entradas_de_mas` falla con una entrada que ya no aparece en el front.

- **Ubicación:** sin ruta: `legajos/views/solapas.py` (incluye otro `aceptar_derivacion_programa` en `:148`), `legajos/views/historial_contactos.py` (+ `historial_contactos.html` y `historial_contactos_view`), `legajos/views/dashboard_contactos.py`, `dar_de_baja_inscripcion`; templates muertos `dashboard/templates/dashboard.html`, `templates/components/widget_contactos.html`, `legajos/templates/legajos/dashboard_simple.html`; la bandeja de `ProgramaDetailView` es «DEPRECATED» fija en ceros; el botón «Derivar a Programa» (`ciudadano_detail.html:191`) crea `DerivacionPrograma` PENDIENTE que nadie puede aceptar desde la UI.
- **Propuesta:** borrar vistas, servicios y templates sin ruta (las rutas de debug/test se borran en SEC-19; `api_contactos.py` en LEG-03). D-L06 (default): ocultar «Derivar a Programa» hasta que la v2 defina las derivaciones (§4.6); la inscripción directa sigue para quien tenga capacidad.
- **Tests:** `test_rutas_muertas_no_resuelven` (si se borran rutas). Verificación: V-STD + V-UI + `grep` de los nombres borrados vacío.

### G1c-17 · La difusión de alertas críticas es código muerto; el channel layer es InMemory fuera de prd
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1c-17 · **Tratamiento:** parchear v1 · **Ola:** 2 (mismo PR que G1c-04) · **Esfuerzo:** S
- **Ubicación:** `legajos/services/alertas.py:185-189` (manda a `alertas_criticas` / `nueva_alerta_critica`, que nadie escucha); `conversaciones/consumers.py:236-240` (el consumer tiene `alerta_critica` y `alerta_cerrada`, que nadie emite); el modal crítico de `alertas_websocket.js:57` **nunca se dispara**; `config/settings.py:387-392` (`InMemoryChannelLayer` fuera de `prd`: lo que emite un CronJob en otro pod no llega a nadie).
- **Propuesta:** alinear nombres de grupo y tipo de mensaje entre emisor y consumer (o borrar la rama crítica si no se quiere); documentar que en QA el WS no recibe lo emitido por el cron (ver OPS-12).
