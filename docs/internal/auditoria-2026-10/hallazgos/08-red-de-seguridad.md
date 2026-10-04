# 4.8 Red de seguridad (RED)

Frente agregado el 03/04-oct-2026 a pedido del PM: *«No quiero cambiar una línea y romper cinco cosas.»* Mide qué
tan bien la suite, el CI y el proceso de deploy **detectan** una regresión antes de que llegue a producción, y propone
las tareas que cierran los huecos. No se desarrolló nada: todo lo de este archivo son **tareas** (Ola R, README §6).

**Base:** `origin/development @ ee0aafe` (las líneas citadas son de ese commit; si se movieron, buscar por nombre).
**Método:** seis análisis independientes (RS-R1 flujos críticos y cobertura, RS-R2 regresión de bugs pasados, RS-R3
contratos/tipado/validaciones, RS-R4 duplicación y dependencias ocultas, RS-R5 migraciones y rollback, RS-R6 gates de
CI/CD y procesos), dos verificaciones adversariales que **prevalecen** sobre los informes (VR1 sobre R1-R3, VR2 sobre
R4-R6; reprodujeron con tests, con SQL compilado contra el backend de MySQL y con un MariaDB 11.8 descartable) y una
prueba de mutación (RS-R7: 49 mutaciones reales sobre 14 puntos críticos). Convenciones, `V-STD` y `V-UI`: README §0.
Severidad y propuesta son las **finales** de VR1/VR2; lo refutado está en README §8.3 y no tiene ficha; los
duplicados de fichas existentes se agregaron a esas fichas con la línea «Ampliado por RS-…» (trazabilidad en README
§9.4).

**Conteo:** 1 CRÍTICA · 28 ALTA · 41 MEDIA · 18 BAJA = **88 fichas**, todas ⬜. Además amplían fichas existentes:
TST-01, TST-02, TST-03, OPS-01, OPS-03, OPS-04, OPS-07, OPS-14 y R0-03 (`05-…`), V5A-NEW-01 y FE-13 (`07-…`), LEG-03
y LEG-06 (`03-…`) y G1-01 (`01-…`). OPS-01, OPS-03, OPS-04, TST-01, TST-02, TST-03 y R0-03 pasan de la Ola 3 a la Ola R.

**Lo que está bien (medido, no re-auditar):** el núcleo de autorización es la parte más blindada del sistema: las 11
mutaciones sobre `core/rbac.py`, `core/api_permissions.py` y `core/middleware.py` murieron todas, varias con 5-8 tests
cada una (§i). El barrido anónimo de las 288 rutas no encontró superficie de backoffice abierta después de la Ola 0
(RED-02). La cobertura de líneas del núcleo de Becas está entre 91 % y 98 % (`rbac.py`, `padron.py`, `respuestas.py`,
`inscripcion_publica.py`, `cupo.py`, `siis_envio.py`, `proceso_masivo.py`, `api/views.py`, `portal/views/inscripcion.py`)
y 36 de 40 arreglos de reglas de negocio dejaron un test que falla sin el fix. Los huecos están en los **bordes**
(negativos, particiones de estados, cupo exacto), en el **motor de producción** (MariaDB: la CI corre en SQLite y sin
migraciones), en los **contratos entre repos** (app de campo) y en el **proceso** (nada es obligatorio en GitHub,
y nada se prueba entre `main` y PRD).

**Cómo implementar una ficha:** los tests de las propuestas se escriben en la app (`<app>/tests/…`), nunca en `docs/`
(RED-34). Un test que **hoy falla** por un bug que se arregla en otra ola entra marcado `@unittest.expectedFailure` con
el ID de la ficha en el docstring, y el PR del arreglo saca el decorador. Un test de «ratchet» fija una lista literal
con lo que existe hoy; la lista solo baja.

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| RED-01 | Datos personales reales (10.321 personas) en un repo público, en el release y en la imagen de PRD | CRÍTICA | CONF. lectura (API + git) | R (hotfix) | M | ⬜ |
| RED-02 | Ningún test recorre el URLconf: una ruta que vuelva a quedar abierta pasa el CI | ALTA | CONF. test (barrido) | R | S | ✅ |
| RED-03 | App de campo: pausa probada en 1 de 6 endpoints, período en 3, ramas de error en ninguna | ALTA | CONF. test (coverage) | R | S-M | ⬜ |
| RED-04 | Crear, eliminar y activar un rol no se ejecutan por HTTP en ningún test | ALTA | CONF. test (coverage) | R | S-M | ⬜ |
| RED-05 | Ningún test sigue un adjunto desde el canal que lo sube hasta la revisión | ALTA | CONF. lectura | R (+3 con DAT-01) | M | ⬜ |
| RED-06 | Legajos: 23 de 36 rutas sin test; `/legajos/alertas/` ya dio 500 y sigue sin test | ALTA | CONF. test (coverage) | R (+2) | S-M + S | ⬜ |
| RED-07 | Nada impide volver a poner `Trunc*`/`__date` sobre un `DateTimeField` (CONVERT_TZ, 500 en PRD) | ALTA | CONF. test (SQL compilado) | R | S-M | ⬜ |
| RED-08 | Los tests del 500 del link público cuentan consultas, no la forma del `WHERE` | ALTA | CONF. test (SQL compilado) | R | S | ⬜ |
| RED-09 | Un `UUIDField` nuevo sin `char(36)` pasa el CI; el único test de UUID se saltea siempre | ALTA | CONF. test | R (+3) | S-M (+S) | ⬜ |
| RED-10 | Las dos escrituras que dieron 500 bajo el lock no tienen presupuesto de consultas | ALTA | CONF. lectura | R (+4) | S (+S-M) | ⬜ |
| RED-11 | Ningún test fija la forma del JSON de `/api/becas/*` que lee la app de campo | ALTA | CONF. lectura (dos repos) | R | S | ⬜ |
| RED-12 | `definicion_formulario` y los prefijos `pg-`/`rn-`: contrato de dos repos sin serializer ni test | ALTA | CONF. lectura (dos repos) | R | M | ⬜ |
| RED-13 | El shell de todo el backoffice y `legajos.ready()` dependen de `conversaciones` | ALTA | CONF. lectura | R (test) + 7 | S + M | ⬜ |
| RED-14 | Un rollback de release con una columna `NOT NULL` nueva rompe el alta de casos (error 1364) | ALTA | CONF. test (MariaDB 11.8) | R | M | ⬜ |
| RED-15 | En MariaDB la reversa falla (errno 150) y deja tabla huérfana y `django_migrations` a mitad | ALTA | CONF. test (MariaDB 11.8) | R | S | ✅ |
| RED-16 | No hay artefacto al que volver: ECOM publica solo `:latest` y `main` no se tagea | ALTA | CONF. lectura (rollout PLAUSIBLE) | R | S | ⬜ |
| RED-17 | Ninguna migración se prueba hacia atrás ni sobre datos; los tests de migración usan los modelos de hoy | ALTA | CONF. test | R | M + S | ⬜ |
| RED-18 | La reversa de `0047`, `0048` y `legajos.0007` falla con «Data truncated» | ALTA | CONF. test (MariaDB 11.8) | R | S | ⬜ |
| RED-19 | Rolling en k8s: cada pod corre `migrate` (choque) y no hay regla expand/contract | ALTA | CONF. test (MariaDB 11.8) | R (+3 en OPS-07) | S-M | ⬜ |
| RED-20 | `development` y `main` sin protección de rama: ningún check es obligatorio | ALTA | CONF. lectura (API) | R | S-M | ⬜ |
| RED-21 | `publish-main.yml` genera el release sin exigir CI verde y con un denylist escrito a mano | ALTA | CONF. lectura | R | S | ⬜ |
| RED-22 | El pipeline de ECOM solo construye la imagen: cero verificación antes del deploy a PRD | ALTA | CONF. lectura | R (propuesta a ECOM) | S | ⬜ |
| RED-23 | `/pushGitLabecom` empuja `test` y `main` en la misma corrida, sin exigir CI ni testing verificado | ALTA | CONF. lectura | R | M | ⬜ |
| RED-24 | Sin gates de contratos del repo: `compile_templates`, `collectstatic`, `requerimientos --check`, `design_audit` | ALTA | CONF. test (corrida) | R | M | ⬜ |
| RED-25 | La capacidad `becas.campo` no se prueba en los endpoints ni en el oráculo de identidad | ALTA | CONF. test (mutación M11) | R | S | ⬜ |
| RED-26 | `FormularioViewSet` sin test de alcance: un territorial podría leer y editar casos ajenos | ALTA | CONF. test (mutación M14) | R | S | ⬜ |
| RED-27 | Promover desde la lista de espera con cupo exactamente 0 no está probado | ALTA | CONF. test (mutación M19) | R | S | ⬜ |
| RED-28 | `FINALIZANDO` está en los estados abiertos de vencimientos y ningún test lo cubre | ALTA | CONF. test (mutación M27) | R | S | ✅ |
| RED-29 | El envío del link público no prueba que el relevamiento siga `EN_CURSO` | ALTA | CONF. test (mutación M44) | R | S | ✅ |
| RED-30 | Sin test de humo por pantalla: nada afirma «ninguna ruta da 500» | MEDIA | CONF. test (barrido) | R | S | ✅ |
| RED-31 | `requisito_eliminar` y `subsegmento_eliminar` no se ejecutan en ningún test | MEDIA | CONF. test (coverage) | R | S | ⬜ |
| RED-32 | Comandos contra SIIS y RENAPER sin red (`validar_casos_siis`, `completar_casos_renaper`, `sincronizar_programas_siis`) | MEDIA | CONF. test (coverage) | R (+1) | S-M (+S-M) | ⬜ |
| RED-33 | Dispositivos y Merenderos: las vistas que operan no tienen test HTTP | MEDIA | CONF. test (coverage) | 5 | M | ⬜ |
| RED-34 | Nada obliga a que una ficha cerrada deje un test permanente (0 tests bajo `docs/`) | MEDIA | CONF. test | R | S | ⬜ |
| RED-35 | Ningún test afirma que las escrituras críticas sigan siendo atómicas | MEDIA | CONF. lectura | R (+3) | S (+S-M) | ⬜ |
| RED-36 | `drf_spectacular` fuera de `INSTALLED_APPS`: `/api/docs/` y `/api/redoc/` dan 500 | MEDIA | CONF. test | R (primero) | S | ⬜ |
| RED-37 | El esquema OpenAPI publica tipos falsos y pierde 11 vistas | MEDIA | CONF. test | R (+7) | S-M (+S-M) | ⬜ |
| RED-38 | Tres motores de condiciones (1 Python + 2 JS, dos repos) sin vectores compartidos | MEDIA | CONF. lectura (dos repos) | R | M | ⬜ |
| RED-39 | Cinco sobres de error JSON leídos con fallback silencioso | MEDIA | CONF. lectura | R (+7) | S (+M) | ⬜ |
| RED-40 | `JSONField` con estructura implícita: 0 `validators` y nada sobre datos viejos | MEDIA | CONF. lectura | R (+3) | S-M (+S) | ⬜ |
| RED-41 | Parsers de RENAPER, Personas y SIIS probados contra diccionarios inventados | MEDIA | CONF. lectura | R | S-M | ⬜ |
| RED-42 | Endpoints JSON del backoffice sin contrato; 4 `fetch` literales resuelven 404 | MEDIA | CONF. test (`resolve`) | R (+5) | S-M (+S) | ⬜ |
| RED-43 | El CI no tiene ningún gate de contrato de API | MEDIA | CONF. lectura | R | S | ⬜ |
| RED-44 | Una capacidad mal tipeada devuelve `False` en silencio y el superusuario no lo ve | MEDIA | CONF. test (prototipo) | R | S | ⬜ |
| RED-45 | `GUNICORN_CMD_ARGS` con gevent activa un parche que apaga `validate_thread_sharing` | MEDIA | CONF. lectura | R (+7 en OPS-13) | S | ⬜ |
| RED-46 | `programas/models/__init__.py` (3.252 líneas, 90 importadores) sin tests de contrato | MEDIA | CONF. test (radon) | R | S-M | ⬜ |
| RED-47 | `normalizar_dni` y sus tres copias agregan un 0 con `float` o `Decimal` | MEDIA | CONF. test | R | S | ⬜ |
| RED-48 | «DNI válido» está implementado 6 veces con 3 reglas de largo | MEDIA | CONF. lectura | 3 | S-M | ⬜ |
| RED-49 | `cupo_disponible` significa tres cosas y dos pantallas lo rotulan igual | MEDIA | CONF. lectura | R (+4) | S (+S) | ⬜ |
| RED-50 | La edad (RN-22) está cuatro veces y tres usan `date.today()` (UTC en los contenedores) | MEDIA | CONF. lectura | R (+3) | S (+S-M) | ⬜ |
| RED-51 | Dos `invalidate_dashboard_cache`; `stats_legajos` colgado del modelo equivocado | MEDIA | CONF. lectura | R (+4) | S (+S) | ⬜ |
| RED-52 | Contrato implícito por `user._state.fields_cache["profile"]` | MEDIA | CONF. lectura | R (+2) | S (+S) | ⬜ |
| RED-53 | Clones literales entre los comandos SIIS y entre las vistas de padrón | MEDIA | CONF. test (pylint + AST) | 1 (+5) | S-M (+S) | ⬜ |
| RED-54 | `revision.py` (1.331 líneas): ningún test fija el contexto del detalle | MEDIA | CONF. test (radon) | R (+7) | S-M (+M) | ⬜ |
| RED-55 | Los context processors corren en cada render y tragan toda excepción sin log | MEDIA | CONF. lectura | R | S | ⬜ |
| RED-56 | Los guards de alcance de Becas fallan abiertos si el Programa BECAS no está sembrado | MEDIA | CONF. test | R | S | ⬜ |
| RED-57 | 14 reversas `RunPython.noop` (más `users/0007`) pierden datos e informan `OK` | MEDIA | CONF. test (SQLite con datos) | R | S-M | ⬜ |
| RED-58 | `legajos.0007` no es re-entrante: un corte deja legajos sin FK y el reintento muere con 1091 | MEDIA | CONF. test (SQL) | 3 | S | ⬜ |
| RED-59 | `deploy_prod.sh`: rollback sin base, detached HEAD y un health que siempre da 200 | MEDIA | CONF. lectura | R | S | ⬜ |
| RED-60 | `processes.md` enseña un rollback que destruye datos y autoriza `--fake` | MEDIA | CONF. lectura | R (prioridad 1) | S | ✅ |
| RED-61 | `SIIS_API_URL` cae al SIIS de desarrollo y nada lo valida al arrancar | MEDIA | CONF. lectura (PRD PLAUSIBLE) | R | S | ⬜ |
| RED-62 | Los presupuestos de performance son autodeclarados: subirlos en el mismo PR pasa | MEDIA | CONF. lectura | 4 | S | ⬜ |
| RED-63 | Ruff y Bandit en `continue-on-error`; excepción de `pip-audit` sin vencimiento | MEDIA | CONF. lectura | R | S | ⬜ |
| RED-64 | `docs/client/` se publica en GitHub Pages público en cada push, sin revisión | MEDIA | CONF. lectura (API) | 7 | S | ⬜ |
| RED-65 | El guard de `publish-main.yml` exige artefactos muertos y va a bloquear OPS-10/OPS-14 | MEDIA | CONF. lectura | R (+7) | S | ⬜ |
| RED-66 | `reabrir` de la app de campo no tiene test negativo de la transición | MEDIA | CONF. test (mutación M17) | R | S | ✅ |
| RED-67 | Ningún test afirma que se tome el `select_for_update` del cupo ni del link | MEDIA | CONF. test (mutaciones M21, M43) | R (+capa 2 en TST-01) | S | ⬜ |
| RED-68 | La posición en la lista de espera no está probada en ningún lado | MEDIA | CONF. test (mutación M23) | R | S | ⬜ |
| RED-69 | Fecha de nacimiento ausente o futura sin test en el payload SIIS | MEDIA | CONF. test (mutación M34) | R | S | ⬜ |
| RED-70 | `celda_segura`: la limpieza de caracteres de control no está probada | MEDIA | CONF. test (mutación M49) | R | S | ⬜ |
| RED-71 | `ApiCorsMiddleware` sin tests de contrato (y el Cambio 52 lo da por inexistente) | BAJA | CONF. test (ajustado) | R | S | ✅ |
| RED-72 | El harness e2e de Playwright no existe en el repo: quedan `.pyc` de julio | BAJA | CONF. lectura | R | S | ⬜ |
| RED-73 | `CiudadanoConfirmarView` decide antes de mirar si hay sesión | BAJA | CONF. test (barrido) | R | S | ✅ |
| RED-74 | Ocho arreglos mergeados sin ningún test | BAJA | CONF. lectura (git) | R | S | ⬜ |
| RED-75 | `/set_dark_mode/` no existe: el toggle de tema postea a un 404 | BAJA | CONF. test (`resolve`) | 5 | S | ⬜ |
| RED-76 | Tipado: 2,7 % de retornos anotados, sin mypy ni pyright | BAJA | CONF. test (AST) | 7 | S-M | ⬜ |
| RED-77 | RN-2 del padrón escrita dos veces: property y filtro de queryset | BAJA | CONF. lectura | R | S | ⬜ |
| RED-78 | `DashboardView`: copia del inicio sin el blindaje de SEC-14, muerta solo por el orden de URLs | BAJA | CONF. test (`resolve`) | R (+7) | S (+S) | ⬜ |
| RED-79 | Tres ciclos de import y nueve aristas vista→vista sin ratchet | BAJA | CONF. test (AST) | R (+2) | S (+S) | ⬜ |
| RED-80 | `programa_becas` y `programa_dispositivos`: mismo cache, distinta guarda e invalidación | BAJA | CONF. lectura | 2 | S | ⬜ |
| RED-81 | El registro de reglas de vencimiento puede quedar vacío y el comando sale OK | BAJA | CONF. lectura | R | S | ⬜ |
| RED-82 | `exportacion_reportes.py` con terminadores CR: git lo trata como binario y pylint lo saltea | BAJA | CONF. test | R | S | ⬜ |
| RED-83 | Índices duplicados en `programas_formulario` y `legajos_ciudadano` | BAJA | CONF. test (`information_schema`) | R (+4) | S (+S) | ⬜ |
| RED-84 | `requerimientos.py --check` no verifica la sección «Reversión» | BAJA | CONF. lectura | R | S | ⬜ |
| RED-85 | Herramientas del CI sin pinear y actions por tag en workflows con `contents: write` | BAJA | CONF. lectura | R (+7) | S (+S) | ⬜ |
| RED-86 | Job de tests con timeout de 15 min, sin `--parallel` ni alarma de crecimiento | BAJA | CONF. test (`gh run list`) | 7 | S | ⬜ |
| RED-87 | El largo mínimo del barrio del payload SIIS no se prueba en su borde | BAJA | CONF. test (mutación M33) | R | S | ⬜ |
| RED-88 | `manage.py test core users portal --parallel` revienta con `cannot pickle 'traceback'` | BAJA | CONF. test | R | S | ⬜ |

«Ola» con paréntesis = la ficha tiene una segunda parte en esa ola (detalle en la ficha y en README §6). Horas: S = 2,
S-M = 4, M = 8, L = 20 (README §6).

---

## (a) Flujos críticos y cobertura

### RED-02 · Ningún test recorre el URLconf: una ruta que vuelva a quedar abierta pasa el CI
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (barrido propio de VR1: 288 rutas) · **Origen:** RS-R1-01 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** no existe el test. Solo `core/tests/test_media_protegida.py:40` (para `/media/`) y
  `core/tests/test_url_namespaces.py` (5 nombres) miran el URLconf; `git grep -n "get_resolver\|url_patterns" */tests/` → 0.
- **Qué es frágil:** la Ola 0 cerró once superficies abiertas una por una, cada una con su test puntual. Ningún test
  mira el conjunto: la regla «toda ruta de backoffice rebota al anónimo» no está escrita en ningún lado ejecutable.
- **Qué cambio lo rompería sin que nadie se entere:** montar un `ModelViewSet` sin `permission_classes` en
  `legajos/urls/api.py` o `core/api_urls.py` (exactamente SEC-02 y SEC-13), o sacarle el `@login_required` a una vista de
  `legajos/views/contactos_api.py`. Los 1.438 tests de `programas` y los 48 de `legajos` siguen verdes.
- **Evidencia:** barrido de VR1 (recorre `get_resolver()`, concreta cada ruta y hace GET anónimo): 288 rutas, 17 no
  rebotan al login y las 17 son públicas por diseño (login y recupero, `/health/`, `/portal/`, `/portal/csrf/`,
  `/favicon.ico`) salvo `/legajos/ciudadanos/confirmar/` (RED-73). RS-R1 midió 571/44 con otro script: **el número
  depende de cómo se concretan los `re_path`; no copiar ninguno de los dos.**
- **Propuesta:** `core/tests/test_superficie_publica.py`:
  - `SuperficieAnonimaTests.test_ninguna_ruta_responde_al_anonimo`: recorre `get_resolver().url_patterns`
    recursivamente, saltea el namespace `admin` y los patrones sin `_route` concretable, hace `self.client.get(url)` sin
    sesión y exige una de tres: (a) redirección a `settings.LOGIN_URL` o a `portal:home`; (b) `401/403/404/405/426`;
    (c) estar en `ALLOWLIST_PUBLICA` (lista literal, con un comentario por entrada). Un `200` fuera de la lista falla con
    `f"{namespace}:{name} → {url} ({status})"`.
  - `test_la_allowlist_publica_no_crecio`: `assertEqual(len(ALLOWLIST_PUBLICA), <n medido al escribirlo>)`. Agregar una
    ruta pública pasa a ser un cambio deliberado y revisable.
  - No generar la allowlist desde el código («toda vista con `@requiere` está bien»): la lista a mano es lo que obliga a
    justificar cada excepción. `/legajos/ciudadanos/confirmar/` se clasifica cuando se cierre RED-73, no se allowlistea.
- **Verificación:** `& $env:PY manage.py test core.tests.test_superficie_publica` (corre en ~3 s sobre SQLite); mutación
  de control: quitar el `login_required` de una vista de `contactos_api.py` → el test falla.

### RED-03 · App de campo: la pausa está probada en 1 de 6 endpoints, el período en 3 y las ramas de error en ninguna
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (coverage: `programas/api/views.py` 92 %, líneas sin ejecutar leídas una por una) · **Origen:** RS-R1-02 (VR1: CONFIRMADO-AJUSTADO), RS-R1-15, RS-VR1-NEW-02 · **Ola:** R · **Esfuerzo:** S-M (4 h) · **Decisión:** D-RED-10
- **Ubicación:** `programas/api/views.py:65-77` (`_mensaje_pausa`/`_respuesta_pausa`) y sus llamadas en `:291`
  (`iniciar`), `:318` (`finalizar`), `:344` (`reabrir`), `:368` (`formularios` POST), `:454` (`perform_update`, el
  PATCH), `:479` (`adjuntos` POST); período (`_captura_habilitada`) en `:330`, `:347`, `:483`; ramas de error en
  `:297-298`, `:322-325` (`capturado_en` malformado), `:335`, `:352`, `:366`, `:437`; `GET adjuntos/` en `:477`.
- **Qué es frágil:** el único test de pausa es `test_becas_api.py:83::test_pausa_se_informa_y_bloquea_inicio` (solo
  `iniciar`). Las líneas 319, 345, 369, 455 y 480 (los cinco `return respuesta` restantes), 330/347/483 y el `GET
  adjuntos/` no se ejecutan nunca. Además el contrato **no es uniforme**: cinco endpoints contestan `409
  {"detail", "pausado": true}` y el PATCH contesta `400 {"detail"}` (`perform_update` usa `ValidationError`). La app
  (`Chaco-mobile@765696a`) no mira ni el 409 ni la clave `pausado` (`grep -rn "pausa" src` → 0).
- **Qué cambio lo rompería sin que nadie se entere:** borrar `if respuesta := _respuesta_pausa(rel): return respuesta` de
  `finalizar`, `reabrir`, `formularios`, `perform_update` o `adjuntos`, o que `_respuesta_pausa` ignore la pausa de la
  convocatoria: el campo sigue cargando con el programa pausado y falla un solo test (el de `iniciar`). Y un
  `finalizar` sobre un relevamiento ya `EN_REVISION` que pase de 400 a 500 deja a la app en bucle de sincronización.
- **Propuesta:** en `programas/tests/test_becas_api.py`:
  - `PausaEnTodosLosEndpointsTests.test_la_pausa_bloquea_y_no_escribe` — `subTest` por endpoint sobre un relevamiento
    pausado, con **el código real de cada uno**: `409` + `{"detail", "pausado": true}` en `iniciar`, `finalizar`,
    `reabrir`, `formularios` y `adjuntos`; **`400` + `{"detail"}` en el PATCH**. Cada caso afirma que nada cambió
    (estado del relevamiento, `Formulario.objects.count()`, `AdjuntoFormulario.objects.count()`). No escribir un `409`
    para los seis: el implementador «arreglaría» el test en vez de la inconsistencia (D-RED-10).
  - `PeriodoEnTodosLosEndpointsTests` con `fecha_hasta` vencida (líneas 330, 347, 483).
  - `test_lista_los_adjuntos_ya_subidos` (`GET …/adjuntos/`, es lo que la app lee para no reenviar).
  - En `RelevamientoApiTests`: `test_finalizar_un_relevamiento_que_no_esta_en_curso_da_400_con_mensaje`,
    `test_reabrir_uno_que_no_esta_finalizado_da_400` (ver también RED-66),
    `test_una_fecha_de_captura_invalida_da_400_en_iniciar_y_en_finalizar` (`subTest`), `test_dni_existe_sin_dni_da_400`.
- **Verificación:** `& $env:PY manage.py test programas.tests.test_becas_api`.

### RED-04 · Crear, eliminar y activar un rol no se ejecutan por HTTP en ningún test
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (coverage: `users/views/roles.py` 54 %) · **Origen:** RS-R1-03 (VR1: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S-M (4 h)
- **Ubicación:** `users/views/roles.py:81-95` (`RolCreateView`), `:140-151` (`RolDeleteView`), `:154-165`
  (`RolToggleActivoView`), `:120-137` (`RolUpdateView.post`), `:64-78` (`RolDetailView.get`).
- **Qué es frágil:** `users/tests/test_roles_abm.py` (614 líneas) prueba `RolForm` y `RolesAdminService` llamándolos
  directo; por HTTP solo se ejercitan el listado y el GET de edición. `git grep "rol_crear\|rol_eliminar\|rol_toggle"`
  en `*/tests/` → 0 (fuera de `docs/…/poc/`, que no corre: RED-34).
- **Qué cambio lo rompería sin que nadie se entere:** `RolCreateView.post` es la única de las cuatro que **no** llama a
  `puede_gestionar_rol`: confía en que `RolForm(operador=request.user)` acote categoría, programa y capacidades. Si un
  refactor deja de pasar `operador`, el admin de roles de Becas crea un rol global con todo tildado (G1b-02 por la
  puerta real) y no falla nada. Simétrico: sacar el `try/except SinAdministradorError` de `RolDeleteView` deja borrar el
  último rol administrador.
- **Propuesta:** `users/tests/test_roles_abm.py::RolesEscrituraHttpTests`:
  `test_admin_de_programa_no_crea_un_rol_global_por_post` (POST a `users:rol_crear` con `categoria=Backoffice` y
  `usuario.administrar` → el `Group` no se crea o nace sin esa capacidad, y el form devuelve error) ·
  `test_crear_rol_por_post_crea_grupo_rolmeta_y_capacidades` · `test_eliminar_el_ultimo_rol_administrador_no_borra_nada` ·
  `test_eliminar_rol_protegido_avisa_y_no_borra` · `test_toggle_de_rol_protegido_avisa_y_no_cambia` ·
  `test_eliminar_y_toggle_solo_aceptan_post` (GET → 405) · `test_rol_de_otro_programa_no_se_elimina_ni_se_desactiva`.
  Punto de partida: el POST a `users:rol_toggle` de `poc/test_repro_usuarios.py:254-263`. Los tests 1 y 3, antes de
  cualquier PR de la Ola 2.
- **Verificación:** `& $env:PY manage.py test users.tests.test_roles_abm`.

### RED-05 · Ningún test sigue un adjunto desde el canal que lo sube hasta la revisión
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura; VR1 verificó el seam) · **Origen:** RS-R1-04 (VR1: CONFIRMADO) · **Ola:** R (el tercer test, con DAT-01 en la Ola 3) · **Esfuerzo:** M (8 h)
- **Ubicación:** escritura en `programas/services/inscripcion_publica.py:194-208` (link) y `programas/api/views.py:487-490`
  (app); lectura en `programas/services/respuestas.py:316-324` (`_adjuntos_por_clave`, indexa por `pg-<pk>`/`rn-<pk>`) y
  `:285,293` (`respuestas_legibles`, busca por la `clave` del ítem de **la foto** del caso).
- **Qué es frágil:** el adjunto se afirma al crearse (`portal/tests/test_inscripcion_envio.py:322`,
  `programas/tests/test_becas_api.py:972-993`) y la revisión se prueba con un adjunto fabricado a mano en el test
  (`test_becas_revision.py:139-162`). Las dos mitades corren en tests distintos con datos distintos: nadie cruza el puente.
- **Qué cambio lo rompería sin que nadie se entere:** cambiar el prefijo de clave en `diseno.clave_pregunta`
  (`diseno.py:47`) sin tocar `_adjuntos_por_clave`, o que el constructor modele una pregunta ARCHIVO como campo propio
  (`cp-…`): el caso guarda el archivo y la revisión renderiza el campo con `adjunto=None`. La foto del DNI desaparece de
  la pantalla sin error ni log (es el síntoma que DAT-01 describe: el revisor lo ve «faltante»).
- **Propuesta:** `programas/tests/test_adjunto_punta_a_punta.py::AdjuntoLlegaALaRevisionTests`, dos tests sobre un helper
  de aserción común:
  `test_el_archivo_subido_por_el_link_se_ve_en_la_revision` (convocatoria con `PreguntaGlobal` ARCHIVO en el diseño →
  paso 1 y paso 2 del link con `SimpleUploadedFile` → `force_login(revisor)` → `GET becas:formulario_detalle` → 200, el
  bloque del campo llega con `es_archivo=True` y `adjunto` no nulo, `adjunto.archivo.name` es el subido y el HTML contiene
  su URL) y `test_el_archivo_subido_por_la_app_se_ve_en_la_revision` (lo mismo por `POST /api/becas/relevamientos/<pk>/formularios/`
  + `POST /api/becas/formularios/<pk>/adjuntos/` con Token). El tercero,
  `test_una_pregunta_recreada_con_otro_pk_no_deja_el_adjunto_huerfano`, es el test invertido de DAT-01 y va en su PR.
- **Verificación:** `& $env:PY manage.py test programas.tests.test_adjunto_punta_a_punta`.

### RED-06 · Legajos: 23 de 36 rutas sin test; `/legajos/alertas/` ya dio 500 y sigue sin test
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (coverage) · **Origen:** RS-R1-05 capa 1 (VR1: CONFIRMADO-AJUSTADO), RS-R2-06 (VR1: CONFIRMADO; mismo PR) · **Ola:** R (capa 2 con SEC-10/11/12/18 en la Ola 2) · **Esfuerzo:** S-M + S (6 h)
- **Ubicación:** `legajos/views/historial_contactos.py` y `dashboard_contactos.py` en 0 %, `solapas.py` 21 %,
  `contactos_api.py` 29 %, `alertas.py` 30 %, `derivacion*.py` 29 %; `legajos/views/alertas.py:18-70`
  (`alertas_dashboard`, el comentario de `:47-51` documenta el 500) y `legajos/urls/__init__.py:96-99`.
- **Qué es frágil:** 48 tests para toda la app. Rutas sin una sola cita: `subir_archivos`, `subir_archivos_ciudadano`,
  `archivos_legajo`, `archivos_ciudadano`, `eliminar_archivo`, `derivar_programa`, `derivacion_ciudadano_aceptar/rechazar`,
  `alertas_dashboard`, `alertas_count_ajax`, `alertas_preview_ajax`, `cerrar_alerta_ajax`, `alertas_ciudadano`,
  `historial_contactos`, `red_contactos`, `evolucion_legajo`, `timeline_ciudadano`, `actividades_ciudadano`,
  `prediccion_riesgo`, `ciudadano_editar`, `ciudadano_manual`, `exportar_csv`, `ciudadano_buscar_api`.
- **Qué cambio lo rompería sin que nadie se entere:** ya pasó (Cambio 66): `select_related("conversacion__usuario")`
  sobre un campo inexistente dio `FieldError` → **500 para todo operador con `conversacion.operar`** y vivió hasta que
  alguien lo leyó. `alertas_preview_ajax:120-121` envuelve todo en `except Exception` con HTTP 200: el próximo fallo
  tampoco se ve desde afuera.
- **Propuesta:**
  1. `legajos/tests/test_humo_pantallas.py::PantallasDeLegajosAbrenTests`: `setUpTestData` con ciudadano + legajo +
     derivación + adjunto + alerta + contacto; `subTest` por cada una de las 36 rutas con un usuario con todas las
     capacidades → `status_code in (200, 302, 405)` y nunca `>= 500`.
  2. `legajos/tests/test_alertas_dashboard.py::AlertasDashboardTests`: `test_responde_200_para_un_operador_de_conversaciones`
     (rol con `conversacion.operar` + un `HistorialAlertaConversacion` suyo; falla con `FieldError` si vuelve el
     `select_related` inválido) · `test_responde_200_sin_la_capacidad_y_no_lista_conversaciones` ·
     `test_los_tres_endpoints_ajax_responden_json` (`count`, `preview`, `cerrar-ajax` con las claves que leen
     `alertas_websocket.js` y `_alerta`).
  3. Capa 2 (Ola 2, en las fichas SEC-10/11/12/18): adjunto ajeno sin capacidad → 403; `.html` rechazado; `GET
     derivar_programa` no crea la derivación.
- **Verificación:** `& $env:PY manage.py test legajos`.

### RED-30 · Sin test de humo por pantalla: nada afirma «ninguna ruta da 500»
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (barrido con superusuario: 305 rutas, 3 con `>= 500`) · **Origen:** RS-R1-06 parte propia (VR1: la parte de Spectacular es RED-36) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación / qué es frágil:** los tests entran por las vistas que les interesan. Una pantalla que depende de un
  template, un tag o un `select_related` puede quedar en 500 permanente sin que la suite diga nada (hoy: `/api/docs/` y
  `/api/redoc/` con `TemplateDoesNotExist`, RED-36).
- **Qué cambio lo rompería sin que nadie se entere:** borrar o renombrar un template incluido, un `{% load %}` faltante,
  un `select_related` sobre una relación renombrada (el caso de RED-06).
- **Propuesta:** en el mismo `core/tests/test_superficie_publica.py`, `NingunaPantallaDa500Tests.test_ninguna_pantalla_da_500`:
  mismo recorrido de RED-02, superusuario, `assertLess(resp.status_code, 500, f"{ns}:{name} → {url}")`, con
  `EXCEPCIONES` comentadas para los proxies a SIIS (`becas:siis_localidades_json`, `becas:siis_funciones_json`) y, hasta
  que se mergee RED-36, `/api/docs/` y `/api/redoc/`.
- **Verificación:** `& $env:PY manage.py test core.tests.test_superficie_publica`.

### RED-31 · `requisito_eliminar` y `subsegmento_eliminar` no se ejecutan en ningún test
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (coverage: cuerpos completos `683-695` y `564-573` sin ejecutar) · **Origen:** RS-R1-07 (VR1: CONFIRMADO) · **Ola:** R (el cuarto test, con DAT-01) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/views/configuracion.py:682-695` (`requisito_eliminar`, el bug de DAT-01) y `:563-573`
  (`subsegmento_eliminar`, el patrón que DAT-01 manda copiar).
- **Qué cambio lo rompería sin que nadie se entere:** quitar el `except ProtectedError` de `subsegmento_eliminar`
  convierte un mensaje en un 500. Al revés, el fix de DAT-01 puede quedar mal cableado (atrapar la excepción pero seguir
  borrando el `ItemDiseno`, que el Cambio 58 sí quiere que se borre) sin que se note.
- **Propuesta:** `programas/tests/test_becas_config.py::EliminarRequisitoYSubsegmentoTests`, **antes** de tocar DAT-01:
  `test_subsegmento_en_uso_por_una_convocatoria_no_se_borra_y_avisa` · `test_subsegmento_libre_se_borra_y_redirige_al_segmento` ·
  `test_requisito_sin_adjuntos_se_borra_con_su_item_de_diseno` (preserva el Cambio 58) ·
  `test_las_dos_vistas_exigen_post_y_capacidad`. El cuarto, `test_requisito_con_adjunto_en_un_caso`, documenta el
  comportamiento de hoy (el adjunto desaparece) y lo invierte el PR de DAT-01.

### RED-32 · Comandos contra SIIS y RENAPER sin red
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (coverage 0 %; VR2 midió `call_command`) · **Origen:** RS-R1-10 (VR1: CONFIRMADO, amplía TST-02), RS-R2-08 (VR1: duplicado de RS-R1-10), RS-R4-15 (VR2: CONFIRMADO-AJUSTADO, «2 tests, no 6») · **Ola:** R (caracterización) + 1 (PR 7 de herramientas: el resto) · **Esfuerzo:** S-M (4 h) + S-M (4 h)
- **Ubicación:** `programas/management/commands/completar_casos_renaper.py` (221 stmts, 0 %),
  `validar_casos_siis.py` (114, 0 %), `sincronizar_programas_siis.py` (25, 0 %, CronJob diario 04:00).
- **Qué es frágil:** de los seis comandos SIIS que la Ola 1 va a tocar, **cuatro ya tienen red** (`corregir_datos_siis`,
  `procesar_casos_siis`, `enviar_casos_siis`, `correr_alta_siis` se ejercen con `call_command`); estos tres no.
  `validar_casos_siis` escribe una `ValidacionSIS` por consulta (`:173`), que es lo que el revisor ve como vigente;
  `completar_casos_renaper` reescribe identidad y ya tuvo un bug de memoria/timeout (`a427bffe`, 23/09, «trae los casos
  lote a lote») cuyo arreglo no tocó ningún test.
- **Qué cambio lo rompería sin que nadie se entere:** en `validar_casos_siis._casos` (`:93-112`), cambiar el `order_by` del
  `Subquery` o el `exclude(estado=RECHAZADO)` → revalida miles de casos ya validados o saltea los que faltan; romper el
  freno `--max-errores` (`:180-186`) deja miles de filas `ERROR` que el revisor lee como «incompatible». En
  `completar_casos_renaper`, volver a un `for caso in qs:` sin lotes.
- **Propuesta:**
  - **R (caracterización, antes de la Ola 1):** `programas/tests/test_comandos_siis_caracterizacion.py`:
    `ValidarCasosSiisTests.test_ensayo_sin_aplicar_no_escribe_y_cuenta_bien` (3 casos ENVIADO/APROBADO/RECHAZADO,
    `SiisAPIClient` mockeado, sin `--aplicar` → `ValidacionSIS.objects.count() == 0` y el conteo en stdout) ·
    `CompletarCasosRenaperTests.test_sin_tabla_de_renaper_aborta_con_mensaje_util` (`assertRaisesMessage(CommandError,
    "No existe la tabla")`) · `CompletarCasosRenaperTests.test_procesa_por_lotes` (5 casos, `--lote 2`, RENAPER
    mockeado: 3 lecturas, no 1) · `CompletarCasosRenaperTests.test_dry_run_no_escribe` ·
    `SincronizarProgramasSiisTests.test_catalogo_vacio_no_pisa_nada` y `test_siis_caido_da_commanderror_y_no_toca_ids`.
  - **Ola 1 (PR 7):** `programas/tests/test_validar_casos_siis.py::ValidarCasosSiisTests` con
    `patch("programas.services.validacion_siis.validar_formulario_en_siis")`: `test_toma_solo_los_casos_sin_validacion` ·
    `test_reintentar_errores_suma_los_que_quedaron_en_error` · `test_un_rechazado_por_el_revisor_se_saltea_salvo_incluir_rechazados` ·
    `test_diez_errores_tecnicos_seguidos_detienen_la_corrida` · `test_un_ok_entre_errores_reinicia_el_contador` ·
    `test_sin_credenciales_con_aplicar_corta_con_commanderror`; y `CompletarCasosRenaperTests.test_un_caso_que_falla_no_corta_el_resto`.
- **Dependencias:** RED-53 (base común de los comandos) va en el mismo PR de la Ola 1.

### RED-33 · Dispositivos y Merenderos: las vistas que operan no tienen test HTTP
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (coverage) · **Origen:** RS-R1-11 (VR1: CONFIRMADO) · **Ola:** 5 (con los parches v1) · **Esfuerzo:** M (8 h)
- **Ubicación:** `programas/views/admisiones.py` (59 %: `EgresoAdmisionView`, `EsperaAdmisionListView`,
  `PromoverEsperaView`, `TrasladoAdmisionView` sin POST); `programas/views/merenderos.py` (76 %:
  `EntregaMercaderiaCreateView`, `MerenderoDetailView`, `MerenderoEstadoView`); `services/merenderos.py:62-75`, `:81-87`.
- **Qué cambio lo rompería sin que nadie se entere:** que la vista deje de pasar el `usuario` al servicio (traza sin
  autor), que `PromoverEsperaView` no revalide la cama bajo el lock, o que la entrega no se asocie al merendero del `pk`
  de la URL. Los tests de servicio pasan porque reciben todo armado.
- **Propuesta:** `programas/tests/test_admisiones_vistas.py::AdmisionesPorHttpTests`:
  `test_egresar_desde_la_pantalla_libera_la_cama_y_registra_quien` · `test_promover_de_la_espera_ocupa_la_cama_y_cierra_la_fila` ·
  `test_trasladar_cierra_el_origen_y_abre_el_destino` · `test_sin_capacidad_las_cuatro_dan_403` · `test_las_cuatro_exigen_post`;
  `programas/tests/test_merenderos.py::EntregaDeMercaderiaTests`: `test_la_entrega_queda_asociada_al_merendero_de_la_url` ·
  `test_una_entrega_de_un_merendero_ajeno_no_se_crea` · `test_sin_capacidad_403`. Si D-V1 = no, estos tests son el
  criterio heredable de la v2 (README §7).

### RED-71 · `ApiCorsMiddleware` sin tests de contrato (y el Cambio 52 lo da por inexistente)
**Severidad:** BAJA (era MEDIA; VR1 refutó el encuadre de vulnerabilidad: README §8.3) · **Estado:** CONFIRMADO con test (ajustado) · **Origen:** RS-R1-08 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `core/middleware.py:40-71` (`ApiCorsMiddleware`, montado en `config/settings.py:130`), `_is_dev_origin`
  en `:21-37`; coverage del módulo 68 % (`22-37`, `49`, `61-71` sin ejecutar).
- **Qué es frágil:** hoy es un no-op en todos los entornos (`DJANGO_CORS_ALLOWED_ORIGINS` no existe en ningún
  `.env.*.example` ni compose; `_is_dev_origin` corta con `if not settings.DEBUG`). Pero el **Cambio 52** fundamenta una
  decisión de seguridad en que «no hay `django-cors-headers` en el proyecto, así que ningún sitio externo puede leerlo»:
  la afirmación es imprecisa (hay un CORS propio) y nada la congela.
- **Qué cambio lo rompería sin que nadie se entere:** poner un origen en `DJANGO_CORS_ALLOWED_ORIGINS` para una demo y
  dejarlo, o quitar la guarda de `DEBUG` de `_is_dev_origin` (que acepta por prefijo: `10.atacante.com` da `True` con
  `DEBUG=True`): ese origen pasa a leer `/api/` con la cookie del usuario (`Allow-Credentials: true`, `:65`).
- **Propuesta:** `core/tests/test_cors_api.py::ApiCorsTests`: `test_sin_origenes_configurados_ninguna_respuesta_lleva_allow_origin` ·
  `test_un_origen_de_la_lista_recibe_las_cabeceras_y_otro_no` · `test_con_debug_false_un_host_privado_no_pasa`
  (`10.0.0.5` y `10.atacante.com`) · `test_options_a_api_responde_200_sin_sesion_y_sin_cuerpo` ·
  `test_una_ruta_fuera_de_api_nunca_lleva_cabeceras_cors`. **Gotcha:** `allowed_origins` se lee en `__init__` con
  `os.getenv`, no de `settings`: `override_settings` no sirve; instanciar el middleware con la variable puesta
  (`patch.dict(os.environ, …)`) o parchear el atributo de la instancia. Documentar la variable vacía en `.env.qa.example`
  con el porqué y corregir la frase del Cambio 52 en su entrada de requerimientos.

### RED-72 · El harness e2e de Playwright no existe en el repo: quedan `.pyc` de julio
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R1-12 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R (decisión y limpieza) · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-06
- **Ubicación:** `tests/e2e/` del checkout principal: solo `__pycache__/*.cpython-314-pytest-9.1.1.pyc` y
  `.pytest_cache/` (última corrida: 2 tests, 14-jul-2026). `git log --all --diff-filter=A -- "tests/e2e/*"` → vacío; no está
  en `.gitignore` ni en CI.
- **Qué es frágil:** la documentación de trabajo del proyecto lo da por existente y «en verde»; quien quiera automatizar
  QA sobre él encuentra cachés de Python 3.14 incompatibles con el 3.12 del CI.
- **Propuesta (default D-RED-06):** borrar `tests/e2e/` del checkout y registrar la decisión en `requerimientos.md`; avisar
  al PM para que corrija su memoria de trabajo (no es un archivo del repo). Si se quiere e2e de verdad: **solo** donde hay
  JavaScript que decide —drag & drop y condiciones del constructor, condiciones en vivo del paso 2 del link— con
  `pytest-playwright` contra el compose local, **nightly o a mano, nunca como gate** (L, no planificado).

### RED-73 · `CiudadanoConfirmarView` decide antes de mirar si hay sesión
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (barrido de VR1) · **Origen:** RS-VR1-NEW-01 · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `legajos/views/ciudadanos.py:153-164`: el `dispatch` lee la sesión de RENAPER y redirige a
  `legajos:ciudadano_nuevo` **antes** de `super().dispatch()`, que es donde corren `LoginRequiredMixin` y la capacidad.
- **Qué es frágil:** no hay fuga (lee la sesión del propio solicitante), pero es la única ruta del barrido que no se
  comporta como el resto, crea una sesión anónima para el `messages.error` y es el molde equivocado: cualquier
  precondición arriba de `super().dispatch()` corre antes de la autorización.
- **Propuesta:** `if not request.user.is_authenticated: return super().dispatch(request, *args, **kwargs)` como primera
  línea (o mover la precondición a `get`/`post`). Tests en `legajos/tests/test_ciudadanos_alta.py::ConfirmarTests`:
  `test_un_anonimo_va_al_login_no_al_alta` (redirección a `settings.LOGIN_URL`) y
  `test_sin_capacidad_da_403_aunque_no_haya_datos_de_renaper`.

## (b) Regresión de bugs pasados

La tabla completa de 74 bugs históricos (cuáles dejaron test, cuáles no) está en el informe RS-R2; lo accionable está en
estas fichas. Resultado: 36 de 40 arreglos de reglas de negocio dejaron un test que falla sin el fix, y todos los de
seguridad de la Ola 0 también. Los agujeros son de cuatro clases, todas **invisibles en SQLite**: comportamiento del
motor, forma del SQL, migraciones y unas pocas vistas o comandos con cero cobertura donde ya hubo un 500.

### RED-07 · Nada impide volver a poner `Trunc*`/`__date` sobre un `DateTimeField`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (SQL compilado contra el backend de MySQL sin conectar) · **Origen:** RS-R2-01 (VR1: CONFIRMADO-AJUSTADO: la propuesta original no compilaba), RS-R6-19 (VR2: amplía DIS-01) · **Ola:** R · **Esfuerzo:** S-M (4 h)
- **Ubicación:** `programas/services/dashboard_becas.py:285-290` y `dashboard/api_views/__init__.py:219-222` (los dos
  guards son **comentarios**); instancias vivas de DIS-01 en `programas/services/registro_diario.py:35-36` y
  `reportes.py:36-43`.
- **Qué es frágil:** el patrón ya costó tres incidentes (Cambio 64: 500 del dashboard en PRD; Cambio 66: `/api/tendencias/`
  en cero; DIS-01) y la única defensa es un comentario. En SQLite los números dan bien; en ECOM (MariaDB sin tablas de
  zona horaria) `CONVERT_TZ` devuelve NULL.
- **Qué cambio lo rompería sin que nadie se entere:** «simplificar» `_serie_semanal` con
  `.annotate(semana=TruncWeek("creado")).values("semana").annotate(total=Count("id"))`, o un `TruncMonth("creado")` en un
  reporte nuevo. Suite verde, imagen construida, gráfico vacío en PRD.
- **Propuesta:** módulo nuevo `core/tests/test_sql_motor_real.py` con **este** helper (el de la PoC `A305SQL` errorea con
  `GROUP BY` porque abre conexión para resolver `allows_group_by_selected_pks`; esta versión, verificada por VR1, corre en
  0,03 s sobre SQLite) — vive una sola vez y lo consumen RED-08, RED-09 y TST-01:
  ```python
  def _sql_mysql(qs, mariadb=False):
      from django.db import connections
      from django.db.backends.mysql.base import DatabaseWrapper
      ajustes = dict(connections["default"].settings_dict)
      ajustes.update({"ENGINE": "django.db.backends.mysql", "HOST": "127.0.0.1", "PORT": "1", "NAME": "x"})
      w = DatabaseWrapper(ajustes, "probe_mysql")
      w.__dict__["mysql_is_mariadb"] = mariadb
      w.__dict__["mysql_version"] = (11, 8, 0) if mariadb else (8, 0, 32)
      w.__dict__["mysql_server_data"] = {"version": "11.8.0-MariaDB" if mariadb else "8.0.32", "sql_mode": (),
          "default_storage_engine": "InnoDB", "lower_case_table_names": False, "has_zoneinfo_database": False}
      w.features.__dict__["allows_group_by_selected_pks"] = False
      return str(qs.query.get_compiler(connection=w).as_sql()[0])
  ```
  Tests: `SinConvertTZTests.test_la_serie_semanal_del_dashboard_no_compila_convert_tz` (queryset de
  `dashboard_becas.py:285-290`) · `test_tendencias_agrupa_por_la_columna_sin_convert_tz` (`dashboard/api_views/__init__.py:219-222`) ·
  `test_truncweek_si_compila_convert_tz` (pin invertido: si Django cambia de estrategia, el test avisa en vez de quedar
  verde por una comparación sin sentido) · `test_ninguna_consulta_de_reporte_usa_convert_tz` (los querysets de
  `registro_diario.parte_f01` y `reportes._movimientos_en_periodo`: hoy **fallan** → `expectedFailure` con «DIS-01» hasta
  la Ola 5). Opcional, en el job `contratos` de RED-24: `scripts/check_sql_portable.py` que emite `::warning::` ante
  cualquier `Trunc*`/`__date` fuera de `tests/` y `migrations/`, con pragma `# sql-portable: ok`. La ejecución real de
  estos casos contra MariaDB va en TST-01 (`--tag mysql`).

### RED-08 · Los tests del 500 del link público cuentan consultas, no la forma del `WHERE`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (las dos formas compiladas por VR1) · **Origen:** RS-R2-02 (VR1: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/becas.py:140-178` (`formulario_por_client_uuid`, `q_uuid_en_texto`,
  `relevamiento_publico_por_token`); tests `portal/tests/test_inscripcion.py:376` (`test_la_busqueda_es_una_sola_consulta`)
  y `programas/tests/test_becas_models.py:347` (`test_dni_en_convocatoria_busca_por_indice`).
- **Qué es frágil:** el bug del Cambio 91 (165 respuestas 500 el 24/09, desde 91 IP) no era de **cantidad** de
  consultas: era `REPLACE(CAST(client_uuid AS CHAR),'-','')` en el `WHERE`, que anula el índice bajo el lock del
  relevamiento. La forma vieja y la de hoy son **una sola consulta**: los dos tests siguen verdes con el código del bug.
- **Qué cambio lo rompería sin que nadie se entere:** «unificar» la búsqueda con
  `.annotate(t=Replace(Cast("client_uuid", CharField()), Value("-"), Value(""))).filter(t=uuid.hex)` —el código que
  estuvo en `programas/api/views.py` entre el 21/08 y el 25/09—.
- **Propuesta:** en `core/tests/test_sql_motor_real.py`,
  `ColumnaSargableTests.test_las_busquedas_por_uuid_y_dni_no_envuelven_la_columna`: compila
  `relevamiento_publico_por_token(uuid4())`, `formulario_por_client_uuid(rel, uuid4())` y `dni_en_convocatoria(conv,
  "30111222")` con `_sql_mysql` y, para cada columna (`token_publico`, `client_uuid`, `dni_titular`),
  `assertNotRegex(sql, r"(REPLACE|CAST|LOWER|UPPER|CONCAT|TRIM)\s*\(\s*`?\w+`?\.`?<columna>`?")`. El nombre real de la
  función es `formulario_por_client_uuid` (RS-R2-02 decía otro).

### RED-09 · Un `UUIDField` nuevo sin `char(36)` pasa el CI; el único test de UUID se saltea siempre
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`UUIDExternosMySQLTests` → `OK (skipped=1)`) · **Origen:** RS-R2-03 parte (b) (VR1; la parte (a) es TST-01), RS-R6-20 (VR2: CONFIRMADO) · **Ola:** R (+3: mover el helper) · **Esfuerzo:** S-M (4 h) + S (2 h)
- **Ubicación:** `programas/tests/test_becas_models.py:38-70` (`skipTest` si `vendor != "mysql"`); 7 `UUIDField`:
  `programas/models/__init__.py:264, 1812, 2491, 2792`, `legajos/models/base.py:383`, `users/models/__init__.py:114`,
  `core/models/base.py:127`; `q_uuid_en_texto` (`programas/services/becas.py:155`) solo cubre `client_uuid` y `token_publico`.
- **Qué es frágil:** `CLAUDE.md` exige «todo `UUIDField` nuevo con su migración a `char(36)` y búsqueda con
  `q_uuid_en_texto`»: es una convención en un `.md`. El test que cubre las 9 columnas nunca corre (los jobs exportan
  `PYTEST_RUNNING=1`).
- **Qué cambio lo rompería sin que nadie se entere:** un modelo nuevo con `uuid = models.UUIDField(default=uuid4,
  unique=True)` y una vista que lo busca con `.get(uuid=valor)`: en MariaDB ≥ 10.7, «Data too long» en el alta y cero
  filas en la búsqueda (el incidente del 29/09).
- **Propuesta:**
  - **R:** `programas/tests/test_becas_models.py::UUIDExternosMySQLTests.test_todo_uuidfield_nuevo_esta_en_la_lista_ampliada`
    — recorre `apps.get_models()`, junta los `UUIDField` (incluido el pk de `TimeStamped`) y exige que cada uno esté en
    `COLUMNAS_UUID_AMPLIADAS` (lista literal con modelo, campo y migración que lo amplió, patrón `programas.0073`). Corre
    en SQLite. No usar la variante que parsea migraciones buscando `AlterField`/`RunSQL` (frágil, no cubre modelos
    nuevos). Y `core/tests/test_uuid_mariadb.py::test_las_busquedas_por_uuid_usan_el_helper`: lint AST sobre
    `**/services/*.py` y `**/views/*.py` que falla si un `filter(...)`/`get(...)` usa como kwarg un `UUIDField` de valor
    externo (`client_uuid`, `token_publico`) sin pasar por `q_uuid_en_texto`; lista blanca por pragma.
  - **Ola 3 (PR 7, con R0-07):** mover `q_uuid_en_texto` de `programas/services/becas.py` a `core/db.py` (hoy legajos y
    users tendrían que importarlo cruzado).

### RED-10 · Las dos escrituras que dieron 500 bajo el lock no tienen presupuesto de consultas
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura de los 23 presupuestos) · **Origen:** RS-R2-05 (VR1: CONFIRMADO) · **Ola:** R (`assertNumQueries`) + 4 (destinos del Performance Guard) · **Esfuerzo:** S (2 h) + S-M (4 h)
- **Ubicación:** `scripts/perf_audit.py:246-390` (`build_targets`, 23 destinos) y `scripts/perf_budgets.json`: no hay
  destino para `POST /portal/inscripcion/<token>/formulario/` (paso 2) ni para el alta por `/api/becas/`.
- **Qué es frágil:** las dos trabajan bajo el lock del relevamiento contra el `read_timeout` de 10 s y las dos ya rompieron
  o estuvieron al borde (Cambio 91: 165 × 500; Cambio 93: alta por API de 32 a 10 consultas). Ese trabajo no tiene ningún
  número que lo defienda.
- **Qué cambio lo rompería sin que nadie se entere:** agregar al alta de la API una lectura por caso (reconstruir la
  definición dentro del lock, re-resolver identidad): de 10 a 40 consultas bajo el lock, CI verde.
- **Propuesta:** **R:** `programas/tests/test_becas_api.py::AltaBajoElLockTests.test_el_alta_no_crece_en_consultas` con
  `assertNumQueries(<medido>)` alrededor del POST, y su gemelo
  `portal/tests/test_inscripcion_envio.py::Paso2ConsultasTests.test_el_envio_no_crece_en_consultas`. **Ola 4:** destinos
  `inscripcion_publica_paso2` (anónimo, sesión del paso 1, `client_uuid` nuevo, `expected_status: 302`) y `becas_api_alta`
  (Token de territorial, `201`, `max_duplicate_queries: 1`) en `build_targets` + filas en `perf_budgets.json` con
  justificación en `adjustments` (y RED-62 para que no se suban en silencio).

### RED-34 · Nada obliga a que una ficha cerrada deje un test permanente
**Severidad:** MEDIA (era ALTA: las PoC nunca se pensaron para correr; el hueco es de proceso) · **Estado:** CONFIRMADO con test (`unittest.defaultTestLoader.discover('docs')` → 0 tests) · **Origen:** RS-R2-04 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `docs/internal/auditoria-2026-10/poc/` (7 módulos, sin `__init__.py`); README §0.1 y §6 definen el cierre
  de cada ola como «las PoC invertidas pasan», una verificación manual que no deja guard.
- **Qué cambio lo rompería sin que nadie se entere:** cerrar SIIS-01 invirtiendo la PoC y mergear sin tocar
  `programas/tests/`: la ficha queda ✅ y la doble alta vuelve el día que alguien toque `siis_envio.py`.
- **Propuesta:** (1) línea obligatoria **«Test permanente: `<app>/tests/<archivo>::<Clase>.<test>`»** debajo de toda
  «Resolución:» de una ficha de `hallazgos/` (agregada a README §0.3); (2) `core/tests/test_contrato_auditoria.py::
  FichasCerradasTests.test_toda_ficha_resuelta_nombra_un_test_que_existe`: lee los `hallazgos/*.md`, toma las fichas con
  «Resolución: ✅» posteriores al 04-oct-2026 y exige que la ruta y la clase nombradas existan (import + `hasattr`). No
  mover las PoC al código (muchas afirman el bug).

### RED-35 · Ningún test afirma que las escrituras críticas sigan siendo atómicas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; 39 usos de `transaction.atomic` en los `services/`, 0 afirmados) · **Origen:** RS-R2-09 (VR1: CONFIRMADO-AJUSTADO: la aserción introspectiva propuesta siempre da `False`) · **Ola:** R (`resolver_ciudadano_offline`) + 3 (el resto de la lista) · **Esfuerzo:** S (2 h) + S-M (4 h)
- **Ubicación:** `programas/services/becas.py:261` (`@transaction.atomic` sobre `resolver_ciudadano_offline`); el Cambio 58
  registra que ese decorador **ya se perdió una vez** al extraer `_completar_contacto`.
- **Qué cambio lo rompería sin que nadie se entere:** mover `aprobar_formulario` o `resolver_ciudadano_offline` a otro
  módulo sin el decorador: un error entre el `save()` del ciudadano y el del formulario deja un ciudadano creado y
  `datos_identificacion` sin limpiar (duplicado silencioso).
- **Propuesta:** prueba **conductual**, no introspectiva (`getattr(fn, "_atomic")` no existe: `atomic` usa `@wraps`; y
  buscar «atomic» en el fuente da verde con un comentario): `core/tests/test_contrato_escrituras.py::EscriturasAtomicasTests.
  test_resolver_ciudadano_offline_no_deja_nada_a_medias` — `patch` del último paso para que lance, ejecutar, y afirmar
  que **nada quedó escrito** (`assertFalse(Ciudadano.objects.filter(dni=…).exists())` y el formulario sin cambios). Ola 3:
  el mismo patrón para `cupo.aprobar_formulario`, `inscripcion_publica.crear_formulario_publico`,
  `padron.quitar_padron_propio` y `admisiones.trasladar_admision`.

### RED-74 · Ocho arreglos mergeados sin ningún test
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura: `git show --stat` de cada uno) · **Origen:** RS-R2-10 (VR1: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación / evidencia:** `f866d052` (serie semanal, → RED-07), `a427bffe` (`completar_casos_renaper`, → RED-32),
  `0a785d75` (`0052` con `padron_archivo` NULL, → RED-17), `45686113` (`0047`, → RED-09), `057cce86` (`atomic` anidado en
  el alta de relevamiento: solo lo guarda un número de `perf_budgets.json`), `7feb9d83` (`_resumen_fijo_padron` sin
  sesión), `1ada8e41` (cubierto hoy por `test_becas_models.py:307`), `7f36ab06` (JS, sin pin).
- **Propuesta:** los cuatro primeros, con sus fichas. Para `057cce86`:
  `programas/tests/test_becas_relevamientos.py::AltaRelevamientoTests.test_el_alta_no_abre_una_transaccion_anidada`
  (`assertNumQueries` + `captureOnCommitCallbacks`). Para `7feb9d83`:
  `programas/tests/test_padron.py::ResumenFijoTests.test_tolera_un_request_sin_sesion` (`RequestFactory` sin middleware de
  sesión → `None`, no `AttributeError`).

## (c) Contratos, tipado y validaciones

Contrastado contra el clon real de la app de campo (`Chaco-mobile @ 765696a`, Expo SDK 54). La regla que hoy existe para
la UI («pieza canónica → mismo diff actualiza el agente») falta para la API, que es el borde con otro repo.

### RED-11 · Ningún test fija la forma del JSON de `/api/becas/*` que lee la app de campo
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura de los dos repos; VR1) · **Origen:** RS-R3-02 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/api/serializers.py:15-62` (`RelevamientoListSerializer`/`RelevamientoDetailSerializer`);
  consumidores `Chaco-mobile/src/services/relevamientoService.js:72-131` (`mapDjangoRelevamiento`, `mapDjangoRelevamientoDetail`).
- **Qué es frágil:** los 76 tests de `test_becas_api.py` verifican comportamiento, ninguno el **conjunto de claves** (no hay
  un solo `assertEqual(set(data.keys()), …)` en el repo). `convocatoria_nombre`, `formularios_count` y `cupo_completo`
  no aparecen en ningún test; `cupo_disponible` solo como property del modelo, nunca como clave de respuesta.
- **Qué cambio lo rompería sin que nadie se entere:** renombrar `convocatoria_nombre` → `convocatoria`
  (`serializers.py:18`): el teléfono muestra los relevamientos sin nombre de convocatoria (`relevamientoService.js:77,88`),
  sin error. Idem `formularios_count` → el contador de personas cargadas queda en 0; `nombre` → todos se llaman
  «Relevamiento».
- **Propuesta:** `programas/tests/test_becas_api_contrato.py::ContratoAppDeCampoTests` con constantes literales en el
  módulo y el comentario «la app de campo lee estas claves; agregar es seguro, renombrar o sacar es un release coordinado
  de Chaco-mobile»: `test_lista_de_relevamientos_tiene_exactamente_estas_claves`
  (`assertEqual(sorted(resp.json()["results"][0]), sorted(CLAVES_RELEVAMIENTO_LIST))`) · `test_detalle_agrega_definicion_formulario` ·
  `test_tipos_del_contrato` (`formularios_count` int; `cupo_completo` y `pausado` bool; `definicion_formulario` dict con
  `items`, `globales`, `requisitos`, `requiere_gps`, `canal`, `version`) · `test_formulario_creado_devuelve_id`
  (`relevamientoService.js:846`). Conjunto **exacto**, no `assertIn`.

### RED-12 · `definicion_formulario` y los prefijos `pg-`/`rn-`: contrato de dos repos sin serializer ni test
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura de los dos repos; 8 sitios Python con el prefijo literal) · **Origen:** RS-R3-04 (VR1: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h)
- **Ubicación:** `programas/services/becas.py:77-136` (`_campo_dict`, `definicion_formulario`), `programas/services/diseno.py:48,52`
  (escribe el prefijo), `:550-632` (`campo_dict`, `serializar`), `programas/services/respuestas.py:176,321,323` e
  `inscripcion_publica.py:195,198,199` (lo leen); `Chaco-mobile/src/services/definicionFormulario.js`
  (`legacyDesdeRespuestas`: `startsWith('pg-') ? 'globales' : 'requisitos'`).
- **Qué es frágil:** la estructura más rica del sistema (grupos → campos/textos con `clave`, `tipo_item`, `origen`,
  `vinculo`, `canal`, `condicion`, `opciones`, `presentacion`, `obligatorio`, `subsegmento_id`, `alcance`, `grupo`) se arma
  con literales de diccionario, sin serializer, `TypedDict`, esquema ni test de claves. El único test
  (`test_becas_api.py:148-158`) mira `requiere_gps` y dos textos con `any(...)`.
- **Qué cambio lo rompería sin que nadie se entere:** cambiar `pg-` por `preg-` en `diseno.py:48` (o agregar un tercer
  origen): el servidor sigue coherente consigo mismo y la app manda **todas** las respuestas de preguntas generales a
  `data["requisitos"]` (su `else` no distingue «no es `pg-`» de «no lo conozco»). El caso se crea con 201 y el alta en
  SIIS lee las respuestas del bucket equivocado (`respuestas_por_destino`).
- **Propuesta:**
  1. Constantes únicas en `programas/services/diseno.py` (`PREFIJO_PREGUNTA = "pg-"`, `PREFIJO_REQUISITO = "rn-"`,
     `PREFIJO_PROPIO = "cp-"`, `PREFIJO_GRUPO = "g-"`, `PREFIJO_TEXTO = "t-"`) usadas en los 8 sitios.
  2. `programas/tests/test_definicion_contrato.py::ContratoDefinicionFormularioTests`: `test_claves_de_un_campo` (pregunta
     global + requisito de segmento + de subsegmento + campo propio; `sorted(campo)` exacto contra `CLAVES_CAMPO`) ·
     `test_claves_de_un_grupo` · `test_claves_de_un_texto` · `test_prefijos_de_clave` (contra las constantes) ·
     `test_origen_y_canal_son_valores_del_enum` (`OrigenRequisito.values`, `CanalFormulario.values`; hoy `_campo_dict:93`
     cuela cualquier cosa con `getattr(..., OrigenRequisito.PREGUNTA)`).
  3. Puente con el móvil: comando `exportar_contrato_definicion` que escribe `docs/internal/contrato-definicion.json` (una
     definición de ejemplo, versionada) + `test_el_contrato_versionado_esta_al_dia` que falla si quedó viejo. El mismo
     JSON se copia a `Chaco-mobile` como fixture de `definicionFormulario.test.js` (tarea del repo móvil).

### RED-36 · `drf_spectacular` fuera de `INSTALLED_APPS`: `/api/docs/` y `/api/redoc/` dan 500
**Severidad:** MEDIA (era ALTA: las tres rutas están detrás de `login_required`; el 500 solo lo ve el personal) · **Estado:** CONFIRMADO con test (VR1: `/api/schema/` 200; `/api/docs/` y `/api/redoc/` → `TemplateDoesNotExist`; `"spectacular" in get_commands()` → `False`) · **Origen:** RS-R3-01 (VR1: CONFIRMADO-AJUSTADO), RS-R1-06 parte Spectacular · **Ola:** R (**primero**: desbloquea RED-37 y RED-43) · **Esfuerzo:** S (2 h)
- **Ubicación:** `config/settings.py:86-103` (`INSTALLED_APPS` sin `drf_spectacular`), `:417` (`DEFAULT_SCHEMA_CLASS`),
  `:634-641`; `config/urls.py:55-57`; `config/middlewares/security_headers.py:108` hasta tiene una excepción de CSP para
  `/api/docs/`.
- **Qué es frágil:** sin la app no existe `manage.py spectacular` (ningún gate de esquema es posible) y los templates de
  las vistas de documentación no se encuentran. `CLAUDE.md` las anuncia como superficie viva.
- **Propuesta:** `"drf_spectacular"` en `INSTALLED_APPS` junto a `rest_framework`. Test
  `core/tests/test_api_schema_contrato.py::EsquemaOpenApiTests.test_schema_docs_y_redoc_responden_200` (con sesión de
  backoffice 200; sin sesión 302 al login). Dejarlas detrás de `BackofficeAutenticado` es el resto de SEC-01 (Ola 2, PR 8).
- **Verificación:** `& $env:PY manage.py spectacular --validate --file NUL` termina sin excepción.

### RED-37 · El esquema OpenAPI publica tipos falsos y pierde 11 vistas
**Severidad:** MEDIA (nadie genera un cliente desde el esquema hoy; el daño es potencial) · **Estado:** CONFIRMADO con test (VR1 reprodujo exacto: 54 paths, 11 `Error [`, 24 `Warning`) · **Origen:** RS-R3-03 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R (puntos 1-2) + 7 (punto 3) · **Esfuerzo:** S-M (4 h) + S-M (4 h)
- **Ubicación:** `programas/api/serializers.py:21-22, 46-51, 55, 60-61` (`SerializerMethodField` sin anotar);
  `programas/api/views.py:215` (`consultar_persona_becas`, sin serializer de request); `dashboard/api_views/__init__.py:29,
  72, 99, 137, 210`.
- **Qué es frágil:** `RelevamientoDetail` publica `definicion_formulario`, `cupo_disponible`, `cupo_completo` y `pausado`
  como `string`; `/api/becas/personas/consultar/` sin `requestBody`; `/api/tendencias/` «No response body». Vistas
  perdidas: `actividad_reciente`, `alertas_criticas`, `buscar_ciudadanos`, `metricas_dashboard`, `tendencias_datos`,
  `consultar_persona_becas`, `run_phase2_tests_api`, `alertas_conversaciones_count`, `alertas_conversaciones_preview`,
  `marcar_mensajes_leidos`, `conversacion_detalle`.
- **Propuesta:** (1) anotar el retorno de los `get_*` del serializer (`def get_pausado(self, obj) -> bool:`, `-> int`,
  `-> dict`): drf-spectacular lee el hint y esto cumple también el paso 3 de RED-76; (2) `ConsultaPersonaSerializer` real
  (`dni`, `sexo` con `choices=("F","M")`, `relevamiento` opcional) que **reemplace** la validación manual de
  `views.py:216-223`, con `@extend_schema(request=…, responses=…)`; (3) Ola 7: `@extend_schema(responses=inline_serializer(...))`
  en las 5 vistas del dashboard y las de `core/views/performance.py` (si OPS-10 no las borra antes). Test
  `EsquemaOpenApiTests.test_el_esquema_se_genera_sin_errores`: `SchemaGenerator().get_schema(request=None, public=True)`
  capturando el logger `drf_spectacular`, falla si aparece un `Error [` fuera de `VISTAS_CON_ERROR_CONOCIDO` (las 11; la
  lista solo baja).

### RED-38 · Tres motores de condiciones sin vectores de prueba compartidos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; VR1 extrajo los 22 operadores de los tres y coinciden hoy) · **Origen:** RS-R3-05 (VR1: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h)
- **Ubicación:** `programas/services/condiciones.py:130-200` (autoridad), `static/custom/js/nodo-condiciones.js` (backoffice
  y link público), `Chaco-mobile/src/services/condiciones.js:84-121` (app); tests escritos por separado
  (`programas/tests/test_condiciones.py`, `Chaco-mobile/src/services/__tests__/condiciones.test.js`).
- **Qué es frágil:** coinciden por disciplina, no por construcción (el docstring de `condiciones.py:8` lo asume).
- **Qué cambio lo rompería sin que nadie se entere:** agregar un operador (p. ej. `contiene_texto`) en Python y en el
  editor: en la app `evaluarRegla` cae al `return false` final, el ítem condicionado nunca se muestra y una pregunta
  obligatoria queda sin responder; o el móvil descarta respuestas vía `respuestasEfectivas`.
- **Propuesta:** (1) `programas/fixtures/contrato_condiciones.json`: ~40 casos `{regla, valor, hoy, esperado}`, uno por
  operador más los bordes (fuente vacía con `no_adjuntado`, `edad_entre` invertido, `5` contra `"5"` en `es`,
  `incluye_alguno` con listas vacías, `lt` no numérico); (2) `programas/tests/test_condiciones.py::ContratoCompartidoTests.
  test_vectores_del_fixture` (`evaluar_regla(...) is esperado`) y `test_todo_operador_tiene_vector` (cada operador de
  `OPERADORES_POR_TIPO` aparece en el fixture); (3) el mismo JSON copiado a `Chaco-mobile` y consumido con `test.each`
  (tarea del repo móvil); (4) para `nodo-condiciones.js`, un paso de `node` en el job `contratos` (RED-43) que lo importe
  y corra el fixture.

### RED-39 · Cinco sobres de error JSON leídos con fallback silencioso
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; VR1 reprodujo el conteo: `error` 79 · `message` 38 · `mensaje` 17 · `detail` 14 · `errors` 5) · **Origen:** RS-R3-08 (VR1: CONFIRMADO) · **Ola:** R (helper y 2 tests) + 7 (migrar las vistas) · **Esfuerzo:** S (2 h) + M (8 h)
- **Ubicación:** consumidores `programas/templates/programas/becas/_ajax_js.html:180,187,189`, `static/custom/js/nodo-constructor.js:133`
  (`data.message ||`), `legajos/templates/legajos/ciudadano_detail.html:1644,1647`, `users/templates/user/_alta_rapida_modal.html:130`.
- **Qué cambio lo rompería sin que nadie se entere:** normalizar `programas/views/diseno.py:243` de `message` a `detail`
  (la convención de DRF): el constructor muestra «No se pudo guardar. Recargá la página.» en vez del motivo real, y el
  coordinador no entiende por qué no puede guardar.
- **Propuesta:** helper `core/http.py::error_json(mensaje, *, status=400, errores=None)` → `{"ok": False, "message", "errors"}`
  y `ok_json(**datos)`; tests `core/tests/test_contrato_errores_ajax.py::SobreDeErrorTests.test_el_constructor_devuelve_el_motivo_en_message`
  (POST que dispara la validación de `diseno.py:485-487` → 400 y `"catálogo" in resp.json()["message"]`) y
  `test_subir_archivos_devuelve_el_motivo_en_mensaje` (legajos, con la clave de hoy). Ola 7: migrar por app empezando por
  `diseno.py` y `legajos/views/contactos_api.py`, y regla WARN en `design_audit.py` para `data.mensaje|detail|errors`.

### RED-40 · `JSONField` con estructura implícita: 0 `validators` y nada sobre datos viejos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R3-09 (VR1: CONFIRMADO) · **Ola:** R (diagnóstico y datos viejos) + 3 (validators, con G1-05) · **Esfuerzo:** S-M (4 h) + S (2 h)
- **Ubicación:** `programas/models/__init__.py`: `Formulario.data:2587`, `.respuestas:2594`, `.definicion:2595`,
  `.datos_identificacion:2598`, `.datos_siis:2614`, `ItemDiseno.condicion:3081`, `.propio:3114`,
  `GrupoRequisito.condicion_defecto:2136`. `validar_condicion` (`condiciones.py:235`) solo se invoca desde el form y la
  vista del constructor.
- **Qué cambio lo rompería sin que nadie se entere:** renombrar `presentacion` → `modo_presentacion` en
  `ItemDiseno.propio` (`diseno.py:567`): los ítems viejos leen `propio.get("presentacion", "LISTA")` y **todos los
  selectores propios ya guardados vuelven a «LISTA»**.
- **Propuesta:** **R:** comando de solo lectura `verificar_json_guardado --json` (condiciones con operadores fuera de
  `OPERADORES_POR_TIPO`, `propio` sin `tipo`, `definicion` con `version` vieja, `datos_siis` con claves que `armar_payload`
  no consume) para correr contra el dump de PRD **antes** de cualquier cambio de forma; test
  `programas/tests/test_json_compatibilidad.py::DatosViejosTests` con un `propio` y una `definicion` de la forma anterior
  al Cambio 58 (listas planas `globales`/`requisitos`, sin `items`) que afirma que revisión, Excel y `definicion_formulario`
  los siguen leyendo. **Ola 3:** `validators=[validar_condicion_json]` en `ItemDiseno.condicion` y
  `GrupoRequisito.condicion_defecto`.

### RED-41 · Parsers de RENAPER, Personas y SIIS probados contra diccionarios inventados
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R3-10 (VR1: CONFIRMADO-AJUSTADO con reserva de datos personales) · **Ola:** R · **Esfuerzo:** S-M (4 h) · **Decisión:** D-RED-04
- **Ubicación:** `legajos/services/consulta_renaper.py:314-327, 449-486`; `programas/services/personas.py:29-79`;
  `programas/services/siis.py:87-90, 145-174, 240-245, 312-321, 371-381`; tests con dicts escritos a mano
  (`programas/tests/test_personas_service.py`, `test_diagnosticar_integraciones.py`; `legajos/tests/test_renaper_api.py`
  tiene un solo test y es sobre una URL que ya no existe).
- **Qué es frágil:** ~20 claves de upstream leídas con `.get()` y default silencioso. Los dos únicos lugares con una
  respuesta realista **discrepan** en el formato de la misma clave (`fechaNacimiento` `08/05/1992` en uno, `1990-01-02` en
  otro). El parser de RENAPER ya mira `isSuccess` y `success` (el proveedor ya cambió una vez).
- **Qué cambio lo rompería sin que nadie se entere:** que lo cambie el **proveedor**: si `result` se anida un nivel,
  `consultar_renaper` devuelve `{"success": True, "data": {}}` y el caso se marca **validado** con nombre vacío.
- **Propuesta (default D-RED-04 = sintético):** **no** grabar respuestas reales sin aprobación explícita (icore tiene datos
  reales y `ENVIRONMENT=prd`). Un fixture **sintético acordado**, un JSON por servicio y rama en
  `programas/fixtures/contratos/{renaper_ok,renaper_fallecido,personas_ok,personas_no_encontrada,siis_alta_ok,siis_rechazado}.json`,
  escrito a mano con la estructura documentada (domicilio anidado incluido) y valores inventados, **compartido** por todos
  los tests. `programas/tests/test_contratos_externos.py::ContratoUpstreamTests`: `test_renaper_ok` (ningún campo vacío),
  `test_renaper_fallecido`, `test_personas_no_encontrada`, `test_siis_alta_ok`, `test_siis_rechazado`,
  `test_personas_no_toma_claves_anidadas` (el de SIIS-10), `test_toda_clave_leida_existe_en_el_fixture`. Si el PM aprueba
  grabar: `diagnosticar_integraciones --grabar <dir>` **solo** con `RENAPER_TEST_MODE=1` contra el DNI de prueba de
  `test_diagnosticar_integraciones`, anonimizando valores y con revisión antes de versionar.

### RED-42 · Endpoints JSON del backoffice sin contrato; 4 `fetch` literales resuelven 404
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`django.urls.resolve` sobre las URLs literales) · **Origen:** RS-R3-11 (VR1: CONFIRMADO; 3 de las 4 URLs ya están en LEG-03/LEG-06) · **Ola:** R (los tests) + 5 (literales → `{% url %}`) · **Esfuerzo:** S-M (4 h) + S (2 h)
- **Ubicación:** `templates/inicio.html:909,938` → `dashboard/api_views/__init__.py:72-97` (`results`, `has_more`), `:210-250`
  (`labels`, `datos`); `legajos/views/alertas.py:86-94` (`count`, `criticas`: **las claves son los kwargs de un
  `aggregate()`**) → `static/custom/js/alertas_conversaciones_simple.js:47`, `alertas_websocket.js:292`.
- **Qué cambio lo rompería sin que nadie se entere:** renombrar `count=Count("id")` a `total=Count("id")` en
  `alertas.py:89-91`: el badge de alertas del navbar queda en 0 para todo el backoffice (`data.count || 0`). Renombrar
  `has_more`: el buscador del inicio pierde el aviso de «hay más».
- **Evidencia:** `404` para `/api/legajos/contactos/vinculos-familiares/` (LEG-03), `/legajos/1/contactos/api/` y
  `/legajos/contactos/1/detalle/` (`historial_contactos.html:334,445`, LEG-06) y `/set_dark_mode/` (RED-75).
- **Propuesta:** `core/tests/test_urls_del_front.py::UrlsDelFrontTests.test_todo_fetch_literal_resuelve`: recorre
  `templates/`, `*/templates/` y `static/**/*.js`, extrae los literales de `fetch("/…")` y `$.ajax({url: "/…"})` sin
  `{{`/`${`, normaliza segmentos numéricos y afirma que `resolve` no levanta `Resolver404`, con allowlist inicial de los 4
  conocidos (ratchet). `dashboard/tests/test_api_contrato.py::ContratoDashboardTests`: `test_buscar_ciudadanos_tiene_results_y_has_more`,
  `test_tendencias_tiene_labels_y_datos` (`len(labels) == len(datos) == dias`), `test_alertas_count_tiene_count_y_criticas`.
  Ola 5: reemplazar literales por `{% url %}` donde el template lo permita (`inicio.html:853-855` es el patrón).

### RED-43 · El CI no tiene ningún gate de contrato de API
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura: `grep -rn "spectacular\|schema\|openapi\|mypy\|contrato" .github/workflows/` → un comentario) · **Origen:** RS-R3-12 (VR1: CONFIRMADO) · **Ola:** R (después de RED-11, 12, 36, 37, 38, 42) · **Esfuerzo:** S (2 h)
- **Propuesta:** job nuevo en `.github/workflows/pr-backend.yml` (no necesita MySQL):
  ```yaml
  contratos-api:
    name: Contratos de API
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env: { DJANGO_SECRET_KEY: test-key, PYTEST_RUNNING: "1", DJANGO_SYNCDB_PROJECT_APPS: "True" }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip, cache-dependency-path: requirements.txt }
      - run: sudo apt-get install -y default-libmysqlclient-dev && pip install -r requirements.txt
      - run: python manage.py spectacular --validate --file /dev/null
      - run: >
          python manage.py test core.tests.test_api_schema_contrato programas.tests.test_becas_api_contrato
          programas.tests.test_definicion_contrato programas.tests.test_contratos_externos
          core.tests.test_urls_del_front dashboard.tests.test_api_contrato
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: node scripts/check_condiciones_js.mjs   # corre el fixture de RED-38 contra nodo-condiciones.js
  ```
  **Sin `--fail-on-warn`** en el primer PR (hoy hay 24 warnings: nacería rojo); se agrega cuando la allowlist de RED-37
  esté vacía. Sumar `Contratos de API` a los checks obligatorios (RED-20) y a `CLAUDE.md` la regla «tocar
  `programas/api/serializers.py` o `definicion_formulario` obliga a actualizar el test de contrato en el mismo diff».

### RED-44 · Una capacidad mal tipeada devuelve `False` en silencio y el superusuario no lo ve
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (prototipo de RS-R6: hoy las 67 capacidades del `CATALOGO` aparecen como literal y no hay huérfanos) · **Origen:** RS-R6-14 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `core/rbac.py:577-593` (`puede`), `:385-388` (`codigos_de_capacidad`).
- **Qué cambio lo rompería sin que nadie se entere:** renombrar `becas.cupo.ver` en el `CATALOGO` y actualizar 4 de los 5
  usos: el quinto evalúa una capacidad inexistente, la pantalla desaparece para todos los roles y el admin (bypass de
  `is_superuser`) la sigue viendo.
- **Propuesta:** `users/tests/test_rbac_contrato.py`: `test_toda_capacidad_evaluada_existe_en_el_catalogo` (extrae los
  literales de `@requiere("…")`, `puede(…, "…")`, `puede_alguna(…, [...])`, `capacidades_requeridas` y los tags de
  template en `**/*.py` y `**/templates/**/*.html`; mensaje con archivo:línea y `difflib.get_close_matches`) y
  `test_toda_capacidad_del_catalogo_se_usa_o_esta_declarada_sin_uso` (`CAPACIDADES_SIN_USO = {"ciudadano.eliminar"}`,
  OPS-14). Hoy pasan los dos: el test es gratis.

### RED-75 · `/set_dark_mode/` no existe: el toggle de tema postea a un 404
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO con test (`resolve("/set_dark_mode/")` → `Resolver404`) · **Origen:** RS-R3-06 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** 5 (el gate es RED-42) · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-07
- **Ubicación:** `static/custom/js/base.js:64-77` (`sendThemePreference`); `users/models/__init__.py:19` (`dark_mode`,
  `default=True`, nunca escrito desde la UI); `users/serializers/__init__.py:27`.
- **Qué es frágil:** el `.fail()` lo tapa con un `console.warn`; cada cambio de tema es un 404 en los logs y cualquier
  trabajo futuro que lea `Profile.dark_mode` va a leer siempre `True`.
- **Propuesta (default D-RED-07 = A):** borrar `sendThemePreference` y su llamada, y sacar `dark_mode` de
  `ProfileSerializer`; test `users/tests/test_tema.py::TemaTests.test_el_shell_no_postea_la_preferencia_de_tema` (patrón de
  `core/tests/test_modern_modal_contrato.py`) y sacar la URL de la allowlist de RED-42. Opción B: vista `POST
  /usuarios/tema/` con `@login_required` y sus tests (200 y perfil actualizado; GET 405; anónimo 302).

### RED-76 · Tipado: 2,7 % de retornos anotados, sin mypy ni pyright
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO con test (AST de RS-R3 sobre 2.195 funciones; `programas`: 5 de 1.117) · **Origen:** RS-R3-07 (VR1: CONFIRMADO-AJUSTADO; el paso 3 va en RED-37) · **Ola:** 7 · **Esfuerzo:** S-M (4 h; la adopción completa es gradual y no se planifica)
- **Qué es frágil:** SIIS-11 (`body.get` sobre una lista) y G1-06 (fecha cruda al ORM) son errores de tipo que un checker
  gradual habría marcado en el diff.
- **Propuesta:** `requirements-dev.txt` (fuera de la imagen) con `mypy==1.14.1`, `django-stubs[compatible-mypy]==5.1.3`,
  `djangorestframework-stubs[compatible-mypy]==3.15.2`; en `pyproject.toml`, `[tool.mypy]` laxo (`ignore_missing_imports`,
  `follow_imports = "silent"`, `exclude` de migraciones/tests/venv) con `plugins = ["mypy_django_plugin.main",
  "mypy_drf_plugin.main"]`, `[tool.django-stubs] django_settings_module = "config.settings"` y un
  `[[tool.mypy.overrides]]` estricto (`disallow_untyped_defs`, `warn_return_any`, `no_implicit_optional`) que arranca con
  `programas.services.condiciones` y `programas.services.personas` y solo crece (un módulo por PR: después
  `programas.api.serializers`, `becas`/`diseno` con `TypedDict` para la definición, `siis`/`siis_envio`). Job en
  `pr-quality.yml` con `continue-on-error: true` hasta que estén los cinco módulos. RED-63 explica por qué antes de esto
  rinde más `ruff --select F` bloqueante.

## (d) Duplicación, dependencias ocultas y acoplamiento

Medido con `pylint --enable=duplicate-code`, `radon` y un detector AST propio de clones y de grafo de imports (RS-R4).
Fan-in máximo: `programas/models/__init__.py` (90 módulos); 3 ciclos de import; 63 funciones de 60 líneas o más.
RS-R4-01 quedó refutado (README §8.3). Regla para este bloque: **los tests van antes del refactor y nunca en el mismo PR
que un cambio funcional.**

### RED-13 · El shell de todo el backoffice y `legajos.ready()` dependen de `conversaciones`
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-03 (VR2: CONFIRMADO), RS-R4-13 (VR2: CONFIRMADO; «las dos mitades de apagar `conversaciones`, un solo PR») · **Ola:** R (test de caracterización) + 7 (con G1-01 fase 2) · **Esfuerzo:** S (2 h) + M (8 h)
- **Ubicación:** `templates/includes/base.html:371-396` (5 `{% url %}` a `conversaciones` en el shell que extiende todo el
  backoffice, `:378-382`); `config/settings.py:195` (`conversaciones.context_processors.user_groups` provee
  `user_groups_list`, `user_primary_group`, `user_is_superuser` y `websockets_enabled`, que **no son de conversaciones** y
  usan `base.html` y `templates/includes/sidebar/opciones.html:30-31`); `core/context_processors.py:34-42`;
  `legajos/apps.py:9-10` → `legajos/signals/alertas.py:4` (`from conversaciones.models import Mensaje`).
- **Qué es frágil:** la ficha G1-01 fase 2 (Ola 7, estimada en 2 h) no nombra el shell, el context processor ni la señal.
- **Qué cambio lo rompería sin que nadie se entere:** desmontar `conversaciones.urls` sin tocar `base.html` →
  `NoReverseMatch` en el shell: **500 en todas las pantallas a la vez**. Quitar solo la línea del context processor: peor
  que un 500, `window.isSuperuser` pasa a `false` y `websockets_enabled` a falso sin aviso. Sacar `"conversaciones"` de
  `INSTALLED_APPS`: `ImportError` en `legajos.ready()` y la app no arranca en el deploy.
- **Propuesta:**
  - **R:** `core/tests/test_shell_backoffice.py::ShellSinConversacionesTests.test_inicio_renderiza_sin_urls_de_conversaciones`
    con `@override_settings(ROOT_URLCONF="core.tests.urls_sin_conversaciones")` (copia de `config.urls` sin los dos
    includes) → `GET /inicio/` = 200. Hoy falla: entra con `@unittest.expectedFailure` («RED-13, se invierte en G1-01
    fase 2»). Es el criterio de «hecho» de la fase 2.
  - **Ola 7 (antes del apagado, PR propio):** mover `user_groups` a `core/context_processors.py` como `identidad_usuario`;
    sacar de `base.html` el bloque `window.conversacionesConfig` y los 3 `<script>` a un include condicional; mover
    `alerta_mensaje_ciudadano` a `conversaciones/signals/`; test `legajos/tests/test_signals_package.py::
    IndependenciaTests.test_legajos_no_importa_conversaciones` (AST: ningún `import conversaciones` a nivel de módulo en
    `legajos/**`). G1-01 fase 2 queda en 2 h + estas 8 h.

### RED-45 · `GUNICORN_CMD_ARGS` con gevent activa un parche que apaga `validate_thread_sharing`
**Severidad:** MEDIA (era ALTA: hoy nadie lo activa) · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-02 (VR2: CONFIRMADO) · **Ola:** R (test y guarda) + 7 (borrado, dentro de OPS-13) · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-08
- **Ubicación:** `config/wsgi.py:13-17` (`if "gevent" in os.environ.get("GUNICORN_CMD_ARGS", "") …`);
  `config/gevent_patch.py:19-25` (`BaseDatabaseWrapper.validate_thread_sharing = patched_validate`, que no hace nada);
  `docker-entrypoint.sh:115-123` (sin `--worker-class`: la única perilla es la variable); `gevent` y `greenlet` están en
  `requirements.txt`.
- **Qué cambio lo rompería sin que nadie se entere:** ante los 504 del padrón, alguien prueba en ECOM
  `GUNICORN_CMD_ARGS="--worker-class gevent"`: gevent real, sin `monkey.patch_all()` (mysqlclient y requests siguen
  bloqueando) y **sin** el chequeo de hilos. Resultado: respuestas con datos de otra request, intermitentes.
- **Propuesta:** **R:** `config/tests/test_wsgi_runtime.py::GeventTests.test_nadie_piso_validate_thread_sharing`
  (`BaseDatabaseWrapper.validate_thread_sharing.__module__.startswith("django.")`, pasa hoy) y, en `docker-entrypoint.sh`,
  abortar si `GUNICORN_CMD_ARGS` contiene `worker-class`. **Ola 7 (default D-RED-08):** borrar `config/gevent_patch.py` y
  las líneas 12-17 de `wsgi.py` junto con `gevent`/`greenlet` (OPS-13), y sumar al test
  `assertFalse(Path("config/gevent_patch.py").exists())`.

### RED-46 · `programas/models/__init__.py` sin tests de contrato
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO con test (`radon`: 3.252 líneas, MI 0.00; fan-in 90) · **Origen:** RS-R4-04 (VR2: CONFIRMADO) · **Ola:** R (los tests; el corte del archivo no se planifica) · **Esfuerzo:** S-M (4 h)
- **Qué cambio lo rompería sin que nadie se entere:** partir el archivo en `becas.py`/`dispositivos.py`/`merenderos.py`
  (90 importadores): un nombre que el `__init__.py` de compatibilidad no re-exporte falla en runtime, no al importar; y un
  modelo que cambie de app label rompe las migraciones de forma irreversible en PRD.
- **Propuesta:** `programas/tests/test_models_contrato.py`: `ExportsTests.test_nombres_publicos_estables` (lista literal de
  los ~60 nombres en mayúscula de `dir(programas.models)`) · `AppLabelTests.test_todos_los_modelos_siguen_en_programas`
  (`app_label == "programas"` y `db_table == TABLAS[m.__name__]`, mapa literal) · `PropiedadesDeNegocioTests` (valores
  concretos de `Segmento.cupo_disponible`, `Relevamiento.cupo_utilizado/cupo_disponible/cupo_completo`,
  `Convocatoria.pausa_efectiva` heredada, `Relevamiento.habilitado_en` con `date` y `datetime`,
  `Formulario._dni_titular_actual` con y sin ciudadano). El corte en sí (L) queda como deuda opcional: con estos tests es
  seguro hacerlo cuando se decida, nunca en un PR con cambios funcionales.

### RED-47 · `normalizar_dni` y sus tres copias agregan un 0 con `float` o `Decimal`
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (VR2 reprodujo la tabla de las cuatro funciones) · **Origen:** RS-R4-05 (VR2: CONFIRMADO-AJUSTADO), RS-VR2-NEW-02 · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** canónica `programas/services/padron.py:59-64` (`if isinstance(valor, float) and valor.is_integer()`);
  copias `completar_casos_renaper.py:109-110` (`_solo_digitos`), `corregir_datos_siis.py:66-67` (`_digitos`),
  `siis_envio.py:259-260` (`_digitos`), `programas/api/serializers.py:168` (inline).
- **Qué es frágil:** `30123456.0` → `301234560` en las tres copias; con `Decimal("30123456.0")` —lo que devuelve el driver
  para una columna `DECIMAL` de la tabla `ciudadanos_renaper`, que crea un script externo— **falla también la canónica**.
- **Qué cambio lo rompería sin que nadie se entere:** ya pasa: si esa columna quedó `DECIMAL`, `corregir_datos_siis`
  (`_fechas_de_renaper:174`, `_localidades_corregidas:197`) no cruza ninguna fila e informa «0 corregidos».
- **Propuesta:** en `padron.py`, `from decimal import Decimal` y `if isinstance(valor, (float, Decimal)) and valor ==
  int(valor): valor = int(valor)`; en los tres sitios, `_digitos = normalizar_dni` / `_solo_digitos = normalizar_dni` como
  alias local. Test `programas/tests/test_padron.py::NormalizarDniTests`: `test_las_cuatro_puertas_normalizan_igual`
  (`subTest` sobre `[30123456.0, Decimal("30123456.0"), "30.123.456", " 30123456 ", "M30123456", None]`) y
  `test_float_y_decimal_no_agregan_un_cero` (hoy falla con `Decimal`).

### RED-48 · «DNI válido» está implementado 6 veces con 3 reglas de largo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; VR2 verificó 6 de las 7 que nombraba el informe) · **Origen:** RS-R4-06 (VR2: CONFIRMADO) · **Ola:** 3 (con G1c-08) · **Esfuerzo:** S-M (4 h)
- **Ubicación:** `programas/api/serializers.py:169` y `programas/forms.py:745` (7 u 8), `programas/services/padron.py:182`
  (7 u 8: si no, **fila descartada en silencio**), `portal/forms/inscripcion.py:41,311` (7 u 8),
  `legajos/services/ciudadanos.py:20` (exactamente 8), `programas/services/siis_envio.py:450` (hasta 10).
- **Qué cambio lo rompería sin que nadie se entere:** aceptar DNI de 9 dígitos en el portal y el serializer: el padrón sigue
  descartando esas filas con un contador, y `siis_envio` deja pasar a SIIS lo que los formularios rechazan.
- **Propuesta:** `LARGOS_DNI_VALIDOS = (7, 8)` y `dni_valido(valor) -> bool` en `padron.py`, usados por las seis puertas
  (documentar en el test si `siis_envio` queda más laxo a propósito). Test `programas/tests/test_padron.py::DniValidoTests.
  test_misma_regla_en_todas_las_puertas` sobre `["123456", "1234567", "12345678", "123456789"]`.

### RED-49 · `cupo_disponible` significa tres cosas y dos pantallas lo rotulan igual
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura + templates) · **Origen:** RS-R4-07 (VR2: CONFIRMADO) · **Ola:** R (test) + 4 (renombre, con PERF-02) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `Segmento.cupo_disponible` (`models/__init__.py:1582`, cupo sin repartir entre subsegmentos),
  `Relevamiento.cupo_disponible` (`:2017-2019`), `get_cupo_stats()["cupo_disponible"]` (`services/cupo.py:16-27`, lugares
  libres reales); pantallas `becas/config/segmento_detail.html:147,298` y `becas/cupo/segmento_detail.html:24-27`.
  `CupoSegmento.cupo_ocupado` es un contador que nadie actualiza y `Segmento.clean:1561-1563` valida contra él.
- **Qué cambio lo rompería sin que nadie se entere:** «unificar» la property con `get_cupo_stats` al hacer PERF-02 cambia
  el número de la pantalla de configuración y la validación de `subsegmento_form.html:11,17`.
- **Propuesta:** **R:** `programas/tests/test_cupo.py::TresCuposTests.test_las_tres_acepciones_son_distintas` con los
  nombres de hoy (segmento `cupo_maximo=10`, subsegmentos de 3 y 4, 6 APROBADO: `Segmento.cupo_disponible == 3` y
  `get_cupo_stats(...)["cupo_disponible"] == 4`). **Ola 4:** renombrar, no unificar (`cupo_sin_distribuir`,
  `cupos_libres_del_relevamiento`; `cupo_disponible` queda solo para `get_cupo_stats`) y actualizar el test.

### RED-50 · La edad (RN-22) está cuatro veces y tres usan `date.today()`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; la TZ real de los contenedores de ECOM es la pregunta H-13) · **Origen:** RS-R4-08 (VR2: CONFIRMADO-AJUSTADO), RS-VR2-NEW-04 · **Ola:** R (test) + 3 (arreglo y regla de ruff) · **Esfuerzo:** S (2 h) + S-M (4 h)
- **Ubicación:** `programas/services/becas.py:211-219` (`es_menor`), `condiciones.py:115-121` (`edad_en_anios`),
  `siis_envio.py:280-281,439` (`_edad`, lo que viaja a SIIS), `corregir_datos_siis.py:70-71,496` (la única con
  `timezone.localdate()`); `legajos/selectors/ciudadanos.py:34,73` (contador «inscripciones de hoy» de la home) y
  `legajos/models/base.py:227`. Ni `Dockerfile`, ni compose, ni `docker/k8s/*.yaml` definen `TZ`: los contenedores corren
  en UTC y `date.today()` es el día siguiente entre las 21:00 y las 24:00 ART.
- **Qué cambio lo rompería sin que nadie se entere:** nada, ya pasa: un caso cargado a las 22:00 la víspera de los 18 años
  se evalúa mayor (no exige apoderado, RN-22), y la home cuenta las inscripciones de mañana todas las noches. En los tests
  no se ve (Windows en ART).
- **Propuesta:** **R:** `programas/tests/test_becas_reglas.py::EdadHorarioTests.test_el_corte_es_la_fecha_local_no_la_del_sistema`
  (`patch` de `timezone.now()` a `2026-07-01T02:00Z` y de `date.today()` a `2026-07-01`; nacido el `2008-07-01` sigue
  menor) con `expectedFailure` hasta el arreglo. **Ola 3:** una sola `edad_en_anios(fecha, hoy=None)` con
  `hoy = hoy or timezone.localdate()` y `MAYORIA_DE_EDAD = 18` en un lugar; `timezone.localdate()` en los sitios de
  `legajos`; regla `DTZ011` (flake8-datetimez) en `pyproject.toml` para `programas/`, `legajos/`, `portal/` con `# noqa`
  donde sea deliberado.

### RED-51 · Dos `invalidate_dashboard_cache`; `stats_legajos` colgado del modelo equivocado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-11 (VR2: CONFIRMADO) · **Ola:** R (tests) + 4 (arreglo) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `dashboard/utils.py:98-106` (5 claves; solo la llama `CiudadanosService.invalidate_ciudadanos_cache`, que
  no tiene llamadores); `core/performance/cache_utils.py:33-57` (mismo nombre, 2 claves, **cableada** por señales de
  `Ciudadano` y `User`); `legajos/signals/core.py:13-16` (invalida `stats_legajos` al guardar `LegajoAtencion`), pero
  `stats_legajos` lo escribe `contar_legajos()` sobre `InscripcionPrograma` (`dashboard/utils.py:60-71`).
- **Qué cambio lo rompería sin que nadie se entere:** la limpieza de OPS-10 «deduplica» las dos funciones y se desconectan
  los únicos receivers que mantienen frescos los contadores de la home. En PRD el cache es Redis compartido; en tests,
  LocMem: esta familia de bugs es invisible para la suite.
- **Propuesta:** **R:** `dashboard/tests/test_cache_invalidacion.py::InvalidacionTests`:
  `test_ciudadano_nuevo_invalida_contar_ciudadanos` (pasa hoy) · `test_inscripcion_nueva_invalida_stats_legajos` y
  `test_alerta_nueva_invalida_alertas_activas` (hoy fallan: `expectedFailure`). **Ola 4:** `dashboard/cache.py` con las
  claves como constantes y el mapa `{modelo: [claves]}`; receiver de `stats_legajos` con `sender=InscripcionPrograma`;
  `test_no_quedan_dos_funciones_llamadas_invalidate_dashboard_cache`.

### RED-52 · Contrato implícito por `user._state.fields_cache["profile"]`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; 5 usos) · **Origen:** RS-R4-12 (VR2: CONFIRMADO-AJUSTADO) · **Ola:** R (tests) + 2 (PR 2, usuarios) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `users/middleware.py:16-20` (`get_or_create` del Profile en cada GET y `fields_cache["profile"] = profile`),
  `:38-39,50` (`CambioContrasenaObligatorioMiddleware` depende de eso); `users/signals/profiles.py:16-21` (`post_save(User)`
  guarda el Profile **completo** si está en caché); `users/services/correo.py:76`; `users/services/admin.py:104`;
  `config/settings.py:137-138` (el orden de los middlewares, sin test).
- **Qué cambio lo rompería sin que nadie se entere:** reordenar `MIDDLEWARE` o borrar la línea del `fields_cache` (parece
  una micro-optimización): `save_user_profile` deja de propagar en silencio. Y cualquier `user.save()` durante un request
  reescribe la fila del Profile con lo leído al inicio (lost update de `backoffice_session_key`).
- **Propuesta:** **R:** `users/tests/test_middleware_profile.py`: `OrdenMiddlewareTests.test_single_session_va_antes_que_cambio_de_clave` ·
  `ProfileEnCacheTests.test_el_gate_de_clave_no_consulta_el_profile` (`assertNumQueries(N)` de hoy sobre `GET /inicio/`) ·
  `ProfileEnCacheTests.test_user_save_no_pisa_la_clave_de_sesion_de_otro_login` (hoy falla: `expectedFailure`). **Ola 2:**
  reemplazar `save_user_profile` por guardados explícitos o acotarlo con `update_fields`.

### RED-53 · Clones literales entre los comandos SIIS y entre las vistas de padrón
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (pylint `R0801`: 14 grupos a 5 líneas; AST: 15 grupos, peso máximo 128) · **Origen:** RS-R4-16 (VR2: CONFIRMADO) · **Ola:** 1 (comandos, dentro del PR 2 o 3) + 5 (vistas) · **Esfuerzo:** S-M (4 h) + S (2 h)
- **Ubicación:** `enviar_casos_siis.py:76-86` ≡ `validar_casos_siis.py:58-68` (`add_arguments`); `:178-198` ≡ `:109-129`;
  bloques de latido y corte por errores entre `enviar_casos_siis.py` y `procesar_casos_siis.py`; resumen final `:283-295` ≡
  `:199-211`; `relevamientos.py:932-953` ≡ `:967-988` (subida de padrón); `dispositivos_config.py:48-61` ≡
  `dispositivos_legajo.py:38-51`; `padron.py:466-479` ≡ `revision.py:1226-1239`.
- **Qué cambio lo rompería sin que nadie se entere:** SIIS-03 agrega el candado de corrida viva a `enviar_casos_siis` y
  `procesar_casos_siis` pero no a `validar_casos_siis`, que comparte el 80 % del código: otra «séptima vía».
- **Propuesta:** **Ola 1:** `programas/management/commands/_base_siis.py::ComandoSiisBase(BaseCommand)` con `add_arguments`
  comunes, `_solicitante`, `_lotes`, latido y resumen; los cuatro comandos heredan; test
  `programas/tests/test_comandos_siis_caracterizacion.py::ParidadTests.test_los_cuatro_comandos_aceptan_los_mismos_flags`;
  paso no bloqueante en CI `pylint --disable=all --enable=duplicate-code --min-similarity-lines=8` con el conteo de hoy
  (4 grupos) como techo. **Ola 5:** `_subir_padron(request, duenio, destino, prefijo="")` en `relevamientos.py`. La
  duplicación de `_sin_formularios_publicos_si_no_puede` y `_assert_scope` se resuelve con RED-79.

### RED-54 · `revision.py`: ningún test fija el contexto del detalle
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`radon`: 1.331 líneas, MI 5.84; `formulario_detalle` CC 26; fan-out 16) · **Origen:** RS-R4-17 (VR2: CONFIRMADO) · **Ola:** R (antes de la Ola 1) + 7 (refactor) · **Esfuerzo:** S-M (4 h) + M (8 h)
- **Ubicación:** `programas/views/revision.py:614` (`formulario_detalle`, 155 líneas, ~30 claves de contexto que consume
  `formulario_detalle.html`, 1.079 líneas).
- **Qué cambio lo rompería sin que nadie se entere:** las Olas 1, 2, 3 y 5 tocan esta vista (SIIS-01, SEC-21, BEC-09, FE-07):
  una clave que deje de ponerse en el contexto se renderiza como cadena vacía y la sección desaparece sin 500 ni test rojo.
- **Propuesta:** **R:** en `programas/tests/test_becas_revision.py`, `ContextoDetalleTests.test_claves_del_contexto_del_detalle`
  (caso ENVIADO completo con adjuntos, respuestas, un `EnvioSIIS` fallido y una `ValidacionSIS`;
  `assertEqual(sorted(response.context.flatten()), CLAVES)`) · `test_detalle_de_caso_minimo_no_rompe` ·
  `ConsultasDetalleTests.test_presupuesto_de_consultas` (`assertNumQueries(N)` de hoy). **Ola 7:** extraer
  `contexto_identidad`, `contexto_siis`, `contexto_respuestas` a `programas/selectors/revision.py`.

### RED-55 · Los context processors corren en cada render y tragan toda excepción sin log
**Severidad:** MEDIA (era BAJA en RS-R4-21 y VR2: se sube porque corre en el 100 % del tráfico autenticado y hoy convierte un `OperationalError` en «usuario sin grupos» sin rastro; va con OPS-03) · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-21 (VR2: CONFIRMADO) · **Ola:** R (va con OPS-03, que pasa a la Ola R) · **Esfuerzo:** S (2 h)
- **Ubicación:** `core/context_processors.py:34-42` (`sidebar_badges`) y `conversaciones/context_processors.py:12-28`
  (`user_groups`), los dos con `except Exception` sin log, en el 100 % del tráfico autenticado.
- **Qué cambio lo rompería sin que nadie se entere:** nada: un `OperationalError` de MariaDB por `read_timeout` ya se
  convierte hoy en «badge 0» y «usuario sin grupos» (el rol desaparece del sidebar) sin rastro.
- **Propuesta:** `logger.exception(...)` en los dos `except`, acotados a `DatabaseError`/`ImportError`. Test
  `core/tests/test_context_processors.py::DegradacionTests.test_el_fallo_se_loguea` (`patch(..., side_effect=OperationalError)`,
  `assertLogs`, el render sigue en 200).

### RED-56 · Los guards de alcance de Becas fallan abiertos si el Programa BECAS no está sembrado
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (VR2: con el programa renombrado, un usuario cuyo único rol es de otro programa atraviesa los tres guards) · **Origen:** RS-VR2-NEW-01 (surgió al refutar RS-R4-01) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/autorizacion.py:82, 88, 96, 106, 144, 185` (`programa = programa or
  programa_becas(user)`); `core/rbac.py:589-591` (con `programa=None` cae al chequeo **global**).
- **Qué es frágil:** si `programa_becas()` devuelve `None` (fila `BECAS` ausente o renombrada, o la clave
  `programas:becas` envenenada en el Redis compartido con TTL 300), cualquier rol de **cualquier** programa con una
  capacidad `becas.*` tildada entra a Becas. Dispositivos ya exige `programa is not None` (`dispositivos.py:56,63,77`);
  Becas no.
- **Qué cambio lo rompería sin que nadie se entere:** un restore, un `crear_programas` que recrea la fila con otro pk o un
  pod que arranca antes del bootstrap abren el acceso durante 300 s y se curan solos, sin rastro.
- **Propuesta:** en `autorizacion.py`, helper `_programa_o_denegar(user, programa=None)` que levanta
  `PermissionDenied("El Programa Becas no está configurado.")` si no hay programa, en las seis apariciones. Tests en
  `programas/tests/test_becas_rbac.py::GuardsFallanCerradoTests`: `test_sin_programa_becas_el_guard_deniega`
  (`Programa.objects.filter(codigo="BECAS").update(codigo="BECAS_RENOMBRADO")`, `cache.clear()`,
  `assertRaises(PermissionDenied)` sobre `_assert_scope_formulario`; hoy falla) y, como ratchet barato,
  `test_los_tres_guards_dan_el_mismo_veredicto` (`_assert_scope`, `_assert_scope_relevamiento`, `_assert_scope_formulario`
  sobre un usuario de otro programa → `PermissionDenied` los tres; pasa hoy). El test completo que usó VR2 está en su
  informe (§A).

### RED-77 · RN-2 del padrón escrita dos veces: property y filtro de queryset
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO (lectura; 3 sitios) · **Origen:** RS-R4-09 (VR2: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `FilaPadron.tiene_identidad` (`models/__init__.py:2115-2118`, con `strip()`) vs `padron.py:378` y
  `:428-431` (`.exclude(nombre="").exclude(apellido="")`, sin strip); consumidores de la property: `revision.py:1218`,
  `api/views.py:133`, `identidad.py:80`.
- **Qué cambio lo rompería sin que nadie se entere:** una `FilaPadron` con `nombre="  "` cargada por otra vía (admin,
  fixture, migración): el cruce masivo la valida y el botón manual la rechaza; o RN-2 suma «y fecha de nacimiento» en la
  property y el cruce masivo —el que valida miles— queda con la regla vieja.
- **Propuesta:** manager `FilaPadron.objects.con_identidad()` (excluye nombre o apellido vacíos o solo espacios) usado por
  los dos sitios de `padron.py`. Test `programas/tests/test_padron.py::IdentidadDelPadronTests.test_property_y_queryset_coinciden`
  (6 filas con las combinaciones vacío/espacios; hoy falla en las dos con espacios).

### RED-78 · `DashboardView`: copia del inicio sin el blindaje de SEC-14, muerta solo por el orden de URLs
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO con test (`resolve('/').view_name == 'users:login'`; `reverse('dashboard:inicio') == '/'`) · **Origen:** RS-R4-10 (VR2: CONFIRMADO) · **Ola:** R (test de ruteo) + 7 (borrado, con OPS-14) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `core/views/public.py:52-126` (`inicio_view`) y `dashboard/views/home.py:19-57` (`DashboardView`, en `/`
  por `dashboard/urls.py:9`); `config/urls.py:36` (`users.urls`) gana sobre `:39`.
- **Qué cambio lo rompería sin que nadie se entere:** reordenar `config/urls.py` (el comentario «Root paths last» lo
  invita): `/` pasa a ser `DashboardView`, con contadores globales y sin el gate por capacidad de SEC-14.
- **Propuesta:** **R:** `core/tests/test_dashboard_redirect.py::RuteoRaizTests.test_la_raiz_es_el_login`. **Ola 7:** borrar
  `dashboard/views/home.py`, `dashboard/templates/dashboard.html` y su `path` (las 5 APIs de `dashboard/api_views` se
  conservan) y llevar los contadores a `dashboard/selectors.py::metricas_home()`.

### RED-79 · Tres ciclos de import y nueve aristas vista→vista sin ratchet
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO con test (AST; VR2 midió 9 aristas, no 2) · **Origen:** RS-R4-14 (VR2: CONFIRMADO-AJUSTADO); incluye la parte no refutada de RS-R4-01 y el punto 3 de RS-R4-16 (VR2 §2.10: «un solo movimiento») · **Ola:** R (ratchets) + 2 (movimientos, PR 5 con SEC-21) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** ciclos `programas.services.becas ↔ diseno` (por privados `_alcance_requisito`, `_campo_dict`),
  `programas.views.configuracion ↔ dashboard_becas` (`_programas_qs`), `users.forms ↔ users.selectors.usuarios`
  (`_roles_asignables_queryset`); aristas vista→vista: `admisiones→dispositivos_legajo`, `configuracion→dashboard_becas`,
  `configuracion→diseno`, `dashboard_becas→configuracion`, `pausas→relevamientos`, `reportes→dispositivos_legajo`,
  `reportes→merenderos`, `revision→cupo`, `revision→relevamientos` (más `ajax_utils`, helper compartido a propósito).
  El mismo invariante de alcance está escrito en `relevamientos.py:_assert_scope`, `revision.py:_assert_scope_relevamiento`
  y `_assert_scope_formulario`, y hay dos funciones `_assert_scope` con semánticas distintas (`configuracion.py:81`).
- **Qué cambio lo rompería sin que nadie se entere:** una «limpieza de imports» que sube un import diferido al encabezado:
  el proyecto no arranca. El silencioso: SEC-21 mueve `_assert_scope_formulario` a `autorizacion.py`, que ya está en un
  ciclo, y nadie se lo señala.
- **Propuesta:** **R:** `programas/tests/test_arquitectura.py::CapasTests.test_no_crecen_las_dependencias_entre_vistas`
  (`ARISTAS_CONOCIDAS` = las 9, `EXENTOS = {"ajax_utils"}`; `actuales - ARISTAS_CONOCIDAS` debe ser vacío) e
  `ImportsTests.test_no_hay_ciclos_nuevos` (`CICLOS_CONOCIDOS` = los 3). **No** escribir «ninguna vista importa de otra»:
  fallaría en 9 lugares y lo terminarían apagando. **Ola 2 (PR 5):** mover `CAP_RELEVAMIENTO_PUBLICO`,
  `_puede_publico`/`_sin_formularios_publicos_si_no_puede` a `autorizacion.py`, `_programas_qs` a `programas/selectors/`,
  unificar los guards en `assert_alcance_relevamiento`/`assert_alcance_formulario` y renombrar
  `configuracion.py:_assert_scope` a `_assert_scope_segmento`; sacar las aristas resueltas de la lista.

### RED-80 · `programa_becas` y `programa_dispositivos`: mismo cache, distinta guarda e invalidación
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-18 (VR2: CONFIRMADO) · **Ola:** 2 (PR 1, con SEC-07) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/autorizacion.py:48-77` (clave `programas:becas`) y `programas/services/dispositivos.py:32-49`
  (`programas:dispositivos`); `seed_becas.py:202` borra la de Becas; **nadie** borra la de Dispositivos.
- **Qué cambio lo rompería sin que nadie se entere:** un restore que recrea la fila `DISPOSITIVOS` con otro pk: durante
  300 s todos los pods evalúan contra el pk viejo y nadie entra a Dispositivos; se cura solo.
- **Propuesta:** `programa_por_codigo(codigo, user=None)` con clave derivada e `invalidar_programa(codigo)` usada por los
  dos seeds (Becas ya falla cerrado con RED-56). Test `programas/tests/test_dispositivos_config.py::CacheProgramaTests.
  test_el_seed_invalida_las_dos_claves`.

### RED-81 · El registro de reglas de vencimiento puede quedar vacío y el comando sale OK
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura; tras `django.setup()` `REGLAS` = `['becas.convocatoria', 'becas.relevamiento']`) · **Origen:** RS-R4-19 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `core/services/vencimientos.py:40-50` (`REGLAS` global), `programas/apps.py:9-12` (`ready()` importa
  `programas.services.vencimientos  # noqa: F401`), `core/management/commands/procesar_vencimientos.py:34`.
- **Qué cambio lo rompería sin que nadie se entere:** «limpiar» el import con `# noqa: F401` (parece sin uso):
  `procesar_vencimientos` (cron 03:10 y arranque) no procesa nada y sale con éxito; las convocatorias vencidas dejan de
  cerrarse. Los tests de vencimientos importan el módulo y lo vuelven a registrar.
- **Propuesta:** `programas/tests/test_becas_vencimientos.py::RegistroTests.test_las_reglas_estan_registradas_al_arrancar`
  (sin importar el módulo: `{r.slug for r in REGLAS} == {"becas.convocatoria", "becas.relevamiento"}`) y, en el comando,
  `if not REGLAS: raise CommandError("No hay reglas de vencimiento registradas")`.

### RED-82 · `exportacion_reportes.py` con terminadores CR: git lo trata como binario y pylint lo saltea
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (122 `\r`, 0 `\n`; único de los 673 `.py`; `pylint` → `E0001` y lo omite sin fallar) · **Origen:** RS-R4-20 (VR2: CONFIRMADO), RS-R7 nota 2 · **Ola:** R (la conversión y el gate; adelanta esa parte de OPS-14) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/exportacion_reportes.py` (lo importan `views/dashboard_becas.py`, `services/reportes.py`
  y `reportes_becas.py`; contiene `celda_segura`, RED-70).
- **Qué es frágil:** `git ls-files --eol` lo marca `i/-text` (los diffs de PR no muestran su contenido), `grep -n` lo ve como
  una sola línea, `ruff format` no lo normalizó y cualquier gate basado en pylint lo deja afuera devolviendo verde. Ningún
  gate del CI lo detecta. La revisión de SEC-20, que toca esta función, sería ilegible.
- **Propuesta:** convertir a LF (`*.py text eol=lf` en `.gitattributes` y `git add --renormalize .`) y test
  `core/tests/test_higiene_fuentes.py::EOLTests.test_ningun_py_con_cr_solitario` (recorre `git ls-files "*.py"` y afirma
  `b.count(b"\r") == b.count(b"\r\n")` por archivo).

## (e) Migraciones y rollback

Reproducido contra **MariaDB 11.8.9** (contenedores descartables de RS-R5 y VR2) y SQLite con datos. Hoy: el rollback
documentado deja la base peor que antes, la CI nunca migra hacia atrás ni sobre datos, y no hay artefacto inmutable al
que volver. El checklist por migración, el job de ida y vuelta, la regla expand/contract y el runbook de rollback están
en los **Anexos A-D** de este archivo.

### RED-14 · Un rollback de release con una columna `NOT NULL` nueva rompe el alta de casos
**Severidad:** ALTA (era CRÍTICA: el daño aparece al ejecutar un rollback, no hoy) · **Estado:** CONFIRMADO con test (`ERROR 1364 … Field 'dni_titular' doesn't have a default value` en MariaDB 11.8; VR2 contó 392 columnas `NOT NULL` sin default solo en `programas_*`) · **Origen:** RS-R5-01 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h)
- **Ubicación:** `programas/migrations/0072_formulario_dni_titular.py:44-48` (y 20 `AddField` con `null=False` en los
  últimos 3 meses, 6 sobre `programas_formulario`); `config/settings.py:287` (`STRICT_TRANS_TABLES`);
  `docs/internal/processes.md:245-254` (el rollback documentado vuelve la imagen sin tocar la base).
- **Qué es frágil:** Django nunca deja un `DEFAULT` en la base para un `AddField`: lo aplica durante el `ALTER` y lo quita.
  Con el esquema adelantado y el código viejo (el estado exacto después de un rollback de release), todo `INSERT` del ORM
  viejo omite la columna y MariaDB lo rechaza.
- **Qué cambio lo rompería sin que nadie se entere:** volver a la release anterior al Cambio 91 sin revertir la 0072:
  **todo alta de caso** (app de campo y link público) responde 500; el backoffice de lectura sigue andando y el síntoma
  llega por el territorial, no por el monitoreo.
- **Propuesta:** (1) regla expand (Anexo C): toda columna nueva nace `null=True` o con `DEFAULT` real en la base
  (`AddField(..., preserve_default=False)` + `RunSQL("ALTER TABLE t ALTER COLUMN c SET DEFAULT '…'", reverse_sql="… DROP
  DEFAULT", state_operations=[])`); (2) `scripts/check_migraciones.py` (corre en `pr-backend.yml` junto a `makemigrations
  --check`): recorre con `ast` las migraciones nuevas del PR (`git diff --name-only origin/development -- "*/migrations/*.py"`)
  y falla ante un `AddField` `null=False` sin el `RunSQL` de default ni la marca `# ROLLBACK-OK: <motivo>`, ante un
  `RemoveField/DeleteModel/RenameField/RenameModel` sin `# CONTRACT: …` (RED-19) y ante un `RunPython.noop` sin
  `# REVERSA-NOOP: …` (RED-57); (3) `programas/tests/test_contrato_migraciones.py::test_columnas_nuevas_toleran_codigo_viejo`
  (`MigrationLoader(None).disk_migrations` posteriores a un `DESDE` fijo; en SQLite); (4) el paso D.2.0 del runbook
  (`ALTER … SET DEFAULT` antes de bajar la release) en `processes.md` (RED-60).

### RED-15 · En MariaDB la reversa falla (errno 150) y deja tabla huérfana y `django_migrations` a mitad
**Severidad:** ALTA (era CRÍTICA) · **Estado:** CONFIRMADO con test (MariaDB 11.8: `migrate programas zero` → 1005 errno 150; reintento → 1050; recuperación hacia adelante «OK» con `legajos_derivacion` huérfana) · **Origen:** RS-R5-02 (VR2: CONFIRMADO), RS-VR2-NEW-03 · **Ola:** R (barrera + runbook) · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-05

**Resolución:** ✅ Resuelto en #549 (Cambio 117), 04-oct-2026, con el default de D-RED-05 (barrera) — `programas.0047`, `programas.0048`, `programas.0073`, `legajos.0007` y `users.0023` llevan el bloque `# BARRERA-DE-REVERSA:` y una operación `RunPython(sin_cambios, bloquear_reversa)` al final de `operations`: hacia adelante no hace nada y, al desaplicar (Django recorre en orden inverso, así que corre primera), aborta con `IrreversibleError` **antes de cualquier DDL**, nombrando la migración y remitiendo al paso D.4. Solo actúa en MySQL/MariaDB (fuera de ahí la ida ya era un no-op); verificado también que bloquea en `mysql:8.0.46`, donde el peligro de UUID con guiones no existe — consistente con «las migraciones no se revierten en producción», a tener en cuenta cuando exista el job `migration-roundtrip` (RED-17). El cuerpo de las funciones `restaurar_*` quedó intacto a propósito, para que RED-18 lo corrija sin chocar. Las ocho barreras (las cinco de UUID más `programas.0032`, `0056` y `0069`, que todavía no abortan: RED-57) están listadas en el paso D.4 del runbook. Verificado contra MariaDB 11.8 real: con la barrera, `migrate legajos zero` aborta sin tocar el esquema y el forward posterior reaplica (`migrate --check` en 0); sin ella, muere con errno 150, deja `legajos_derivacion` huérfana y `django_migrations` repartido entre seis apps. **Test permanente:** `core.tests.test_barreras_de_reversa.BarrerasDeReversaTests` (5 tests). Queda pendiente el chequeo inverso de `verificar_esquema_migraciones` (OPS-01, PR R-15).
- **Ubicación:** `legajos/migrations/0007_ampliar_uuid_legajos.py:44-59` (`MODIFY … char(36)` por SQL crudo, fuera del estado
  de Django) + `legajos/migrations/0004_remove_derivacion.py` (su reversa recrea `legajos_derivacion` con el tipo nativo
  `uuid` de MariaDB ≥ 10.7, contra un `char(32)`).
- **Qué es frágil:** sin DDL transaccional, el fallo deja la tabla creada; además (VR2-NEW-03) `django_migrations` quedó con
  la reversa aplicada a medias **en varias apps a la vez** (`legajos 4 · programas 1 · users 2 · core 2 · dashboard 1 ·
  conversaciones 1`): no corresponde a ninguna release. En SQLite el mismo plan termina OK, por eso el CI no lo ve.
- **Qué cambio lo rompería sin que nadie se entere:** ya está roto: el día que haya que revertir una migración de `legajos`
  o `programas` en PRD, el operador sigue `processes.md:256-258`, ve un traceback, reintenta y lo deja peor.
- **Propuesta (default D-RED-05 = barrera):** declarar `legajos.0007`, `programas.0047/0048/0073` y `users.0023` como
  **barrera de reversa** (`# BARRERA-DE-REVERSA: por debajo solo se vuelve con restore` en cada archivo, listadas en el
  runbook D.4); en el runbook, «si el `migrate` falló durante una **reversa**, ir directo a D.4 (restore); D.3 solo aplica a
  un `migrate` hacia adelante cortado en una sola migración, verificado con `showmigrations --plan`»; y que
  `verificar_esquema_migraciones` (OPS-01, Ampliado) incluya el chequeo inverso: tablas en la base que no corresponden a
  ningún modelo del estado final. El arreglo de fondo (sacar el `MODIFY` crudo de la reversa, L) solo si el PM decide lo
  contrario en D-RED-05; no se planifica.

### RED-16 · No hay artefacto al que volver: ECOM publica solo `:latest` y `main` no se tagea
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura); que `kubectl rollout undo` vuelva a bajar la misma imagen es PLAUSIBLE (manifiesto de ECOM fuera del repo) · **Origen:** RS-R5-03 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-02
- **Ubicación:** `.gitlab-ci.yml:11,19-20` (`docker build -t ${IMAGE_BASE}:latest` y push del mismo tag);
  `.github/workflows/publish-main.yml:61-62` (commit y push a `main`, sin `git tag`).
- **Qué es frágil:** cada build pisa la imagen anterior. «Volver a la release anterior» es revertir en GitLab y esperar un
  build (5-7 min con PRD rota y la base ya migrada).
- **Propuesta:** en `publish-main.yml`, después del push: `git tag -a "release-$(date +%Y.%m.%d)-$short" -m "release
  (development@$short)"` y `git push origin --tags`. Pedir a ECOM (D-RED-02, H-12) `-t ${IMAGE_BASE}:${CI_COMMIT_SHORT_SHA}`
  además de `:latest`: el rollback pasa a `kubectl set image deploy/<web> web=…:<sha anterior>` (segundos). El runbook
  (Anexo D) documenta los dos casos.

### RED-17 · Ninguna migración se prueba hacia atrás ni sobre datos; los tests de migración usan los modelos de hoy
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (ida y vuelta ejercida a mano: OK en SQLite, rota en MariaDB) · **Origen:** RS-R5-04 (VR2: CONFIRMADO), RS-R2-07 parte «modelos históricos» (VR1; el punto 1 amplía TST-01), RS-R5-11 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h) + S (2 h) · **Decisión:** D-RED-03
- **Ubicación:** `.github/workflows/pr-backend.yml:98` (`DJANGO_SYNCDB_PROJECT_APPS: "True"` → `config/settings.py:112-122`
  anula las migraciones de las 8 apps); `pr-performance.yml:120-124` (único `migrate` real: `mysql:8.0`, base vacía, y
  `seed_perf` **después**); `users/tests/test_migracion_becas.py:21,40`, `programas/tests/test_migracion_catalogo.py:17,22-26`,
  `test_dispositivos_migrations.py:21`, `users/tests/test_migracion_administrador_publico.py` (invocan la función de la
  migración con `django.apps.apps`, los modelos **vivos**).
- **Qué es frágil:** un error dentro de una migración solo lo ve el job efímero, solo hacia adelante y sobre tablas vacías
  (28 `RunPython` en 27 archivos nunca corren sobre filas). El repo ya registró este modo de falla: el Cambio 58 anotó que
  `test_migracion_catalogo` pasaba solo porque el CI arma el esquema sin migraciones, y `0a785d75` (26/08) arregló una
  `0052` que murió en el deploy con `padron_archivo` NULL.
- **Qué cambio lo rompería sin que nadie se entere:** una migración de datos que use un campo agregado después de ella, o
  que asuma un `NOT NULL` que en PRD es NULL: CI verde (no itera), initContainer en CrashLoop en PRD.
- **Propuesta:** (1) job `migration-roundtrip` del **Anexo B** en `pr-performance.yml` (matriz `mariadb:10.11`, `mariadb:11`,
  `mysql:8.0`: forward hasta la release anterior → `seed_perf --scale 200` **con el código de la release anterior** → forward del PR **con datos** → backward a la
  release anterior → forward → `migrate --check`), con `continue-on-error: true` hasta cerrar RED-18 y declarar las barreras
  de RED-15 (default D-RED-03: dos semanas, después obligatorio); (2) tests de migración con el registro **histórico**:
  `MigrationExecutor(connection).loader.project_state(("users", "0006_…")).apps` en vez de `django.apps.apps` en los cuatro
  archivos citados, más `programas/tests/test_migracion_catalogo.py::test_la_migracion_usa_solo_campos_que_existian_en_su_momento`.
- **Dependencias:** RED-16 (el tag da «la release anterior»; mientras no exista, un SHA fijo), TST-01 (comparte servicios),
  OPS-05 (`DB_READ_TIMEOUT`; mientras no esté, el job usa un settings de CI que sube `read_timeout`).

### RED-18 · La reversa de `0047`, `0048` y `legajos.0007` falla con «Data truncated»
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (MariaDB 11.8: `ALTER TABLE … MODIFY client_uuid char(32)` con un valor de 36 → `ERROR 1265`) · **Origen:** RS-R5-06 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/migrations/0047_ampliar_formulario_client_uuid.py:12-17` (achica sin normalizar),
  `0048_…:38-44` y `legajos/migrations/0007_…:72-75` (normalizan **solo** `if has_native_uuid_field`); el patrón correcto
  está en `0073_ampliar_relevamiento_token_publico.py:35-41` (normaliza siempre, y su comentario explica por qué: una base
  restaurada desde otro motor trae guiones aunque no sea MariaDB).
- **Propuesta:** copiar el patrón de la 0073 en las tres (dos líneas cada una; no cambia la ida ni requiere migración nueva).
  Test `programas/tests/test_migraciones_uuid.py::test_reversa_uuid_normaliza_antes_de_achicar`: llama a las tres
  `restaurar_*` con un `schema_editor` espía y afirma que el `UPDATE … REPLACE(col,'-','')` precede al `MODIFY … char(32)`,
  con y sin `has_native_uuid_field`.

### RED-19 · Rolling en k8s: cada pod corre `migrate` y no hay regla expand/contract
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (dos `migrate` en paralelo contra MariaDB 11.8: uno muere; el error depende de dónde se crucen: 1050 desde base vacía, 1060 desde base al día) · **Origen:** RS-R5-07 (VR2: CONFIRMADO-AJUSTADO) · **Ola:** R (puntos 1 y 2; el candado va en OPS-07, Ola 3) · **Esfuerzo:** S-M (4 h)
- **Ubicación:** `docker-entrypoint.sh:38-41` (`migrate` dentro de `run_bootstrap`, en todo arranque sin `command`);
  `docker/k8s/README.md:37` («Sin `command`/`args` en el pod (recomendado): el entrypoint hace todo»), `:60`, `:66`.
- **Qué es frágil:** Django no toma candado para `migrate` en MySQL/MariaDB; con la forma que el README recomienda y
  `replicas > 1`, N pods migran a la vez y, si se cruzan dentro de una migración de varias operaciones, el esquema queda a
  medias sin fila en `django_migrations`. Y durante el rolling los pods viejos siguen atendiendo: una migración que borra o
  renombra una columna en la misma release da 500 intermitentes los ~60 s del rollout.
- **Propuesta:** (1) un solo migrador: `RUN_MIGRATIONS=false` en el Deployment web y `migrate` solo en el Job/initContainer
  `args: ["bootstrap"]` (`docker-entrypoint.sh:76-82`); corregir `docker/k8s/README.md:37` (con `replicas > 1` esa opción no
  es válida) y pedirlo a ECOM con el manifiesto (H-05); (2) regla expand/contract (Anexo C) en `CLAUDE.md` y en
  `.claude/agents/chaco-dev-reviewer.md`, con el gate `# CONTRACT:` de `scripts/check_migraciones.py` (RED-14); (3) el
  candado `GET_LOCK('datanach_migrate', 900)` alrededor del `migrate` va en el comando `bootstrap_lock` de OPS-07 (Ampliado).

### RED-57 · 14 reversas `RunPython.noop` (más `users/0007`) pierden datos e informan `OK`
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO con test (SQLite con datos: revertir `programas.0032` deja todos los segmentos sin `siis_segmento_id`; `migrate` dice OK) · **Origen:** RS-R5-05 (VR2: CONFIRMADO-AJUSTADO: 14 archivos con `RunPython.noop`; `users/0007` es otro patrón, `noop_reverse` vacía) · **Ola:** R · **Esfuerzo:** S-M (4 h)
- **Ubicación:** destructivas: `programas/0032:22-23` (copia y borra el origen), `0056:110,120-127` (además borra filas en la
  ida), `0069:25-28` (`RemoveField` sin copia); noop sin pérdida de esquema: `programas/0012, 0020, 0024, 0035, 0036,
  0045:88, 0046, 0060:125, 0072:49`, `legajos/0006:21-23`, `users/0013:29`, `0016:20`; `users/0007:85-97`.
- **Qué cambio lo rompería sin que nadie se entere:** la próxima migración que mueva datos entre columnas con reversa noop.
- **Propuesta:** marca `# REVERSA-NOOP: <qué dato queda inconsistente al revertir>` sobre cada una de las 15;
  `# BARRERA-DE-REVERSA` en `0032`, `0056` y `0069` (y en el runbook D.4); test
  `programas/tests/test_contrato_migraciones.py::test_todas_las_migraciones_son_reversibles_o_lo_declaran`
  (`MigrationLoader(None).disk_migrations`: cada `RunPython`/`RunSQL` tiene reversa real, o `noop` con la marca en el
  archivo, o `None` explícito); el gate de `check_migraciones.py` (RED-14) lo exige en las nuevas.

### RED-58 · `legajos.0007` no es re-entrante
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (dos `DROP FOREIGN KEY` seguidos → `ERROR 1091`) · **Origen:** RS-R5-08 (VR2: CONFIRMADO) · **Ola:** 3 (con OPS-05) · **Esfuerzo:** S (2 h)
- **Ubicación:** `legajos/migrations/0007_ampliar_uuid_legajos.py:24-30` (drop de 2 FK con nombres **hardcodeados** `:4-5`),
  `:44-59`, `:80` (`atomic = False`).
- **Qué cambio lo rompería sin que nadie se entere:** que el `MODIFY` del medio espere el metadata lock más que el
  `read_timeout` (OPS-05): las FK ya no están y el reintento muere en la primera línea con un 1091 que no dice nada.
- **Propuesta:** ya está aplicada en PRD: el arreglo es **preventivo** para las próximas `atomic = False` (ítem 6 del
  checklist, Anexo A): cada paso idempotente, con el nombre real de la FK desde `information_schema.KEY_COLUMN_USAGE` y
  chequeo previo en `information_schema.COLUMNS`. Test sobre el banco `scripts/perf_mysql/`:
  `legajos/tests/test_migracion_uuid.py::test_ampliar_uuid_es_idempotente` (`@tag("mysql")`, dos llamadas seguidas).

### RED-59 · `deploy_prod.sh`: rollback sin base, detached HEAD y un health que siempre da 200
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R5-09 (VR2: CONFIRMADO; su punto 2 es el mismo hallazgo que RS-R6-06, que se agregó a OPS-04) · **Ola:** R (con OPS-04, que pasa a la Ola R) · **Esfuerzo:** S (2 h)
- **Ubicación:** `scripts/deploy_prod.sh:15` (`HEALTH_URL=…/health/`), `:18` (`ROLLBACK_ON_FAIL=1` por default), `:52-54`
  (`git pull --ff-only`), `:78-90`, `:92-109`, `:99` (`git checkout --force "$PREV_COMMIT"`). Viaja en el release.
- **Qué es frágil:** el rollback vuelve el código y nunca la base (el contenedor rearrancado corre `migrate` con los
  archivos viejos: filas sin archivo y esquema adelantado, RED-14); el criterio de éxito es `/health/`, que da 200 con la
  base caída (OPS-04); y el `checkout --force` deja detached HEAD, así que el `pull --ff-only` del deploy siguiente falla.
- **Propuesta:** `HEALTH_URL` → `/health/ready/` (OPS-04) más `post_deploy_checks()` (`manage.py migrate --check`, manifest de
  `staticfiles.json` con más de 50 entradas, `GET /accounts/login/` = 200); `git checkout --force` →
  `git switch --force-create "rollback/$TIMESTAMP" "$PREV_COMMIT"`; si `showmigrations --plan` detecta migraciones nuevas
  aplicadas, **abortar** el rollback automático e imprimir el runbook (decisión humana). Test
  `core/tests/test_scripts_deploy.py::DeployProdTests.test_no_usa_checkout_force_ni_health_desnudo` (lee el script).

### RED-60 · `processes.md` enseña un rollback que destruye datos y autoriza `--fake`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R5-10 (VR2: CONFIRMADO; prioridad 1 dentro de las migraciones) · **Ola:** R (es media hora y evita que el próximo incidente lo empeore) · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #549 (Cambio 117), 04-oct-2026 — §Rollback de `processes.md` pasa a ser el runbook del Anexo D (D.0 dump obligatorio con el comando escrito para icore y el pedido a ECOM; D.1 qué camino corresponde; D.2 rollback de código con el paso previo D.2.0 de RED-14 y los escenarios ECOM/Kubernetes e icore; D.3 `migrate` cortado hacia adelante; D.4 restore con la lista de las ocho barreras; D.5 registro), y §Gestión de migraciones se reescribió: dump obligatorio, `--fake` prohibido, las migraciones no se revierten en producción y expand/contract. Tres desvíos respecto del Anexo D, todos code-first: (1) `--fake` **se prohíbe** en vez de desaparecer —el criterio 7 del «Hecho cuando» pedía que no se mencionara, pero el propio D.3 lo nombra, y quien lo busque tiene que encontrar el «no»—; (2) el comando de dump del Anexo D no funcionaba como estaba escrito (`$MYSQL_ROOT_PASSWORD` lo expandía la shell del host): quedó con `sh -c '…'` y `$DATABASE_NAME`; (3) D.2.2 opera sobre **`main`**, que es la rama del checkout de icore-srv (`.claude/commands/servidor.md`), con `git switch --force-create rollback/<ts>` en vez de `reset --hard`, que el próximo `pull --ff-only` desharía en silencio. Se corrigieron además las dos referencias al servicio `django`, que no existe en `docker-compose.prod.yml`. **Test permanente:** `core.tests.test_runbook_rollback.RunbookRollbackTests` (6 tests). Queda operativo: el pedido escrito a ECOM del dump previo al deploy (H-11).
- **Ubicación:** `docs/internal/processes.md:256-258` (`docker compose exec django python manage.py migrate <app>
  <anterior>`: el servicio se llama `web`, el comando ni arranca, y la reversa traba MariaDB: RED-15), `:282` («usar
  `--fake` solo si…», lo contrario de `docker-entrypoint.sh:31-37` y OPS-01), `:280` («siempre hacer backup» sin ningún
  mecanismo: `grep -rn "mysqldump\|mariadb-dump"` en scripts, compose y workflows → 0).
- **Propuesta:** reemplazar §Rollback y §Gestión de migraciones de `processes.md` con el runbook del **Anexo D** (incluidos
  el D.2.0 de RED-14 y la regla de RED-15), borrar la línea del `--fake` y escribir el comando de dump concreto para icore y
  el pedido escrito a ECOM (H-11).

### RED-83 · Índices duplicados en `programas_formulario` y `legajos_ciudadano`
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (`information_schema.STATISTICS` en MariaDB 11.8: los 5 pares) · **Origen:** RS-R5-12 (VR2: CONFIRMADO) · **Ola:** R (guard) + 4 (migración) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `programas/models/__init__.py:2484-2490` (`estado` con `db_index=True`) vs `:2631`
  (`Index(fields=["estado"])`); `legajos/models/base.py:23` vs `:194` (`dni`, ya `unique`), `:29` vs `:202` (`email`),
  `:25` vs `:195` (`apellido`, cubierto por `apellido,nombre`), `:43` vs `:201` (`activo`, cubierto por
  `legajos_ciu_listado_idx`).
- **Propuesta:** **R:** `core/tests/test_indices_redundantes.py::test_no_hay_indices_prefijo_de_otro` (recorre los modelos
  de `programas` y `legajos`; falla si un `Index`/`db_index`/`unique` es prefijo exacto de otro del mismo modelo, con
  `REDUNDANTES_CONOCIDOS` = los 5 pares; la lista solo baja). **Ola 4:** `AlterField` (sin `db_index`) + `RemoveIndex`
  por par (`DROP INDEX` secundario es `INPLACE`/`LOCK=NONE`).

### RED-84 · `requerimientos.py --check` no verifica la sección «Reversión»
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R5-13 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** la plantilla obligatoria de `docs/internal/requerimientos.md:87-140` ya tiene `**Migración**`,
  `## Base de datos` y `## Reversión`; `scripts/requerimientos.py:226-263` (`comando_check`) no las mira.
- **Propuesta:** en `comando_check`, para cada entrada **nueva** (número mayor al último Cambio al momento del merge, para no
  romper el histórico) cuyo `**Migración**` no diga «No requiere», exigir `## Reversión` con más de una línea y que
  `## Base de datos` nombre la migración. Test del script con dos entradas sintéticas (una válida, una con la sección vacía).

## (f) Gates de CI/CD y deploy

**Foto medida del CI (03-oct).** Siete workflows. Bloquean solo si el PR los dispara y nadie está obligado a esperarlos
(RED-20): `pr-backend.yml` (`check --deploy`, `makemigrations --check`, `coverage run manage.py test` con
`DJANGO_SYNCDB_PROJECT_APPS=True` y `fail_under = 48`), `pr-performance.yml` (presupuestos + `migrate` real en `mysql:8.0`
desde base vacía), `pr-security.yml` (`pip-audit`), `pr-quality.yml` (ruff, ruff format y bandit, **los tres
`continue-on-error`**, filtrado por `paths`) y `design-agent-contract.yml` (filtrado por `paths`). Sobre `push` a
`development` corren solo `publish-main.yml` (genera `main`, el release que se espeja a PRD) y `docs-auto-deploy.yml`
(publica Pages). No hay type checking, `docker build`, `collectstatic`, `compile_templates.py`, `design_audit.py`,
`requerimientos.py --check` ni verificación del CSS de Tailwind. Entre `main` y PRD (GitLab de ECOM) solo hay un
`docker build`.

### RED-01 · Datos personales reales (10.321 personas) en un repo público, en el release y en la imagen de PRD
**Severidad:** CRÍTICA (el único hallazgo del frente con daño real hoy: los datos están expuestos en este momento) · **Estado:** CONFIRMADO (lectura por API y git; VR2 leyó solo el encabezado del archivo, ninguna fila) · **Origen:** RS-R6-01 (VR2: CONFIRMADO-AJUSTADO: hay una decisión previa del PM que el informe no vio) · **Ola:** R (**hotfix**, primer PR) · **Esfuerzo:** M (8 h de código; la purga y la coordinación con ECOM son operativas) · **Decisión:** **D-RED-01 (DECISIÓN CLIENTE)**
- **Ubicación:** `scripts/DatosPersonas.sql` (2.874.634 bytes; encabezado «10321 filas»: DNI, CUIL, nombre, sexo, fecha de
  nacimiento y domicilio completo devueltos por RENAPER, incluye menores), `scripts/Aprobados.sql` (111.036 bytes, DNI de
  aprobados) y `scripts/Localidades.sql` (172.299 bytes, también indexado por DNI). **Este documento no reproduce ningún
  dato.**
- **Qué es frágil:** el repositorio `Mkdir-arg/Chaco-Back` es **público** (`gh api repos/Mkdir-arg/Chaco-Back` →
  `"visibility": "public"`); los `.sql` no están en `export-ignore`, así que viajan a `main` (`git ls-tree origin/main
  scripts/` los lista) y de ahí al GitLab de ECOM; el `Dockerfile` hace `COPY . .` y `.dockerignore` no los excluye: están
  **dentro de la imagen de PRD**. Nada en CI, `.gitignore`, `.gitattributes` ni `.dockerignore` impide subir otro volcado.
  La decisión registrada (Cambio 79, `requerimientos.md:8900`: «`scripts/DatosPersonas.sql` queda en el repo por decisión
  del PM») **no contempla** que el repo es público, que el archivo viaja al release y a la imagen, ni la Ley 25.326.
- **Qué cambio lo rompería sin que nadie se entere:** ya está roto; el próximo «chore(becas): lista nueva de aprobados»
  (patrón real: `661c1a43`, `917e583e`) agrega otro volcado sin que nada lo detecte.
- **Propuesta (opción recomendada de D-RED-01; el orden importa):**
  1. **Inmediato, no espera la decisión:** sacar los tres de `HEAD` (`git rm --cached scripts/DatosPersonas.sql
     scripts/Aprobados.sql scripts/Localidades.sql`), `scripts/*.sql` en `.gitignore` (con excepción explícita de las
     plantillas sin datos, p. ej. `!scripts/aprobados_materias_plantilla.sql` si existe), `export-ignore` en
     `.gitattributes` y `scripts/*.sql` en `.dockerignore`.
  2. **Fuente alternativa para `correr_alta_siis`** (hoy los lee de la imagen: `correr_alta_siis.py:62-64`;
     `completar_casos_renaper.py:171` y `corregir_datos_siis.py:169` piden «cargala con scripts/DatosPersonas.sql»):
     variable `DATOS_SIIS_DIR` (default `/datos-siis`), montada como volumen o secret en el pod y como bind mount en icore;
     si no existe, `CommandError` que nombra la variable; `scripts/README-datos-siis.md` (versionado, sin datos) con de dónde
     salen los tres volcados y quién los genera; `programas/tests/test_correr_alta_siis.py:213` pasa a un directorio
     temporal con tres `.sql` sintéticos.
  3. **Decisión del cliente (D-RED-01):** repo **privado**; **purga del historial** (`git filter-repo --invert-paths --path
     scripts/DatosPersonas.sql --path scripts/Aprobados.sql --path scripts/Localidades.sql`) coordinada **antes** con ECOM
     porque reescribe `main` y su pipeline despliega PRD; pedir a GitHub Support que elimine las referencias de PR y las
     vistas cacheadas de los commits viejos; reconstruir la imagen de PRD sin los archivos; antes de dar la purga por
     suficiente, correr `gitleaks` o `trufflehog` sobre el historial completo. La notificación y la evaluación de
     cumplimiento de la **Ley 25.326** (seguridad de los datos, cesión) las decide **el organismo responsable de la base**,
     no el equipo: nuestra parte es informarlo por escrito con estos datos y dejar constancia en `requerimientos.md`.
  4. **Gate para que no vuelva:** `.github/workflows/pr-datos.yml`, job `Sin datos personales`, obligatorio en RED-20:
     ```yaml
     name: Datos
     on: { pull_request: { branches: [development] } }
     permissions: { contents: read }
     jobs:
       sin-datos-personales:
         name: Sin datos personales
         runs-on: ubuntu-latest
         timeout-minutes: 5
         steps:
           - uses: actions/checkout@v4
             with: { fetch-depth: 0 }
           - name: Ningún archivo nuevo grande ni con volcados de personas
             run: |
               base="${{ github.event.pull_request.base.sha }}"; fail=0
               for f in $(git diff --name-only --diff-filter=AM "$base" HEAD); do
                 [ -f "$f" ] || continue
                 case "$f" in static/custom/css/*|package-lock.json|*.png|*.jpg|*.svg|*.woff2) continue;; esac
                 size=$(wc -c < "$f")
                 [ "$size" -gt 524288 ] && { echo "::error file=$f::archivo de $size bytes (techo 512 KB)"; fail=1; }
                 if head -c 2000000 "$f" | grep -qiE "insert into .*(dni|cuil|cuit|apellido|fecha_nac|domicilio)"; then
                   echo "::error file=$f::parece un volcado con datos personales"; fail=1
                 fi
               done
               exit "$fail"
     ```
     y `core/tests/test_release_sin_datos.py::ReleaseSinDatosTests.test_ningun_sql_versionado_tiene_volcado_de_personas`
     (`git ls-files "*.sql"`; falla si alguno tiene más de 100 líneas de tuplas `(…)`).
- **Verificación:** `git ls-files "*.sql"` sin volcados; `git ls-tree origin/main scripts/` sin los tres después del
  próximo release; `docker build` + `docker run --rm <img> ls scripts/` sin `.sql`; `correr_alta_siis --help` documenta
  `DATOS_SIIS_DIR`.

### RED-20 · `development` y `main` sin protección de rama: ningún check es obligatorio
**Severidad:** ALTA (era CRÍTICA: los PRs recientes se mergearon en verde; falta el mecanismo, no hay daño consumado) · **Estado:** CONFIRMADO (API: `branches/development/protection` y `branches/main/protection` → 404; `rulesets` → `[]`) · **Origen:** RS-R6-02 (VR2: CONFIRMADO-AJUSTADO), RS-R6-17 (filtro `paths`; lo resuelve el punto 3) · **Ola:** R (**lo aplica el dueño del repo**; sin esto ningún gate nuevo es obligatorio) · **Esfuerzo:** S-M (4 h)
- **Qué es frágil:** `CLAUDE.md` («Gates de CI… Bloquean el merge») describe una política que no existe: un PR en rojo se
  mergea con el botón normal y un `git push origin development` entra sin disparar ningún workflow de verificación
  (todos son `on: pull_request`) **pero sí** `publish-main.yml`, que regenera `main`. Medido por VR2 en una ventana
  enunciable: **23 commits de código (`.py`, `.html`, migraciones) en los últimos 90 días entraron sin PR** (verificados por
  API, p. ej. `71621fb7`, `0948de89`, `7b229544`; la cifra «36 de 200» de RS-R6 estaba mal enunciada).
- **Propuesta:**
  1. Ruleset sobre `development` (`gh api repos/Mkdir-arg/Chaco-Back/rulesets -X POST --input ruleset-development.json`):
     ```json
     {"name": "development protegida", "target": "branch", "enforcement": "active",
      "conditions": {"ref_name": {"include": ["refs/heads/development"], "exclude": []}},
      "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
        {"type": "pull_request", "parameters": {"required_approving_review_count": 0,
          "dismiss_stale_reviews_on_push": false, "require_code_owner_review": false,
          "require_last_push_approval": false, "required_review_thread_resolution": false}},
        {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": true,
          "required_status_checks": [{"context": "Django System Check"}, {"context": "Migration Check"},
            {"context": "Tests & Coverage"}, {"context": "Query Budgets & Smoke Time"},
            {"context": "Ephemeral MySQL Redis Contract"}, {"context": "Pip Audit"}]}}],
      "bypass_actors": []}
     ```
     **`required_approving_review_count: 0` a propósito:** todo el equipo (y los agentes) publica PRs con la misma cuenta, y
     GitHub no deja aprobar el propio PR: exigir 1 aprobación bloquearía todos los merges. La revisión independiente sigue
     siendo el «Aprobado @ SHA» del proceso. Los checks nuevos (`Sin datos personales`, `Contratos de API`, `Contratos del
     repo`, `Ruff errores`) se suman a la lista cuando existan.
  2. Ruleset sobre `main`: `deletion`, `non_fast_forward` y `update` (nadie empuja) con bypass solo para la app GitHub
     Actions (`{"actor_type": "Integration", "actor_id": 15368, "bypass_mode": "always"}`), que es quien publica.
  3. `pr-quality.yml` y `design-agent-contract.yml` **sin** `paths:` en el trigger y con el filtro adentro del job
     (`dorny/paths-filter`, pineado por SHA: RED-85): el check siempre termina (`success` si no hay cambios relevantes) y
     puede ser obligatorio; sumar `tailwind.config.js`, `package.json` y `package-lock.json` al filtro del contrato de diseño.
  4. Mientras no esté el ruleset: `push: branches: [development]` en `pr-backend.yml` y `pr-performance.yml`, para que un
     push directo deje al menos un check rojo visible antes del espejo a ECOM.
  5. Corregir `CLAUDE.md` §«Gates de CI» para que describa lo que de verdad se exige.
- **Verificación:** `gh api repos/Mkdir-arg/Chaco-Back/rulesets` devuelve los dos; un PR de prueba con un test roto no
  muestra el botón de merge habilitado; `git push origin development` desde local es rechazado.

### RED-21 · `publish-main.yml` genera el release sin exigir CI verde y con un denylist escrito a mano
**Severidad:** ALTA (era CRÍTICA) · **Estado:** CONFIRMADO (lectura: `grep -c "manage.py\|coverage\|docker build" publish-main.yml` → 0) · **Origen:** RS-R6-03 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `.github/workflows/publish-main.yml:4-7` (`on: push: branches: [development]`), `:28-46` (guard con dos
  listas literales: 15 rutas prohibidas y 10 requeridas), `:46-62`; `.gitattributes:11-25` duplica hoy exactamente las 15
  prohibidas, a mano y sin nada que las mantenga sincronizadas (y `CONTEXT.md`, 17.907 bytes de documentación interna en la
  raíz, no está en ninguna y viaja al release).
- **Qué cambio lo rompería sin que nadie se entere:** commitear `NOTAS.md`, `.cursor/` o una carpeta de trabajo en la raíz:
  no está en ninguna lista, viaja a `main`, a ECOM y a la imagen de PRD.
- **Propuesta:** (1) derivar el denylist de `.gitattributes` (`git check-attr export-ignore` sobre `git ls-files`) y fallar
  si un `.md` de raíz no es de runtime ni está marcado; (2) exigir que el commit venga de un PR con CI verde. **Ajuste de la
  consolidación:** la propuesta de RS-R6-03 consultaba los check-runs del commit publicado, pero el commit de merge en
  `development` **no tiene check-runs** (los PRs los corren sobre su head): el paso pasaría siempre. Versión correcta:
  ```yaml
  permissions: { contents: write, pull-requests: read, checks: read }
  # …
      - name: Exigir que el commit venga de un PR con CI verde
        env: { GH_TOKEN: "${{ github.token }}" }
        run: |
          head=$(gh api "repos/${{ github.repository }}/commits/${{ github.sha }}/pulls" \
                 --jq '[.[] | select(.merged_at != null)][0].head.sha // empty')
          [ -z "$head" ] && { echo "::error::${{ github.sha }} no viene de un PR mergeado"; exit 1; }
          rojo=$(gh api "repos/${{ github.repository }}/commits/$head/check-runs?per_page=100" \
                 --jq '[.check_runs[] | select(.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped")] | length')
          [ "$rojo" != "0" ] && { echo "::error::el PR tiene $rojo checks no exitosos en $head"; exit 1; }
          exit 0
  ```
  Con RED-20 activo esto es defensa en profundidad (un push directo ya no entra); sin RED-20 es lo único que frena un
  release ciego.

### RED-22 · El pipeline de ECOM solo construye la imagen: cero verificación antes del deploy a PRD
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura de `.gitlab-ci.yml` entero: una etapa `build`) · **Origen:** RS-R6-04 (VR2: CONFIRMADO) · **Ola:** R (es una **propuesta a ECOM**: el archivo es de ellos y nuestra copia debe quedar igual) · **Esfuerzo:** S (2 h) · **Pregunta:** H-12
- **Ubicación:** `.gitlab-ci.yml` (`docker build` + `docker push :latest`, regla `test` o `main`); `main` → ArgoCD →
  **producción automática, sin aprobación** (`.claude/commands/pushGitLabecom.md:11-16`).
- **Qué cambio lo rompería sin que nadie se entere:** cualquier regresión que no sea un error de sintaxis (p. ej. un
  `TruncWeek` que compila, construye, levanta y da NULL solo en MariaDB).
- **Propuesta:** llevarle a ECOM, por escrito, una etapa `verify` antes de `build` (imagen `python:3.12-slim`;
  `apt-get install gcc default-libmysqlclient-dev pkg-config`; `pip install -r requirements.txt`; con
  `DJANGO_SECRET_KEY`, `PYTEST_RUNNING=1`, `DJANGO_SYNCDB_PROJECT_APPS=True`, `DJANGO_DEBUG=False`:
  `python manage.py check --deploy`, `makemigrations --check --dry-run`, `test --verbosity=1`; misma regla `test || main`) y
  el tag inmutable de RED-16. Si ECOM no lo acepta, el equivalente de nuestro lado es `release-gate.yml` (RED-23), que
  verifica **antes** de que exista el espejo.

### RED-23 · `/pushGitLabecom` empuja `test` y `main` en la misma corrida, sin exigir CI ni testing verificado
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R6-05 (VR2: CONFIRMADO; escribir junto con el runbook de RED-60 para que no se contradigan) · **Ola:** R · **Esfuerzo:** M (8 h)
- **Ubicación:** `.claude/commands/pushGitLabecom.md:73-101` (paso 4 pushea `test`, paso 5 `git push ecom main`, una sola
  confirmación).
- **Qué es frágil:** el build de ECOM tarda 5-7 min: cuando se ejecuta el paso 5, testing ni terminó de construir. «`test`
  primero, se verifica ahí, recién después `main`» es prosa que el procedimiento no implementa, y nada comprueba que el
  commit espejado haya pasado el CI de GitHub ni que `main` local esté al día con `origin/main`.
- **Propuesta:**
  1. Partir el comando en `/pushGitLabecomTEST` y `/pushGitLabecomPRD`. El segundo recibe el **SHA verificado en testing**,
     comprueba que `git ls-remote ecom test` tenga el mismo árbol (`git rev-parse <sha>^{tree}`), exige que el `release-gate`
     del punto 2 esté en verde para ese SHA y pide una segunda confirmación escribiendo `PRODUCCION`.
  2. `.github/workflows/release-gate.yml` (`workflow_dispatch` con input `sha`), con servicio `mariadb:10.11` (hasta H-01):
     (a) CI verde del PR de origen, con el mismo ajuste que RED-21 (el SHA de `development` se deriva del mensaje
     `release: … (development@<sha>)` de `main` y se busca su PR con `commits/<sha>/pulls`; el script de RS-R6-05 miraba el
     merge commit, que no tiene check-runs); (b) suite completa en SQLite; (c) `migrate --noinput`, `migrate --check` y
     `makemigrations --check --dry-run` contra MariaDB; (d) `docker build -t datanach:gate .` y `collectstatic` dentro de la
     imagen, fallando si no queda `staticfiles/staticfiles.json`; (e) smoke HTTP con la imagen levantada contra MariaDB:
     `/health/` responde, `GET /becas/` da 302 o 200 (nunca 500) y `GET /accounts/login/` da 200.
  3. Actualizar `.claude/commands/pushGitLabecom.md` con los dos pasos y el runbook de RED-60.

### RED-24 · Sin gates de contratos del repo: `compile_templates`, `collectstatic`, `requerimientos --check`, `design_audit`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (corridas de RS-R6 y VR2 sobre `ee0aafe`: `compile_templates` 0 errores sobre 198; `requerimientos.py --check` OK con 153 entradas; `design_audit` completo **44 errores y 28 warnings**) · **Origen:** RS-R6-09 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h)
- **Qué es frágil:** las tres condiciones de cierre de `CLAUDE.md` corren solo en la máquina de quien desarrolla, y
  `design_audit`/`check_design_agent` solo como hook de Claude Code: un cambio desde un IDE o desde la web de GitHub no pasa
  por nada. `collectstatic` nunca corre en CI y produce el 500 más caro del sistema («Missing staticfiles manifest entry»).
- **Qué cambio lo rompería sin que nadie se entere:** un `{% static 'custom/js/nuevo.js' %}` sin el archivo commiteado:
  `check`, `compile_templates` y la suite (con `ManifestStaticFilesStorage` apagado) pasan; en PRD, 500 en el primer render.
- **Propuesta:** job `contratos-repo` en `pr-quality.yml`, **sin** `continue-on-error`, nombre `Contratos del repo`
  (obligatorio en RED-20), con `actions/checkout@v4` (`fetch-depth: 0`), Python 3.12 y `pip install -r requirements.txt`:
  - `python scripts/compile_templates.py` (`DJANGO_SECRET_KEY`, `PYTEST_RUNNING=1`);
  - `python scripts/requerimientos.py --check` (`PYTHONIOENCODING=utf-8`);
  - `python manage.py collectstatic --noinput` con `DJANGO_DEBUG=False` y `ENVIRONMENT=prd` (variables de base dummy: no se
    conecta), fallando si no queda el manifest;
  - `design_audit` con **ratchet**: `actual=$( { python scripts/design_audit.py || true; } | sed -nE 's/.*: ([0-9]+) error.*/\1/p')` (el script sale
    con 1 cuando hay errores y Actions corre con `-e -o pipefail`: sin el `|| true` el paso aborta antes de comparar)
    contra el techo de `.design-audit-ratchet` (valor inicial: lo que mida el PR que lo crea; hoy 44); falla si sube y
    avisa (`::notice::`) si baja. Cuando la Ola 6 entregue `--ratchet`, este paso lo reemplaza.
  - Opcional (`::warning::`, no bloqueante): un PR con `feat`/`fix` en el título que no toca `docs/internal/requerimientos.md`.
  `docker build` entra por el `release-gate` (RED-23), no en cada PR. Type checking: ver RED-63 y RED-76.

### RED-61 · `SIIS_API_URL` cae al SIIS de desarrollo y nada lo valida al arrancar
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura: `config/settings.py:494`, default `https://siisapi.ecomdev.ar`); el valor real en PRD es PLAUSIBLE · **Origen:** RS-R6-10 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Qué es frágil:** de ~90 `os.getenv` de `settings.py`, el único validado es `DJANGO_SECRET_KEY`. Si en PRD la variable
  falta o cambia de nombre, el sistema arranca y manda las altas al SIIS de desarrollo, que responde 200: el caso queda
  «informado» y el organismo nunca recibe nada, en un sistema **sin baja** (SIIS-01).
- **Propuesta (ajustada en la consolidación):** (1) sin default: `os.getenv("SIIS_API_URL", "")`, y los `.env.*.example` con el
  valor vacío y de dónde sale; (2) system check propio en `core/checks.py` (`@register(Tags.compatibility, deploy=True)`)
  que, con `DEBUG=False`, devuelve `Error` si `SIIS_API_URL` está vacía y `Error` si apunta a `*.ecomdev.ar` **solo cuando
  `DATANACH_ES_PRODUCCION=1`** — una variable explícita que ECOM setea únicamente en PRD. **No** usar `settings.ENVIRONMENT`:
  QA (testing de ECOM, que legítimamente usa el SIIS de desarrollo) e icore valen `prd` (OPS-12; README §0.4). `Warning`
  si `RENAPER_TEST_MODE=True` con `DEBUG=False`. En el CI, `check --deploy` corre con `SIIS_API_URL` de un host ficticio.
  (3) mostrar el host de SIIS en la pantalla del proceso masivo y en `diagnosticar_siis`. Test
  `core/tests/test_checks_entorno.py`: `test_siis_vacio_es_error`, `test_siis_de_desarrollo_en_produccion_es_error`
  (`override_settings` + `patch.dict(os.environ, {"DATANACH_ES_PRODUCCION": "1"})`) y
  `test_siis_de_desarrollo_fuera_de_produccion_no_es_error`.
- **Dependencias:** confirmar con ECOM (H-09) que PRD define `SIIS_API_URL` y pedirles `DATANACH_ES_PRODUCCION=1`. Un check
  con `deploy=True` no corre al arrancar el contenedor, solo con `manage.py check --deploy` (nuestro CI; en ECOM, recién con
  la etapa `verify` de RED-22): sin la variable el check de PRD nunca dispara, y sin `SIIS_API_URL` lo que queda rojo es el
  CI. Para frenar el arranque en PRD habría que llamar al check desde el entrypoint.

### RED-62 · Los presupuestos de performance son autodeclarados
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R6-11 (VR2: CONFIRMADO) · **Ola:** 4 · **Esfuerzo:** S (2 h)
- **Ubicación:** `scripts/perf_budgets.json:6` (la regla «subir un `max_queries` requiere justificación» es prosa dentro del
  JSON), `:23` (`reference_total_ms 1432.86`), `:25` (`failure_multiplier 3.0`: la alarma de tiempo salta a 4,3 s);
  `scripts/check_perf_timing.py:36-41` (lee el archivo del propio commit).
- **Qué cambio lo rompería sin que nadie se entere:** un N+1 en `becas_revision`: el job falla «16 → 61», el autor sube el
  presupuesto a 61 en el mismo PR y pasa. Hasta hoy siempre se justificó (11 entradas en `adjustments`): automatizarlo no
  cambia el proceso.
- **Propuesta:** paso en el job `performance-budgets` de `pr-performance.yml` que carga `perf_budgets.json` de la base del PR
  (`git show "${{ github.event.pull_request.base.sha }}":scripts/perf_budgets.json`) y falla si algún `max_queries` sube, o
  `reference_total_ms` sube más de 5 %, sin una clave nueva en `_meta.adjustments`; `failure_multiplier` a `2.0`.

### RED-63 · Ruff y Bandit en `continue-on-error`; excepción de `pip-audit` sin vencimiento
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R6-12 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `pr-quality.yml:20,39,58` y `pr-security.yml:36` (`continue-on-error: true`); `pr-security.yml:29-30`
  (`--ignore-vuln PYSEC-2026-3447`, «preexistente aprobada», sin fecha ni ticket).
- **Qué cambio lo rompería sin que nadie se entere:** un refactor que deja un nombre indefinido en una rama poco transitada:
  `ruff` lo marca `F821`, el job sale en amarillo, el PR se mergea y la excepción salta en PRD.
- **Propuesta:** partir `lint` en `Ruff errores` (`ruff check . --select F --output-format=github`, **bloqueante** y
  obligatorio en RED-20; verificar antes de encenderlo que hoy da 0) y `Ruff estilo` (`E,W,I`, `continue-on-error` hasta
  limpiar la deuda); `security/excepciones.toml` con `{id, motivo, vence_el, ticket}` y un paso que falla si `vence_el` ya
  pasó; Bandit sigue no bloqueante, con versión fija.

### RED-64 · `docs/client/` se publica en GitHub Pages público en cada push, sin revisión
**Severidad:** MEDIA · **Estado:** CONFIRMADO (API: Pages `public: true`, `status: built`) · **Origen:** RS-R6-15 (VR2: CONFIRMADO) · **Ola:** 7 · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-09
- **Ubicación:** `.github/workflows/docs-auto-deploy.yml:4-11,38` (`on: push` + `paths: docs/client/**`, `mkdocs gh-deploy
  --force`); hoy se publican el financiero (horas por tarea del equipo), minutas, equipo, metodología y arquitectura.
- **Qué cambio lo rompería sin que nadie se entere:** `/pm:reporte` o `/pm:minuta` escriben un documento con un dato que no
  debería ser público (un nombre de beneficiario en un ejemplo, una URL interna) y queda en internet en menos de un minuto.
- **Propuesta (default D-RED-09):** `environment: github-pages` con *required reviewers* (GitHub pide aprobación antes del
  deploy); paso previo que falla si un `.md` de `docs/client/` matchea `\b\d{7,8}\b` cerca de «DNI» o
  `(?i)(password|contraseña|secret|token)\s*[:=]\s*\S`, y si aparece un archivo fuera del `nav` de `mkdocs.yml` y de
  `not_in_nav`.

### RED-65 · El guard de `publish-main.yml` exige artefactos muertos y va a bloquear OPS-10/OPS-14
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R6-16 (VR2: CONFIRMADO) · **Ola:** R (el test) + 7 (sacar las rutas, sin horas extra: dentro de OPS-10/OPS-14) · **Esfuerzo:** S (2 h)
- **Ubicación:** `publish-main.yml:38` exige `docker/django/Dockerfile` (no lo construye nadie; su `CMD` corre
  `entrypoint_final.py`, que OPS-14 confirmó muerto) y `scripts/startup.sh` (corre `setup_system`, que OPS-10 borra).
- **Qué cambio lo rompería sin que nadie se entere:** el PR de OPS-10/OPS-14 borra esos archivos y `Publish main` falla
  **después del merge**, con `main` sin actualizar y sin alerta para quien no mira Actions.
- **Propuesta:** **R:** `core/tests/test_publish_guard.py::PublishGuardTests.test_los_requeridos_existen_en_el_arbol` (lee la
  lista del YAML y afirma que cada ruta existe: el fallo aparece en el PR). **Ola 7:** sacar las dos rutas de la lista en el
  mismo PR de OPS-10/OPS-14.

### RED-85 · Herramientas del CI sin pinear y actions por tag en workflows con `contents: write`
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO (lectura: 7 `pip install` sin versión) · **Origen:** RS-R6-13 (VR2: CONFIRMADO) · **Ola:** R (pinear las actions con `contents: write`) + 7 (el resto) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `pr-quality.yml:30,48,68`, `pr-backend.yml:88`, `pr-security.yml:26`, `docs-auto-deploy.yml:32` (`pip install
  ruff|bandit|coverage|pip-audit|mkdocs-material`); `publish-main.yml:21` (`actions/checkout@v5`) y
  `docs-auto-deploy.yml:22,25`, los dos con `permissions: contents: write`.
- **Qué cambio lo rompería sin que nadie se entere:** un release de `ruff` o `coverage` vuelve rojo o mueve el `fail_under`
  de un PR que no cambió nada; un tag comprometido en una action de `publish-main.yml` es un camino directo al artefacto
  de PRD.
- **Propuesta:** **R:** pinear por SHA (con el tag en comentario) las actions de `publish-main.yml` y `docs-auto-deploy.yml`, y
  `dorny/paths-filter` de RED-20. **Ola 7:** `requirements-ci.txt` con versiones fijas y `pip install -r requirements-ci.txt`
  en todos los workflows, más un dependabot semanal sobre ese archivo.

### RED-86 · Job de tests con timeout de 15 min, sin `--parallel` ni alarma de crecimiento
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (`gh run list`: 5-7 min por corrida; local, 20 min) · **Origen:** RS-R6-18 (VR2: CONFIRMADO) · **Ola:** 7 · **Esfuerzo:** S (2 h)
- **Ubicación:** `pr-backend.yml:71` (`timeout-minutes: 15`), `:95` (`coverage run manage.py test --verbosity=2`, en serie).
- **Qué cambio lo rompería sin que nadie se entere:** los `TransactionTestCase` de la Ola 1 empujan el job sobre los 15 min:
  un timeout se ve como «failure» genérico, la reacción es «re-run» y nadie ve el número crecer.
- **Propuesta:** `coverage run --concurrency=multiprocessing manage.py test --parallel 4` + `coverage combine` (**depende de
  RED-88**: hoy `--parallel` revienta en `core`/`users`/`portal`); `timeout-minutes: 25` y un paso que escribe la duración
  en `$GITHUB_STEP_SUMMARY` y emite `::warning::` sobre 12 min.

## (g) Las 10 partes más frágiles

Ranking por el cruce de churn medido (`git log origin/development --name-only -400 -- "*.py"`, sin tests ni migraciones),
tamaño, historial de defectos y cobertura (RS-R6 §2, contrastado con las mediciones de R1 y la mutación de R7).

| # | Pieza | Tamaño · churn | Por qué es frágil | Qué cambio la rompería sin que nadie se entere | Fichas |
|---|---|---|---|---|---|
| 1 | `programas/services/siis_envio.py` + `proceso_masivo.py` + `siis.py` | 816 + 489 + 420 líneas · 13 + 10 + ~6 | Integración **sin baja**: un alta de más es irreversible; SIIS-01 a 04 abiertos; el host cae a un default de desarrollo | Mover el `commit` respecto del POST o agregar un `retry` al cliente HTTP: un corte de red pasa de «reintentar» a dos altas. Relajar el borde de la fecha de nacimiento o del barrio (mutaciones M33, M34 sobreviven) | SIIS-01..04, RED-61, RED-69, RED-87 |
| 2 | `programas/models/__init__.py` | 3.252 · **45** | El archivo más tocado; define los tres productos; cada `AlterField` es una migración en MariaDB con `read_timeout` 10 s y sin DDL transaccional | Un `AddIndex` sobre `Formulario`: el cliente corta a los 10 s, el `ALTER` se aplica igual y el `migrate` queda a medias; el CI migra sobre base vacía | RED-14, RED-17, RED-46, OPS-05 |
| 3 | `programas/forms.py` | 2.001 · **43** | 2.000 líneas de validación del constructor dinámico: la puerta de los datos del ciudadano | Mover una validación de `clean_<campo>` a `clean()`: el error deja de verse junto al campo y la pantalla parece aceptar | RED-48, RED-40 |
| 4 | `programas/views/revision.py` + `relevamientos.py` | 1.331 + 1.056 · 34 + 30 | Las pantallas más caras (dieron 500 por timeout) y las más tocadas; su único guard de performance es un `max_queries` autodeclarado | Un `.annotate(Exists(...))` sobre una FK casi siempre nula: 0 consultas más, scan por fila en MySQL; una clave de contexto que se cae sin 500 | RED-54, RED-62, RED-79 |
| 5 | `programas/services/dashboard_becas.py` | 1.253 · ~4 | El servicio grande con menos red; concentra la agregación temporal | Reemplazar la agrupación en Python por `TruncWeek` «para que sea más rápido»: gráfico vacío en PRD, números bien en SQLite | RED-07 |
| 6 | `core/rbac.py` + sus consumidores | 772 · 13 | Pieza única de autorización; el alcance de admin de programa vive en constantes que se mueven juntas (`CAPS_ADMIN_*`); un código inexistente da `False` en silencio. **Es la más blindada por tests** (11/11 mutaciones detectadas) | Agregar una capacidad a `CAPS_ADMIN_PROGRAMA` sin tocar `seed_becas.py`; renombrar una capacidad y olvidar un uso (el superusuario no lo ve) | RED-44, RED-56, G1b-02 |
| 7 | `legajos/services/alertas.py` + `generar_alertas` | 268 · ~3 | Sin ningún test y corre **cada hora**; 3 consultas por ciudadano activo; cron de icore sin versionar | Cambiar la condición de «alerta ya existente»: la pasada recrea y re-notifica; una corrida colgada frena las siguientes en silencio | TST-02 (ampliado), LEG-01, PERF-20, G3-04/05 |
| 8 | `docker-entrypoint.sh` + bootstrap (`seed_datos_base`, `crear_programas`, `seed_catalogo_siis`) | 128 · — | Corre en cada arranque de cada pod, bajo `set -eu`, sin candado entre réplicas, y corre `migrate` en cada pod | Un `update_or_create` nuevo en un seed sobre un campo editable en el ABM; dos pods migrando a la vez | OPS-06, OPS-07, RED-19, OPS-01 |
| 9 | Link público: `portal/views/inscripcion.py` + `portal/services/inscripcion.py` + `programas/services/inscripcion_publica.py` | 476 · 22 + ~5 + 9 | La única superficie sin login en alcance; sesión en Redis compartido; cupo bajo `select_for_update` (no-op en SQLite); `token_publico` ya rompió en MariaDB | Quitar el `select_for_update` o la condición `EN_CURSO` del re-chequeo bajo lock (M43, M44 sobreviven); `debug_ciudadanos` en PRD corta todos los pasos en curso | RED-29, RED-67, RED-08, G1c-12 |
| 10 | `static/custom/css/tailwind.css` (build committeado) | 55 KB · 7 | Artefacto generado versionado a mano; hoy desactualizado (faltan `w-40`, `mt-px`, `text-opacity-90`, `bg-info-soft`) y su único guard tiene falsos positivos | Cambiar un token en `tailwind.config.js` sin `npm run build:tailwind`: toda la app con la paleta vieja en PRD | V5A-NEW-01, FE-13 (ampliados), RED-20 |

## (h) Lo que depende de que nadie se equivoque

| Proceso o convención | Riesgo si alguien se olvida | Automatismo propuesto | Dónde | Ficha |
|---|---|---|---|---|
| No commitear datos personales ni archivos gigantes | 10.321 personas ya están en un repo público y en la imagen de PRD | Job `Sin datos personales` + test `test_release_sin_datos` | CI (PR) | RED-01 |
| Abrir PR y esperar el verde antes de mergear | 23 commits de código en 90 días entraron sin CI y republicaron `main` | Rulesets con PR y checks obligatorios, `strict` | GitHub | RED-20 |
| No tocar `main` a mano | El snapshot se desincroniza del release | Ruleset en `main` con bypass solo para GitHub Actions | GitHub | RED-20 |
| Verificar que el commit publicado en `main` esté verde | Release de PRD desde un commit sin verificar | Paso «el commit viene de un PR con CI verde» en `publish-main.yml` | CI | RED-21 |
| Mantener iguales las dos listas de archivos del release | Un directorio de desarrollo viaja a la imagen de PRD | Denylist derivado de `git check-attr export-ignore` | CI | RED-21 |
| Probar en testing antes de pushear `main` a ECOM | PRD se despliega antes de que testing termine de construir | `/pushGitLabecomTEST` y `/pushGitLabecomPRD` + `release-gate.yml` | Comando + CI | RED-23 |
| Leer el estado de `main` antes de espejar | Se espeja un snapshot viejo | El gate recibe el SHA y lo compara con `ecom/test` y `origin/main` | Comando | RED-23 |
| Hacer un dump antes de un deploy con migración | No hay a qué volver si la migración destruye datos | Comando escrito en el runbook + confirmación de ECOM (H-11) | Runbook | RED-60 |
| No revertir migraciones en PRD con `migrate <app> <anterior>` | La base queda trabada y con tablas huérfanas | Runbook D.1-D.4 + barreras de reversa marcadas | Runbook + migraciones | RED-15, RED-60 |
| Que toda columna nueva tolere el código viejo | Un rollback de release rompe las altas (1364) | `scripts/check_migraciones.py` + test de contrato | CI | RED-14 |
| Declarar qué se pierde al revertir una migración de datos | Revertir borra datos e informa OK | Marca `# REVERSA-NOOP:` exigida por test y gate | Test + CI | RED-57 |
| No poner expand y contract en la misma release | 500 intermitentes durante el rolling | Marca `# CONTRACT:` exigida por el gate | CI | RED-19 |
| Correr `migrate` desde un solo lugar | Dos pods migran a la vez y el esquema queda a medias | `RUN_MIGRATIONS=false` en web + Job único + `GET_LOCK` | Manifiesto + entrypoint | RED-19, OPS-07 |
| Escribir la sección «Reversión» en `requerimientos.md` | Nadie sabe qué pasa al volver atrás | `requerimientos.py --check` la exige con migración | CI | RED-84 |
| Correr `npm run build:tailwind` y commitear el CSS | Utilidades sin CSS en PRD (hoy 4) | Rebuild + `git diff --exit-code` en CI | CI | V5A-NEW-01 (ampliado) |
| Correr `compile_templates`, `requerimientos --check` y `design_audit` | 44 errores de diseño acumulados; el hook solo mira lo tocado y solo en Claude Code | Job `Contratos del repo` con ratchet | CI | RED-24 |
| Que `collectstatic` funcione en la imagen | 500 «Missing staticfiles manifest entry» en PRD | `collectstatic` en `Contratos del repo` y en `release-gate` | CI | RED-24, RED-23 |
| No usar `Trunc*`/`__date` sobre `DateTimeField` | Pantallas vacías o 500 solo en PRD | Test de SQL compilado + `--tag mysql` en MariaDB | Test + CI | RED-07, TST-01 |
| Migrar a `char(36)` cada `UUIDField` y buscar con `q_uuid_en_texto` | «Data too long» y búsquedas vacías solo en MariaDB | Test que recorre todos los `UUIDField` contra la lista ampliada | Test | RED-09 |
| Justificar cada presupuesto de performance que sube | Un N+1 se tapa subiendo el techo | Paso que compara contra la base del PR | CI | RED-62 |
| Que un cambio de la API se coordine con `Chaco-mobile` | La app muestra campos vacíos sin error | Tests de contrato exactos + job `Contratos de API` | Test + CI | RED-11, RED-12, RED-43 |
| Que los tres motores de condiciones sigan iguales | La app oculta o descarta respuestas | Fixture de vectores compartido entre los dos repos | Test | RED-38 |
| Que cada capacidad usada exista en el `CATALOGO` | Una pantalla desaparece para todos menos el superusuario | Test que cruza literales con el catálogo | Test | RED-44 |
| Definir `SIIS_API_URL` en PRD | Las altas van al SIIS de desarrollo y se dan por informadas | System check `deploy=True` con variable explícita de producción | `check --deploy` | RED-61 |
| No borrar archivos que el guard del release exige | `Publish main` falla después del merge | Test que valida la lista en el PR | Test | RED-65 |
| Que una ficha cerrada deje su test en la suite | El bug vuelve sin test rojo | Línea «Test permanente» + test de contrato de la auditoría | Test | RED-34 |
| Instalar en CI la misma versión de las herramientas | Un release de una herramienta vuelve rojo un PR ajeno | `requirements-ci.txt` + actions por SHA | CI | RED-85 |
| Revisar alguna vez la excepción `PYSEC-2026-3447` | La excepción es permanente de hecho | `security/excepciones.toml` con vencimiento | CI | RED-63 |
| Revisar qué se publica en `docs/client/` | Un dato no público queda en internet en un minuto | `environment` con revisores + chequeo de patrones | CI | RED-64 |
| No correr `debug_ciudadanos`, `optimize_db`, `setup_system`, `crear_usuarios_sistema` ni seeds demo en PRD | Deslogueo total; claves conocidas en el rol Administrador | Borrar los comandos; `exigir_entorno_demo()` en los que quedan | Código | OPS-02, OPS-10, G1c-12 |
| Versionar y vigilar los cron de icore | Una corrida colgada frena las siguientes sin aviso | `.cron` versionados con `flock`, `timeout`, fecha y logrotate | `docker/cron/` | G3-04, G3-05 |
| Renombrar a mano las migraciones viejas de icore antes de redesplegar | CrashLoop con «Table already exists» | `verificar_esquema_migraciones` en el entrypoint | Entrypoint | OPS-01 |
| Volver a tildar capacidades que el seed pisaba | Cada deploy revertía la configuración del cliente | Seeds respetuosos del ABM (hecho en #508) | Código + test | OPS-06 |
| Que quien edita UI sea una sesión de Claude Code | Los controles de diseño no corren para otros editores | Los mismos scripts en CI (el hook queda como atajo) | CI | RED-24 |
| Resetear `Status=Backlog` después de crear un issue | Tareas sin casos de QA aparecen listas para tomar | Fuera de alcance técnico; automatizable con un workflow `issues: [opened]` | GitHub | — |

## (i) Prueba de mutación

**Método (RS-R7).** 49 mutaciones chicas y plausibles (1-6 líneas) sobre 14 puntos críticos, aplicadas de a una en un
worktree de `ee0aafe`, corridas con `.venv312` (Python 3.12 + Django 5.2.17, igual al CI) y revertidas con `git checkout`
verificando el árbol limpio. Una mutación **sobrevive** cuando ningún test falla: ese cambio puede entrar en un PR, pasar
el Backend CI en verde y llegar a producción. Las 12 supervivientes se re-corrieron contra la suite completa de las apps
que pueden tocar el archivo (`programas`, 1.438 tests; `programas portal`, 1.607) para descartar una mala elección de
módulos; M46 parecía sobrevivir y la mata `portal.tests.test_correcciones_review`. Línea base sin mutar: `programas` →
1.438 OK; `core users portal` → 643 OK. Las mediciones son corridas reales: las fichas de esta sección son CONFIRMADO con
test.

**Resultado: 37 detectadas, 12 sobreviven (puntaje 76 %).**

| Punto crítico | Mutaciones | Detectadas | Supervivientes → ficha |
|---|---:|---:|---|
| `core/rbac.py` (`puede`, alcance de programa, roles y usuarios inactivos) | 5 | **5** | — |
| `BackofficeAutenticado` (`core/api_permissions.py`) | 2 | **2** | — |
| `PortalCiudadanoMiddleware` y `es_ciudadano_portal` | 2 | **2** | — |
| Decorador `@requiere` y `CapacidadRequeridaMixin` | 2 | **2** | — |
| App de campo (token, permiso, alcance, sync, transiciones) | 8 | 5 | M11 → RED-25 · M14 → RED-26 · M17 → RED-66 |
| Cupo y lista de espera | 6 | 3 | M19 → RED-27 · M21 → RED-67 · M23 → RED-68 |
| `procesar_vencimientos` | 4 | 3 | M27 → RED-28 |
| Payload SIIS y exclusión de duplicados | 7 | 5 | M33 → RED-87 · M34 → RED-69 |
| Normalización de DNI y `q_uuid_en_texto` | 3 | **3** | — |
| Cruce de padrón | 2 | **2** | — |
| Inscripción pública (validaciones, token, cupo, duplicado) | 6 | 4 | M43 → RED-67 · M44 → RED-29 |
| Seeds de arranque (opt-in de OPS-06) | 1 | **1** | — |
| Exportaciones (`celda_segura`) | 2 | 1 | M49 → RED-70 |
| **Total** | **49** | **37** | **12 supervivientes en 11 fichas** |

| # | Mutación superviviente (archivo:línea en `ee0aafe`) | Tests corridos | Ficha |
|---|---|---|---|
| M11 | `programas/api/views.py:86`: `CampoBecasPermission` sin `and puede(user, CAP)` | `programas` (1.438) + 14 cruzados | RED-25 |
| M14 | `programas/api/views.py:448`: `FormularioViewSet` con `Formulario.objects.all()` | `programas` (1.438) + 14 cruzados | RED-26 |
| M17 | `programas/api/views.py:351`: guarda de `reabrir` → `if False:` | `programas` (1.438) + 14 cruzados | RED-66 |
| M19 | `programas/services/cupo.py:225`: promover con `< 0` en vez de `<= 0` | `programas` (1.438) | RED-27 |
| M21 | `programas/services/cupo.py:267`: sin `select_for_update` del segmento al aprobar | `programas` (1.438) | RED-67 |
| M23 | `programas/services/cupo.py:319`: `posicion = max_pos` | `programas` (1.438) | RED-68 |
| M27 | `programas/services/vencimientos.py:34`: sin `FINALIZANDO` en los estados abiertos | `programas` (1.438) | RED-28 |
| M33 | `programas/services/siis_envio.py:502`: barrio con `>` en vez de `>=` | `programas` (1.438) | RED-87 |
| M34 | `programas/services/siis_envio.py:470`: sin `and nacimiento <= hoy` | `programas` (1.438) | RED-69 |
| M43 | `programas/services/inscripcion_publica.py:89`: sin `select_for_update` del relevamiento | `programas portal` (1.607) | RED-67 |
| M44 | `programas/services/inscripcion_publica.py:128`: re-chequeo sin `rel.estado != EN_CURSO` | `programas portal` (1.607) | RED-29 |
| M49 | `programas/services/exportacion_reportes.py:22`: sin `ILLEGAL_CHARACTERS_RE.sub` | `programas` (1.438) | RED-70 |

**Fortaleza medida.** Las 11 mutaciones sobre `core/rbac.py`, `core/api_permissions.py` y `core/middleware.py` murieron
todas, varias con 5-8 tests independientes, y las dos que reintroducen regresiones ya cerradas por la Ola 0 (`/media/` de
SEC-09 y el opt-in de OPS-06) tienen su test. **El riesgo de que la Ola 2 (autorización) rompa algo sin que nadie se entere
es bajo; el de las Olas 1 y 3 (SIIS, app de campo, reglas de Becas) es alto.**

**Patrón.** Las 12 supervivientes caen en uno solo: la suite prueba el camino feliz y el negativo grueso, **no los bordes ni
las particiones completas** (una capacidad, un alcance, un estado, un cupo exacto, un umbral). Tres (RED-28, RED-29, RED-66)
se cierran con el mismo recurso —un `subTest` que recorre **todo** el enum de estados, para que agregar un estado al modelo
obligue a decidir de qué lado cae— y van en un solo PR (Ola R, PR R-08).

**No medido (RS-R7, zonas no revisadas):** `legajos`, `dispositivos`, `merenderos`, `configuracion` (por TST-02 se espera
cerca del 100 % de supervivencia), `dashboard`, el candado del proceso masivo, `siis_sync`/`validacion_siis`, migraciones y
front; mutaciones combinadas y mutaciones sobre los tests. Las mutaciones que solo se manifiestan en MariaDB (los
`select_for_update`, UUID con guiones, `CONVERT_TZ`) **no las puede matar la suite actual en ningún escenario**: es la
justificación empírica del paso `--tag mysql` de TST-01.

### RED-25 · La capacidad `becas.campo` no se prueba en los endpoints ni en el oráculo de identidad
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M11 sobrevive a 1.452 tests) · **Origen:** RS-R7-01 · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/api/views.py:79-86` (`CampoBecasPermission.has_permission`), usada por `consultar_persona_becas`
  (`:213-215`), `RelevamientoViewSet` (`:259`) y `FormularioViewSet` (`:443`), que montan `TokenAuthentication` **y**
  `SessionAuthentication`.
- **Qué es frágil:** el único test de capacidad prueba el **login** de la app (`TokenAuthTests.test_token_denegado_sin_capacidad`,
  `test_becas_api.py:69`); ninguno autentica a un usuario de backoffice sin `becas.campo` contra un endpoint.
- **Qué cambio lo rompería sin que nadie se entere:** borrar `and puede(user, CAP)` (`:86`) al agregar un segundo rol de
  campo: el oráculo de identidad RENAPER/Personas que SEC-04 y G1-02 cerraron para los anónimos queda abierto para todo el
  personal.
- **Propuesta:** en `programas/tests/test_becas_api.py::TokenAuthTests`: `test_sesion_de_backoffice_sin_becas_campo_no_lista`
  (`force_login` del coordinador que ya arma el test de la línea 69 → `GET becas_api:relevamiento-list` = 403) ·
  `test_sesion_de_backoffice_sin_becas_campo_no_consulta_persona` (403 y `mock_consultar.assert_not_called()`) ·
  `test_token_sin_capacidad_revocada_no_opera` (Token emitido con la capacidad, después se quita el rol → 403).

### RED-26 · `FormularioViewSet` sin test de alcance: un territorial podría leer y editar casos ajenos
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M14 sobrevive; la equivalente de `RelevamientoViewSet`, M13, muere) · **Origen:** RS-R7-02 · **Ola:** R (o en el PR de SEC-23, Ola 2, si va antes) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/api/views.py:447-450` (`get_queryset`, único filtro de alcance de `/api/becas/formularios/<id>/`:
  `GET`, `PUT`, `PATCH` y `POST …/adjuntos/`).
- **Qué cambio lo rompería sin que nadie se entere:** `Formulario.objects.all()` para que un supervisor vea los casos de su
  equipo: todos los casos de Becas (DNI, contacto, GPS, respuestas, adjuntos) visibles y **editables** por cualquier
  territorial con token.
- **Propuesta:** en `programas/tests/test_becas_api.py::FormularioSyncTests` (ya tiene `self.terri2` y `self.rel_ajeno`):
  `test_no_accede_a_formulario_ajeno` (404) · `test_no_actualiza_formulario_ajeno` (`PATCH` → 404 y la base sin cambios; si
  SEC-23 saca `UpdateModelMixin`, pasa a esperar 405) · `test_no_sube_adjunto_a_formulario_ajeno` (404).

### RED-27 · Promover desde la lista de espera con cupo exactamente 0 no está probado
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M19 sobrevive; la simétrica de aprobar, M20, muere con 3 tests) · **Origen:** RS-R7-04 · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/cupo.py:224-226` (`promover_lista_espera`, única guarda de cupo de la promoción). El único
  test que promueve (`test_becas_revision.py:1404-1415`) sube el cupo a 10 antes.
- **Qué cambio lo rompería sin que nadie se entere:** `<= 0` → `< 0`: se promueve con cupo 0, el segmento termina con más
  aprobados que `cupo_maximo` y, como aprobar dispara el alta, **el excedente se informa a SIIS, que no tiene baja**.
- **Propuesta:** `programas/tests/test_cupo_espera_reglas.py::PromoverRespetaElCupoTests(_BaseEsperaTest)`:
  `test_promover_sin_cupo_disponible_falla` (`cupo_maximo = 1` con un APROBADO; `assertRaises(ValidationError)` con «No hay
  cupo disponible»; el caso sigue ENVIADO y `promovido` en `False`) y `test_promover_con_el_ultimo_lugar_funciona`.

### RED-28 · `FINALIZANDO` está en los estados abiertos de vencimientos y ningún test lo cubre
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M27 sobrevive) · **Origen:** RS-R7-07 · **Ola:** R (PR de particiones, con RED-29 y RED-66; releer al implementar G1-04) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/vencimientos.py:31-36` (`ESTADOS_RELEVAMIENTO_ABIERTOS`), consumida en `:66` y por la regla
  `becas.relevamiento` (`:105-112`). `CascadaRelevamientoTests` cubre `ASIGNADO`, `EN_CURSO`, `FINALIZADO`, `TERMINADO` y
  `EN_REVISION`; **no** `FINALIZANDO` (el relevamiento que está sincronizando desde la app).
- **Qué cambio lo rompería sin que nadie se entere:** sacar `FINALIZANDO` de la tupla (natural al implementar la gracia de
  G1-04): esos relevamientos quedan fuera del cierre automático **para siempre** y sus casos nunca se revisan ni se informan.
  Al revés, un estado de más cortaría campo en curso.
- **Propuesta:** en `programas/tests/test_becas_vencimientos.py::CascadaRelevamientoTests`:
  `test_todos_los_estados_abiertos_pasan_a_revision` (`subTest` sobre `ASIGNADO, EN_CURSO, FINALIZANDO, FINALIZADO`) ·
  `test_los_estados_cerrados_no_se_tocan` (`EN_REVISION, TERMINADO`) · `test_la_particion_de_estados_cubre_el_enum`
  (`set(Relevamiento.Estado) == set(ESTADOS_RELEVAMIENTO_ABIERTOS) | ESTADOS_CERRADOS`, con `ESTADOS_CERRADOS` declarado en
  `vencimientos.py`).

**Resolución:** ✅ Resuelto en el PR R-08 (Cambio 120), 04-oct-2026 — los tres tests propuestos, más
`test_por_fecha_hasta_solo_vencen_asignado_y_en_curso` (caracterización de la **segunda** rama de la regla, que usa una
lista de estados más corta: con la convocatoria vigente, un `FINALIZANDO` o `FINALIZADO` con `fecha_hasta` pasada no se
cierra solo). Las listas que recorren los `subTest` son literales, no las constantes del servicio: si lo fueran, la
mutación M27 se llevaría puesta también al test. La constante nueva se llama `ESTADOS_RELEVAMIENTO_CERRADOS` (simetría
con la de al lado) en vez de `ESTADOS_CERRADOS`. Verificado a mano: M27 → 2 tests en rojo; `TERMINADO` de más en la tupla
de abiertos → 3 en rojo.
**Test permanente:** `programas/tests/test_becas_vencimientos.py::CascadaRelevamientoTests.test_todos_los_estados_abiertos_pasan_a_revision`

### RED-29 · El envío del link público no prueba que el relevamiento siga `EN_CURSO`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M44 sobrevive a 1.607 tests) · **Origen:** RS-R7-10 · **Ola:** R (PR de particiones; releer con G1-04) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/inscripcion_publica.py:128-131` (re-chequeo **bajo lock** en `_insertar_formulario`); el de
  la vista es `portal/views/inscripcion.py:157`. `IngestaPublicaTests` prueba cupo, duplicado y fecha
  (`test_vencido_al_enviar_no_crea`), nunca el estado.
- **Qué cambio lo rompería sin que nadie se entere:** simplificar el `or` a «con que esté en fecha alcanza»: alguien abre el
  paso 1 a las 03:09, el cron de las 03:10 pasa el relevamiento a `EN_REVISION` y el paso 2 **crea el caso igual**, colgado
  de un relevamiento que el revisor ya cerró (o `TERMINADO`, con reportes emitidos).
- **Propuesta:** en `portal/tests/test_inscripcion_envio.py::IngestaPublicaTests`: `test_cerrado_entre_pasos_al_enviar_no_crea`
  (`subTest` sobre `FINALIZADO, EN_REVISION, TERMINADO, ASIGNADO` **con `fecha_hasta` vigente**, para aislar el estado de la
  fecha; `assertRaises(InscripcionNoDisponible)` y `formularios.count() == 0`) y `test_en_curso_y_en_fecha_sigue_creando`.

**Resolución:** ✅ Resuelto en el PR R-08 (Cambio 120), 04-oct-2026 — los dos tests propuestos (el negativo recorre el enum
entero menos `EN_CURSO`, así que incluye `FINALIZANDO`, y arranca afirmando `habilitado_en(now)` para que la fecha no pueda
ser la que rechaza), más `test_solo_en_curso_habilita_el_link` sobre la guarda de la vista
(`portal/services/inscripcion.py::relevamiento_disponible`, el otro lado del mismo contrato). Verificado a mano: M44 →
`test_cerrado_entre_pasos_al_enviar_no_crea` en rojo; sacarle el estado a `relevamiento_disponible` → 5 `subTest` en rojo.
**Test permanente:** `portal/tests/test_inscripcion_envio.py::IngestaPublicaTests.test_cerrado_entre_pasos_al_enviar_no_crea`

### RED-66 · `reabrir` de la app de campo no tiene test negativo de la transición
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutación M17 sobrevive) · **Origen:** RS-R7-03 · **Ola:** R (PR de particiones) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/api/views.py:341-356` (`reabrir`; guarda en `:351`). Hay camino feliz
  (`test_iniciar_finalizar_reabrir`, `:199`) y negativo de `iniciar` (`:217`), no de `reabrir`.
- **Qué cambio lo rompería sin que nadie se entere:** neutralizar la guarda: el territorial reabre un relevamiento que el cron
  ya mandó a `EN_REVISION` (vuelve a `EN_CURSO` mientras el revisor trabaja, y el cron lo vuelve a cerrar al día siguiente,
  contra la decisión «EN_REVISION no tiene vuelta a EN_CURSO»), o uno `TERMINADO`.
- **Propuesta:** en `programas/tests/test_becas_api.py::RelevamientoApiTests`,
  `test_no_reabre_un_relevamiento_que_no_este_finalizado` (`subTest` sobre `ASIGNADO, EN_CURSO, FINALIZANDO, EN_REVISION,
  TERMINADO` → 400 con «Solo se puede reabrir un relevamiento finalizado.» y el estado intacto) y el mismo recorrido para
  `iniciar` y `finalizar`.

**Resolución:** ✅ Resuelto en el PR R-08 (Cambio 120), 04-oct-2026 — las tres transiciones recorren `Relevamiento.Estado`
completo (no una lista de estados «malos»): un estado nuevo entra solo al recorrido y hay que decidir de qué lado cae.
Cada test afirma el camino feliz y el negativo en la misma pasada, incluida la idempotencia de `iniciar` sobre `EN_CURSO`
y que `finalizar` también cierra desde `FINALIZANDO`. Verificado a mano: M17 (`if False:` en la guarda de `reabrir`) → 5
`subTest` en rojo; la misma mutación en `iniciar` → 5 en rojo (más `test_iniciar_estado_invalido`); sacarle `FINALIZANDO`
a `finalizar` → 1 en rojo.
**Test permanente:** `programas/tests/test_becas_api.py::RelevamientoApiTests.test_no_reabre_un_relevamiento_que_no_este_finalizado`

### RED-67 · Ningún test afirma que se tome el `select_for_update` del cupo ni del link
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutaciones M21 y M43 sobreviven; `grep -rn "select_for_update" programas/tests portal/tests` → solo un docstring) · **Origen:** RS-R7-05 · **Ola:** R (capa 1) + capa 2 dentro de TST-01 (Ampliado) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/cupo.py:205, 267, 316`; `programas/services/inscripcion_publica.py:89`;
  `programas/api/views.py:387`; `programas/tests/test_candados_concurrencia.py:11-15` (prueba bien **la decisión** bajo el
  candado, que mata M22, M24 y M46, pero en SQLite el candado es un no-op).
- **Qué cambio lo rompería sin que nadie se entere:** borrar la línea del lock al optimizar (PERF-02 y PERF-12 piden reducir
  trabajo bajo el lock, y en SQLite «no hace nada»): en MariaDB dos aprobaciones simultáneas leen el mismo cupo y aprueban
  las dos (cupo excedido y dos altas en SIIS); dos envíos del link pasan el cupo y el duplicado por DNI.
- **Propuesta:** capa 1: `programas/tests/test_candados_concurrencia.py::ContratoDeCandadosTests` con
  `patch.object(Segmento.objects, "select_for_update", wraps=Segmento.objects.select_for_update)` alrededor de
  `aprobar_o_poner_en_espera`, `promover_lista_espera` y `agregar_a_lista_espera` (`spy.assert_called()`), e igual con
  `Relevamiento.objects` para `crear_formulario_publico` y el POST de `relevamientos/<id>/formularios/`. Capa 2 (TST-01):
  `TransactionTestCase` `@tag("mysql")` con dos hilos sobre un segmento con un lugar → exactamente un APROBADO y una
  `ListaEspera`.

### RED-68 · La posición en la lista de espera no está probada en ningún lado
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutación M23 sobrevive; ningún `assert` sobre `posicion`) · **Origen:** RS-R7-06 · **Ola:** R (tests; la constraint, con BEC-02 en la Ola 1) · **Esfuerzo:** S (2 h) · **Decisión:** D-RED-11
- **Ubicación:** `programas/services/cupo.py:318-325` (`max_pos + 1`); `programas/models/__init__.py:2977,2984` (`posicion`,
  `ordering = ["segmento", "posicion"]`, sin unicidad).
- **Qué cambio lo rompería sin que nadie se entere:** `max_pos + 1` → `max_pos` (o cambiar el `aggregate` por un `count()`):
  toda la lista en la misma posición, `ordering` arbitrario y **a quién le toca el cupo que se libera** lo decide el orden
  físico de la tabla.
- **Propuesta:** `programas/tests/test_cupo_espera_reglas.py::PosicionEnLaListaTests(_BaseEsperaTest)`:
  `test_las_altas_consecutivas_llevan_posiciones_correlativas` ([1, 2, 3]) · `test_la_posicion_tras_promover` (fija la
  conducta elegida en D-RED-11; hoy el máximo se calcula sobre no promovidos y el nuevo recibe 3) ·
  `test_el_listado_de_cupo_respeta_el_orden_de_llegada`. Con BEC-02, si D-RED-11 lo pide, `UniqueConstraint(fields=["segmento",
  "posicion"])` con columna nullable (no `condition=`: MariaDB no crea índices parciales, README §0.2).

### RED-69 · Fecha de nacimiento ausente o futura sin test en el payload SIIS
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutación M34 sobrevive; la rama `else` no la ejecuta ningún test) · **Origen:** RS-R7-09 · **Ola:** R (o Ola 1, que abre `siis_envio.py`) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/siis_envio.py:469-473` (`if nacimiento and nacimiento <= hoy`).
- **Qué cambio lo rompería sin que nadie se entere:** sacar `and nacimiento <= hoy` al mover la validación al form: un dedazo
  («2027-05-14») viaja a SIIS como alta real, sin baja; además `_edad` da negativo y dispara la rama de apoderado.
- **Propuesta:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_fecha_de_nacimiento_ausente_o_futura_falta`:
  `subTest` con `None`, `hoy + 1 día` (los dos en `faltantes` y `cargar_beneficiario` no se llama) y `hoy` (pasa: el borde);
  en el mismo test, los negativos de `apellido`, `nombre` y `dni` vacíos.

### RED-70 · `celda_segura`: la limpieza de caracteres de control no está probada
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutación M49 sobrevive; la de fórmulas, M48, muere) · **Origen:** RS-R7-11 · **Ola:** R (o dentro de SEC-20, Ola 2, que toca la misma función) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/exportacion_reportes.py`, `celda_segura` (línea 22 del archivo, que usa terminadores CR:
  RED-82): `valor = ILLEGAL_CHARACTERS_RE.sub("", valor)`.
- **Qué cambio lo rompería sin que nadie se entere:** borrar esa línea (parece redundante): una respuesta con un carácter de
  control pegado desde Word o un PDF hace que `libro.save(response)` lance `IllegalCharacterError` → **500 en la descarga**,
  para una fila entre miles. SEC-20 va a aplicar la función a 5 exports más.
- **Propuesta:** en `programas/tests/test_reportes.py`: `test_un_caracter_de_control_no_rompe_el_xlsx` (`"Mart\x0bin\x07"` →
  `respuesta_reporte(…, "xlsx")` = 200 y la celda leída con `openpyxl` vale `"Martin"`) ·
  `test_celda_segura_limpia_y_prefija_a_la_vez` (`celda_segura("\x0b=1+1") == "'=1+1"`: si se invierte el orden, el `\x0b`
  impide detectar la fórmula, un bypass real de SEC-20) · el mismo par para `respuesta_libro`.

### RED-87 · El largo mínimo del barrio del payload SIIS no se prueba en su borde
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (mutación M33 sobrevive) · **Origen:** RS-R7-08 · **Ola:** R (mismo PR que RED-69) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/siis_envio.py:502-505` (`len(barrio) >= BARRIO_MINIMO`, con `BARRIO_MINIMO = 4` en `:21`);
  el test existente usa `"108"` (→ `"Barrio 108"`) y `"Sur"` (3), nunca 4.
- **Qué cambio lo rompería sin que nadie se entere:** `>=` → `>`: todo barrio de 4 caracteres pasa a `faltantes`, el caso cae a
  INCOMPLETO y la pantalla pide corregir un dato correcto (bloqueo silencioso de altas).
- **Propuesta:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_el_barrio_de_cuatro_caracteres_es_el_minimo_aceptado`
  (`"Sur2"` aceptado, `"Sur"` en `faltantes`) y el mismo borde para `len(dni) <= 10` (`:450`) y `[:LARGO_TEXTO]` (`:503,518`).

### RED-88 · `manage.py test core users portal --parallel` revienta con `cannot pickle 'traceback'`
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (sin mutación: `--parallel N` → `TypeError: cannot pickle 'traceback' object` en `django/test/runner.py:541`; en serie, 643 OK; `programas --parallel 6`, 1.438 OK) · **Origen:** RS-R7 nota 3 (lo pidió el juez como ficha) · **Ola:** R · **Esfuerzo:** S (2 h)
- **Qué es frágil:** algún test de esas tres apps produce una excepción no serializable durante el setup del subproceso. En
  modo paralelo el runner aborta **sin decir qué test falló**: enmascara el resultado y bloquea la vía obvia para acelerar el
  CI (RED-86).
- **Propuesta:** bisecar `core`, `users` y `portal` con `manage.py test <app> --parallel 2` hasta aislar la clase (candidatos:
  `setUpClass`/`setUpTestData` que guardan un objeto con traceback, p. ej. una excepción capturada como atributo de clase o un
  mock con `side_effect` de excepción instanciada a nivel de clase); arreglarla y agregar a `pr-backend.yml` un paso **no
  bloqueante** `manage.py test core users portal --parallel 2` que avise si vuelve a romperse, hasta que RED-86 pase la suite
  entera a paralelo.

---

## Anexo A · Checklist obligatorio por migración

Para `CLAUDE.md` (§Convenciones) y `.claude/agents/chaco-dev-reviewer.md`. Lo marcado **[auto]** lo verifica
`scripts/check_migraciones.py` (RED-14) o un test de contrato.

**Antes de escribirla**
1. ¿La tabla es grande (`programas_formulario` ~283 MB, `legajos_ciudadano`, `programas_adjuntoformulario`)? Ensayar en el banco
   `scripts/perf_mysql/` y medir el `ALTER` antes de mergear.
2. ¿Entra en la misma release que el código que la usa? Si borra algo, **no** (Anexo C).

**Forma**
3. **[auto]** Columna nueva: `null=True`, o `NOT NULL` con `DEFAULT` real en la base (`RunSQL … SET DEFAULT`,
   `state_operations=[]`), o la marca `# ROLLBACK-OK: <motivo>` (RED-14).
4. **[auto]** Todo `RunPython` tiene reversa. Si es `RunPython.noop`, arriba va `# REVERSA-NOOP: <qué queda inconsistente>`; si
   mueve datos y borra el origen, la reversa copia de vuelta o es `None` (RED-57).
5. **[auto]** Nada de `from <app>.models import …` en el cuerpo: solo `apps.get_model` (hoy se cumple; lo único del código vivo
   que entra son los `upload_to` `programas.models.ruta_padron_becas`, `ruta_adjunto_becas` y `core.models.generate_codigo`:
   si se renombran, `migrate` desde cero deja de funcionar).
6. `atomic = False` ⇒ cada paso idempotente (FK real desde `information_schema.KEY_COLUMN_USAGE`; `MODIFY` previo chequeo en
   `information_schema.COLUMNS`) (RED-58).
7. Migración de datos por lotes de pk (patrón `programas/0072:19-35`), nunca un queryset entero ni un `save()` por fila en
   tabla grande (antipatrón `0056:19-38`).
8. Índices con `ALGORITHM=INPLACE, LOCK=NONE` vía `RunSQL` + `state_operations`; **[auto]** ninguno prefijo de otro (RED-83).
9. UUID: la reversa normaliza a hex siempre (patrón `0073:35-41`) (RED-18).
10. MariaDB no crea `UniqueConstraint(condition=…)`: columna nullable dentro de un índice único (README §0.2).
11. **[auto]** `RemoveField`/`DeleteModel`/`RenameField`/`RenameModel` llevan `# CONTRACT: la columna dejó de leerse en la
    release <X>` (RED-19).

**Antes del merge**
12. `makemigrations --check --dry-run` (ya es gate) y el job `migration-roundtrip` (Anexo B).
13. Entrada de `requerimientos.md` con `## Base de datos` nombrando la migración y `## Reversión` diciendo qué se pierde al
    revertir; `requerimientos.py --check` en OK (RED-84).

**Antes del deploy a PRD**
14. Dump de la base con el comando escrito (D.0) y el destino verificado; en ECOM, confirmación escrita de ECOM (H-11).
15. Si la migración es barrera de reversa, decirlo en el aviso de deploy: «a partir de acá solo se vuelve con restore».

## Anexo B · Job `migration-roundtrip` (ida y vuelta en CI)

En `.github/workflows/pr-performance.yml`, junto al único `migrate` real que ya existe. Nace con `continue-on-error: true`
(D-RED-03) porque hoy falla en MariaDB 11 (RED-15, RED-18): ese rojo documentado es su primer valor.

```yaml
  migration-roundtrip:
    name: Migrate ida y vuelta (${{ matrix.motor }})
    runs-on: ubuntu-latest
    timeout-minutes: 25
    continue-on-error: true            # D-RED-03: se saca al cerrar RED-18 y declarar las barreras de RED-15
    strategy:
      fail-fast: false
      matrix:
        motor: ["mariadb:10.11", "mariadb:11", "mysql:8.0"]   # 10.11 hasta conocer la versión de ECOM (H-01)
    services:
      db:
        image: ${{ matrix.motor }}
        env: { MARIADB_ROOT_PASSWORD: root, MYSQL_ROOT_PASSWORD: root, MARIADB_DATABASE: chaco_mig, MYSQL_DATABASE: chaco_mig,
               MARIADB_USER: chaco, MYSQL_USER: chaco, MARIADB_PASSWORD: chaco, MYSQL_PASSWORD: chaco }
        ports: ["3306:3306"]
        options: >-
          --health-cmd="mysqladmin ping -h 127.0.0.1 -uchaco -pchaco --silent"
          --health-interval=5s --health-timeout=5s --health-retries=30
    env:
      DJANGO_SECRET_KEY: ci-test-key-not-a-real-secret
      DJANGO_DEBUG: "False"
      DATABASE_NAME: chaco_mig
      DATABASE_USER: chaco
      DATABASE_PASSWORD: chaco
      DATABASE_HOST: 127.0.0.1
      DATABASE_PORT: "3306"
      DB_READ_TIMEOUT: "600"           # requiere OPS-05; hasta entonces, un settings de CI que suba read/write_timeout
      DB_WRITE_TIMEOUT: "600"
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip, cache-dependency-path: requirements.txt }
      - run: sudo apt-get install -y default-libmysqlclient-dev && pip install -r requirements.txt
      - name: Forward hasta la release anterior   # tag de RED-16; mientras no exista, un SHA fijo
        run: |
          git worktree add ../anterior "$(git describe --tags --abbrev=0 --match 'release-*' HEAD^ 2>/dev/null || echo HEAD~50)"
          (cd ../anterior && python manage.py migrate --noinput)
      - name: Sembrar datos con el código de la release anterior (las migraciones del PR corren sobre filas)
        run: (cd ../anterior && python manage.py seed_perf --scale 200)
      - name: Forward del PR
        run: python manage.py migrate --noinput
      - name: Backward a la release anterior
        run: |
          # configuracion no tiene migraciones; dashboard y conversaciones sí participan del plan de reversa (VR2 §2.5)
          for app in programas legajos users core dashboard conversaciones; do
            destino="$(cd ../anterior && python manage.py showmigrations "$app" | grep '\[X\]' | tail -1 | awk '{print $2}' || true)"
            [ -n "$destino" ] && python manage.py migrate "$app" "$destino" --noinput
          done
      - name: Forward de nuevo
        run: python manage.py migrate --noinput
      - name: Coherencia esquema <-> django_migrations
        run: |
          python manage.py migrate --check
          python manage.py verificar_esquema_migraciones   # OPS-01 (Ola R); con el chequeo inverso de RED-15
```

Para correrlo a mano: contenedor `mariadb:11` en un puerto libre y un settings fuera del repo que importe `config.settings`,
apunte `DATABASES` al contenedor, suba `read_timeout`/`write_timeout` y deje `MIGRATION_MODULES = {}`; `migrate`,
`migrate programas <anterior>`, `migrate`.

## Anexo C · Regla expand/contract

Entre el código y el esquema, el que se mueve primero es siempre el esquema, y nunca hacia atrás dentro de la misma release.

| Clase | Qué hace | ¿Convive con el código viejo? | Regla |
|---|---|---|---|
| Expand | `AddField null=True`, `AddField NOT NULL` con `DEFAULT` de base, `CreateModel`, `AddIndex`, `AddConstraint` que ya se cumple | Sí | Va sola en la release N, en cualquier momento |
| Migrate | `RunPython` que copia o rellena datos | Sí | Release N o N+1; idempotente y por lotes |
| Contract | `RemoveField`, `DeleteModel`, `RenameField`, `RenameModel`, `AlterField` que achica o pone `NOT NULL`, `RemoveIndex` en uso | No | Solo en N+2, cuando ninguna release viva la lee |

1. Una release nunca mezcla expand y contract sobre la misma columna (`programas/0032` es el antipatrón: se parte en N agregar y
   escribir en las dos, N+1 leer solo la nueva, N+2 borrar la vieja).
2. Renombrar una columna está prohibido: agregar, copiar, escribir en las dos, cambiar el lector y borrar en N+2.
3. Un solo migrador: `RUN_MIGRATIONS=false` en el Deployment web; `migrate` en un Job/initContainer único (RED-19).

## Anexo D · Runbook de rollback (reemplaza `docs/internal/processes.md:245-258` y `:278-282`)

**D.0 · Antes de cada deploy con migración (obligatorio).** icore:
`docker compose -f docker-compose.prod.yml exec -T mysql mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers chaco | gzip > ~/backups/chaco-$(date +%Y%m%d_%H%M%S)-pre-deploy.sql.gz`.
ECOM: pedir el dump por escrito y esperar la confirmación **antes** de espejar a `main` (H-11). Anotar la release de la que
se viene (tag o SHA de `main`) y la última migración aplicada (`showmigrations --plan | grep '\[X\]' | tail -1`).

**D.1 · Qué rollback corresponde.**

| Situación | Qué hacer |
|---|---|
| El deploy no traía migraciones | D.2 (solo código) |
| Traía solo migraciones expand, aplicadas OK | D.2, previa verificación D.2.0 |
| Traía contract, datos destructivos o una barrera de reversa | D.4 (restore). No intentar `migrate <app> <anterior>` |
| El `migrate` falló a mitad **hacia adelante**, en una sola migración | D.3 primero, después decidir |
| El `migrate` falló durante una **reversa** | D.4 directo (RED-15) |

**D.2 · Rollback de código.** D.2.0: listar columnas `NOT NULL` sin default (`information_schema.COLUMNS` con `IS_NULLABLE='NO'
AND COLUMN_DEFAULT IS NULL AND EXTRA NOT LIKE '%auto_increment%'` en `programas_formulario`, `legajos_ciudadano`,
`programas_padronhabilitado`); a cada una que no existía en la release de destino, `ALTER TABLE … ALTER COLUMN … SET DEFAULT
'…'` (solo metadata, reversible) **antes** de bajar la release. D.2.1 ECOM: con tag inmutable (RED-16), `kubectl set image` al
SHA anterior; sin tag, `git revert` del commit de alineación en `ecom/main`, esperar el build y `kubectl rollout restart`
(**`kubectl rollout undo` no sirve**: las dos revisiones apuntan al mismo `:latest`). Verificar con un alta de caso de prueba,
no con `/health/`. D.2.2 icore: `git -C <repo> switch development && git reset --hard <SHA_ANTERIOR>`, `docker compose -f
docker-compose.prod.yml up -d --build --force-recreate web`, `restart nginx` (cachea la IP del upstream).

**D.3 · `migrate` cortado hacia adelante.** No reintentar el deploy ni usar `--fake`; `RUN_MIGRATIONS=false`; diagnosticar con
`showmigrations --plan` y `sqlmigrate <app> <NNNN>` contra `SHOW CREATE TABLE`; completar a mano solo las operaciones que falten
de **esa** migración y recién entonces insertar su fila en `django_migrations`. Si falta más de una operación o hay dudas: D.4.

**D.4 · Restore.** Obligatorio para contract, datos borrados o barreras de reversa (`programas.0032`, `0056`, `0069` —pérdida de
datos—; `programas.0047`, `0048`, `0073`, `legajos.0007`, `users.0023` —UUID—). Bajar la app (`replicas=0` o `stop web
websocket`); `DROP DATABASE` + `CREATE DATABASE` + restore del dump de D.0 (**nunca encima**: deja tablas huérfanas, OPS-01); si
la base viene de otro motor, re-normalizar UUID (V2-NEW-05); desplegar la release anterior y verificar que la última `[X]` sea
la de esa release; levantar y verificar con un alta real; registrar qué se perdió entre el dump y el rollback.

**D.5 · Después, siempre.** Issue con label `incident` y una línea en `## Reversión` de la entrada de `requerimientos.md`
correspondiente con lo que pasó de verdad al revertir.
