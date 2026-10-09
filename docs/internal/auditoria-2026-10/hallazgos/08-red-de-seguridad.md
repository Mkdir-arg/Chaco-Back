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

**Conteo:** 2 CRÍTICA · 28 ALTA · 41 MEDIA · 18 BAJA = **89 fichas** (las 88 del relevamiento del 03/04-oct más
**RED-89**, que salió de la revisión del PR R-05, se midió el 04-oct y es la **segunda CRÍTICA** del frente). Avance al
cierre de la **Ola R mínima** (PRs R-01 a R-10) **más R-19** (#556, Cambio 126), todos mergeados el 04-oct:
**33 ✅ · 3 🟡 · 53 ⬜**; por severidad (✅/🟡/⬜), CRÍTICA 1/1/0, ALTA 14/2/12, MEDIA 14/0/27, BAJA 4/0/14. Los tres 🟡
son RED-01 y RED-20 (el código está, falta el paso del dueño del repo) y RED-10 (falta el gemelo del link público).
R-19 cerró RED-89, RED-04 y RED-06. Además amplían fichas existentes:
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
| RED-01 | Datos personales reales (10.321 personas) en un repo público, en el release y en la imagen de PRD | CRÍTICA | CONF. lectura (API + git) | R (hotfix) | M | 🟡 (falta el PM) |
| RED-02 | Ningún test recorre el URLconf: una ruta que vuelva a quedar abierta pasa el CI | ALTA | CONF. test (barrido) | R | S | ✅ |
| RED-03 | App de campo: pausa probada en 1 de 6 endpoints, período en 3, ramas de error en ninguna | ALTA | CONF. test (coverage) | R | S-M | ✅ |
| RED-04 | Crear, eliminar y activar un rol no se ejecutan por HTTP en ningún test | ALTA | CONF. test (coverage) | R | S-M | ✅ |
| RED-05 | Ningún test sigue un adjunto desde el canal que lo sube hasta la revisión | ALTA | CONF. lectura | R (+3 con DAT-01) | M | ✅ |
| RED-06 | Legajos: 23 de 36 rutas sin test; `/legajos/alertas/` ya dio 500 y sigue sin test | ALTA | CONF. test (coverage) | R (+2) | S-M + S | ✅ |
| RED-07 | Nada impide volver a poner `Trunc*`/`__date` sobre un `DateTimeField` (CONVERT_TZ, 500 en PRD) | ALTA | CONF. test (SQL compilado) | R | S-M | ✅ |
| RED-08 | Los tests del 500 del link público cuentan consultas, no la forma del `WHERE` | ALTA | CONF. test (SQL compilado) | R | S | ✅ |
| RED-09 | Un `UUIDField` nuevo sin `char(36)` pasa el CI; el único test de UUID se saltea siempre | ALTA | CONF. test | R (+3) | S-M (+S) | ✅ |
| RED-10 | Las dos escrituras que dieron 500 bajo el lock no tienen presupuesto de consultas | ALTA | CONF. lectura | R (+4) | S (+S-M) | ✅ |
| RED-11 | Ningún test fija la forma del JSON de `/api/becas/*` que lee la app de campo | ALTA | CONF. lectura (dos repos) | R | S | ✅ |
| RED-12 | `definicion_formulario` y los prefijos `pg-`/`rn-`: contrato de dos repos sin serializer ni test | ALTA | CONF. lectura (dos repos) | R | M | ⬜ |
| RED-13 | El shell de todo el backoffice y `legajos.ready()` dependen de `conversaciones` | ALTA | CONF. lectura | R (test) + 7 | S + M | ✅ |
| RED-14 | Un rollback de release con una columna `NOT NULL` nueva rompe el alta de casos (error 1364) | ALTA | CONF. test (MariaDB 11.8) | R | M | ✅ |
| RED-15 | En MariaDB la reversa falla (errno 150) y deja tabla huérfana y `django_migrations` a mitad | ALTA | CONF. test (MariaDB 11.8) | R | S | ✅ |
| RED-16 | No hay artefacto al que volver: ECOM publica solo `:latest` y `main` no se tagea | ALTA | CONF. lectura (rollout PLAUSIBLE) | R | S | 🟡 |
| RED-17 | Ninguna migración se prueba hacia atrás ni sobre datos; los tests de migración usan los modelos de hoy | ALTA | CONF. test | R | M + S | ✅ |
| RED-18 | La reversa de `0047`, `0048` y `legajos.0007` falla con «Data truncated» | ALTA | CONF. test (MariaDB 11.8) | R | S | ✅ |
| RED-19 | Rolling en k8s: cada pod corre `migrate` (choque) y no hay regla expand/contract | ALTA | CONF. test (MariaDB 11.8) | R (+3 en OPS-07) | S-M | ✅ |
| RED-20 | `development` y `main` sin protección de rama: ningún check es obligatorio | ALTA | CONF. lectura (API) | R | S-M | 🟡 (falta el PM) |
| RED-21 | `publish-main.yml` genera el release sin exigir CI verde y con un denylist escrito a mano | ALTA | CONF. lectura | R | S | ✅ |
| RED-22 | El pipeline de ECOM solo construye la imagen: cero verificación antes del deploy a PRD | ALTA | CONF. lectura | R (propuesta a ECOM) | S | 🟡 |
| RED-23 | `/pushGitLabecom` empuja `test` y `main` en la misma corrida, sin exigir CI ni testing verificado | ALTA | CONF. lectura | R | M | 🟡 |
| RED-24 | Sin gates de contratos del repo: `compile_templates`, `collectstatic`, `requerimientos --check`, `design_audit` | ALTA | CONF. test (corrida) | R | M | ✅ |
| RED-25 | La capacidad `becas.campo` no se prueba en los endpoints ni en el oráculo de identidad | ALTA | CONF. test (mutación M11) | R | S | ✅ |
| RED-26 | `FormularioViewSet` sin test de alcance: un territorial podría leer y editar casos ajenos | ALTA | CONF. test (mutación M14) | R | S | ✅ |
| RED-27 | Promover desde la lista de espera con cupo exactamente 0 no está probado | ALTA | CONF. test (mutación M19) | R | S | ✅ |
| RED-28 | `FINALIZANDO` está en los estados abiertos de vencimientos y ningún test lo cubre | ALTA | CONF. test (mutación M27) | R | S | ✅ |
| RED-29 | El envío del link público no prueba que el relevamiento siga `EN_CURSO` | ALTA | CONF. test (mutación M44) | R | S | ✅ |
| RED-30 | Sin test de humo por pantalla: nada afirma «ninguna ruta da 500» | MEDIA | CONF. test (barrido) | R | S | ✅ |
| RED-31 | `requisito_eliminar` y `subsegmento_eliminar` no se ejecutan en ningún test | MEDIA | CONF. test (coverage) | R | S | ✅ |
| RED-32 | Comandos contra SIIS y RENAPER sin red (`validar_casos_siis`, `completar_casos_renaper`, `sincronizar_programas_siis`) | MEDIA | CONF. test (coverage) | R (+1) | S-M (+S-M) | ✅ |
| RED-33 | Dispositivos y Merenderos: las vistas que operan no tienen test HTTP | MEDIA | CONF. test (coverage) | 5 | M | ✅ |
| RED-34 | Nada obliga a que una ficha cerrada deje un test permanente (0 tests bajo `docs/`) | MEDIA | CONF. test | R | S | ✅ |
| RED-35 | Ningún test afirma que las escrituras críticas sigan siendo atómicas | MEDIA | CONF. lectura | R (+3) | S (+S-M) | ✅ |
| RED-36 | `drf_spectacular` fuera de `INSTALLED_APPS`: `/api/docs/` y `/api/redoc/` dan 500 | MEDIA | CONF. test | R (primero) | S | ✅ |
| RED-37 | El esquema OpenAPI publica tipos falsos y pierde 11 vistas | MEDIA | CONF. test | R (+7) | S-M (+S-M) | ✅ (R; falta Ola 7) |
| RED-38 | Tres motores de condiciones (1 Python + 2 JS, dos repos) sin vectores compartidos | MEDIA | CONF. lectura (dos repos) | R | M | ⬜ |
| RED-39 | Cinco sobres de error JSON leídos con fallback silencioso | MEDIA | CONF. lectura | R (+7) | S (+M) | ✅ (R; falta Ola 7) |
| RED-40 | `JSONField` con estructura implícita: 0 `validators` y nada sobre datos viejos | MEDIA | CONF. lectura | R (+3) | S-M (+S) | ✅ (R y Ola 3) |
| RED-41 | Parsers de RENAPER, Personas y SIIS probados contra diccionarios inventados | MEDIA | CONF. lectura | R | S-M | ✅ |
| RED-42 | Endpoints JSON del backoffice sin contrato; 4 `fetch` literales resuelven 404 | MEDIA | CONF. test (`resolve`) | R (+5) | S-M (+S) | ✅ |
| RED-43 | El CI no tiene ningún gate de contrato de API | MEDIA | CONF. lectura | R | S | ✅ |
| RED-44 | Una capacidad mal tipeada devuelve `False` en silencio y el superusuario no lo ve | MEDIA | CONF. test (prototipo) | R | S | ✅ |
| RED-45 | `GUNICORN_CMD_ARGS` con gevent activa un parche que apaga `validate_thread_sharing` | MEDIA | CONF. lectura | R (+7 en OPS-13) | S | ✅ |
| RED-46 | `programas/models/__init__.py` (3.252 líneas, 90 importadores) sin tests de contrato | MEDIA | CONF. test (radon) | R | S-M | ✅ |
| RED-47 | `normalizar_dni` y sus tres copias agregan un 0 con `float` o `Decimal` | MEDIA | CONF. test | R | S | ✅ |
| RED-48 | «DNI válido» está implementado 6 veces con 3 reglas de largo | MEDIA | CONF. lectura | 3 | S-M | ✅ |
| RED-49 | `cupo_disponible` significa tres cosas y dos pantallas lo rotulan igual | MEDIA | CONF. lectura | R (+4) | S (+S) | ✅ |
| RED-50 | La edad (RN-22) está cuatro veces y tres usan `date.today()` (UTC en los contenedores) | MEDIA | CONF. lectura | R (+3) | S (+S-M) | ✅ |
| RED-51 | Dos `invalidate_dashboard_cache`; `stats_legajos` colgado del modelo equivocado | MEDIA | CONF. lectura | R (+4) | S (+S) | ✅ |
| RED-52 | Contrato implícito por `user._state.fields_cache["profile"]` | MEDIA | CONF. lectura | R (+2) | S (+S) | ✅ |
| RED-53 | Clones literales entre los comandos SIIS y entre las vistas de padrón | MEDIA | CONF. test (pylint + AST) | 1 (+5) | S-M (+S) | ✅ |
| RED-54 | `revision.py` (1.331 líneas): ningún test fija el contexto del detalle | MEDIA | CONF. test (radon) | R (+7) | S-M (+M) | ✅ (R; falta Ola 7) |
| RED-55 | Los context processors corren en cada render y tragan toda excepción sin log | MEDIA | CONF. lectura | R | S | ✅ |
| RED-56 | Los guards de alcance de Becas fallan abiertos si el Programa BECAS no está sembrado | MEDIA | CONF. test | R | S | ✅ |
| RED-57 | 14 reversas `RunPython.noop` (más `users/0007`) pierden datos e informan `OK` | MEDIA | CONF. test (SQLite con datos) | R | S-M | ✅ |
| RED-58 | `legajos.0007` no es re-entrante: un corte deja legajos sin FK y el reintento muere con 1091 | MEDIA | CONF. test (SQL) | 3 | S | ✅ |
| RED-59 | `deploy_prod.sh`: rollback sin base, detached HEAD y un health que siempre da 200 | MEDIA | CONF. lectura | R | S | ✅ |
| RED-60 | `processes.md` enseña un rollback que destruye datos y autoriza `--fake` | MEDIA | CONF. lectura | R (prioridad 1) | S | ✅ |
| RED-61 | `SIIS_API_URL` cae al SIIS de desarrollo y nada lo valida al arrancar | MEDIA | CONF. lectura (PRD PLAUSIBLE) | R | S | ✅ |
| RED-62 | Los presupuestos de performance son autodeclarados: subirlos en el mismo PR pasa | MEDIA | CONF. lectura | 4 | S | ✅ |
| RED-63 | Ruff y Bandit en `continue-on-error`; excepción de `pip-audit` sin vencimiento | MEDIA | CONF. lectura | R | S | ✅ |
| RED-64 | `docs/client/` se publica en GitHub Pages público en cada push, sin revisión | MEDIA | CONF. lectura (API) | 7 | S | ⬜ |
| RED-65 | El guard de `publish-main.yml` exige artefactos muertos y va a bloquear OPS-10/OPS-14 | MEDIA | CONF. lectura | R (+7) | S | ✅ |
| RED-66 | `reabrir` de la app de campo no tiene test negativo de la transición | MEDIA | CONF. test (mutación M17) | R | S | ✅ |
| RED-67 | Ningún test afirma que se tome el `select_for_update` del cupo ni del link | MEDIA | CONF. test (mutaciones M21, M43) | R (+capa 2 en TST-01) | S | ✅ |
| RED-68 | La posición en la lista de espera no está probada en ningún lado | MEDIA | CONF. test (mutación M23) | R | S | ✅ |
| RED-69 | Fecha de nacimiento ausente o futura sin test en el payload SIIS | MEDIA | CONF. test (mutación M34) | R | S | ✅ |
| RED-70 | `celda_segura`: la limpieza de caracteres de control no está probada | MEDIA | CONF. test (mutación M49) | R | S | ✅ |
| RED-71 | `ApiCorsMiddleware` sin tests de contrato (y el Cambio 52 lo da por inexistente) | BAJA | CONF. test (ajustado) | R | S | ✅ |
| RED-72 | El harness e2e de Playwright no existe en el repo: quedan `.pyc` de julio | BAJA | CONF. lectura | R | S | ✅ |
| RED-73 | `CiudadanoConfirmarView` decide antes de mirar si hay sesión | BAJA | CONF. test (barrido) | R | S | ✅ |
| RED-74 | Ocho arreglos mergeados sin ningún test | BAJA | CONF. lectura (git) | R | S | ✅ |
| RED-75 | `/set_dark_mode/` no existe: el toggle de tema postea a un 404 | BAJA | CONF. test (`resolve`) | 5 | S | ✅ |
| RED-76 | Tipado: 2,7 % de retornos anotados, sin mypy ni pyright | BAJA | CONF. test (AST) | 7 | S-M | ⬜ |
| RED-77 | RN-2 del padrón escrita dos veces: property y filtro de queryset | BAJA | CONF. lectura | R | S | ✅ |
| RED-78 | `DashboardView`: copia del inicio sin el blindaje de SEC-14, muerta solo por el orden de URLs | BAJA | CONF. test (`resolve`) | R (+7) | S (+S) | ✅ |
| RED-79 | Tres ciclos de import y nueve aristas vista→vista sin ratchet | BAJA | CONF. test (AST) | R (+2) | S (+S) | ✅ |
| RED-80 | `programa_becas` y `programa_dispositivos`: mismo cache, distinta guarda e invalidación | BAJA | CONF. lectura | 2 | S | ✅ |
| RED-81 | El registro de reglas de vencimiento puede quedar vacío y el comando sale OK | BAJA | CONF. lectura | R | S | ✅ |
| RED-82 | `exportacion_reportes.py` con terminadores CR: git lo trata como binario y pylint lo saltea | BAJA | CONF. test | R | S | ✅ |
| RED-83 | Índices duplicados en `programas_formulario` y `legajos_ciudadano` | BAJA | CONF. test (`information_schema`) | R (+4) | S (+S) | ✅ |
| RED-84 | `requerimientos.py --check` no verifica la sección «Reversión» | BAJA | CONF. lectura | R | S | ✅ |
| RED-85 | Herramientas del CI sin pinear y actions por tag en workflows con `contents: write` | BAJA | CONF. lectura | R (+7) | S (+S) | ✅ |
| RED-86 | Job de tests con timeout de 15 min, sin `--parallel` ni alarma de crecimiento | BAJA | CONF. test (`gh run list`) | 7 | S | ⬜ |
| RED-87 | El largo mínimo del barrio del payload SIIS no se prueba en su borde | BAJA | CONF. test (mutación M33) | R | S | ✅ |
| RED-88 | `manage.py test core users portal --parallel` revienta con `cannot pickle 'traceback'` | BAJA | CONF. test | R | S | ✅ |
| RED-89 | Ningún test recorre el URLconf con un usuario **sin rol**: 200 en 31 rutas, y 17 de Legajos dejan borrar adjuntos y cerrar alertas ajenas (SEC-10, SEC-18, SEC-11) | CRÍTICA | CONF. test (barrido 04-oct) | R (**primero**) | S-M | ✅ |

«Ola» con paréntesis = la ficha tiene una segunda parte en esa ola (detalle en la ficha y en README §6). Horas: S = 2,
S-M = 4, M = 8, L = 20 (README §6).

**Convención de la columna «Avance»:** `✅ (R; falta Ola N)` = **la parte de la Ola R está cerrada** y lo que queda es la
segunda parte, que ya estaba planificada en esa otra ola (y cuyas horas se cuentan allá). `🟡` se reserva para una ficha
cuya **propia parte de la Ola R** quedó incompleta —RED-01 y RED-20, que esperan un paso del dueño del repo, y RED-10,
a la que le falta un test—. Un `⬜` nunca lleva paréntesis.

---

## (a) Flujos críticos y cobertura

### RED-02 · Ningún test recorre el URLconf: una ruta que vuelva a quedar abierta pasa el CI
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (barrido propio de VR1: 288 rutas) · **Origen:** RS-R1-01 (VR1: CONFIRMADO-AJUSTADO) · **Ola:** R · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #553 (Cambio 122, PR R-05), 04-oct-2026 — `core/tests/test_superficie_publica.py` recorre `get_resolver()` recursivo, concreta cada patrón con valores de juguete y lo descarta si no vuelve a resolver. El número de rutas lo mide el propio archivo y no se copia de ningún informe: **315** al 04-oct (los 33 patrones que quedan fuera son los sufijos de formato de DRF, que repiten una ruta ya cubierta). `SuperficieAnonimaTests.test_ninguna_ruta_responde_al_anonimo` exige que toda ruta rebote al anónimo —`401/403/426` o redirección cuyo **path exacto** sea el login o `portal:home`, no un `in`, porque el login vive en la raíz—, con `ALLOWLIST_PUBLICA` literal de 17 entradas, un motivo escrito por entrada y un ratchet que falla en los **dos** sentidos (publicar una ruta tiene que ser deliberado; una entrada que dejó de hacer falta hay que sacarla). **Un MAJOR de la ronda 2 cambió el test de raíz:** `404` y `405` estaban entre los estados que «rebotan» y dejaban ciego al barrido —el revisor le sacó `CapacidadRequeridaMixin` y `LoginRequiredMixin` a `CiudadanoDetailView` sin conseguir ponerlo en rojo—; la versión final no los acepta, repite con POST las rutas POST-only y manda a la allowlist los 404 legítimos del anónimo (las tres del link público de inscripción). Con eso el barrido encontró por su cuenta un segundo caso del molde de RED-73 en `EntregaMercaderiaCreateView`, que se arregló en el mismo PR. Mutación de control: sacar `@login_required` de `archivos_ciudadano_api` → rojo. **Test permanente:** `core.tests.test_superficie_publica.SuperficieAnonimaTests.test_ninguna_ruta_responde_al_anonimo`. **Lo que esta ficha no cubre tiene ahora ficha propia:** el mismo barrido con un usuario de backoffice **sin ningún rol** es **RED-89**.
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
- **Al implementarlo (Cambio 122) la propuesta se corrigió en dos puntos.** (1) Aceptar `404` y `405` como rebote —como
  dice el guion de arriba— deja ciego al barrido: las URLs se concretan con valores de juguete sobre una base vacía, así
  que el 404 es la respuesta esperable de buena parte del URLconf y aceptarlo tapa la pregunta. Se demostró sacándole los
  mixins a `CiudadanoDetailView` sin conseguir poner el test en rojo. La versión final solo acepta
  `401/403/426` o la redirección, repite con POST las rutas POST-only y manda a la allowlist los 404 legítimos del
  anónimo. Con eso el barrido encontró un segundo caso del molde de RED-73 en `EntregaMercaderiaCreateView`. (2) El
  ratchet falla en los **dos** sentidos, no solo al crecer: una entrada que dejó de hacer falta hay que sacarla.
- **Hallazgo abierto que esta ficha no cubre → ahora es `RED-89`:** el barrido pregunta por el anónimo. Con un usuario de
  backoffice autenticado y **sin ningún rol**, 44 rutas contestan `200` y 31 de ellas no son públicas (`/inicio/`,
  `/legajos/alertas/`, `/legajos/ciudadanos/<id>/archivos/`, la api-root de DRF, los `ajax/load-*`). El revisor del PR lo
  levantó con una primera medición de 40; el conteo definitivo, con la clasificación de cuáles son deliberadas y cuáles
  exponen datos, está en **RED-89**.

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

**Resolución:** ✅ Resuelto en el PR R-07 (Cambio 119), 04-oct-2026 — `programas/tests/test_becas_api.py` suma la base
`_SeisEndpointsTest` (los seis endpoints de escritura de una jornada de campo: `iniciar`, `finalizar`, `reabrir`,
`formularios` POST, `formulario` PATCH y `adjuntos` POST) y dos barridos con `subTest` sobre ella:
`PausaEnTodosLosEndpointsTests` (pausa de la convocatoria y pausa propia del relevamiento) y
`PeriodoEnTodosLosEndpointsTests` (franja vencida). Cada caso afirma el **código real** del endpoint —409 con
`{"detail", "pausado": true}` en cinco, **400 solo con `detail`, y envuelto en lista, en el PATCH**, tal cual
D-RED-10— y que nada se escribió (estado y `fecha_finalizado` del relevamiento, `celular` del caso,
`Formulario.objects.count()`, `AdjuntoFormulario.objects.count()`). Las ramas de error entran en
`RelevamientoApiTests` (`capturado_en` inválido en `iniciar` y en `finalizar`, `dni-existe` sin DNI) y el
`GET …/adjuntos/` en `AdjuntoValidacionTests` (listado vacío, listado con un adjunto, y que leer lo ya subido sigue
funcionando con el relevamiento pausado). **El estado de origen de las tres transiciones no se repite acá:** lo
recorre entero RED-66 (Cambio 120, PR R-08), que entró primero; los casos sueltos que este PR había escrito
(`finalizar` fuera de curso, `finalizar` desde `FINALIZANDO`, `reabrir` no finalizado) se podaron al mergear, porque
los `subTest` sobre todo el enum los subsumen. Mutaciones de control ejercidas a mano: sacar el `_respuesta_pausa` de
`finalizar` → rojo; sacarlo de `adjuntos` → rojo; `reabrir` sin `habilitado_en` → rojo.
**Test permanente:** `programas/tests/test_becas_api.py::PausaEnTodosLosEndpointsTests.test_la_pausa_bloquea_y_no_escribe`
y `::PeriodoEnTodosLosEndpointsTests.test_fuera_del_periodo_se_rechaza_y_no_escribe`.

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

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — `RolesEscrituraHttpTests` ejercita las cuatro
escrituras por HTTP: los siete tests de la propuesta más `test_sin_capacidad_de_roles_no_entra_a_ninguna_escritura`
(un usuario sin rol no crea ni elimina). Los ocho pasan **también sobre `development`**, que es lo esperado: RED-04 es
un hueco de cobertura, no un bug — lo que se arregla es que el día que `RolCreateView.post` deje de pasar `operador` a
`RolForm`, o que alguien saque el `try/except SinAdministradorError` de `RolDeleteView`, el CI lo diga. **Dónde la
ficha no coincidía con el código:** la propuesta decía «el `Group` no se crea **o** nace sin esa capacidad»; el
comportamiento real es el primero, y más estricto — el form del admin de programa recorta `categoria` a `Programa` y
las capacidades a los módulos de alcance, así que el POST vuelve al form con errores y no se crea nada.
**Test permanente:** `users.tests.test_roles_abm.RolesEscrituraHttpTests`.

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

**Resolución:** ✅ Resuelto en #604 (Cambio 156, PR R-16), 07-oct-2026 — `AdjuntoLlegaALaRevisionTests` recorre los dos
canales **por HTTP de punta a punta** y los dos terminan en la misma aserción compartida
(`_assert_el_adjunto_se_ve_en_la_revision`): paso 1 + paso 2 del link público con el padrón como fuente de identidad, y
el alta por `POST /api/becas/relevamientos/<pk>/formularios/` + `POST /api/becas/formularios/<pk>/adjuntos/` con Token.
La aserción mira la fila `AdjuntoFormulario`, el bloque del campo en el contexto de `becas:formulario_detalle`
(`es_archivo=True`, `adjunto` no nulo, el mismo pk), el contenido guardado y la URL del archivo en el HTML. **Mutación
de control:** cambiar `pg-` por `pgx-` en `_adjuntos_por_clave` deja los dos tests en rojo nombrando el puente.
**Dónde la ficha no coincidía con el código:** (1) `seed_becas` siembra cinco `PreguntaGlobal` ARCHIVO **obligatorias**,
así que el test desactiva las que no mira para no tener que subir cinco archivos por envío; (2) el rol
`Becas — Administrador` **no** trae `becas.relevamiento.publico`, y sin esa capacidad RN-P13 le da 403 sobre un caso del
link: el test se la agrega explícitamente, que es lo que pasa en producción. El tercer test
(`test_una_pregunta_recreada_con_otro_pk_no_deja_el_adjunto_huerfano`) sigue siendo de DAT-01, en la Ola 3.
**Test permanente:** `programas.tests.test_adjunto_punta_a_punta.AdjuntoLlegaALaRevisionTests`
(`test_el_archivo_subido_por_el_link_se_ve_en_la_revision` y `test_el_archivo_subido_por_la_app_se_ve_en_la_revision`).

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

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — los dos puntos de la capa 1, y la capa 2 se
adelantó al mismo PR por D-RED-14 (SEC-10, SEC-11 y SEC-18). `PantallasDeLegajosAbrenTests` abre las **37** rutas con
un usuario con todas las capacidades y datos reales (ciudadano, legajo, derivación, adjunto, alerta) y falla ante
cualquier `>= 500`; `test_el_mapa_cubre_todas_las_rutas_de_legajos` cruza el mapa literal contra
`legajos.urls.urlpatterns`, así que una ruta nueva sin humo pone el test en rojo con su nombre.
`AlertasDashboardTests` cubre el 200 para un operador de conversaciones (el `FieldError` del Cambio 66, que vuelve a
romperlo si alguien reintroduce el `select_related` inválido), el 200 sin `conversacion.operar` y el contrato JSON de
`count`, `preview` y `cerrar-ajax`. **Dónde la ficha no coincidía con el código:** son **37** rutas, no 36 — SEC-10
partió `eliminar_archivo` en dos (una por dueño) en este mismo PR. Y el test del operador de conversaciones ahora
necesita además `ciudadano.ver`: SEC-18 le puso esa capacidad al dashboard, así que un rol de conversaciones puro ya
no entra (ver «Riesgos» del PR). De paso, `alertas_preview_ajax` dejó de devolver `str(e)` con HTTP 200 —el motivo por
el que el `FieldError` vivió meses sin verse desde afuera—: ahora loguea la traza y contesta 500.
**Test permanente:** `legajos.tests.test_humo_pantallas.PantallasDeLegajosAbrenTests.test_ninguna_pantalla_de_legajos_revienta`
y `legajos.tests.test_alertas_dashboard.AlertasDashboardTests`.

### RED-30 · Sin test de humo por pantalla: nada afirma «ninguna ruta da 500»
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (barrido con superusuario: 305 rutas, 3 con `>= 500`) · **Origen:** RS-R1-06 parte propia (VR1: la parte de Spectacular es RED-36) · **Ola:** R · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #553 (Cambio 122, PR R-05), 04-oct-2026 — `NingunaPantallaDa500Tests.test_ninguna_pantalla_da_500` corre el mismo recorrido de RED-02 con un superusuario y falla ante cualquier `>= 500`. `EXCEPCIONES_HUMO` quedó **vacía**: `/api/docs/` y `/api/redoc/` estuvieron ahí por RED-36 y salieron al mergearse el PR R-04 (Cambio 118), y `test_las_excepciones_del_humo_siguen_siendo_necesarias` se pone rojo el día que una excepción deje de hacer falta. Fuera del humo quedan solo los dos proxies al catálogo de SIIS, que sin la red del organismo contestan **503 a propósito** (`SiisCatalogError` → `JsonResponse(status=503)`): degradación declarada, no una pantalla rota. Hay además `test_la_sesion_del_humo_entra_al_backoffice`, para que un middleware que redirija todo no deje el humo barriendo la nada. **Dónde la ficha no coincidía con el código:** los proxies no se llaman `becas:siis_localidades_json`/`becas:siis_funciones_json` sino `becas:siis_localidades`/`becas:siis_funciones`. Mutación de control: renombrar el template de `RolListView` → rojo. **Test permanente:** `core.tests.test_superficie_publica.NingunaPantallaDa500Tests.test_ninguna_pantalla_da_500`.
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

**Resolución:** ✅ Resuelto en #604 (Cambio 156, PR R-16), 07-oct-2026 — `EliminarRequisitoYSubsegmentoTests` ejecuta
los dos cuerpos completos: el subsegmento usado por una convocatoria no se borra y el `ProtectedError` sale como
mensaje (sacar ese `except` lo convierte en 500); el libre se borra y redirige al segmento; el requisito sin adjuntos se
borra **con su `ItemDiseno`**, que es lo que el Cambio 58 quiere conservar; y `test_las_dos_vistas_exigen_post_y_capacidad`
recorre GET, anónimo y usuario sin rol en las dos vistas con `subTest`, sin que ninguno borre nada.
`test_requisito_con_adjunto_en_un_caso` deja **caracterizado** el daño de DAT-01 —la fila del adjunto desaparece y el
archivo queda huérfano en `media/`— y su mensaje de fallo dice textualmente qué invertir cuando llegue el arreglo.
**Dónde la ficha no coincidía con el código:** el login del backoffice vive en la raíz (`settings.LOGIN_URL` =
`users:login` → `/`), no en `/login/`; el test lo arma con `reverse(settings.LOGIN_URL)`.
**Test permanente:** `programas.tests.test_becas_config.EliminarRequisitoYSubsegmentoTests`.

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

**Resolución:** ✅ Resuelto **la mitad de la Ola R** en el PR R-06 (Cambio 123), 04-oct-2026 — nuevo
`programas/tests/test_comandos_siis_caracterizacion.py`, 23 tests, el cliente HTTP mockeado siempre (y donde el comando
no debería salir a la red, el mock afirma que no se llamó). `validar_casos_siis`: el ensayo no escribe y cuenta bien, el
host de SIIS se informa, las cuatro combinaciones de selección (`--incluir-rechazados`, `--reintentar-errores`,
`--todos`, ya validado), y los dos frenos (`--aplicar` sin credenciales, `--usuario` inexistente).
`completar_casos_renaper`: los dos frenos (sin tabla, sin campos del catálogo), el ensayo, el cruce real con su
normalización de provincia y localidad, `--pisar-existentes`, `--sin-lugar-nacimiento`, `--limite`, `_ok = 0` y el
avance **lote a lote**. `sincronizar_programas_siis`: sin cambios, catálogo vacío, `--dry-run` y SIIS caído.
**Desvío de la ficha, a favor del código:** el test propuesto `test_catalogo_vacio_no_pisa_nada` se llama
`test_catalogo_vacio_marca_todo_desconocido`, porque el comando pisa **a propósito** —`listar_programas_todos` pide
`estado=TODOS` justamente porque una baja se ve como una ausencia— y el costo (un catálogo vacío por un error del
servicio bloquea todos los programas) queda fijado a la vista para que la Ola 1 lo decida.
**Nota de implementación:** `information_schema` y `DATABASE()` se emulan sobre SQLite (base adjunta en memoria + una
función registrada en la conexión) en vez de saltear la clase en motores que no sean MySQL: el CI corre SQLite y
saltearla dejaría a la guarda sin red. El SQL del comando corre tal cual.
Verificado a mano: volver a un solo lote (`_lotes(ids, len(ids))`) → `test_procesa_por_lotes` en rojo; sacar el
`exclude(estado=RECHAZADO)` de `_casos` → 4 tests en rojo.

**Resolución (segunda parte, Ola 1):** ✅ Cerrada en #610 (Cambio 162), 07-oct-2026 — nuevo
`programas/tests/test_validar_casos_siis.py::ValidarCasosSiisTests`, 11 tests, todos **con `--aplicar`**: lo que R-06
dejó fijado era el ensayo, y lo que la ficha nombra como frágil solo se ve cuando el comando corre de verdad. Los seis
de la propuesta (`test_toma_solo_los_casos_sin_validacion`, `test_reintentar_errores_suma_los_que_quedaron_en_error`,
`test_un_rechazado_por_el_revisor_se_saltea_salvo_incluir_rechazados`,
`test_diez_errores_tecnicos_seguidos_detienen_la_corrida`, `test_un_ok_entre_errores_reinicia_el_contador`,
`test_sin_credenciales_con_aplicar_corta_con_commanderror`) más cinco que salieron de mirar el código al lado de la
ficha: `test_el_limite_corta_la_lista_por_el_orden_de_pk`, `test_un_caso_sin_dni_se_saltea_y_no_cuenta_como_error` —un
salteo no puede sumar al freno ni, peor, ponerle el contador en cero a una racha de errores de verdad—,
`test_el_usuario_queda_como_solicitante_de_la_validacion`, `test_un_rechazo_de_siis_no_es_una_falla_tecnica` y
`test_el_tope_de_errores_se_puede_bajar`.
**Desvío de la ficha, a favor del código:** el patch no va sobre `programas.services.validacion_siis.validar_formulario_en_siis`
sino sobre `programas.management.commands.validar_casos_siis.validar_formulario_en_siis`. El comando importa el nombre
en su encabezado, así que parchear el módulo del servicio no cambia la referencia que el comando ya tiene: con el
target de la ficha los tests pasarían **saliendo a la red de verdad**, que es exactamente lo que no se quiere. (La
caracterización de R-06 usa el target de la ficha y no se nota porque ahí el comando nunca llega a llamar al servicio.)
`CompletarCasosRenaperTests.test_un_caso_que_falla_no_corta_el_resto` **sí necesitó tocar código**: hoy una excepción
en un caso mataba la corrida, y con los lotes anteriores ya confirmados volver a correrla avanzaba hasta el mismo caso
y moría ahí para siempre, sin flag con el que saltearlo. Ahora el caso se saltea, se cuenta y se nombra por pk en el
resumen; el traceback va a `logger.exception` (log del pod) y no a la consola, porque puede traer valores del caso.
Verificado a mano con tres mutaciones sobre `validar_casos_siis`: invertir el `order_by` del `Subquery`
(`-creado, -id` → `creado, id`) → `test_reintentar_errores_suma_los_que_quedaron_en_error` en rojo; sacar el
`exclude(estado=RECHAZADO)` → `test_un_rechazado_por_el_revisor_se_saltea_salvo_incluir_rechazados` en rojo; cambiar el
`if freno.registrar(falla): break` por un `freno.registrar(falla)` suelto → los dos tests del freno en rojo.
**Test permanente:** `programas.tests.test_validar_casos_siis.ValidarCasosSiisTests` y
`programas.tests.test_comandos_siis_caracterizacion.CompletarCasosRenaperTests.test_un_caso_que_falla_no_corta_el_resto`.
**Queda abierto (Ola 1, PR 7):** los seis tests de `validar_casos_siis` con `validar_formulario_en_siis` mockeado de
verdad (contador de errores seguidos, `--max-errores`) y `test_un_caso_que_falla_no_corta_el_resto`, más RED-53.
**Test permanente:** `programas/tests/test_comandos_siis_caracterizacion.py::CompletarCasosRenaperTests.test_procesa_por_lotes`

### RED-33 · Dispositivos y Merenderos: las vistas que operan no tienen test HTTP
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (coverage) · **Origen:** RS-R1-11 (VR1: CONFIRMADO) · **Ola:** 5 (con los parches v1) · **Esfuerzo:** M (8 h)

**Resolución:** ✅ Resuelta en #611 (Cambio 164, PR 8 de la Ola 5), 07-oct-2026 — **30 tests HTTP, ningún cambio de comportamiento**: son caracterización, que es lo que la ficha pedía. `programas/tests/test_admisiones_vistas.py::AdmisionesPorHttpTests` (16) entra por la URL a las cuatro pantallas con los cuatro perfiles —anónimo (302 al login), cuenta sin rol de Dispositivos (403), rol con la capacidad justa y superusuario—, y `programas/tests/test_merenderos.py` suma `EntregaDeMercaderiaTests` (5) y `MerenderoDetalleYEstadoPorHttpTests` (9). **Las tres conductas que la ficha nombra quedaron verificadas por mutación, una por una:** pasar `usuario=None` en vez de `request.user` pone rojo el egreso y la promoción; sacar el `if admision.dispositivo_id != self.get_dispositivo().pk: raise PermissionDenied` de `get_admision`/`get_espera` pone rojo las dos pantallas que operan por id ajeno; y resolver el merendero de la entrega desde el cuerpo del POST en vez del `pk` de la URL pone rojo `test_una_entrega_de_un_merendero_ajeno_no_se_crea`. **Desvíos de la ficha, los tres code-first:** (1) `test_las_cuatro_exigen_post` no se puede escribir como la ficha lo nombra —tres de las cuatro vistas **tienen** GET, que dibuja el formulario—, así que el test afirma lo que de verdad protege: el GET no mueve nada y la lista de espera, que no tiene POST, contesta 405. (2) **La promoción no persiste quién promovió**: `promover_espera` usa el `usuario` para resolver la membresía, pero no hay campo «promovida por»; el test ata la acción a su autor espiando el kwarg (`patch(..., side_effect=promover_espera)`, que corre el servicio real) y la ausencia del campo queda anotada, no arreglada —agregarlo es una migración y no está en la ficha—. (3) Se midió una conducta que la ficha no nombra y conviene conocer: el combo de destino del traslado sale de `dispositivos_visibles`, que exige `dispositivo.ver`, así que un rol con `egresar` y sin `ver` no puede trasladar a ningún lado; y el destino pide `dispositivo.admitir` aparte (403 en el POST). **Test permanente:** `programas.tests.test_admisiones_vistas.AdmisionesPorHttpTests`, `programas.tests.test_merenderos.EntregaDeMercaderiaTests` y `programas.tests.test_merenderos.MerenderoDetalleYEstadoPorHttpTests`. **Para la v2:** si D-V1 = no, estos 30 tests son el criterio heredable del README §7.
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

**Resolución:** ✅ Resuelto en #553 (Cambio 122, PR R-05), 04-oct-2026 — `core/tests/test_cors_api.py` fija el contrato de `ApiCorsMiddleware` en tres clases: `ApiCorsTests` (6 tests: sin orígenes configurados ninguna respuesta lleva `Allow-Origin`; un origen de la lista recibe las cabeceras y otro no; con `DEBUG=False` un host privado no pasa y con `DEBUG=True` el prefijo de dev acepta un host ajeno —`10.atacante.com`, que es el agujero que la ficha señala—; una ruta fuera de `/api/` nunca lleva CORS; sin cabecera `Origin` no agrega nada), `OptionsAnonimoTests` (2) y `ConfiguracionCorsTests` (3: el middleware está montado, **ningún** `.env.*.example` trae orígenes cargados, y la variable está documentada vacía con su porqué). El gotcha de la ficha se resolvió como decía: `allowed_origins` se lee en `__init__` con `os.getenv`, así que `override_settings` no sirve y los tests instancian el middleware con la variable puesta. La frase imprecisa del **Cambio 52** («no hay `django-cors-headers` en el proyecto, así que ningún sitio externo puede leerlo») **no se reescribe** —el archivo de requerimientos no se reescribe nunca—: la conclusión sigue siendo correcta, la corrección del motivo queda registrada en el Cambio 122 y lo que ahora la sostiene es este módulo. **Test permanente:** `core.tests.test_cors_api.ApiCorsTests` y `core.tests.test_cors_api.ConfiguracionCorsTests`. **Operativo (PM / ECOM):** `DJANGO_CORS_ALLOWED_ORIGINS` tiene que seguir **vacía** en testing y en PRD; el test solo cubre los `.env.*.example` del repo.
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

**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026, con el **default D-RED-06 aplicado = No** —
no se reconstruye un e2e por ahora. **Code-first, lo que había es menos de lo que la ficha suponía:** en
`tests/e2e/` del checkout principal no quedó **ni un `.py`**, solo `__pycache__/`, `pages/__pycache__/` y
`.pytest_cache/`, todos de julio-2026 y bytecode de Python 3.14 (incompatible con el 3.12 del CI). Nunca estuvo
versionado (`git ls-files tests/` vacío), así que un PR no puede borrarlo: **el `rm` queda como paso operativo del
PM**, anotado en la entrada del Cambio 163. Lo que sí hace el PR es cerrarle la puerta desde el repo: `/tests/e2e/`
entra al `.gitignore` —ahí viven el usuario y la clave del compose local, y un `git add -A` distraído los
publicaría— y cuatro tests afirman que nada de `tests/` está versionado, que la regla del `.gitignore` sigue puesta,
que **no hay bytecode en el árbol** y que **ningún workflow menciona Playwright**, que es la forma ejecutable de
«nunca como gate». Si alguna vez se reconstruye, ese último test se pone rojo y obliga a volver a discutir D-RED-06.
**Test permanente:** `core/tests/test_higiene_fuentes.py::HarnessE2ENoVersionadoTests.test_ningun_workflow_depende_de_playwright`
(y `.test_no_hay_nada_versionado_bajo_tests`, `.test_el_gitignore_cubre_el_harness_local`, `.test_no_hay_bytecode_versionado`).

### RED-73 · `CiudadanoConfirmarView` decide antes de mirar si hay sesión
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (barrido de VR1) · **Origen:** RS-VR1-NEW-01 · **Ola:** R · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #553 (Cambio 122, PR R-05), 04-oct-2026 — de los dos caminos de la propuesta se eligió **mover la precondición a los handlers**, no poner `if not request.user.is_authenticated` arriba del `dispatch`: la precondición de RENAPER vive ahora en `CiudadanoConfirmarView._sin_datos_de_renaper`, que llaman `get` y `post`, o sea ya con `CapacidadRequeridaMixin` y `LoginRequiredMixin` resueltos. Un anónimo va al login con su `?next=`, y no se estrena una sesión anónima solo para colgarle el `messages.error`. **Dónde la ficha no coincidía con el código:** el `test_sin_capacidad_da_403` que pedía la propuesta no corresponde —el contrato real del backoffice sin capacidad es **redirect** al inicio, y el 403 es solo para `XMLHttpRequest`—, así que los tests quedaron escritos contra el contrato real (`test_sin_capacidad_no_llega_al_alta_aunque_no_haya_datos_de_renaper` y `test_sin_capacidad_por_ajax_da_403`), más `test_con_capacidad_y_sin_datos_de_renaper_vuelve_al_alta`, que mantiene viva la precondición para quien sí puede crear. El mismo molde apareció una segunda vez en `EntregaMercaderiaCreateView` (Merenderos) —lo encontró el barrido de RED-02, no la ficha— y se arregló acá con la misma forma. **Test permanente:** `legajos.tests.test_ciudadanos_alta.ConfirmarTests.test_un_anonimo_va_al_login_no_al_alta`; el segundo caso lo protege el barrido de RED-02.
- **Ubicación:** `legajos/views/ciudadanos.py:153-164`: el `dispatch` lee la sesión de RENAPER y redirige a
  `legajos:ciudadano_nuevo` **antes** de `super().dispatch()`, que es donde corren `LoginRequiredMixin` y la capacidad.
- **Qué es frágil:** no hay fuga (lee la sesión del propio solicitante), pero es la única ruta del barrido que no se
  comporta como el resto, crea una sesión anónima para el `messages.error` y es el molde equivocado: cualquier
  precondición arriba de `super().dispatch()` corre antes de la autorización.
- **Propuesta:** `if not request.user.is_authenticated: return super().dispatch(request, *args, **kwargs)` como primera
  línea (o mover la precondición a `get`/`post`). Tests en `legajos/tests/test_ciudadanos_alta.py::ConfirmarTests`:
  `test_un_anonimo_va_al_login_no_al_alta` (redirección a `settings.LOGIN_URL`) y
  `test_sin_capacidad_da_403_aunque_no_haya_datos_de_renaper`.

### RED-89 · Ningún test recorre el URLconf con un usuario sin rol: 200 en 31 rutas, y 17 de Legajos dejan borrar adjuntos y cerrar alertas ajenas
**Severidad:** CRÍTICA (subida de ALTA en la ronda 2 del PR #555, al medirse el borrado; la misma medición subió **SEC-10** a CRÍTICA, que es la ficha dueña del arreglo: `DELETE /legajos/archivos/<id>/eliminar/` hace **hard delete** de cualquier `Adjunto` —`archivo.delete()`, sin papelera ni auditoría— para **cualquier** cuenta de backoffice autenticada, incluido un rol de Becas o de Dispositivos sin una sola capacidad de Legajos. Mismo encuadre que SEC-02: «cualquier autenticado escribe sobre datos del ciudadano». No es CRÍTICA-por-anónimo —las cuentas las crea el administrador y `PortalCiudadanoMiddleware` deja a los ciudadanos del portal afuera—, pero el daño es destructivo e irreversible, y los documentos del ciudadano son justo lo que **la etapa 1 de SEC-09** puso detrás de login) · **Estado:** CONFIRMADO con test (barrido propio, 04-oct-2026, sobre `origin/development @ cdd9c71`; borrado y escrituras re-medidos en la ronda 2 sobre `@ 005508b`) · **Origen:** revisor del PR R-05 (#553); anotado como hallazgo abierto en RED-02 y en los *Pendientes* del Cambio 122; borrado medido por el revisor del PR #555. **La medición no descubre rutas nuevas: confirma y agrava `SEC-10` (adjuntos), `SEC-18` (alertas y el `pk` no numérico) y `SEC-11` (las APIs JSON de legajos)**, que son las dueñas del arreglo y ya estaban en la Ola 2. Lo propio de esta ficha es el **barrido** que lo habría detectado y el ratchet que impide que vuelva · **Ola:** R (**primero**, PR R-19) · **Esfuerzo:** S-M (4 h; las capacidades las cuentan SEC-10, SEC-11 y SEC-18, que se adelantan al mismo PR — ver D-RED-14)
- **Ubicación exacta de las 17 rutas de Legajos** (nombre de URL → vista; `legajos/urls/__init__.py`). Las once de
  `legajos/views/contactos_api.py` y las cuatro de `legajos/views/alertas.py` llevan **solo `@login_required`**; las dos
  de `legajos/api_views/__init__.py:65-102` cuelgan de `AlertasViewSet`, con
  `permission_classes = [BackofficeAutenticado, IsAuthenticated]` y **ninguna capacidad**:

  | URL | Vista | Archivo:línea |
  |---|---|---|
  | `legajos:alertas_dashboard` `/legajos/alertas/` | `alertas_dashboard` | `legajos/views/alertas.py:18` |
  | `legajos:alertas_count_ajax` `/legajos/alertas/count/` | `alertas_count_ajax` | `legajos/views/alertas.py:81` |
  | `legajos:alertas_preview_ajax` `/legajos/alertas/preview/` | `alertas_preview_ajax` | `legajos/views/alertas.py:98` |
  | `legajos:cerrar_alerta_ajax` `/legajos/alertas/<id>/cerrar-ajax/` | `cerrar_alerta_ajax` | `legajos/views/alertas.py:71` |
  | `legajos:cerrar_alerta_ciudadano` `/legajos/alertas/<id>/cerrar/` | `cerrar_alerta_api` | `legajos/views/contactos_api.py:124` |
  | `legajos:alertas_ciudadano` `/legajos/ciudadanos/<id>/alertas/` | `alertas_ciudadano_api` | `legajos/views/contactos_api.py:97` |
  | `legajos:actividades_ciudadano` `/legajos/ciudadanos/<id>/actividades/` | `actividades_ciudadano_api` | `legajos/views/contactos_api.py:18` |
  | `legajos:timeline_ciudadano` `/legajos/ciudadanos/<id>/timeline/` | `timeline_ciudadano_api` | `legajos/views/contactos_api.py:174` |
  | `legajos:archivos_ciudadano` `/legajos/ciudadanos/<id>/archivos/` | `archivos_ciudadano_api` | `legajos/views/contactos_api.py:75` |
  | `legajos:archivos_legajo` `/legajos/<uuid>/archivos/` | `archivos_legajo_api` | `legajos/views/contactos_api.py:183` |
  | `legajos:evolucion_legajo` `/legajos/<uuid>/evolucion/` | `evolucion_legajo_api` | `legajos/views/contactos_api.py:156` |
  | `legajos:prediccion_riesgo` `/legajos/ciudadanos/<id>/prediccion-riesgo/` | `prediccion_riesgo_api` | `legajos/views/contactos_api.py:139` |
  | `legajos:subir_archivos_ciudadano` `/legajos/ciudadanos/<id>/subir-archivos/` | `subir_archivos_ciudadano` | `legajos/views/contactos_api.py:27` |
  | `legajos:subir_archivos` `/legajos/<uuid>/subir-archivos/` | `subir_archivos_legajo` | `legajos/views/contactos_api.py:51` |
  | `legajos:eliminar_archivo` `/legajos/archivos/<id>/eliminar/` | `eliminar_archivo` → `eliminar_archivo_por_id` (`legajos/services/contactos.py:47`) | `legajos/views/contactos_api.py:84` |
  | `alertaciudadano-list` `/api/legajos/alertas/` | `AlertasViewSet.list` | `legajos/api_views/__init__.py:65` |
  | `alertaciudadano-count` `/api/legajos/alertas/count/` | `AlertasViewSet.count` | `legajos/api_views/__init__.py:85` |

  La decimoctava, `alertaciudadano-cerrar` `/api/legajos/alertas/<id>/cerrar/`
  (`AlertasViewSet.cerrar`, `legajos/api_views/__init__.py:95`), **no está entre las 31** porque con la base vacía del
  barrido no hay objeto que cerrar (404 con `pk` numérico, 500 con el `pk` de juguete del recorrido); con una alerta
  sembrada contesta 200 y escribe.
- **Qué es frágil:** la Ola 0 y RED-02 cerraron la pregunta «¿qué ve un **anónimo**?». Nadie preguntó «¿qué ve un
  **autenticado sin rol**?», que es el usuario recién creado, el del programa equivocado y el que quedó sin capacidades
  después de un cambio de rol. `core/tests/test_superficie_publica.py` no lo cubre: su cliente es anónimo.
- **Qué cambio lo rompería sin que nadie se entere:** nada tiene que romperse, ya está así; y una vista nueva de Legajos
  copiada del molde de al lado (`@login_required` solo) suma otra ruta sin que ningún test diga nada.
- **Evidencia (medida el 04-oct-2026 con un `User` recién creado, sin grupos, sin `user_permissions` y sin
  `is_superuser`, sobre el mismo recorrido de `core/tests/test_superficie_publica.rutas_concretas()`):** de las **315**
  rutas, **44 contestan 200**. 13 están en `ALLOWLIST_PUBLICA` (login, recupero, `/portal/`, `/health/`): quedan **31
  rutas de backoffice** abiertas a un usuario sin rol. Repetida con un `Ciudadano` real («Mirta Quiroga») y una
  `AlertaCiudadano` CRÍTICA suya:

  | Grupo | Rutas | Qué se midió |
  |---|---:|---|
  | **Legajos — exponen datos** | 7 | **3 traen el nombre del ciudadano:** `/legajos/alertas/` (HTML de 59 KB: «Mirta Quiroga» y el texto de la alerta), `/legajos/alertas/preview/` (`ciudadano_nombre` + `mensaje`) y `/api/legajos/alertas/` (ídem en JSON paginado). **2 traen solo el texto de la alerta**, no el nombre: `/legajos/ciudadanos/<id>/alertas/` y `/legajos/ciudadanos/<id>/timeline/`. **2 son un contador global:** `/legajos/alertas/count/` y `/api/legajos/alertas/count/` (`{"count": 1, "criticas": 1}`) |
  | **Legajos — escrituras** | 5 | **Las 5 medidas, todas con efecto real.** `DELETE /legajos/archivos/<id>/eliminar/` → 200 `{"success": true}` y el `Adjunto` **deja de existir** (`Adjunto.objects.filter(pk=…).exists()` → `False`): es un **hard delete** sin papelera ni auditoría, vía `eliminar_archivo_por_id`, que hace `get_object_or_404(Adjunto, id=…).delete()` sin mirar de quién es el adjunto. `POST /legajos/alertas/<id>/cerrar-ajax/` y `POST /legajos/alertas/<id>/cerrar/` → 200 y la alerta ajena queda en `activa=False`. `POST /legajos/ciudadanos/<id>/subir-archivos/` y `POST /legajos/<uuid>/subir-archivos/` llegan al handler —contestan «No se seleccionaron archivos», o sea el guard no las frenó— y con un archivo adjunto escribirían. **Una sexta, fuera de las 31:** `POST /api/legajos/alertas/<id>/cerrar/` da 404 con la base vacía, pero con una alerta sembrada contesta 200 y la cierra |
  | **Legajos — resto** | 5 | `/legajos/ciudadanos/<id>/{actividades,archivos,prediccion-riesgo}/` y `/legajos/<uuid>/{archivos,evolucion}/`: con la base de prueba vacía devuelven listas vacías o scores en cero; el payload lo arman los mismos selectores que los de arriba, sin filtro de alcance, así que con datos devuelven los del ciudadano pedido |
  | **Catálogos y agregados — legítimas** | 10 | las 3 api-root de DRF (`/api/core/`, `/api/legajos/`, `/api/becas/`: listan nombres de endpoints), `/api/core/{dias,localidades}/`, los 3 `ajax/load-{localidades,municipios,subsecretarias}/`, `/configuracion/programas/` (catálogo institucional) e **`/inicio/`**, que es deliberada: se verificó que su HTML **no** contiene ni el nombre ni el DNI del ciudadano sembrado, solo contadores agregados |
  | **Conversaciones — legítimas** | 4 | `/{api/conversaciones,conversaciones/api}/alertas/{count,preview}/`: **tienen el guard adentro de la vista**, no en el decorador. `alertas_conversaciones_count` y `alertas_conversaciones_preview` (`conversaciones/api_views/__init__.py:17-40`) llaman a `usuario_tiene_permiso_conversaciones(request.user)` y, si da `False`, devuelven `{"count": 0}` y `{"results": []}` con **200**. O sea: contestan, pero vacío. No exponen nada |

  Suma: 7 + 5 + 5 (Legajos) + 10 + 4 = **31**.

  Un hallazgo lateral del mismo barrido: `POST /api/legajos/alertas/x/cerrar/` —el `pk` de juguete del recorrido no es
  numérico— da **500**, porque `AlertasService.cerrar_alerta` recibe el `pk` crudo; es la única ruta del URLconf que
  revienta con este usuario.
- **Propuesta (mismo molde que RED-02, en dos partes):**
  1. **Ola R, PR R-19 (4 h) — el barrido.** En `core/tests/test_superficie_publica.py`, tercera clase
     `SuperficieSinRolTests.test_ninguna_ruta_privada_responde_a_un_usuario_sin_rol`: mismo `rutas_concretas()`, cliente
     con un `User` sin grupos ni permisos, `ALLOWLIST_SIN_ROL` **literal y medida** con un motivo de una línea por
     entrada, y el ratchet de las dos direcciones que ya usa `ALLOWLIST_PUBLICA`. Rebotar acá es 403, redirect al inicio
     o el 403 de `XMLHttpRequest` (contrato real de `_respuesta_sin_permiso`, el mismo que fijó RED-73).

     **Qué va a cada lado, decidido** (el implementador no tiene que volver a juzgarlo):

     | Rutas | Dónde van | Motivo |
     |---|---|---|
     | Las 13 de `ALLOWLIST_PUBLICA` | `ALLOWLIST_SIN_ROL` | si un anónimo puede, un autenticado también |
     | 3 api-root de DRF, `/api/core/{dias,localidades}/`, 3 `ajax/load-*`, `/configuracion/programas/` | `ALLOWLIST_SIN_ROL` | catálogo o índice de endpoints, sin datos de personas |
     | `/inicio/` | `ALLOWLIST_SIN_ROL` | «es el destino al que redirige el propio `_respuesta_sin_permiso`; solo contadores agregados, verificado» |
     | **Las 4 de Conversaciones** | **`ALLOWLIST_SIN_ROL`**, con el motivo literal **«responde vacío, el guard está adentro de la vista (`usuario_tiene_permiso_conversaciones`)»** | contestan 200 pero con `count: 0` y `results: []`: no exponen nada, y `conversaciones` está fuera de uso. **No** van a `expectedFailure`: ponerlas ahí afirmaría que hay un bug que arreglar, y no lo hay |
     | **Las 17 de Legajos** | **`@unittest.expectedFailure`** con «RED-89» en el docstring | son el bug; el PR del punto 2 saca el decorador y las deja rebotando |

     El `expectedFailure` va en un test aparte (`test_las_rutas_de_legajos_siguen_abiertas_red89`) que recorre la lista
     literal de las 17, para que el test principal quede verde de verdad y el día que se arregle Legajos el
     `unexpectedSuccess` avise solo.
  2. **Las capacidades no son de esta ficha: ya tienen dueño.** Esta ficha **no** escribe una propuesta de autorización
     paralela —sería una tercera copia de la misma regla—. El arreglo de las 17 rutas vive en tres fichas de
     `01-seguridad.md` que esta medición confirma y agrava, y que por **D-RED-14** se adelantan al mismo PR R-19:

     | Ficha | Qué cubre de las 17 | Dónde se hace |
     |---|---|---|
     | **SEC-10** (CRÍTICA, 4 h) | las 5 de adjuntos: `archivos_ciudadano_api`, `archivos_legajo_api`, los dos `subir_archivos_*` y `eliminar_archivo`. Su propuesta es mejor que un `@requiere` suelto: ruta nueva con el dueño en la URL y `eliminar_archivo_de_objeto(instance, archivo_id)`, que filtra por `content_type` + `object_id`, más `archivo.archivo.delete(save=False)` para no dejar el blob huérfano | **R-19, completa** |
     | **SEC-18** (MEDIA, 2 h) | las 7 de alertas: el dashboard, los dos `count`, el `preview`, las **dos** entradas de cierre que están entre las 17 (`cerrar_alerta_ajax` y `cerrar_alerta_api`), más `AlertasViewSet.cerrar`, la 18.ª, que queda fuera del barrido pero es el mismo agujero. Incluye el `self.get_object()` que además mata el 500 del `pk` no numérico, y el fallback `AlertaCiudadano.objects.none()` de `FiltrosUsuarioService` | **R-19, completa** |
     | **SEC-11** (ALTA, 2 h) | las 5 restantes (`actividades`, `evolucion`, `timeline`, `alertas_ciudadano_api`, `prediccion-riesgo`) | **partida:** en R-19 van las 5 (1 h); en la Ola 2, el ascenso de 3 de ellas (1 h) — ver el piso de abajo |

     **El piso de `ciudadano.ver` cubre las 17, también las sensibles.** Tres de las de SEC-11 —`timeline_ciudadano_api`,
     `alertas_ciudadano_api` y `prediccion_riesgo_api`— tienen como capacidad **fina** `ciudadano.sensible`, que depende
     de **D-11** y por eso quedaba en la Ola 2. Si R-19 las dejara con solo `@login_required` a la espera de esa
     decisión, el PR no podría sacar sus `expectedFailure` y cerraría con tres rutas abiertas: la ficha quedaría «hecha»
     con el agujero puesto. Así que **R-19 les pone `@requiere("ciudadano.ver")` como piso** —una capacidad que ya
     existe y no necesita decisión— y la **Ola 2 (PR 3) las sube a `ciudadano.sensible`** cuando D-11 se resuelva.
     Subir un `@requiere` de una capacidad a otra es un cambio de una línea por vista: el reparto de horas no se mueve
     (R-19 1 h, Ola 2 1 h).

     Lo que R-19 tiene que dejar escrito al cerrar: **los 17 `expectedFailure` del punto 1 sacados, sin excepciones**
     (de ahí el piso de arriba), el conteo de `ALLOWLIST_SIN_ROL` ajustado en el mismo commit, y la línea
     «Resolución:» de SEC-10 y SEC-18 (RED-34). SEC-11 queda 🟡 hasta que la Ola 2 cierre lo de `ciudadano.sensible`.
- **Verificación:** la clase nueva en verde con `& $env:PY manage.py test core.tests.test_superficie_publica`; con el
  punto 2 hecho, **los 17 `expectedFailure` sacados** (ninguna de las 17 queda con solo `@login_required`) y el conteo
  de la allowlist bajado en el mismo commit. Mutaciones de control:
  sacarle el `@requiere` a `alertas_preview_ajax` tiene que poner el barrido en rojo, y el borrado tiene su propio test
  de regresión (`legajos/tests/`: un usuario sin rol hace `DELETE` sobre un `Adjunto` ajeno → rebota y el adjunto sigue).

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — `SuperficieSinRolTests` recorre el mismo
`rutas_concretas()` de RED-02 con un `User` recién creado (sin grupos, sin `user_permissions`, sin `is_superuser`).
`ALLOWLIST_SIN_ROL` quedó en **31 entradas**: las 17 de `ALLOWLIST_PUBLICA`, que hereda («si un anónimo puede, un
autenticado también»), más **14 propias** —3 api-root de DRF, `/api/core/{dias,localidades}/`, los 3 `ajax/load-*`,
`/configuracion/programas/`, `/inicio/` y las **4 de Conversaciones** con el motivo literal acordado—. **Los 17
`expectedFailure` no llegaron a escribirse: las 17 rutas se cerraron en el mismo PR** (SEC-10, SEC-11, SEC-18), así que
el barrido nació en verde con las 17 rebotando. Hay un cuarto test, `test_ninguna_ruta_revienta_con_un_usuario_sin_rol`,
que mata el **500** de `POST /api/legajos/alertas/x/cerrar/`. **Dónde la ficha no coincidía con el código:** el contrato
de «rebotar» de RED-02 (`404` y `405` **no** rebotan) no se podía trasladar tal cual. Con él, el barrido lista ~24 rutas
más —Becas/cupo, el wizard de `configuracion`, `marcar_leidos`— que **sí** tienen guard pero resuelven el objeto antes
(`dar_baja_beneficiario_view`: `get_object_or_404` y después `PermissionDenied`), así que contestan 404 al `pk` de
juguete. Cerrarlas es reordenar vistas de otras fichas y el barrido mediría lo mismo antes y después. Por eso
`SuperficieSinRolTests` mide **qué le llega al usuario** (`2xx`), que es exactamente lo que reporta la evidencia de esta
ficha —31 rutas— y deja el 404/405 anotado como límite explícito en el docstring; `SuperficieAnonimaTests` sostiene la
regla estricta. Mutación de control: la medición inicial del 04-oct, con las 17 todavía abiertas, listó
`alertas_preview_ajax` entre las 31 — el barrido ve exactamente lo que tiene que ver. **Test permanente:**
`core.tests.test_superficie_publica.SuperficieSinRolTests.test_ninguna_ruta_privada_responde_a_un_usuario_sin_rol`.

**Queda anotado, sin arreglar (revisión del PR #556, 04-oct-2026):**

- **Lo que este barrido estructuralmente no puede ver: el oráculo de existencia.** Una vista que
  resuelve el objeto antes del guard —molde en `programas/views/cupo.py:147-156`,
  `get_object_or_404` y después `PermissionDenied`— contesta **404 al `pk` inexistente y 403 al
  real**. La diferencia le dice a quien no tiene permiso si el objeto existe, y el barrido, que mide
  `2xx`, nunca la va a detectar (tampoco la vería el contrato estricto de RED-02: los dos casos son
  «no 2xx»). Es un hallazgo **de otra naturaleza** —fuga por canal lateral, no superficie abierta— y
  necesita su **ficha nueva** en el frente de seguridad, con su propio test: mismo endpoint, `pk`
  inexistente vs. `pk` real, el mismo usuario sin capacidad, y las dos respuestas iguales.
- **La rama `config.administrar` de `legajos/services/filtros_usuario.py:20` quedó muerta para el
  rol «Configuración» del seed**, que trae `config.ver` y `config.administrar` pero **no**
  `ciudadano.ver`: el alcance global se le sigue calculando y las vistas que lo usarían lo rebotan
  antes. En los hechos, «ver todas las alertas» pasó a ser del superusuario. **Decisión del PM:**
  tildarle `ciudadano.ver` a ese rol, o aceptarlo y retirar la rama. No se resolvió acá porque las
  dos salidas cambian quién ve datos del ciudadano.
- **Las alertas de Conversaciones nacen con `legajo=None`** (`generar_alerta_mensaje_ciudadano`), y
  el alcance cuelga del legajo: solo las ven el superusuario y `config.administrar`. Es **coherente
  con D-18** —sin legajo propio no hay alcance—, pero vale decirlo: el operador que las genera no
  las encuentra en `/legajos/alertas/`. Conversaciones está fuera de uso, así que no bloquea.

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

**Resolución:** ✅ Resuelto en el PR R-10 (Cambio 125), 04-oct-2026 — el módulo nuevo con los cuatro tests propuestos. El
helper compila con `GROUP BY` en 0,03 s sobre SQLite; se le sacó el guion bajo (`sql_mysql`) porque lo van a importar
TST-01 y lo que venga, y acepta `QuerySet` o `Query`. **Corrección a la ficha:** la línea
`w.features.__dict__["allows_group_by_selected_pks"] = False` del bloque de arriba no va. Lo que evita la conexión es
sembrar `mysql_is_mariadb`, `mysql_version` y `mysql_server_data`, nada más; y esa propiedad vale `True` en MySQL 8 y en
MariaDB sin `ONLY_FULL_GROUP_BY`, así que forzarla a `False` hacía que el SQL compilado **difiriera del que recibe el
motor** (agrupa por el pk en vez de por todas las columnas). Lo fijan dos tests nuevos:
`HelperSqlMysqlTests.test_compilar_no_abre_ninguna_conexion` (socket, `get_new_connection` y `cursor` bloqueados, con un
queryset agrupado y los dos motores) y `test_el_backend_conserva_sus_features_reales`. Dos desvíos más: (a) los tests no
reescriben el queryset, lo **capturan** del código de producción con `consultas_de(*modelos)` —un context manager que
intercepta `_fetch_all`/`exists`/`count`/`iterator` de los modelos indicados y deja pasar los demás, así que
`test_tendencias_...` llama a la vista entera—, porque un test que reescribe el queryset sigue verde cuando el código real
cambia; (b) la función del parte diario se llama `calcular_cantidades`, no `parte_f01`. Se agregó
`test_hoy_los_reportes_de_dispositivos_si_compilan_convert_tz` (caracterización de DIS-01 que **tiene** que pasar) para que
el `expectedFailure` no pueda quedar verde por una excepción tonta. Verificado a mano: `_serie_semanal` con `TruncWeek` → 2
`subTest` en rojo; `tendencias_datos` con `TruncDate` → 1 en rojo. `scripts/check_sql_portable.py` (opcional) no se hizo:
su lugar es el job `Contratos del repo` de RED-24 (PR R-14).
**Test permanente:** `core/tests/test_sql_motor_real.py::SinConvertTZTests.test_la_serie_semanal_del_dashboard_no_compila_convert_tz`

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

**Resolución:** ✅ Resuelto en el PR R-10 (Cambio 125), 04-oct-2026 — el test propuesto, con el regex tal cual, sobre las
tres columnas y **contra los dos motores** (MySQL 8.0.32 y MariaDB 11.8: el manejo del `UUIDField` difiere). Además del
`assertNotRegex` afirma que la columna aparece en una comparación de igualdad pelada (``\`columna\` = ``), que es lo que
deja usar el índice. `dni_en_convocatoria` devuelve un `bool`, no un queryset: se capturan sus **dos** consultas con
`consultas_de(Formulario)` y se compila cada una, lo que de paso fija que sigan siendo dos por su índice (Cambio 91) y no
una con `OR`. Se agregó el pin invertido `test_la_forma_vieja_del_cambio_91_si_envuelve_la_columna`, sin el cual el
`assertNotRegex` podría quedar verde para siempre mirando un patrón que ya no matchea nada. Verificado a mano:
`formulario_por_client_uuid` reescrito con `Replace(Cast(...))` → el test en rojo en los dos motores.
**Test permanente:** `core/tests/test_sql_motor_real.py::ColumnaSargableTests.test_las_busquedas_por_uuid_y_dni_no_envuelven_la_columna`

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

**Resolución:** ✅ **Parte R resuelta** en el PR R-10 (Cambio 125), 04-oct-2026; la parte de la Ola 3 sigue pendiente. El
ratchet `COLUMNAS_UUID_AMPLIADAS` (9 entradas: modelo, campo, tabla, columna y migración que la amplió) vive en
`programas/tests/test_becas_models.py` y lo consume **también** el test físico contra MySQL, así que no hay dos listas que
puedan desincronizarse. El recorrido va sobre los modelos de **las apps del repo** (no `admin`, `auth`, `sessions`…: esas
columnas las amplía Django) e incluye las FK que apuntan a un pk UUID (`legajos.AlertaCiudadano.legajo`,
`legajos.HistorialContacto.legajo`), que son columnas UUID igual; la ficha hablaba del «pk de `TimeStamped`» y en el código
el pk UUID lo declara `core.models.base.LegajoBase`. Además de la declaración, el ratchet verifica que la migración que
nombra **exista y amplíe esa columna a `char(36)`** (`test_cada_columna_uuid_declara_su_migracion_a_char36`, leyendo el
archivo del disco: con `DJANGO_SYNCDB_PROJECT_APPS=True` —que es como corre el CI— el `MigrationLoader` ve las apps del
proyecto sin migraciones). Desvío del lint: barre **todas las apps del proyecto** (registro de apps de Django, menos tests
y migraciones: 335 módulos, 2,4 s) y no solo `**/services/*.py` y `**/views/*.py`, porque el código del Cambio 91 vivía en
`programas/api/views.py`, que no es ninguna de las dos. Reconoce las cuatro formas de escribir la búsqueda: kwarg directo,
`Q(...)` —que puede armarse lejos del `filter` que lo usa—, `**{"client_uuid": v}` literal y travesía por relación
(`relevamiento__formularios__client_uuid`, donde la columna comparada es el último segmento significativo; los lookups
salen del registro del ORM, no de una lista a mano). Un `**variable` opaco se deja pasar: el lint no adivina. Escribir el
UUID por kwarg en un `create()` es correcto y `__isnull` no compara el valor, así que ninguno es infracción; pragma de
excepción `# uuid-externo: ok`. Hoy no hay ninguna infracción, y las ocho formas —cuatro que tienen que caer, cuatro que
no— quedan fijadas con fuente sintética en el propio módulo. Verificado a mano: `UUIDField` nuevo en `ValidacionSIS` →
ratchet en rojo nombrando modelo y campo; `programas.0073` cambiado por `0072` → rojo por «no amplía ninguna columna a
char(36)»; `users.0023` por `users.0099` → rojo por inexistente;
`bloqueado.formularios.filter(client_uuid=client_uuid)` en `programas/api/views.py` → lint en rojo con archivo y línea.
**Test permanente:** `programas/tests/test_becas_models.py::UUIDExternosMySQLTests.test_todo_uuidfield_nuevo_esta_en_la_lista_ampliada`
y `core/tests/test_uuid_mariadb.py::BusquedasUUIDTests.test_las_busquedas_por_uuid_usan_el_helper`

**Parte de la Ola 3:** ✅ Cerrada en #625 (Cambio 176, PR 7b), 08-oct-2026, junto con R0-07. `q_uuid_en_texto` vive
en **`core/db.py`**: siete de los nueve `UUIDField` del repo están fuera de `programas` (`legajos`, `users`, `core`) y
cualquiera de esas apps tenía que importar el servicio de un dominio ajeno para buscar por su propio UUID —y
`legajos.models` no puede importar `programas` sin cerrar un ciclo—. Mismo criterio que `core/dni.py` (RED-48).
`programas/services/becas.py` lo **reexporta**: ningún llamador tuvo que cambiar, y borrar el reexport es un cambio
aparte. Entró con él la guarda de tipo de R0-07 (acepta `str`, devuelve un `Q` vacío con lo que no es un UUID) y el
mensaje del lint pasó a apuntar a `core/db.py`. El ratchet de arquitectura (`programas/tests/test_arquitectura.py`) sigue
igual: `core.db` no importa nada de las apps. **Test permanente:**
`programas/tests/test_ola3_link_publico.py::QUuidEnTextoTests.test_vive_en_core_y_becas_lo_reexporta` (y los tres de la
guarda de tipo).

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

**Resolución:** 🟡 Parcial en el PR R-07 (Cambio 119), 04-oct-2026 — hecha la mitad del alta por la app:
`programas/tests/test_becas_api.py::AltaBajoElLockTests` con `CONSULTAS_ALTA = 29`, el número **medido** sobre SQLite
(el motor del CI) para el POST completo de un caso nuevo, y el mismo presupuesto repetido con el relevamiento ya
poblado (5 casos con ciudadano) para que el número fije además que el alta **no escala** con el tamaño del
relevamiento. Mutación de control: resolver el duplicado por DNI recorriendo los casos en Python en vez de las dos
lecturas por índice → los dos tests en rojo (el segundo, por el N+1 por ciudadano). **Falta:** (1) el gemelo
`portal/tests/test_inscripcion_envio.py::Paso2ConsultasTests.test_el_envio_no_crece_en_consultas`, que queda para el PR
que toque el link público; (2) los dos destinos del Performance Guard (`inscripcion_publica_paso2`, `becas_api_alta`),
que siguen en la Ola 4 como dice la ficha.
**Test permanente:** `programas/tests/test_becas_api.py::AltaBajoElLockTests.test_el_alta_no_crece_en_consultas`.

**Resolución:** ✅ (segunda parte, Ola 4 PR 9) Resuelta en #648 (Cambio 194), 08-10-2026 — los **dos** destinos del
Performance Guard, con la mitad que faltaba del gemelo del link público resuelta por el mismo camino.
`inscripcion_publica_paso2` (anónimo, sesión del paso 1 ya sembrada, `expected_status: 302` al comprobante) y
`becas_api_alta` (Token del territorial, `201`, `max_duplicate_queries: 1`) entran a `build_targets` y a
`perf_budgets.json` con su justificación en `adjustments`, como pedía la ficha. Medidos con `seed_perf --scale 200`
bajo el TestCase de presupuestos: **42 consultas / 6 duplicadas** el paso 2 y **31 / 1** el alta por API; los techos
quedan en medido + 1, salvo las duplicadas del alta, que quedan en el medido. **Tres cosas que la ficha no
anticipaba:** (a) el link público no tenía dónde medirse —`seed_perf` no creaba ningún relevamiento `PUBLICO` ni
ninguno `EN_CURSO`—, así que el seed estrena un **segmento propio** con su convocatoria, su relevamiento público y el
del alta por API, justamente para no moverles ni una fila a `becas_cupo_segmento` ni al detalle del caso, que leen el
segmento 000; (b) la sesión del paso 1 se siembra **al armar el manifiesto** y no adentro de la petición medida, con
un `session_key` y un DNI distintos por muestra —el control de duplicados por convocatoria (RN-P5) rechaza el segundo
envío del mismo documento—, porque crearla adentro le cobraría al presupuesto dos consultas que no son de la pantalla;
(c) el payload del paso 2 **no se escribe a mano**: el formulario es dinámico (RN-1) y se le pregunta al propio
`InscripcionPaso2Form` qué campos tiene, de modo que los cinco adjuntos obligatorios del catálogo viajan solos. Como el
envío sube archivos de verdad, el TestCase y `perf_audit` mandan `MEDIA_ROOT` a un temporal: medir no puede dejar
basura en el `media/` del repo.
**Test permanente:** `core/tests/test_performance_budgets.py::PerformanceBudgetTests.test_key_routes_stay_within_query_budgets`
(cubre los dos destinos; el gemelo con `assertNumQueries` del alta sigue siendo `AltaBajoElLockTests`).

**Resolución:** ✅ (ronda 2 de #648, Cambio 194), 09-10-2026 — **medir encontró un N+1 y la ficha se cierra
arreglándolo, no tolerándolo.** Con el destino nuevo puesto, el job `Ephemeral MySQL Redis Contract` quedó rojo: el
guardado de los adjuntos del paso 2 era un `AdjuntoFormulario.objects.create()` **por archivo**, y como el catálogo de
Becas pide cinco archivos obligatorios la sonda veía cinco `INSERT` idénticos en una sola request —su regla es «el
mismo SQL más de tres veces»—. Es el camino público más pesado, el mismo que el Cambio 91 vio romper contra el
`read_timeout` de 10 s, así que las cinco idas y vueltas no eran un artefacto de la medición. `_completar_envio` pasa a
un único `bulk_create` (guarda igual cada archivo en el storage: `FileField.pre_save` corre por fila también en el
insert por lotes) y el paso 2 baja de 46/10 a **42/6** consultas; el techo **baja** de 47/11 a 43/7. Lo que fija el
arreglo no es el presupuesto —el catálogo decide cuántos adjuntos hay, y sumar uno lo correría de nuevo— sino un test
de forma: el mismo envío con 2 y con 6 adjuntos tiene que costar lo mismo (verificado en rojo contra `b8071a48`:
33 → 37 consultas, una por archivo). Y la sonda deja de decir solo «hubo N+1»: el `CommandError` nombra la ruta y la
forma de la consulta repetida (`portal:inscripcion_paso2`, `INSERT programas_adjuntoformulario ×5`), que cruza entre
workers por Redis como verbo + tabla —nunca el SQL, los parámetros ni datos de personas—. Con eso queda también la
mitad que la ficha daba por pendiente: el gemelo del link público del `AltaBajoElLockTests` de la app de campo.
**Test permanente:** `portal/tests/test_inscripcion_envio.py::AdjuntosConsultasConstantesTests.test_el_envio_no_paga_una_consulta_por_adjunto`.

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

**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026 — `core/tests/test_contrato_auditoria.py`
(8 tests) lee los ocho `hallazgos/*.md`, parsea las **131** líneas «Test permanente» y exige que módulo, clase y
método existan. La regla queda cerrada **por las dos puntas**, que es lo que la propuesta no cubría: un segundo test
exige que toda ficha cerrada **desde el 04-oct-2026 declare la línea**, porque sin eso cerrar una ficha sin dejar test
seguía siendo gratis —bastaba con no escribirla—. Las 18 fichas anteriores al corte quedan exentas y están **todas con
fecha**, cosa que un tercer test sostiene: sin fecha no se puede saber a quién le toca la regla y la excepción sería
para siempre. **Tres detalles que la propuesta no anticipaba:** (a) en `hallazgos/` conviven **dos** formatos de target
(`app/tests/mod.py::Clase.test` y `app.tests.mod.Clase.test`) y **dos** de fecha (`06-oct-2026` y `06-10-2026`), así
que el parser acepta los cuatro; (b) la forma punteada no dice dónde termina el módulo, así que se importa el prefijo
más largo que importe y el resto se resuelve por `getattr`; (c) dos fichas de front (FE-13 y V5A-NEW-08) nombran
`scripts/test_design_audit.py`, que **no** lo descubre el runner de Django y aun así es permanente porque lo corre el
job obligatorio `Validate inventory and authority` —se carga por ruta, con su carpeta en `sys.path`—. La premisa de la
ficha queda afirmada en un test: `unittest.defaultTestLoader.discover('docs')` sigue devolviendo **0 tests**. Las PoC
**no** se movieron al código, como pide la ficha.
**Test permanente:** `core/tests/test_contrato_auditoria.py::FichasCerradasTests.test_toda_ficha_resuelta_nombra_un_test_que_existe`
(y `.test_toda_ficha_resuelta_desde_el_04_oct_declara_su_test_permanente`, `.test_toda_resolucion_lleva_fecha`,
`.test_las_poc_siguen_sin_ser_descubiertas_por_el_runner` y `ParserDelContratoTests` ×4).

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

**Resolución:** ✅ Resuelto (parte R) en #604 (Cambio 156, PR R-16), 07-oct-2026 —
`EscriturasAtomicasTests.test_resolver_ciudadano_offline_no_deja_nada_a_medias` hace fallar `_completar_contacto` —que
corre **después** del `get_or_create` del `Ciudadano` y antes de guardar el formulario— y afirma que no quedó nada
escrito: ni el legajo, ni el `ciudadano_id` del caso, ni el `datos_identificacion` limpiado. Un test de control afirma
que sin la falla inyectada la escritura ocurre entera, para que el primero no pueda quedar verde porque la función dejó
de hacer algo. El motivo por el que la aserción introspectiva no sirve (`atomic` usa `@wraps`, `_atomic` no existe)
quedó escrito en el docstring del módulo para que nadie la reintroduzca. **Mutación de control:** sacar
`@transaction.atomic` de `resolver_ciudadano_offline` deja el test en rojo con su mensaje.
Hay además un gemelo `@tag("mysql")` —`EscriturasAtomicasMotorRealTests`, `TransactionTestCase`— que corre contra
`mariadb:10.11` y `mysql:8.0`, donde lo que deshace el error es un `ROLLBACK` de InnoDB y no un savepoint de SQLite.
Las otras cuatro escrituras siguen en la Ola 3.
**Test permanente:** `core.tests.test_contrato_escrituras.EscriturasAtomicasTests.test_resolver_ciudadano_offline_no_deja_nada_a_medias`.

**2.ª parte (Ola 3, PR 9) — ✅ cerrada en #630 (Cambio 180), 08-oct-2026.** Las cuatro
escrituras restantes quedan afirmadas por conducta en el mismo módulo, cada una haciendo
fallar el paso siguiente a la primera escritura: `AprobacionAtomicaTests` (la traza se cae
después del cambio de estado → el caso no queda APROBADO sin registro),
`InscripcionPublicaAtomicaTests` (un paso después del insert → no queda medio caso; y la
contracara: lo que corre **fuera** del candado a propósito —adjuntos y legajo, Cambio 91—
sí sobrevive y lo completa el reintento), `QuitarPadronAtomicoTests` (falla el `save` → las
filas del padrón siguen estando) y `TrasladoAtomicoTests` (no se puede cerrar el origen →
no queda nada del destino). Cada uno tiene su control sin la falla inyectada, para que no
pueda quedar verde porque la función dejó de hacer su trabajo.
**Desvío code-first:** la ficha nombra `cupo.aprobar_formulario`, que no existe; la función
es `cupo.aprobar_o_poner_en_espera`.
**Dos de las cuatro no estaban enteras, y lo mostró el test antes del arreglo:** (a)
`admisiones.trasladar_admision` guarda el F-00 del destino **antes** de cerrar el origen, y
el storage no vuelve atrás con la transacción —medido: el traslado que falla al cerrar
dejaba `constancia.txt` en `media/` sin ninguna fila que lo nombre, con el DNI y el informe
social adentro—; lo resuelve `core/archivos.py` (`@archivos_atomicos` + `anotar_archivo_escrito`),
la simétrica del `on_commit` que ya existía para la otra dirección, aplicada a las tres
operaciones de admisiones que reciben F-00; (b) `padron.quitar_padron_propio` borraba filas y
escribía `padron_archivo` **sin** el candado que `cargar_padron` sí toma (BEC-15), así que una
carga y un quitado simultáneos se intercalaban y podían dejar el padrón propio vacío con el
Excel puesto —y un padrón propio vacío no retiene a nadie: el link pasa a aceptar cualquier
DNI (RN-P14)—. El candado es `select_for_update().filter(pk=…)` sobre una fila que siempre
existe (no se promete un gap lock que un `FOR UPDATE` sin filas no da) y conserva el orden de
candados del módulo, sin ciclo posible. **Mutaciones de control, las cuatro medidas:** sacar
el `@transaction.atomic` de `aprobar_o_poner_en_espera` y el de `quitar_padron_propio`, abrir
el `with transaction.atomic()` de `crear_formulario_publico` y sacar el `@archivos_atomicos`
de `trasladar_admision` ponen en rojo exactamente su test, con su mensaje.
**Test permanente:** `core/tests/test_contrato_escrituras.py::TrasladoAtomicoTests.test_si_no_se_puede_cerrar_el_origen_no_queda_nada_del_destino`
(y `AprobacionAtomicaTests.test_aprobar_no_deja_el_caso_aprobado_sin_su_traza`,
`InscripcionPublicaAtomicaTests.test_una_falla_despues_del_insert_no_deja_el_caso_escrito`,
`QuitarPadronAtomicoTests.test_si_falla_al_guardar_el_relevamiento_las_filas_siguen_estando`,
más `programas/tests/test_becas_reglas_negocio.py::PadronConcurrenteTests.test_quitar_el_padron_propio_toma_el_mismo_candado_que_la_carga`).

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

**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026 — los dos arreglos que **no tenían ficha
propia** quedan cubiertos; los cuatro primeros de la lista ya los habían cerrado sus fichas (RED-07 ✅, RED-32 ✅,
RED-17 ✅, RED-09 ✅) y los dos últimos siguen como dice la ficha (`1ada8e41` ya está cubierto por
`test_becas_models.py`; `7f36ab06` es JS). Para `057cce86`:
`AltaRelevamientoTests.test_el_alta_no_abre_una_transaccion_anidada` cuenta los `SAVEPOINT` que emite el alta y exige
**uno** —el de `Relevamiento.save()`—, en vez de confiar en un número de `perf_budgets.json` que mide la pantalla
entera y seguiría en verde si el anidado volviera junto con cualquier otra consulta de menos. **Desvío code-first:**
la ficha pedía además el caso «con padrón», que era la rama que sí necesitaba transacción propia; esa rama **ya no
existe** —`RelevamientoForm` no tiene `save()`, `grep padron programas/forms.py` da cero, la carga del Excel se mudó a
su propia vista—, así que el control que ocupa su lugar envuelve el alta en un `atomic()` extra y verifica que el
contador ve **dos**: sin eso, `assertEqual(…, 1)` podría estar verde por no medir nada. Se suma
`test_el_alta_no_deja_callbacks_de_on_commit_colgados`. Para `7feb9d83`, el test va en
`ResumenFijoPadronTests` —la clase que ya existe, no una `ResumenFijoTests` nueva— con su control de andamio.
**Test permanente:** `programas/tests/test_becas_relevamientos.py::AltaRelevamientoTests.test_el_alta_no_abre_una_transaccion_anidada`
(y `programas/tests/test_padron.py::ResumenFijoPadronTests.test_tolera_un_request_sin_sesion`).

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

**Resolución:** ✅ Resuelto en el PR R-07 (Cambio 119), 04-oct-2026 — `programas/tests/test_becas_api_contrato.py::
ContratoAppDeCampoTests`, con las constantes literales del módulo (`CLAVES_RELEVAMIENTO_LIST`,
`CLAVES_RELEVAMIENTO_DETAIL`, `CLAVES_DEFINICION`, `CLAVES_FORMULARIO`, `CLAVES_ADJUNTO`, `CLAVES_PAGINACION`) y el
aviso de que agregar una clave es seguro pero renombrarla o sacarla es un release coordinado de `Chaco-mobile`. Se
fijan con `assertEqual(sorted(...), ...)` —conjunto exacto— el listado y el detalle de relevamientos, el sobre de
paginación de DRF, el caso creado y el listado de casos, y el adjunto subido y listado; más `test_tipos_del_contrato`
(int/bool/str de cada clave, `definicion_formulario` dict con sus seis claves) y
`test_el_contador_de_personas_cargadas_sale_anotado_y_cuenta` (`formularios_count`, `cupo_maximo`, `cupo_disponible`,
`cupo_completo`, que no afirmaba ningún test). Mutación de control: renombrar `convocatoria_nombre` →
`convocatoria` en `serializers.py:18` —que dejaba en verde los 54 tests que hoy tiene `test_becas_api.py`; el «76»
de arriba es el número del relevamiento original, de otro corte del archivo— pone en rojo tres de estos tests. La
forma de **cada campo** de `definicion_formulario` sigue siendo RED-12 (PR R-17).
**Test permanente:** `programas/tests/test_becas_api_contrato.py::ContratoAppDeCampoTests.test_lista_de_relevamientos_tiene_exactamente_estas_claves`.

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

**Resolución:** ✅ Resuelto en #546 (Cambio 118, PR R-04), 04-oct-2026 — `"drf_spectacular"` entró en `INSTALLED_APPS` de `config/settings.py`, después de `rest_framework.authtoken`. Era literalmente lo único que faltaba: el `DEFAULT_SCHEMA_CLASS`, los `SPECTACULAR_SETTINGS`, las tres rutas de `config/urls.py` y hasta la excepción de CSP de `/api/docs/` en `config/middlewares/security_headers.py` ya estaban. `/api/docs/` y `/api/redoc/` responden 200 con sesión de backoffice y 302 al login sin sesión, y `manage.py spectacular --validate --file /dev/null` existe y termina en 0 —sin eso ningún gate de esquema era posible, que es lo que desbloquea RED-37 y RED-43—. **Decisión de producto, aplicada por default:** Swagger-UI y Redoc se sirven desde el propio sistema con `drf-spectacular-sidecar` en vez de los CDN de terceros; el HTML servido referencia solo `/static/…` (cuatro etiquetas en `/api/docs/`, una en `/api/redoc/`) y `collectstatic` copia ~2,5 MB más. La exención de CSP se mantiene aunque el CDN ya no la necesite. **Test permanente:** `core.tests.test_api_schema_contrato.DocumentacionDeApiTests` (`test_schema_docs_y_redoc_responden_200`, `test_schema_docs_y_redoc_siguen_detras_de_login`, `test_el_comando_spectacular_esta_disponible`) y `core.tests.test_api_schema_contrato.DocumentacionSinTercerosTests` (2). Antes del cambio el módulo daba 5 fallas y 2 errores (`TemplateDoesNotExist: drf_spectacular/swagger_ui.html` y `…/redoc.html`). **Sigue pendiente, en otra ficha:** poner las tres rutas detrás de `BackofficeAutenticado` es el resto de SEC-01 (Ola 2, PR 8); `drf-spectacular-sidecar` se actualiza a mano, porque `pip-audit` sobre `drf-spectacular` no avisa de un CVE en los assets vendorizados; y en el deploy a icore conviene verificar que `/static/drf_spectacular_sidecar/` quedó servido antes de dar `/api/docs/` por buena.
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

**Resolución:** ✅ **Los puntos 1 y 2 —la parte de la Ola R— resueltos** en #546 (Cambio 118, PR R-04), 04-oct-2026; **el punto 3 sigue en la Ola 7**. Punto 1: `get_pausado(self, obj) -> bool`, `get_pausa_motivo(…) -> str` y `get_definicion_formulario(…) -> dict` anotados en `programas/api/serializers.py`; `cupo_disponible` y `cupo_completo` se declaran **en el serializer y no en el modelo**, porque son propiedades de la relación convocatoria-segmento. Punto 2: `ConsultaPersonaSerializer` real (`dni`, `sexo` con `choices`, `relevamiento` opcional) **reemplaza** la validación manual de `programas/api/views.py`, con `@extend_schema(request=…, responses={200, 400, 404, 502})` sobre `consultar_persona_becas`; el cuerpo del 400 no cambia y el único trato que sí cambió es que un `relevamiento` que no sea un id entero ahora da 400 (antes `true` y una cadena pasaban). El esquema sigue con 54 paths; los errores bajan de **11 a 10** y los warnings de **24 a 15**, los dos con ratchet que solo baja. La allowlist nace en **10** y no en las 11 de la ficha porque `consultar_persona_becas` salió de la lista al anotarse. El esquema además dejó de reportarse como issues de `manage.py check --deploy`: el mismo dato, con allowlist y ratchet, lo da `EsquemaOpenApiTests`. **Test permanente:** `core.tests.test_api_schema_contrato.EsquemaOpenApiTests` (`test_el_esquema_se_genera_sin_errores`, `test_el_esquema_no_suma_warnings`, `test_relevamiento_detail_publica_los_tipos_reales`, `test_consultar_persona_declara_su_cuerpo`). **Falta (Ola 7, 4 h):** `@extend_schema(responses=inline_serializer(...))` en las 5 vistas del dashboard y en las de `core/views/performance.py` (si OPS-10 no las borra antes), y los 15 warnings restantes —`get_dispositivo_nombre` y `get_legajos_count` de legajos, `get_full_name` de users, dos parámetros de path sin tipo y dos colisiones de enum que se arreglan con `ENUM_NAME_OVERRIDES`—. El gate de esquema en el CI es **RED-43** (PR R-18).
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

**Resolución:** ✅ **La parte R** resuelta en #608 (Cambio 160, PR R-18), 07-oct-2026 — `core/http.py` con `error_json(mensaje, *, status=400, errores=None)` y `ok_json(**datos)`, y los dos consumidores que el usuario nota congelados en **su** clave de hoy: el constructor en `message` (`nodo-constructor.js:133`) y la subida de archivos de legajos en `error` —y en `mensaje` el camino feliz, que es una quinta clave más—. **Desvío de la ficha, code-first:** el detalle por campo se llama `errores` y no `errors`, porque así está escrito en `programas/views/diseno.py` y cambiarlo ahora sería exactamente el renombre silencioso que la ficha vino a evitar. **Verificado por mutación:** pasar `diseno.py` de `message` a `detail` —la convención de DRF, que parece una mejora— pone rojo `test_el_constructor_devuelve_el_motivo_en_message`. **Test permanente:** `core.tests.test_contrato_errores_ajax.SobreDeErrorTests` (`test_el_constructor_devuelve_el_motivo_en_message`, `test_subir_archivos_devuelve_el_motivo_en_error`, `test_subir_archivos_exitosa_devuelve_el_resumen_en_mensaje`) y `core.tests.test_contrato_errores_ajax.SobreUnicoTests` (4). **Falta (Ola 7, 8 h):** migrar las vistas al sobre único, app por app, empezando por `diseno.py` y `legajos/views/contactos_api.py`, y la regla WARN en `design_audit.py` para `data.mensaje|detail|errors`.
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

**Resolución:** ✅ **La parte R** resuelta en #608 (Cambio 160, PR R-18), 07-oct-2026 — comando de **solo lectura** `verificar_json_guardado [--json] [--detalle N]` (no hay un solo `save()`/`update()`/`delete()` en el archivo, así que se puede correr contra una réplica o contra un dump de PRD restaurado), que recorre en lotes de 500 las condiciones (`ItemDiseno.condicion`, `GrupoRequisito.condicion_defecto`), los campos propios (`ItemDiseno.propio`), las fotos (`Formulario.definicion`) y las correcciones (`Formulario.datos_siis`), y reporta diez formas rotas, la que más duele primero: un operador fuera de `OPERADORES_POR_TIPO` cae al `return False` final de `evaluar_regla` y el ítem condicionado **no se muestra nunca**. **Dos desvíos, los dos code-first:** (a) un `Formulario.definicion` «con la forma plana anterior al Cambio 58» **no puede existir**: el campo nació en `programas.0062`, que es del propio Cambio 58, junto con `foto_definicion`, que siempre escribe `{version, canal, items}`; lo viejo de verdad es `definicion = NULL` con `data` en el contrato plano de la app, y eso es lo que prueba el test (`respuestas_legibles` devuelve `None` y el lector cae al camino por pk, en vez de mostrar el caso vacío); (b) por lo mismo, para `propio` el test fija que la **clave** `presentacion` es el contrato —renombrarla adentro del JSON devuelve todo a «LISTA»— además de probar que un `propio` sin ella se sigue leyendo. **Verificado por mutación:** `propio.get("presentacion", "LISTA")` → `propio.get("modo_presentacion", "LISTA")` pone rojo `test_la_clave_presentacion_es_el_contrato`. **Test permanente:** `programas.tests.test_json_compatibilidad.DatosViejosTests` (5) y `programas.tests.test_json_compatibilidad.VerificarJsonGuardadoTests` (9, incluido `test_las_claves_del_apoderado_siguen_siendo_las_que_lee_el_payload`, que cruza la lista escrita a mano contra `siis_envio.py`).

**La parte Ola 3** resuelta en #624 (Cambio 175), 08-oct-2026, con G1-05 como pedía el plan — `programas/validadores.py::validar_condicion_json` declarado en `validators=[…]` de `ItemDiseno.condicion` y de `GrupoRequisito.condicion_defecto` (`programas.0080`, dos `AlterField` cuyo `sqlmigrate` sale `(no-op)`). Valida la **forma**: modo conocido, `reglas` como lista de objetos, fuente presente, **operador existente**, valor donde el operador lo necesita y lista donde espera una lista. La coherencia —que la fuente exista, esté antes y el operador aplique al tipo de **ese** campo— sigue siendo de `condiciones.validar_condicion`, que necesita el diseño alrededor y no cabe en un validador de campo. **Dos decisiones de implementación:** (a) la función vive en un módulo propio, `programas/validadores.py`, porque `programas.models` la importa y `services/condiciones` importa `programas.models` —el import diferido de adentro de la función es lo que corta el ciclo—, y su **ruta queda escrita en la migración**, así que mover el archivo es un cambio de contrato; (b) un `validators=[…]` solo corre en `full_clean()`, así que además se lo llama **explícitamente** en el endpoint del constructor (`formulario_condicion`), que hasta ahora validaba solo que el cuerpo fuera un objeto y era por donde entraba el operador inventado. `None`, `{}` y `""` siguen siendo válidos: no hay condición. **Test permanente:** `programas.tests.test_json_compatibilidad.ValidadorDeCondicionTests` (7, encabezada por `test_un_operador_inventado_no_se_guarda`) y `programas.tests.test_constructor.CondicionTests.test_rechaza_una_condicion_cuya_forma_no_se_puede_ni_evaluar` (+ `.test_rechaza_un_modo_que_el_motor_no_conoce`).
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

**Resolución:** ✅ Resuelto en #608 (Cambio 160, PR R-18), 07-oct-2026 — **D-RED-04 aplicada por default: fixture sintético**, seis archivos en `programas/fixtures/contratos/` (`renaper_ok`, `renaper_fallecido`, `personas_ok`, `personas_no_encontrada`, `siis_alta_ok`, `siis_rechazado`) con su README, escritos a mano con la estructura documentada —domicilio anidado incluido— y DNI `11111111`/`22222222`. **No** se graba nada real: icore tiene datos de personas y corre con `ENVIRONMENT=prd`. Los tres parsers los consumen **completos**, no desde el dict de tres claves de antes: RENAPER por la cadena entera (`consultar_ciudadano` → `consultar_datos_renaper`, con los dos sobres que el proveedor ya usó, `success`/`data` e `isSuccess`/`result`), Personas con su token y su 404, y SIIS con el token y el alta de la tabla intermedia (201 con `ids_generados`, 400 con `detalles` por campo). **Dos cosas que el fixture dejó medidas y no se arreglan acá:** `test_personas_no_toma_claves_anidadas` entra con `@unittest.expectedFailure` porque hoy `_aplanar` toma `domicilio.localidad.nombre` y la persona queda validada llamándose «Resistencia» (SIIS-10, Ola 3; al lado va su contracara sin decorador, para que el bug quede afirmado y no solo esperado), y `test_renaper_con_el_result_anidado_un_nivel_mas_no_se_marca_validado` afirma que con `result` anidado un nivel el caso se marca **validado con el nombre en `None`**, que es el escenario que la ficha nombra. **Test permanente:** `programas.tests.test_contratos_externos.ContratoUpstreamTests` (9, una por rama) y `programas.tests.test_contratos_externos.ClavesDelContratoTests` (`test_toda_clave_leida_existe_en_el_fixture`, `test_los_fixtures_existen_y_son_json`). **Operativo:** si el PM aprueba grabar respuestas reales, el camino es `diagnosticar_integraciones --grabar <dir>` **solo** con `RENAPER_TEST_MODE=1` contra el DNI de prueba, anonimizando y revisando antes de versionar.
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

**Resolución:** ✅ **La parte R** resuelta en #608 (Cambio 160, PR R-18), 07-oct-2026 — `core/tests/test_urls_del_front.py` barre `templates/`, los ocho `*/templates/` y `static/**/*.js`, saca los literales de `fetch(...)` y `url: "..."`, normaliza los segmentos que son una interpolación entera (`${id}`, `{{ pk }}`) probándolos con una sonda entera **y** una UUID, **una por segmento y en todas las combinaciones** (corregido en la ronda 2: con una sonda única para toda la URL, un literal que mezclara `<uuid:>` con `<int:>` —como `/legajos/<uuid:legajo_id>/archivos/<int:archivo_id>/eliminar/`, que existe— se reportaba como roto sin serlo), y afirma que `resolve` los encuentra. **Medición al 07/10/2026: 14 literales, 3 rotos**, que son la `ALLOWLIST` inicial, cada uno con su ficha: `/legajos/1/contactos/api/` y `/legajos/contactos/1/detalle/` (LEG-06, el template es código muerto) y `/set_dark_mode/` (RED-75, D-RED-07 = A). **Reconciliado con la Ola 5 PR 2:** la allowlist nace **sin** `/api/legajos/contactos/vinculos-familiares/` —LEG-03 ya retiró la solapa de Red Familiar—, así que son 3 y no 4. El ratchet corre en las dos direcciones: `test_la_allowlist_no_tiene_entradas_de_mas` falla cuando una entrada ya resuelve o ya no aparece en el front, que es lo que cada ficha tiene que hacer al cerrar. Del lado de las claves, `dashboard/tests/test_api_contrato.py` congela el conjunto **exacto** de `results`/`has_more`, `labels`/`datos` (con `len(labels) == len(datos) == dias` para los cuatro períodos) y `count`/`criticas`. **Code-first:** `templates/inicio.html` ya usa `{% url %}` para las dos del dashboard (líneas 853-855), así que lo que queda de la parte Ola 5 son los literales de `base.js` e `historial_contactos.html`, que sus propias fichas borran. **Verificado por mutación:** `count=Count("id")` → `total=Count("id")` en `legajos/views/alertas.py` y `"has_more"` → `"hasMore"` en `dashboard/api_views/__init__.py` ponen rojo su test. **Test permanente:** `core.tests.test_urls_del_front.UrlsDelFrontTests` (4, incluida `test_una_url_que_mezcla_conversores_no_da_falso_roto`) y `dashboard.tests.test_api_contrato.ContratoDashboardTests` (6). ~~**Falta (Ola 5, 2 h):** reemplazar los literales por `{% url %}` donde el template lo permita.~~

**Resolución (Ola 5):** ✅ **La parte 5** resuelta en #611 (Cambio 164, PR 8 de la Ola 5), 07-oct-2026 — **los once literales vivos se fueron; quedan los dos de LEG-06**, que son de su ficha. Nueve pasaron a `{% url %}` dentro del template: los cuatro de `legajos/templates/legajos/ciudadano_detail.html` (`archivos_ciudadano`, `subir_archivos_ciudadano`, `actividades_ciudadano`, `prediccion_riesgo`) y los cinco de `templates/core/performance_dashboard.html` (`core:system_metrics_api`, `performance_api`, `query_analysis_api`, `optimization_suggestions_api`, `run_phase2_tests_api`). Los dos restantes vivían en `static/custom/js/alertas_websocket.js`, donde **`{% url %}` es imposible** —`static/` no pasa por el motor de templates—: las rutas viajan como `data-url-count`/`data-url-preview` sobre `#alertas-campana` (`templates/includes/navbar.html`) y el JS las lee con `dataset`, con el mismo patrón que ya usaban `_dashboard_panel.html` y `convocatoria_formulario.html`; sin el atributo, no consulta nada. El décimo-segundo literal, `/set_dark_mode/`, lo borró **RED-75** en este mismo PR y salió de la `ALLOWLIST` en el mismo diff. **Desvío de la propia resolución R:** la nota «lo que queda de la parte Ola 5 son los literales de `base.js` e `historial_contactos.html`» quedó corta —se escribió mirando `inicio.html`, que ya estaba convertido—: el barrido del módulo lista además los nueve de `ciudadano_detail.html` y `performance_dashboard.html` y los dos de `alertas_websocket.js`, que **resolvían** (por eso no estaban en la allowlist) pero eran exactamente lo que la ficha manda convertir. **Efecto sobre el propio módulo:** `test_el_barrido_encuentra_literales` medía que hubiera más de cinco literales vivos, lo que deja de tener sentido cuando el trabajo es justamente que no queden —y daría cero legítimo el día que LEG-06 borre su template—; se reemplazó por `test_los_patrones_siguen_sacando_la_ruta`, que ejercita el extractor contra una muestra escrita en el test (con una URL de otro origen y una interpolación mezclada, que tiene que descartar), más `test_el_barrido_recorre_el_front_de_verdad`, que afirma que las carpetas siguen donde el módulo las busca. **Ronda 2 de la revisión — las dos puntas de RED-42 no tenían candado, y el barrido tenía un punto ciego.** (1) Los dos tests de JS **no discriminaban**: con el `alertas_websocket.js` viejo —el de `origin/development`, con las rutas escritas a mano— los cinco pasaban igual. `test_la_ruta_de_la_vista_previa_sale_del_template` ponía en el stub la *misma* ruta que el literal viejo, así que no podía distinguir de dónde salía; ahora la campana del harness anuncia rutas **centinela** (`/sentinela/preview/`, `/sentinela/count/`) y el test exige que el `fetch` haya ido ahí. Y `test_sin_la_campana_del_navbar_no_consulta_nada` stubeaba `querySelector` devolviendo `null` para **todo**, con lo que el script salía por el «no hay dónde pintar» antes de mirar la URL; ahora `#alertas-counter` y `#alertas-preview` son los elementos reales del harness y el `null` es solo para `#alertas-campana`. Los dos (más `test_vista_previa_del_menu`, que arrastra la centinela) **fallan con el JS viejo y pasan con el nuevo**, comprobado. (2) **Del lado del template no había nada**: borrar los dos `data-url-*` del navbar dejaba la suite entera en verde y la campana dejaba de contar **en silencio** —sin 404, sin error de consola—. Lo cubre ahora `legajos.tests.test_adjuntos_rbac.CampanaDeAlertasEnElNavbarTests`, que afirma el render contra `reverse()` con `ciudadano.ver` y con superusuario, y la contracara sin la capacidad; verificado borrando los atributos. (3) **El barrido no veía las rutas asignadas a una variable**, solo las del punto de llamada (`fetch(`, `url:`), y por ahí se le escapaban las dos de borrado de adjuntos de `ciudadano_detail.html` (`const urlEliminar = …`). Se agregó `LITERAL_ASIGNADO`, filtrado por **prefijo real del URLconf** (`_prefijos_de_la_app`, calculado del URLconf y no de una lista a mano) para no inundarlo con `/static/…`, `/media/…` ni `href` ajenos, y se saltean los comentarios (`sin_comentarios`, el helper que ahora comparten este módulo y `users/tests/test_tema.py`): sin eso, el comentario que **documenta** una ruta retirada la volvía a dar por viva —así entraban `/legajos/<id>/` (FE-09) y `/legajos/<uuid>/`—. Las dos rutas de borrado pasaron a salir del tag `url` con marcadores, y el reemplazo del id va **anclado al final** porque el patrón de `alertas_eventos.html` (`.replace('0', id)`) acá pisa el primer cero, que es el del **ciudadano**: con `ciudadano.id = 10`, `/legajos/ciudadanos/10/archivos/0/eliminar/` salía como `/legajos/ciudadanos/177/archivos/0/eliminar/`. Lo mide `legajos.tests.test_adjuntos_rbac.UrlDeBorradoDelDetalleTests`, que corre el script **renderizado** con `node`. **Qué destapó el barrido ensanchado:** dos literales más del `historial_contactos.html` muerto (LEG-06, que ya tenía dos) y **un hallazgo nuevo sin ficha**: `legajos/templates/legajos/programas/programa_detail.html:654` le pone al form de «Dar de baja» un `action` (`/legajos/acompanamiento/<id>/dar-de-baja/`) que **no existe en el URLconf**. La vista existe (`legajos/views/programas.py::dar_de_baja_inscripcion`) pero **nadie la rutea**: el botón de una pantalla viva (`/legajos/programas/<pk>/`) postea a un 404 desde siempre. **No se arregla acá**: rutearla haría funcionar por primera vez una baja destructiva que nunca corrió en producción, y eso lo decide el PM. Queda en la `ALLOWLIST` con su motivo escrito. **Qué mide hoy la `ALLOWLIST` (5 entradas):** cuatro de `historial_contactos.html` (LEG-06) y la de `dar-de-baja`. **Test permanente (parte 5):** `core.tests.test_urls_del_front.UrlsDelFrontTests` (8), `users.tests.test_tema.TemaTests` (5), `legajos.tests.test_alertas_websocket_escape.AlertasWebSocketEscapeTests` (5), `legajos.tests.test_adjuntos_rbac.CampanaDeAlertasEnElNavbarTests` (5) y `legajos.tests.test_adjuntos_rbac.UrlDeBorradoDelDetalleTests` (2).
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

**Resolución:** ✅ Resuelto en #608 (Cambio 160, PR R-18), 07-oct-2026 — job `Contratos de API` en `.github/workflows/pr-backend.yml`: `manage.py spectacular --validate --file /dev/null` (hoy sale en 0; **sin `--fail-on-warn`**, que se enciende cuando la allowlist de RED-37 quede vacía) más los ocho módulos de contrato en **un solo proceso** —`core.tests.test_api_schema_contrato`, `core.tests.test_contrato_errores_ajax`, `core.tests.test_urls_del_front`, `dashboard.tests.test_api_contrato`, `programas.tests.test_becas_api_contrato`, `programas.tests.test_contratos_externos`, `programas.tests.test_json_compatibilidad` y `users.tests.test_rbac_contrato`—. **Entra obligatorio desde el primer día:** medido antes de decidir, son **62 tests en 8,8 s**, sin base de verdad (SQLite en memoria), sin red y sin dependencia del orden; lo único caro es `pip install`. Va a `docs/internal/rulesets/ruleset-development.json` y a `CHECKS_OBLIGATORIOS` de `core/tests/test_gates_ci.py` en el mismo PR, con el filtro por rutas **adentro** del job (RED-20): un check con `paths:` en el trigger no reporta nunca y no puede ser obligatorio. **Desvío de la ficha:** no se nombran `programas.tests.test_definicion_contrato` ni el paso de `node` con `scripts/check_condiciones_js.mjs` —los crea el PR R-17 (RED-12, RED-38)—; hoy no existen y nombrarlos dejaría el job rojo desde el primer día. Queda el comentario en el workflow. `CLAUDE.md` suma la regla: tocar `programas/api/serializers.py`, `definicion_formulario` o una clave que el front lee a mano obliga a actualizar el test de contrato en el mismo diff. **Test permanente:** `core.tests.test_gates_ci.RulesetsPropuestosTests` (los 60 tests del módulo cubren que el check exista como job, que su workflow corra en **todo** PR a `development` y que el ruleset y `CHECKS_OBLIGATORIOS` coincidan). **Corregido en la ronda 2:** `pr-backend.yml` declaraba solo `permissions: contents: read`, y `dorny/paths-filter` en `pull_request` necesita además `pull-requests: read`; hoy anda porque el repo es público, pero con **D-RED-01** (repo privado) el filtro podía dejar de resolver y el check **obligatorio** habría terminado en verde sin correr nada. Se agregó el permiso acá y en `pr-performance.yml`, que arrastraba la misma omisión en `Migrate ida y vuelta`, y en los dos jobs un paso nuevo **falla** si la salida del filtro no es `true` ni `false`: un gate que no puede decidir no tiene permitido decir «verde». **Verificación:** `actionlint` (Docker `rhysd/actionlint`) sobre los nueve workflows sale en 0.
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

**Resolución:** ✅ Resuelto en #608 (Cambio 160, PR R-18), 07-oct-2026 — `users/tests/test_rbac_contrato.py` cruza las dos direcciones. Ida: extractor por AST de los argumentos **posicionales** de `requiere`, `puede`, `puede_alguna`, `RequiereCapacidad`, `puede_en_programa_dispositivos` y `puede_operar_dispositivo`, más lo asignado a `capacidades_requeridas` **y a `capacidad_requerida`** (el mixin de Dispositivos, en singular), resolviendo las constantes `CAP_*`/`CAPS_*` de **todo** el repo en dos pasadas (una se arma con otra), más los tags de template (`|puede:"…"` y los tres `{% … %}` que toman capacidad); el mensaje trae `archivo:línea` y `difflib.get_close_matches`. Hoy no hay ninguna huérfana. Vuelta: toda capacidad del catálogo se usa **como literal** o está declarada con su motivo en una de tres listas —`CAPACIDADES_SIN_USO` (nadie la evalúa), `CAPACIDADES_SOLO_COLECTIVAS` (solo suma dentro de un conjunto: ninguna pantalla pregunta por ella) o `USOS_EN_BLOQUE` (se evalúa por una constante escrita a mano, en una comprensión que el extractor no ve como llamada)—. **`CAPS_GESTION` no cuenta como uso** (corregido en la ronda 2): se calcula *del propio catálogo* en tiempo de import —todo `becas.*` menos dos—, así que contarla volvía **circular** la vuelta y dejaba sin medir las 33 capacidades finas de Becas, la mitad del catálogo. Al sacarla apareció `becas.coordinador.ver`, que `crear` y `editar` sí tienen su `{% if %}` pero el «ver» no. **Desvío de la ficha:** la ficha esperaba que «hoy pasan los dos» con una sola entrada (`ciudadano.eliminar`); medidas de verdad son **seis** (cinco sin uso y una solo colectiva). Las cuatro nuevas son reales y están verificadas una por una: `config.ver` (todo `/configuracion/` exige `config.administrar`), `relevamiento.ver` (el módulo genérico quedó sin consumidores: Becas usa `becas.relevamiento.ver`) e `institucion.ver`/`institucion.administrar` (**no existe el módulo de Instituciones**: no hay vista ni URL que las evalúe, solo el tab del ABM de Roles). El ABM las sigue ofreciendo y tildarlas no habilita nada: **qué hacer con cada una lo decide la Ola 7 (OPS-14)**, o se usan o salen del catálogo. **Verificado por mutación:** renombrar `becas.cupo.ver` en el `CATALOGO` sin tocar sus usos pone rojo `test_toda_capacidad_evaluada_existe_en_el_catalogo`. **Test permanente:** `users.tests.test_rbac_contrato.CapacidadesEvaluadasTests` (`test_toda_capacidad_evaluada_existe_en_el_catalogo`, `test_toda_capacidad_del_catalogo_se_usa_o_esta_declarada_sin_uso`, `test_la_vuelta_no_es_ciega_a_las_capacidades_de_becas`, `test_los_usos_en_bloque_declarados_son_los_que_hay`, `test_lo_declarado_sin_uso_sigue_sin_usarse`, `test_el_barrido_encuentra_capacidades`). **Verificado por mutación (ronda 2):** agregar al `CATALOGO` un `becas.inventada.ver` que nadie usa pone rojo la vuelta —antes pasaba en silencio, tapado por `CAPS_GESTION`—, y sacar `becas.coordinador.ver` de `CAPACIDADES_SOLO_COLECTIVAS` también.
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

**Resolución:** ✅ Resuelta en #611 (Cambio 164, PR 8 de la Ola 5), 07-oct-2026, con el **default D-RED-07 = A** (la preferencia se persiste solo en el navegador) — se fueron `sendThemePreference` y su llamada de `static/custom/js/base.js`, y con ellas la opción `notify` de `applyTheme`, que era lo único que la disparaba; se fue `dark_mode` de `ProfileSerializer`; y `/set_dark_mode/` salió de la `ALLOWLIST` de `core/tests/test_urls_del_front.py` **en el mismo diff**, que es lo que el ratchet de RED-42 exige. La conducta que el usuario ve no cambia: el tema ya se guardaba de verdad en `localStorage` y se sincroniza entre pestañas por el evento `storage`. **La columna `users_profile.dark_mode` no se toca:** borrarla es *contract* y va dos releases después de que nadie la lea (expand/contract, RED-15); hoy queda escrita con su `default=True` y sin lectores. **Code-first, y corrige a la ficha:** `static/custom/js/base.js` **no lo carga ningún template** (`grep -rn "base\.js"` sobre `templates/` y `*/templates/` no devuelve nada), así que el 404 por cada cambio de tema que describe la ficha **no estaba ocurriendo en producción**: lo que había era código muerto que prometía una persistencia inexistente. Eso no cambia el arreglo —el archivo sigue versionado y la próxima persona que lo cargue estrenaría el 404—, pero sí baja el impacto real a cero y explica por qué nadie vio los 404 en los logs. Que el archivo entero esté huérfano es materia de **FE-14** (Ola 7), que barre el JS sin consumidores. **Test permanente:** `users.tests.test_tema.TemaTests` (5: el barrido del front sin comentarios, su propio control de que el barrido no se coma el código, `resolve("/set_dark_mode/")` que sigue dando `Resolver404`, el serializer sin el campo y el `localStorage` que sostiene la conducta).
- **Ubicación:** `static/custom/js/base.js:64-77` (`sendThemePreference`); `users/models/__init__.py:19` (`dark_mode`,
  `default=True`, nunca escrito desde la UI); `users/serializers/__init__.py:27`.
- **Qué es frágil:** el `.fail()` lo tapa con un `console.warn`; cada cambio de tema es un 404 en los logs y cualquier
  trabajo futuro que lea `Profile.dark_mode` va a leer siempre `True`.
- **Propuesta (default D-RED-07 = A):** borrar `sendThemePreference` y su llamada, y sacar `dark_mode` de
  `ProfileSerializer`; test `users/tests/test_tema.py::TemaTests.test_el_shell_no_postea_la_preferencia_de_tema` (patrón de
  `core/tests/test_modern_modal_contrato.py`) y sacar `/set_dark_mode/` de la `ALLOWLIST` de `core/tests/test_urls_del_front.py` **en el mismo diff** (existe desde el Cambio 160: una entrada que ya no aparece en el front hace fallar `test_la_allowlist_no_tiene_entradas_de_mas`). Opción B: vista `POST
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

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **el refactor sigue siendo de
la Ola 7.** `core/tests/test_shell_backoffice.py` deja los **dos** criterios de «hecho» de G1-01 fase 2 escritos y
rojos, con `expectedFailure`: (1) `ShellSinConversacionesTests.test_inicio_renderiza_sin_urls_de_conversaciones`, con
`ROOT_URLCONF` apuntando a `core/tests/urls_sin_conversaciones.py`; (2)
`IndependenciaTests.test_legajos_no_importa_conversaciones` (AST sobre `legajos/**`), que la ficha ubicaba en la Ola 7 y
se adelanta porque es la mitad que impide **arrancar**, no la que da 500. **Un desvío de la ficha, a favor:**
`urls_sin_conversaciones.py` no es una copia de `config/urls.py` sino un **filtro** sobre la lista real —una ruta nueva
aparece ahí sola, y el test no termina midiendo un URLconf congelado—. Cada `expectedFailure` va con su control de
andamio (`test_el_urlconf_recortado_no_tiene_las_rutas_de_conversaciones` y `test_el_detector_ve_el_import_de_hoy`) y,
el primero, con un test que fija **por qué** falla hoy (`NoReverseMatch` nombrando `conversaciones`): sin eso, el
criterio de la fase 2 podría quedar midiendo otra rotura. La tercera pata —el context processor prestado— queda en
verde y fijada: `ContextProcessorPrestadoTests` afirma que la línea sigue en `settings.py`, que las cuatro variables
llegan al contexto del inicio y que `window.isSuperuser = true;` sale renderizado. Ese es el modo de falla silencioso
que la ficha describe como «peor que un 500».
**Test permanente:** `core.tests.test_shell_backoffice.ShellSinConversacionesTests.test_inicio_renderiza_sin_urls_de_conversaciones`
(y `IndependenciaTests.test_legajos_no_importa_conversaciones`, `ContextProcessorPrestadoTests`).

**Resolución (Ola 7):** ✅ Cerrada en #663 (Cambio 198), 09-oct-2026 — el refactor va **antes** del apagado y en el mismo PR, como pedía RS-R4-13. (1) El context processor se mudó a `core.context_processors.identidad_usuario` (la línea de `settings.py` apunta ahí) y `conversaciones/context_processors.py` se borró; publica las cuatro variables prestadas más `puede_alertas_sensibles`, y pierde `puede_conversaciones`. (2) `alerta_mensaje_ciudadano` se mudó a `conversaciones/signals/alertas.py`, donde vive su `sender`: `legajos` ya no importa `conversaciones` a nivel de módulo. (3) Del shell salieron `window.conversacionesConfig` y los cuatro `<script>` de chat. **Dos desvíos de la ficha, los dos a favor:** el bloque no se movió a «un include condicional» sino que se **borró**, porque el apagado va en el mismo PR y un include para nadie es deuda nueva; y el detector AST de `legajos/**` quedó en `core/tests/test_shell_backoffice.py` (donde lo dejó la Ola R) en vez de abrir `legajos/tests/test_signals_package.py`. Se agregó, además de lo que pedía la ficha: `AlertasConsumer` y su test se mudaron a `legajos` —`ws/alertas/` es de legajos y es lo único que sobrevive al apagado— y `ConversacionesConfig.ready()` dejó de registrar `signals.presencia`, que enganchaba `user_logged_in`/`user_logged_out` para escribir en Redis en **todo** login del backoffice. Los dos `expectedFailure` de la Ola R se invirtieron y el andamio (`core/tests/urls_sin_conversaciones.py`) se borró: el URLconf real ya es ese.
**Test permanente (Ola 7):** `core.tests.test_shell_backoffice` (`ShellSinConversacionesTests.test_inicio_renderiza_sin_urls_de_conversaciones`, `IndependenciaTests.test_legajos_no_importa_conversaciones`, `IndependenciaTests.test_el_receiver_vive_en_conversaciones_y_sigue_conectado`, `IdentidadDelUsuarioTests`) y `legajos.tests.test_ws_alertas_rbac` (el módulo mudado, en verde en su destino).

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

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **el borrado del parche sigue
siendo OPS-13 (Ola 7), D-RED-08.** Dos mitades. (1) `config/tests/test_wsgi_runtime.py::GeventTests.
test_nadie_piso_validate_thread_sharing` afirma que `BaseDatabaseWrapper.validate_thread_sharing` sigue siendo el de
Django; pasa hoy y se pone rojo el día que el parche se aplique, por la variable de entorno o por un import suelto. Lo
acompañan dos controles de andamio: que `gevent_patch.py` siga pisando esa función (si dejara de hacerlo, el riesgo se
fue por otro lado) y que `wsgi.py` siga teniendo **las dos** perillas. (2) `docker-entrypoint.sh` aborta con el motivo
en vez de arrancar roto. **Desvío de la ficha:** la guarda cubre **las dos** perillas, no solo `GUNICORN_CMD_ARGS`:
`config/wsgi.py:13` también reacciona a `GUNICORN_WORKER_CLASS=gevent`, así que frenar únicamente la primera dejaba
abierto el mismo camino. Y cubre también `eventlet`, que tiene el mismo problema de hilos aunque `wsgi.py` no lo
parchee. `EntrypointTests` **ejecuta el script de verdad** (`sh docker-entrypoint.sh true`, que llega a la rama del
comando personalizado sin tocar la base) en vez de leer su texto, y verifica también que sin las variables el arranque
sigue y que la guarda corre **antes** de `wait_for_database` —si quedara después, en un ambiente con la base caída el
pod esperaría para siempre sin dar nunca el motivo real—. `test_el_parche_ya_no_existe` queda escrito y salteado: deja
de saltearse cuando OPS-13 borre el archivo.
**Ronda 2 de la revisión:** la guarda tenía un agujero y era demasiado ancha a la vez. (a) Miraba la cadena
`worker-class`, así que **`-k gevent` y `-k=gevent` —la forma corta— pasaban con rc 0** y el proceso arrancaba con el
parche aplicado: exactamente el estado que la ficha viene a cerrar, y los dos **sí** lo encienden, porque `wsgi.py`
busca la palabra en toda la variable. La condición pasó a ser la palabra (`gevent`/`eventlet`) y no la bandera, que
cubre las cuatro formas de una. (b) Abortaba ante **cualquier** `--worker-class`, y este script es el `ENTRYPOINT`
único de la imagen —daphne, gunicorn, el Job de bootstrap y los cuatro CronJobs—: un `sync` o un `gthread` explícito
habrían dejado un ambiente sin arrancar por un valor inocuo. Ahora esos dejan un `AVISO` y siguen. Y la rama de
`GUNICORN_WORKER_CLASS` dice qué hacer («Sacar la variable del entorno»), como la otra. Los ocho subcasos nuevos
fallan contra la guarda anterior. La verificación de las dos variables en el ambiente antes de espejar quedó como paso
0 de [`espejo-ecom.md`](../../espejo-ecom.md), junto al `--solo-reporte` de OPS-01.
**Test permanente:** `config.tests.test_wsgi_runtime.GeventTests.test_nadie_piso_validate_thread_sharing` (y
`EntrypointTests.test_las_cuatro_formas_de_pedir_gevent_abortan`,
`EntrypointTests.test_un_worker_class_inocuo_avisa_pero_arranca`).

**Resolución (parte Ola 7):** ✅ Cerrada en el PR 2 de la Ola 7 (Cambio 196), 09-oct-2026, adentro de OPS-13 y con
**D-RED-08 en su default**. Se borraron `config/gevent_patch.py`, las líneas 12-17 de `config/wsgi.py` y
`gevent`/`greenlet` de `requirements.txt`. `test_el_parche_ya_no_existe` dejó de saltearse, y los dos controles de
andamio se dieron vuelta: ahora afirman que `wsgi.py` **no** lee las dos perillas y que los dos paquetes **no** están
en `requirements.txt`.
**Antes de borrar se verificó qué worker usa gunicorn**, como pedía la consigna: `docker-entrypoint.sh` arranca
`gunicorn config.wsgi:application` **sin `--worker-class`** y con `--threads`, o sea gthread; la única forma de pedir
gevent eran las dos variables de entorno, y desde el Cambio 159 el entrypoint aborta ante las cuatro formas de pedirlo
en cualquiera de las dos. Ningún ambiente puede estar arrancando con gevent sin que el pod muera primero con el motivo
escrito.
**La guarda del entrypoint se queda tal cual**, y pasa a ser lo único que sostiene la ficha: sin el paquete, pedir
gevent haría morir a gunicorn con un «class uri 'gevent' invalid or not found», que no dice nada; la guarda corre
antes y dice qué pasa y qué hacer. **Lo que ECOM tiene configurado sigue sin confirmarse (H-05)**, así que el paso 0
de [`espejo-ecom.md`](../../espejo-ecom.md) —leer `GUNICORN_CMD_ARGS` y `GUNICORN_WORKER_CLASS` del ambiente antes de
espejar— **no se tocó**: sigue siendo la verificación humana, y lo que cambió es que el peor caso pasó de «respuestas
con datos de otra persona» a «no arranca y lo dice».
**Test permanente (Ola 7):** `config.tests.test_wsgi_runtime.GeventTests.test_el_parche_ya_no_existe`
(y `.test_wsgi_ya_no_lee_las_perillas_de_gevent`, `.test_gevent_y_greenlet_no_viajan_en_la_imagen`).

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

**Resolución:** ✅ Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — `programas/tests/test_models_contrato.py`,
19 tests. `ExportsTests` fija los **65** nombres públicos de `dir(programas.models)` (la ficha estimaba «~60») y falla
en **las dos direcciones**: uno que desaparezca es el re-export que el `__init__.py` de compatibilidad se olvidó —error
de runtime, no de import—, y uno nuevo es el recordatorio de que el contrato se escribe a mano. `AppLabelTests` fija el
`app_label` y la `db_table` de los **45** modelos contra un mapa literal, más la aserción de que la app no tiene modelos
sin registrar. `PropiedadesDeNegocioTests` cubre las properties con valores concretos: `Segmento.cupo_disponible`,
`Relevamiento.cupo_utilizado/cupo_disponible/cupo_completo` con su borde negativo, `Convocatoria.pausa_efectiva`
heredada y su cadena hasta el segmento, `habilitado_en` con `date` y con `datetime` —incluido el borde en que el `date`
se evalúa a las 00:00 locales y cae **antes** de la apertura de las 08:00— y `_dni_titular_actual` en sus cuatro
caminos. **Dos cosas que la ficha no tenía:** (a) de los 65 nombres, 8 son **imports que se filtran** al namespace
(`Ciudadano`, `Group`, `User`, `Path`, `TimeStamped`, `ValidationError` y los dos validadores); se verificó sobre los
320 `from … import` del repo que nadie los importa desde ahí, así que el corte puede dejarlos afuera a propósito, y el
test lo dice en el comentario; (b) `BloqueoSiis` aparece en `dir()` pero **no es un modelo** —es una clase plana,
duck-type de `PausableMixin`—. Dos tests cubren la anotación `formularios_count` y el `assertNumQueries(0)` de
`_dni_titular_actual` con el ciudadano asignado por id: un corte que «simplifique» esas dos ramas agrega N+1 sin que
ningún test de valores lo note. **Mutación de control:** renombrar `PausableMixin` y sacarle el `max(..., 0)` a
`Relevamiento.cupo_disponible` deja dos tests en rojo. El corte del archivo sigue siendo deuda opcional.
**Test permanente:** `programas.tests.test_models_contrato` (`ExportsTests.test_nombres_publicos_estables`,
`AppLabelTests.test_todos_los_modelos_siguen_en_programas`, `PropiedadesDeNegocioTests`).

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

**Resolución:** ✅ Resuelto en el PR R-06 (Cambio 123), 04-oct-2026 — `padron.normalizar_dni` acepta `Decimal` además
de `float` y las tres copias (`completar_casos_renaper._solo_digitos`, `corregir_datos_siis._digitos`,
`siis_envio._digitos`) pasan a ser alias de ella. El cast va al **entero**, no a texto. Se agregó una guarda que la
ficha no pedía: un `NaN` o un decimal con parte fraccionaria siguen yendo por texto en vez de reventar con
`int(Decimal("NaN"))` (la propuesta literal, `valor == int(valor)`, levanta `InvalidOperation`).
`NormalizarDniTests` recorre las **cuatro** puertas con `subTest` sobre los seis valores de la ficha; antes del cambio
daba 11 fallas (los tres alias con `float` y las cuatro con `Decimal`).
La quinta mención —`programas/api/serializers.py:168`, inline— no se tocó: recibe un string de DRF, nunca un `float` ni
un `Decimal`, y unificarla es parte de RED-48, que además tiene que resolver las tres reglas de largo.
**Test permanente:** `programas/tests/test_padron.py::NormalizarDniTests.test_float_y_decimal_no_agregan_un_cero`

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

**Resolución:** ✅ Resuelto en el PR 2 de la Ola 3 (Cambio 168), 07-oct-2026 — `LARGOS_DNI_VALIDOS = (7, 8)`,
`MENSAJE_DNI_INVALIDO` y `dni_valido()` en **`core/dni.py`**, consumidos por las puertas. **Tres desvíos:**
(1) la regla vive en `core/` y no en `padron.py`, porque `legajos` y `portal` también tienen puertas de DNI y
`legajos.models` no puede importar `programas` sin cerrar un ciclo que mide el ratchet de RED-79 — `padron`
**reexporta** los cuatro nombres, así que las ~20 importaciones que ya existían siguen andando y
`NormalizarDniTests` (RED-47) no se mueve; (2) las puertas eran **ocho**, no seis: la ficha no nombraba
`ConsultaRenaperForm.clean_dni` (7-8) ni `portal/forms/ciudadano.py::RegistroStep1Form.clean_dni` (**6 a 9**,
la más laxa de todas, y la séptima que VR2 no verificó) — la del registro se unificó igual, aunque su ruta no
esté publicada desde SEC-29, para que la regla no vuelva con el portal; (3) `siis_envio` **no** queda más laxo:
el `len(dni) <= 10` dejaba pasar un DNI de un dígito, el alta en SIIS no tiene baja y es mejor frenar el caso
con su motivo que informar un documento que ninguna pantalla habría aceptado. Eso último es un **cambio de
conducta** declarado en el riesgo de deploy del PR. El ratchet es `core/tests/test_regla_dni.py`, que recorre
el código productivo con `ast` y marca una comparación de largo contra 6-10 en una sentencia que habla de un
documento: se comprobó contra `HEAD` que detecta las **ocho** reglas que este PR retiró, incluida la del form
dinámico del portal, donde la variable se llama `valor` y quien dice de qué se habla es la rama
(`vinculo == "dni"`) y el mensaje de error. Escape documentado `# regla-dni: ok`, con la allowlist vacía.
**Ronda 2:** el ratchet barre además `scripts/` —el docstring lo decía y no lo hacía— y detecta la regla
escrita como **expresión regular** (`\d{7,8}`, `[0-9]{8}`, venga de `re`, de un `RegexValidator` o de un
`__regex` del ORM), no solo con `len()`. Al encenderlo apareció la **novena** puerta, que ningún barrido anterior
había visto: `users/forms/__init__.py` validaba el DNI del **usuario de backoffice** con
`RegexField(r"^\d{6,8}$")` —6 a 8 dígitos—. Queda unificada; el DNI de 6 que deja de aceptarse corresponde a
personas nacidas antes de 1930, y el campo sigue siendo opcional (Cambio 5). Se exceptúa
`scripts/check_datos_personales.py`, cuyo `\b\d{7,8}\b` es el gate que busca documentos, no una validación.
También se sumó `FormularioSerializer.apoderado_dni` —la puerta de la app de campo— al cruce de
`DniValidoTests`.
**Ronda 3:** la novena puerta estaba a medias. El ABM de usuarios **validaba normalizado y guardaba crudo**:
`Profile.dni` es un `CharField(max_length=8)`, así que `12.345.678` entraba por el form y moría en la escritura
con `DataError (1406, "Data too long for column 'dni'")` —un **500**— en MariaDB y en MySQL; SQLite no aplica el
`max_length` y la suite normal no lo veía. Se normaliza en `_validar_dni_perfil_usuario`, la regla de largo se
exige solo si el DNI cambia o es un alta (igual que en `Ciudadano`), y el barrido del resto encontró una más del
mismo patrón: `ConsultaRenaperForm.dni` limitaba a 8 el valor **crudo**. De ahí sale el invariante nuevo: **toda
puerta que acepta un DNI con puntos tiene que devolverlo en dígitos**, que es lo que mide
`test_toda_puerta_que_acepta_un_dni_con_puntos_lo_deja_en_digitos`.
**Test permanente:** `programas.tests.test_padron.DniValidoTests.test_misma_regla_en_todas_las_puertas`
(+ `test_toda_puerta_que_acepta_un_dni_con_puntos_lo_deja_en_digitos`,
`test_el_padron_descarta_la_fila_con_la_misma_regla` y
`test_siis_envio_ya_no_es_mas_laxo_que_los_formularios`),
`core.tests.test_regla_dni.UnaSolaReglaDeDniTests` y `users.tests.test_dni_usuario`
(`UsuarioDniMotorRealTests` con `@tag("mysql")`, que es donde el 1406 existe).

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

**Resolución:** ✅ Resuelto (parte R) en #604 (Cambio 156, PR R-16), 07-oct-2026 —
`TresCuposTests.test_las_tres_acepciones_son_distintas` fija los tres números con un segmento de 10, subsegmentos de 3 y
4 y 6 casos APROBADO: `Segmento.cupo_disponible == 3`, `get_cupo_stats(...)["cupo_disponible"] == 4` y
`Relevamiento.cupo_disponible == 2` (la tercera acepción, que la ficha nombra y no numeraba). Hay además una aserción
explícita de que las dos acepciones del segmento **siguen difiriendo**: es la que se pone roja si PERF-02 las unifica en
vez de renombrarlas. `test_el_contador_de_cuposegmento_no_lo_mueve_nadie` deja fijado el otro cabo de la ficha:
`CupoSegmento.cupo_ocupado` queda en 0 mientras `get_cupo_stats` cuenta 6, y `Segmento.clean()` valida contra el
primero. El renombre sigue en la Ola 4.
**Test permanente:** `programas.tests.test_cupo.TresCuposTests.test_las_tres_acepciones_son_distintas`.

**Resolución (parte Ola 4):** ✅ Cerrada en #632 (Cambio 182, Ola 4 PR 1-2), 08-oct-2026 — renombradas, no unificadas:
`Segmento.cupo_disponible` → **`cupo_sin_distribuir`** y `Relevamiento.cupo_disponible` →
**`cupos_libres_del_relevamiento`**; `cupo_disponible` queda solo para `get_cupo_stats`. Sin alias de compatibilidad: se
actualizaron los dos templates de configuración, la variable de contexto homónima de
`programas/views/configuracion.py` —que es la misma acepción calculada aparte— y los tres tests de contrato. **El campo
de la API no cambia**: `RelevamientoListSerializer` declara `cupo_disponible = IntegerField(source=
"cupos_libres_del_relevamiento")`, porque lo lee la app de campo ya instalada y lo congelan
`test_becas_api_contrato.py` y `test_api_schema_contrato.py`. **Los textos visibles no cambian** (la ficha no lo pedía):
las dos pantallas siguen rotulando «Cupo disponible», cada una con su número; decidir si uno de los dos rótulos cambia
es del cliente y queda anotado para el PM.
**Test permanente:** `programas.tests.test_cupo.TresCuposTests.test_ninguna_de_las_tres_acepciones_se_llama_ya_cupo_disponible`.

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

**Resolución:** 🟡 Caracterizada en #604 (Cambio 156, PR R-16), 07-oct-2026 — **el arreglo sigue siendo de la Ola 3.**
`EdadHorarioTests` pone al proceso en las 23:00 del 30/06 local (02:00 UTC del 01/07) parcheando `timezone.now` y el
`date` que importaron los cuatro módulos que resuelven «hoy» (`becas`, `condiciones`, `siis_envio`,
`legajos.selectors.ciudadanos`). `test_el_corte_es_la_fecha_local_no_la_del_sistema` afirma que quien cumple 18 el 01/07
sigue siendo menor esa noche y está **rojo**, marcado `@unittest.expectedFailure`: cuando la Ola 3 unifique la edad en
`timezone.localdate()` pasa a *unexpected success* y hay que sacarle el decorador. Lo acompañan un control del andamio
—para que el `expectedFailure` no quede rojo por un parche que no hace lo que dice— y dos tests en verde que fijan la
aritmética con `hoy` explícito y el `None` sin fecha, que el arreglo tiene que conservar. La severidad sigue atada a
**H-13** (la `TZ` real de los contenedores de ECOM).
**Test permanente:** `programas.tests.test_becas_reglas.EdadHorarioTests.test_el_corte_es_la_fecha_local_no_la_del_sistema`.

**Ampliado por #621 (Cambio 172, Ola 3 PR 6), 07-oct-2026 — ✅ cerrada.** La cuenta vive una
sola vez en `core/edad.py` (`edad_en_anios(fecha, hoy=None)`, `es_menor(fecha, hoy=None)` y
`MAYORIA_DE_EDAD = 18`) y resuelve «hoy» con `timezone.localdate()`, que lee el `TIME_ZONE` del
proyecto y no el reloj del contenedor. Las **seis** copias medidas —la ficha decía cuatro; el
detector encontró además `legajos/selectors/ciudadanos.py` y `Ciudadano.edad`— quedaron en cero:
`becas.es_menor` y `condiciones.edad_en_anios` se borraron y sus dos llamadores
(`programas/api/serializers.py`, `programas/forms.py`) importan de `core.edad`; `siis_envio._edad` y
`corregir_datos_siis._edad` también, con un solo `MAYORIA_DE_EDAD`. De paso se unificó el lector
permisivo de fechas (`core.edad.fecha_o_none`), que estaba duplicado entre `condiciones` y la
conversión de la edad.

`test_el_corte_es_la_fecha_local_no_la_del_sistema` perdió su `@unittest.expectedFailure` y pasa de
verdad; el andamio se simplificó —ya no hace falta parchear el `date` de cuatro módulos, porque
ninguno lo usa: alcanza con `core.tests.reloj.reloj_en`—. **Dos guardarraíles nuevos**, porque un
arreglo de duplicación sin ratchet se vuelve a duplicar: (1) la regla **`DTZ011`** de ruff en
`pyproject.toml`, que prohíbe `date.today()` en todo el código productivo (los tests quedan
exentos y los dos usos deliberados —rotación de logs por día de la máquina y el default de
`check_excepciones_seguridad.py`— llevan `# noqa: DTZ011` con el motivo); (2)
`SinCalculoDeEdadPropioTests`, que recorre con `ast` los seis módulos de la ficha buscando la forma
de la resta de cumpleaños y los nombra con archivo y línea si vuelve a aparecer, con su control de
andamio. La severidad ya no depende de **H-13**: el arreglo no asume ninguna `TZ` de contenedor.
**Test permanente:** `programas/tests/test_becas_reglas.py::EdadHorarioTests.test_el_corte_es_la_fecha_local_no_la_del_sistema` (y `.test_la_mayoria_de_edad_se_lee_de_un_solo_lugar`, `SinCalculoDeEdadPropioTests` ×2, más las doce de `legajos/tests/test_fechas_locales_bec18.py`, que cubren la edad del buscador rápido y de `Ciudadano.edad`).

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

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **el arreglo sigue siendo de la
Ola 4.** `dashboard/tests/test_cache_invalidacion.py`, 11 tests, con los **dos** bugs en `expectedFailure`:
`test_inscripcion_nueva_invalida_stats_legajos` (la clave la escribe `contar_legajos()` sobre `InscripcionPrograma` y el
único receiver que la borra está colgado de `LegajoAtencion`) y `test_alerta_nueva_invalida_alertas_activas` (nadie
borra esa clave cuando nace una alerta). Los dos pasan a *unexpected success* al agregar los receivers con el `sender`
correcto: se verificó. En verde quedan fijados los caminos que la deduplicación de OPS-10 **no puede perder**: el
receiver de `Ciudadano`, el de `User` con su rama que saltea `update_last_login`, el que sí borra `stats_legajos` al
guardar un `LegajoAtencion` (para que el arreglo mueva el `sender` sin borrar el receiver) y la limpieza que hace hoy el
alta de ciudadanos. `DosFuncionesTests.test_no_borran_las_mismas_claves` es el ratchet que vuelve visible la trampa: no
son copias —una borra tres claves más—, así que «deduplicar» quedándose con cualquiera de las dos pierde algo.
**Un desvío de la ficha, verificado contra el código:** `CiudadanosService.invalidate_ciudadanos_cache` **sí tiene
llamadores** —las tres vistas de alta, edición y borrado de ciudadanos (`legajos/views/ciudadanos.py:142,199,233`)—, así
que la función de `dashboard/utils.py` se ejecuta en producción y borrarla no es gratis. Queda fijado con un test AST
(`test_el_servicio_de_ciudadanos_tiene_llamadores`).
**Test permanente:** `dashboard.tests.test_cache_invalidacion.InvalidacionTests.test_inscripcion_nueva_invalida_stats_legajos`
(y `.test_alerta_nueva_invalida_alertas_activas`).

**Resolución:** ✅ (segunda parte, Ola 4 PR 9) Resuelta en #648 (Cambio 194), 08-10-2026 — `dashboard/cache.py` es la
tabla única que pedía la ficha: cada clave con la consulta que la escribe y el `label_lower` del modelo que la
invalida (`CLAVES_POR_MODELO`), con `clave_seguimientos_hoy()` resuelta en el momento porque lleva la fecha adentro.
Los dos `expectedFailure` pasan a verde: `stats_legajos` la borra ahora el receiver de `InscripcionPrograma`
(`dashboard/signals/cache.py`, registrado en `DashboardConfig.ready()`) y `alertas_activas` estrena el suyo sobre
`AlertaCiudadano`. La segunda `invalidate_dashboard_cache` **se borró**: el receiver de `User` llama a
`invalidar_por_modelo` y `CiudadanosService.invalidate_ciudadanos_cache` a `invalidar_dashboard`, la única que queda.
`DosFuncionesTests` quedó invertido en `UnaSolaFuncionTests`: un recorrido `ast` por las siete apps falla si el nombre
vuelve a definirse **en cualquier lado**, y dos tests nuevos cierran la regla por la otra punta —que la función única
borre todo lo que la tabla declara, y que todo contador que escriba una clave esté en la tabla—, porque la mitad del
bug original era un contador sin dueño. **Tres desvíos, los tres a favor:** (1) el receiver de `User` ya **no** borra
`contar_ciudadanos` —dar de alta a alguien del backoffice no cambia cuántos ciudadanos hay, y la ficha no lo pedía
pero es la consecuencia directa de invalidar por modelo—; (2) ese mismo receiver pasa a `on_commit`, como el de
`Ciudadano` desde PERF-04, para no invalidar ante un rollback; (3) `invalidar_dashboard` borra **en el acto** y no
diferido, que es la semántica de la función que reemplaza —la llaman las tres vistas de ciudadanos después de
guardar—. Mutación de control: sin el `import` de `dashboard.signals` en `ready()`, los dos tests invertidos vuelven a
rojo.
**Test permanente:** `dashboard.tests.test_cache_invalidacion.InvalidacionTests.test_inscripcion_nueva_invalida_stats_legajos`
(y `.test_alerta_nueva_invalida_alertas_activas`, `UnaSolaFuncionTests.test_no_quedan_dos_funciones_llamadas_invalidate_dashboard_cache`).

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

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **el arreglo sigue siendo de la
Ola 2 (PR 2).** `users/tests/test_middleware_profile.py`, 11 tests. `OrdenMiddlewareTests` fija el orden del que
depende todo —`BackofficeSingleSessionMiddleware` antes que `CambioContrasenaObligatorioMiddleware`, y los dos después
de `AuthenticationMiddleware`, porque antes de ese `request.user` no existe y la sesión única dejaría de aplicarse en
silencio—. `ProfileEnCacheTests` prueba la promesa del `fields_cache` midiendo el middleware, no la pantalla:
`assertNumQueries(0)` con la caché poblada y `assertNumQueries(1)` sin ella, que es el costo exacto que la línea evita.
**Desvío de la ficha:** se midió el gate en vez de `GET /inicio/` entero; el número global es frágil, ya está cubierto
por los presupuestos de performance y no distingue qué consulta se agregó.
**Un hallazgo que la ficha no tenía:** el *lost update* tiene **dos** caras, no una. La que la ficha describe
(`backoffice_session_key` pisada por un `user.save()` concurrente) está en
`test_user_save_no_pisa_la_clave_de_sesion_de_otro_login`; la segunda apareció escribiendo el módulo —el primer intento
de probar el gate de clave provisoria falló por este motivo—: **el login mismo** lo dispara. `login()` llama a
`update_last_login`, que hace `user.save(update_fields=["last_login"])`, y `save_user_profile` guarda el Profile
**entero** que tenía en la caché del objeto en memoria, revirtiendo un `debe_cambiar_contrasena` escrito por otro
request. Queda en `test_un_login_pisa_el_flag_de_clave_provisoria`, también con `expectedFailure`. El arreglo (acotar
con `update_fields` o sacar el guardado del `post_save`) cubre las dos de una: se verificó que los dos pasan a
*unexpected success*. `test_sin_profile_en_la_cache_el_user_save_no_consulta` deja fijada la optimización que el
receiver **sí** aporta y que el arreglo tiene que conservar (nada de N+1 en un `User.save()` en lote).
**Ronda 2 de la revisión — el bug de esta ficha se comió a uno de sus propios tests.**
`test_la_api_no_pasa_por_el_gate_de_clave` era **vacuo**: usaba el objeto de `setUpTestData`, que arrastra en su
`fields_cache` el Profile del alta con `debe_cambiar_contrasena=False`, así que el gate salía por la rama del flag y
nunca llegaba a evaluar el path. Medido: con el filtro `request.path.startswith("/api/")` **borrado**, el test seguía
pasando. Ahora el usuario se relee de la base y lo acompaña
`test_fuera_de_la_api_la_misma_peticion_si_redirige`, que cambia **solo** el path; con esa mutación, el primero queda
rojo. De paso quedó corregido el docstring, que atribuía la exención al usuario anónimo cuando la condición escrita en
el código es por path (los tokens de DRF se resuelven dentro de la vista, pero eso no es lo que el gate mira).
**Test permanente:** `users.tests.test_middleware_profile.ProfileEnCacheTests.test_user_save_no_pisa_la_clave_de_sesion_de_otro_login`
(y `.test_un_login_pisa_el_flag_de_clave_provisoria`, `OrdenMiddlewareTests.test_single_session_va_antes_que_cambio_de_clave`).

**Resolución:** ✅ (segunda parte, Ola 2) Resuelta en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 —
`save_user_profile` **se borró**, no se acotó con `update_fields`. Acotarlo dejaba en pie el patrón
(«el Profile se propaga solo en algún `User.save()`») sin que nadie lo use: los cuatro llamadores que
escriben el Profile —`users/middleware.py`, `users/services/admin.py`, `users/services/correo.py` e
`import_users_from_csv`— ya lo guardan explícitos con `update_fields`, y el único lector de
`user.profile` fuera de ahí (`users/presentation.py`) solo lee. Los dos `expectedFailure` pasaron a
verdes y el andamio `test_hoy_el_user_save_propaga_el_profile_entero` se reemplazó por
`test_el_user_save_ya_no_propaga_el_profile_entero`, que fija el contrato nuevo en la dirección
contraria: si alguien reintroduce el receiver —parece prolijidad—, se pone rojo antes de que vuelva
el *lost update*. `test_sin_profile_en_la_cache_el_user_save_no_consulta` sigue en pie: la
optimización que el receiver sí aportaba se conserva trivialmente.
**Lo que destapó, y que ningún test miraba:** `programas/tests/test_padron.py::UnaSolaPuertaDePadronTests`
abría varios `Client` sobre el mismo usuario y pasaba **gracias al bug** —`force_login` no escribe
`backoffice_session_key`, y el receiver reponía el valor viejo del objeto cacheado, de modo que
`BackofficeSingleSessionMiddleware` adoptaba cada sesión nueva—. Sin el receiver, el segundo cliente
recibe «Tu sesión fue reemplazada», que es el comportamiento real del producto. El test ahora escribe
la clave de sesión como lo hace `UsuariosLoginView.form_valid`.
**Test permanente (Ola 2):** `users.tests.test_middleware_profile.ProfileEnCacheTests.test_el_user_save_ya_no_propaga_el_profile_entero`.

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

**Resolución:** ✅ Resuelta **la parte de la Ola 1** en el PR 2 (Cambio 127), 05-oct-2026 —
`programas/management/commands/_base_siis.py::ComandoSiisBase` con los flags comunes (`--aplicar`,
`--lote`, `--pausa`, `--max-errores`, `--usuario`), `_log`, `_solicitante`, `_lotes`, `_resumen`,
`_avisar_ensayo`, `_exigir_credenciales` y `_cortado_por_errores`; heredan los cuatro comandos que
hablan con SIIS caso por caso. **Desvíos de la ficha:** (1) el cuarto comando es
`reenviar_siis_pendientes` y no `correr_alta_siis`, que no llama a la API —encadena a los otros—;
(2) la paridad se mide sobre los cinco flags que tienen sentido en los cuatro, no sobre todos
(`--limite`/`--total` y los filtros siguen siendo de cada comando); (3) el paso de `pylint` en CI no
entró: el repo no tiene pylint instalado y agregarlo es una dependencia nueva del CI, que es trabajo
de la Ola 7 (RED-85 pinea herramientas). Efecto lateral: `reenviar_siis_pendientes` pasa a correr en
seco por defecto, como los otros tres. Falta la parte de la Ola 5 (`_subir_padron`).
**Test permanente:** `programas/tests/test_siis_un_solo_envio.py::FrenoConSiisCaidoTests.test_los_comandos_honran_el_freno_con_siis_ambiguo` (y `ParidadComandosSiisTests.test_los_cuatro_comandos_aceptan_los_mismos_flags`).
**Ronda 3 de la revisión:** el test de paridad miraba que el flag **existiera**, no que el comando
lo **usara**, y así dejó pasar justo el caso que la ficha describe: `reenviar_siis_pendientes`
heredaba `--max-errores` y `--max-inciertos` de la base y los ignoraba. Desde entonces los tres
comandos se ejercitan con SIIS contestando mal y se exige que corten de verdad.

**Resolución (Ola 5):** ✅ Resuelta **la parte de la Ola 5** en #611 (Cambio 164, PR 8 de la Ola 5),
07-oct-2026 — `programas/views/relevamientos.py::_subir_padron(request, duenio, destino, clave,
prefijo="")`: el cuerpo que `convocatoria_padron` (Cambio 57) y `relevamiento_padron` (Cambio 74)
tenían escrito dos veces queda en un solo lugar y cada vista pasa a ser el `get_object_or_404`, su
guard y la llamada. **Lo que no se unificó, a propósito:** la autorización, que es distinta en cada
una —la convocatoria filtra por `convocatorias_visibles` y el relevamiento llama a `_assert_scope`—,
y por eso un test afirma que cada vista conserva la suya. **Desvío de la ficha:** la firma lleva un
argumento más (`clave`), porque la clave del resumen fijo en sesión (`conv-<pk>` / `rel-<pk>`) la lee
el detalle de cada pantalla (`relevamientos.py:311` y `:738`) y derivarla del tipo del objeto ataría
dos cosas que hoy son independientes. **Verificado por mutación:** volver a escribir el cuerpo dentro
de `convocatoria_padron` pone rojo los tres tests de la puerta única (el AST, el largo del cuerpo y el
borde compartido del Excel ilegible). **Test permanente:**
`programas.tests.test_padron.UnaSolaPuertaDePadronTests` (6: las dos vistas llaman a `_subir_padron` y
ninguna a `cargar_padron`/`parsear_padron`, el cuerpo de cada una no pasa de cinco sentencias, las dos
avisan igual sin archivo, las dos conservan el padrón anterior si el Excel no se entiende, solo el
relevamiento lleva el prefijo «Padrón propio de este relevamiento. » y cada vista conserva su guard).
Los otros tres grupos de clones que lista la *Ubicación* (`dispositivos_config` ≡
`dispositivos_legajo`, `padron.py` ≡ `revision.py`) **siguen abiertos** y son de RED-79.

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

**Resolución:** ✅ Resuelta **la mitad de la Ola R** en el PR R-06 (Cambio 123), 04-oct-2026 — `ContextoDetalleTests`
declara por separado las **36** claves que pone la vista y las **17** del entorno (builtins del engine y context
processors) y las compara por igualdad en los dos sentidos: una clave que se cae pone el test en rojo, y una clave nueva
hay que anotarla. Tres escenarios: el caso rico (APROBADO con adjunto, respuesta, GPS, una `ValidacionSIS`, un
`EnvioSIIS` RECHAZADO con detalles y una traza), el caso mínimo (sin ciudadano, sin GPS, sin datos, ENVIADO) y el caso
en lista de espera. `ConsultasDetalleTests` fija el presupuesto en **15 consultas** —el número de hoy, ratchet que solo
baja— y agrega el test que caza un N+1: cinco envíos y cinco validaciones más no mueven el número.
**Desvío de la ficha:** la propuesta decía `assertEqual(sorted(response.context.flatten()), CLAVES)`; `response.context`
es un `ContextList` (todos los templates renderizados, incluidos los locales de cada `include`) y no tiene `flatten`.
Se usa `response.context[0].flatten()`, que es el contexto de la vista.
Verificado a mano: sacar `"mapa": mapa` del contexto → 2 tests en rojo.
**Queda abierto (Ola 7):** extraer `contexto_identidad`, `contexto_siis` y `contexto_respuestas` a
`programas/selectors/revision.py`.
**Test permanente:** `programas/tests/test_becas_revision.py::ContextoDetalleTests.test_claves_del_contexto_del_detalle`

### RED-55 · Los context processors corren en cada render y tragan toda excepción sin log
**Severidad:** MEDIA (era BAJA en RS-R4-21 y VR2: se sube porque corre en el 100 % del tráfico autenticado y hoy convierte un `OperationalError` en «usuario sin grupos» sin rastro; va con OPS-03) · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-21 (VR2: CONFIRMADO) · **Ola:** R (va con OPS-03, que pasa a la Ola R) · **Esfuerzo:** S (2 h)
- **Ubicación:** `core/context_processors.py:34-42` (`sidebar_badges`) y `conversaciones/context_processors.py:12-28`
  (`user_groups`), los dos con `except Exception` sin log, en el 100 % del tráfico autenticado.
- **Qué cambio lo rompería sin que nadie se entere:** nada: un `OperationalError` de MariaDB por `read_timeout` ya se
  convierte hoy en «badge 0» y «usuario sin grupos» (el rol desaparece del sidebar) sin rastro.
- **Propuesta:** `logger.exception(...)` en los dos `except`, acotados a `DatabaseError`/`ImportError`. Test
  `core/tests/test_context_processors.py::DegradacionTests.test_el_fallo_se_loguea` (`patch(..., side_effect=OperationalError)`,
  `assertLogs`, el render sigue en 200).

**Resolución:** ✅ Resuelto en el PR R-15 (Cambio 153), 06-oct-2026 — `logger.exception` en los dos `except`, con el
motivo escrito al lado. **Un desvío deliberado:** los `except` siguen siendo `except Exception` y **no** se acotaron a
`DatabaseError`/`ImportError`. Acotarlos cambia lo que ve el usuario en el 100 % del tráfico autenticado: cualquier otra
excepción —un `TypeError` en `nombres_de_grupos`, un selector que cambia de forma— pasaría de «sidebar degradado» a
**500 en toda pantalla del backoffice**, que es un riesgo mayor que el que la ficha cierra. El hallazgo era «traga sin
log», no «traga»; el log es lo que se agregó. Los tests fijan las dos mitades: que el fallo se registre con su traceback
y que el contexto siga degradando igual (`badge 0`, `user_groups_list` vacío) con la pantalla en 200. Va de la mano con
OPS-03: sin aquello, estos `logger.exception` tampoco llegarían a `kubectl logs` en ECOM. **Test permanente:**
`core.tests.test_context_processors` (`SidebarBadgesDegradacionTests.test_el_fallo_se_loguea`,
`UserGroupsDegradacionTests.test_el_fallo_se_loguea`, `RenderDegradadoTests`).

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

**Resolución:** ✅ Resuelto en el PR R-06 (Cambio 123), 04-oct-2026 — `_programa_o_denegar(user, programa=None)` en
`autorizacion.py`, aplicado en las seis apariciones: levanta `PermissionDenied("El Programa Becas no está
configurado.")` cuando `programa_becas()` devuelve `None`. `puede_operar_subsegmento` quedó afuera a propósito: delega
en `puede_gestionar_segmento`, que ya la tiene.
`GuardsFallanCerradoTests` arma el escenario de VR2 (un rol de **otro** programa con `becas.programa.administrar`,
`becas.revision.ver` y `becas.revision.editar` tildadas; el árbol del ABM de Roles muestra el catálogo entero, así que
tildarlas es un clic) y recorre los tres guards de las vistas más las cuatro puertas de servicio. Antes del cambio: 7
fallas. El ratchet con el programa sembrado pasaba ya.
**Efecto no previsto por la ficha, decidido a favor de fallar cerrado:** la guarda está **antes** del bypass del RBAC,
así que un superusuario también recibe 403 si falta la fila `BECAS` — igual que en Dispositivos
(`dispositivos.py:56, 63, 77`), que es el patrón que la ficha pide copiar. El síntoma fue que cinco tests existentes que
nunca sembraban el programa empezaron a dar 403 (`test_presentacion_selector`, `test_nodo_tables_css`,
`test_nodo_ui_piezas`, `test_correcciones_review`, `test_correcciones_review_2`); se les agregó `seed_becas`, que es el
escenario de producción.
**Test permanente:** `programas/tests/test_becas_rbac.py::GuardsFallanCerradoTests.test_sin_programa_becas_los_tres_guards_deniegan`

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

**Resolución:** ✅ Resuelto en #604 (Cambio 156, PR R-16), 07-oct-2026 — `q_con_identidad()` es el único lugar donde la
RN-2 se escribe para la base, y `PadronHabilitadoQuerySet.con_identidad()` es su envoltorio para un queryset; los
docstrings de la property y del método se nombran mutuamente. Se expone como **`Q`** y no solo como método porque el
contador del detalle de la convocatoria es un `Count(filter=…)` anotado, no un queryset: sin el `Q` no había forma de
que usara la misma definición. `IdentidadDelPadronTests` recorre las once combinaciones con `subTest` y enfrenta las
dos mitades fila por fila; cuatro tests más miran la clase de caracteres contra `str.isspace()`, el cruce automático
(con su control, que sí valida la fila completa), `objetivo_con_identidad` y el contador de la pantalla. Corridos
contra la regla vieja (`.exclude(nombre="")`) dan 4 rojos.
**Tres desvíos de la propuesta, los tres code-first:** (1) el modelo se llama **`PadronHabilitado`**, no `FilaPadron`;
(2) los sitios con la regla duplicada eran **cuatro**, no dos — además de los dos de `padron.py`,
`programas/management/commands/diagnosticar_integraciones.py:320` y `programas/views/relevamientos.py:301` (el
«N con identidad» del detalle de la convocatoria, encontrado en la ronda 2 de revisión), los dos cambiados; (3) la
regla **no** usa `Trim` —el `TRIM()` de MySQL y de MariaDB saca solo espacios y `str.strip()` saca también
tabulaciones, saltos y los espacios Unicode— **ni `\s`, ni `[[:space:]]`**: Django compila el lookup `regex` como
`%s REGEXP BINARY %s` en MariaDB (PCRE, donde las dos clases son **ASCII**) y como `REGEXP_LIKE(…, 'c')` en MySQL 8
(ICU, Unicode). Medido contra `mariadb:10.11`: con `\s`, un nombre de un solo NBSP (`\xa0`), EM SPACE, IDEOGRAPHIC
SPACE o NEL quedaba **dentro** de `con_identidad()` mientras `tiene_identidad` decía `False`, y **en SQLite la suite
seguía verde**. La regla es ahora la clase literal `CARACTERES_SIN_TEXTO`, los 29 caracteres que `str.strip()` saca
—ninguno especial dentro de una clase de regex—, y `test_la_clase_cubre_exactamente_lo_que_saca_strip` impide que la
lista se desfase de `str.isspace()`. Que los tres motores coincidan con `strip()` lo fija
`IdentidadDelPadronMotorRealTests`, `@tag("mysql")`, con 17 casos —incluidos tres controles de falso positivo que
`REGEXP BINARY` haría sospechar: `à`, que se codifica con el mismo byte `A0` del NBSP; un NBSP **interno**; y el ZWSP,
que para Python no es whitespace—, verificado contra `mariadb:10.11` (sin tzinfo) y `mysql:8.0`.
**Test permanente:** `programas.tests.test_padron.IdentidadDelPadronTests.test_property_y_queryset_coinciden`.

### RED-78 · `DashboardView`: copia del inicio sin el blindaje de SEC-14, muerta solo por el orden de URLs
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO con test (`resolve('/').view_name == 'users:login'`; `reverse('dashboard:inicio') == '/'`) · **Origen:** RS-R4-10 (VR2: CONFIRMADO) · **Ola:** R (test de ruteo) + 7 (borrado, con OPS-14) · **Esfuerzo:** S (2 h) + S (2 h)
- **Ubicación:** `core/views/public.py:52-126` (`inicio_view`) y `dashboard/views/home.py:19-57` (`DashboardView`, en `/`
  por `dashboard/urls.py:9`); `config/urls.py:36` (`users.urls`) gana sobre `:39`.
- **Qué cambio lo rompería sin que nadie se entere:** reordenar `config/urls.py` (el comentario «Root paths last» lo
  invita): `/` pasa a ser `DashboardView`, con contadores globales y sin el gate por capacidad de SEC-14.
- **Propuesta:** **R:** `core/tests/test_dashboard_redirect.py::RuteoRaizTests.test_la_raiz_es_el_login`. **Ola 7:** borrar
  `dashboard/views/home.py`, `dashboard/templates/dashboard.html` y su `path` (las 5 APIs de `dashboard/api_views` se
  conservan) y llevar los contadores a `dashboard/selectors.py::metricas_home()`.

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **el borrado de `DashboardView`
sigue siendo de la Ola 7 (con OPS-14).** `core/tests/test_dashboard_redirect.py::RuteoRaizTests`, 3 tests:
`test_la_raiz_es_el_login` (`resolve('/').view_name == 'users:login'`), `test_dashboard_inicio_sigue_apuntando_a_la_raiz`
(`reverse('dashboard:inicio') == '/'`, o sea la vista está **tapada**, no montada en otra ruta) y
`test_la_vista_tapada_no_tiene_el_gate_de_capacidad`, que es lo que vuelve grave al reordenamiento: `DashboardView` solo
exige `LoginRequiredMixin` y no tiene el gate por capacidad de SEC-14, así que si alguna vez lo tuviera, ese test se
pone rojo y la ficha baja de riesgo. **Mutación de control:** mover `path("", include("dashboard.urls"))` arriba de
`users.urls` —lo que el comentario «Root paths last» de `config/urls.py` invita a hacer— deja
`test_la_raiz_es_el_login` en rojo con `'dashboard:inicio' != 'users:login'`.
**Test permanente:** `core.tests.test_dashboard_redirect.RuteoRaizTests.test_la_raiz_es_el_login`.

**Resolución:** ✅ (parte Ola 7) Resuelto en #651 (Cambio 197, Ola 7 PR 3), 09-oct-2026 — se van
`dashboard/views/` entero (`home.py` y el `__init__.py` que la reexportaba),
`dashboard/templates/dashboard.html` y el `path("", …, name="inicio")` de `dashboard/urls.py`. Las cinco
APIs de `dashboard/api_views` se conservan, con un test que lo fija: el hallazgo era la pantalla, no la
app. `RuteoRaizTests` cambia de forma en consecuencia —`test_dashboard_inicio_sigue_apuntando_a_la_raiz`
y `test_la_vista_tapada_no_tiene_el_gate_de_capacidad` describían una vista que ya no existe— y pasa a
afirmar que `reverse("dashboard:inicio")` levanta `NoReverseMatch` y que `dashboard.views` no se puede
importar; `test_la_raiz_es_el_login` queda, ahora sin depender del orden del URLconf.

**Que estaba muerta se demostró antes de borrar:** `dashboard:inicio` no lo nombra ningún template, vista,
estático, cron, entrypoint ni workflow (el único uso era el comentario de `core/urls.py`, que explicaba
por qué el alias `/dashboard/` **no** apunta ahí), y `dashboard.html` no lo incluye ni lo extiende nadie.

**Un desvío y una aclaración, los dos code-first.** (1) **`dashboard/selectors.py::metricas_home()` no se
crea:** la propuesta pedía «llevar los contadores» ahí, y con la vista borrada no hay contadores que
llevar —los que sirven pantallas vivas son los de `inicio_view` y ya están en `dashboard/utils.py`, que
RED-51 acaba de reorganizar en #648—. (2) **`contar_legajos()` se queda**, aunque esta vista era su último
llamador: RED-51 tiene dos tests escritos sobre que `stats_legajos` agrega inscripciones y el mapa de
claves de `dashboard/cache.py` la contempla; sacarla es de esa ficha. Su docstring queda actualizado para
no seguir citando a un llamador que no existe. **Test permanente:**
`core.tests.test_dashboard_redirect.RuteoRaizTests.test_dashboard_inicio_ya_no_existe`
(y `.test_el_paquete_de_vistas_del_dashboard_no_esta`, `.test_las_apis_del_dashboard_siguen_ruteadas`,
`.test_la_raiz_es_el_login`).

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

**Resolución:** ✅ (parte R) Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **los movimientos siguen siendo
de la Ola 2 (PR 5, con SEC-21).** `programas/tests/test_arquitectura.py`, 11 tests, con un detector AST propio del grafo
de imports de las diez apps (sin migraciones ni tests), que además distingue el import **a nivel de módulo** del
**diferido**. `CapasTests.test_no_crecen_las_dependencias_entre_vistas` fija las 9 aristas vista→vista con
`EXENTOS = {"ajax_utils"}`, e `ImportsTests.test_no_hay_ciclos_nuevos` los ciclos conocidos. Los dos ratchets fallan en
**las dos direcciones**: lo que crece y lo que se resolvió y nadie sacó de la lista —que es, literalmente, el registro
que la Ola 2 tiene que dejar—.
**Un desvío de la ficha:** los ciclos son **cinco**, no tres. A los tres que la ficha nombra (`becas ↔ diseno`,
`views.configuracion ↔ views.dashboard_becas`, `users.forms ↔ users.selectors.usuarios`) la medición agrega
`programas.models ↔ programas.services.inscripciones` y `programas.services.proceso_masivo ↔
programas.services.siis_envio`; este último es el único con una pata ya a nivel de módulo. El detector **excluye** la
relación paquete↔submódulo (`models/__init__.py` re-exporta `models/base.py`, que importa del paquete): sin ese filtro
aparecen dos «ciclos» más que son diseño normal de paquetes, no acoplamiento.
`test_cada_ciclo_conocido_tiene_al_menos_un_import_diferido` deja escrito **por qué** hoy ninguno explota, que es
exactamente lo que una «limpieza de imports» se lleva puesto. El tercer cabo de la ficha —el invariante de alcance
escrito tres veces y los dos `_assert_scope` homónimos— queda en `GuardsDeAlcanceTests`, que fija dónde está cada copia
hoy y se pone rojo cuando SEC-21 las mueva: ese es el aviso que la ficha pide que nadie se pierda.
**Mutación de control:** un import nuevo entre `views/merenderos.py` y `views/cupo.py` deja los dos ratchets en rojo.
**Test permanente:** `programas.tests.test_arquitectura.CapasTests.test_no_crecen_las_dependencias_entre_vistas`
(y `ImportsTests.test_no_hay_ciclos_nuevos`, `GuardsDeAlcanceTests`).

**Resolución:** ✅ (parte Ola 2, los movimientos) en #626 (Cambio 177, Ola 2 PR 5), 08-oct-2026 — con SEC-21,
como pedía la ficha. A `services/autorizacion.py` se mudaron `CAP_RELEVAMIENTO_PUBLICO`, el filtro de RN-P13 (hoy
`puede_relevamiento_publico` + `sin_relevamientos_publicos_si_no_puede` + `sin_formularios_publicos_si_no_puede`, que
estaba escrito dos veces) y el invariante de alcance, unificado en `assert_alcance_relevamiento` /
`assert_alcance_formulario` —las tres copias de `relevamientos.py` y `revision.py` se borran—; y
`configuracion._assert_scope` pasa a `_assert_scope_segmento`, que era el homónimo peligroso. **Los dos ratchets bajan
en el mismo PR**, que es la mitad que mide `test_las_aristas_resueltas_salen_de_la_lista`: las aristas vista→vista
pasan de **9 a 7** (se van `dashboard_becas → configuracion` y `pausas → relevamientos`) y los ciclos de **6 a 5**
(se va `views.configuracion ↔ views.dashboard_becas`). `GuardsDeAlcanceTests` se da vuelta: en vez de fijar dónde
está cada copia, afirma que **no hay** copias privadas en las vistas.
**Dos desvíos de la ficha, los dos code-first:** (1) `_programas_qs` iba a `programas/selectors/`, pero ese paquete
**no existe** en `programas` —el resto de los querysets de alcance de Becas vive en `autorizacion.py`—, así que queda
ahí como `programas_siis_visibles`; (2) `revision → relevamientos` **no se pudo cerrar**: además de la constante,
`revision` importa `PaginadorConConteo`, que es una pieza de paginación y no de autorización. Queda en la lista con
ese motivo.

### RED-80 · `programa_becas` y `programa_dispositivos`: mismo cache, distinta guarda e invalidación
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R4-18 (VR2: CONFIRMADO) · **Ola:** 2 (PR 1, con SEC-07) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/autorizacion.py:48-77` (clave `programas:becas`) y `programas/services/dispositivos.py:32-49`
  (`programas:dispositivos`); `seed_becas.py:202` borra la de Becas; **nadie** borra la de Dispositivos.
- **Qué cambio lo rompería sin que nadie se entere:** un restore que recrea la fila `DISPOSITIVOS` con otro pk: durante
  300 s todos los pods evalúan contra el pk viejo y nadie entra a Dispositivos; se cura solo.
- **Propuesta:** `programa_por_codigo(codigo, user=None)` con clave derivada e `invalidar_programa(codigo)` usada por los
  dos seeds (Becas ya falla cerrado con RED-56). Test `programas/tests/test_dispositivos_config.py::CacheProgramaTests.
  test_el_seed_invalida_las_dos_claves`.

**Resolución:** ✅ Resuelta en #646 (Cambio 193, Ola 2 PR 1), 08-oct-2026 —
`programas/services/programa_cache.py` es la pieza única: `clave_de(codigo)` (que **deriva** las dos claves históricas,
`programas:becas` y `programas:dispositivos`, así que una base con Redis vivo no pierde lo cacheado el día del deploy),
`programa_por_codigo(codigo, user=None)` con el memo por request —ahora un dict por código en vez de dos atributos— y
`invalidar_programa(codigo)` *best-effort*, con el mismo tratamiento del cache caído que tenía Becas (OPS-12: un Redis
inalcanzable no puede dejar el pod en CrashLoopBackOff). `programa_becas` e `invalidar_programa_becas` quedan como
fachadas, y `programa_dispositivos` también.
**Desvío de la ficha, code-first:** el test que pedía —«el seed invalida las dos claves»— no se puede escribir, porque
**no hay seed de Dispositivos**: `crear_programas` solo crea Becas y la fila `DISPOSITIVOS` se carga desde
Configuración. Así que la invalidación se enganchó donde un `Programa` **de verdad se escribe**, que es el wizard
(`programa_editar_paso4` y `programa_cambiar_estado`), y ahí está además el caso que la ficha no contemplaba: el paso 1
deja **cambiar el código**, así que se invalidan la clave vieja y la nueva. Eso cubre el escenario de la ficha mejor que
el seed: un restore que recrea la fila con otro pk sigue dependiendo del TTL de 300 s —nadie puede invalidar una clave
por un cambio hecho fuera de la aplicación—, pero todo cambio hecho **desde el producto** se invalida ya.
**Test permanente:** `programas.tests.test_programa_cache` (7).

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

**Resolución:** ✅ Resuelto en #604 (Cambio 156, PR R-16), 07-oct-2026 — `procesar_vencimientos` levanta `CommandError`
con el registro vacío (antes escribía un aviso y salía con éxito), y el chequeo va **antes** del filtro `--solo`, para
que el mensaje sea el que corresponde. El test que vale es
`RegistroTests.test_el_ready_de_la_app_es_el_que_las_registra`: vacía el registro, saca el módulo de reglas de
`sys.modules` **y del paquete que lo contiene** —`from X import Y` lo encuentra como atributo del paquete y no lo
volvería a ejecutar, así que sin esa segunda parte el test daría verde siempre— y vuelve a correr
`ProgramasConfig.ready()`. **Mutación de control:** borrar ese import deja el test en rojo.
**Un hallazgo que la ficha no tenía:** el comando hacía `from core.services.vencimientos import REGLAS`, y `registrar()`
**rebindea** la lista global; una regla registrada después de cargar el comando no la vería. Hoy no se manifiesta
—el comando se importa después de `django.setup()`—, pero es la misma fragilidad: ahora lee `registro.REGLAS` por el
módulo. **Riesgo de deploy anotado:** `procesar_vencimientos` corre en el bootstrap opcional del contenedor bajo
`set -eu`, así que con el registro vacío el contenedor no arranca. Es lo buscado, y que los opcionales no sean fatales
es **OPS-07** (Ola 3).
**Test permanente:** `programas.tests.test_becas_vencimientos.RegistroTests` (`test_las_reglas_estan_registradas_al_arrancar`,
`test_el_ready_de_la_app_es_el_que_las_registra` y `test_el_comando_corta_si_no_hay_ninguna_regla`).

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

**Resolución:** ✅ Resuelto en #607 (Cambio 159, PR R-21), 07-oct-2026 — **prerrequisito de SEC-20, cerrado antes
de su revisión.** `programas/services/exportacion_reportes.py` pasa de 122 CR y cero LF a 122 líneas LF, **sin un solo
cambio de contenido**: verificado normalizando el blob de `HEAD` (`git show HEAD:<archivo> | tr` de CR a LF), que da
idéntico al archivo nuevo. `git ls-files --eol` lo marcaba `i/-text` y ahora `i/lf`, así que el diff del PR de SEC-20
se va a poder leer. La guarda es doble: `core/tests/test_higiene_fuentes.py::EOLTests.test_ningun_py_con_cr_solitario`
recorre `git ls-files "*.py"` y exige que cada CR sea parte de un CRLF —tolera CRLF en el árbol de trabajo, que es lo
que deja un checkout de Windows, y no tolera el CR solitario, que git **no** normaliza—, y `.gitattributes` suma
`*.py text eol=lf` para que tampoco entre un `.py` con CRLF. Antes del cambio el test daba rojo nombrando el archivo;
hay además un control de andamio (`git ls-files` devuelve más de 100 `.py`) para que no pase por lista vacía.
**Test permanente:** `core.tests.test_higiene_fuentes.EOLTests.test_ningun_py_con_cr_solitario`.

## (e) Migraciones y rollback

Reproducido contra **MariaDB 11.8.9** (contenedores descartables de RS-R5 y VR2) y SQLite con datos. Hoy: el rollback
documentado deja la base peor que antes, la CI nunca migra hacia atrás ni sobre datos, y no hay artefacto inmutable al
que volver. El checklist por migración, el job de ida y vuelta, la regla expand/contract y el runbook de rollback están
en los **Anexos A-D** de este archivo.

### RED-14 · Un rollback de release con una columna `NOT NULL` nueva rompe el alta de casos
**Severidad:** ALTA (era CRÍTICA: el daño aparece al ejecutar un rollback, no hoy) · **Estado:** CONFIRMADO con test (`ERROR 1364 … Field 'dni_titular' doesn't have a default value` en MariaDB 11.8; VR2 contó 392 columnas `NOT NULL` sin default solo en `programas_*`) · **Origen:** RS-R5-01 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h)

**Resolución:** ✅ Resuelto en #591 (Cambio 135, PR R-12), 06-oct-2026 — `scripts/check_migraciones.py` recorre con `ast` las migraciones **agregadas** respecto de la base del PR (`git diff --diff-filter=A`) y falla ante las tres cosas que dejan la base en un estado que no corresponde a ninguna release: una columna nueva `NOT NULL` sin `DEFAULT` real en la base (regla `EXPAND`, con la salida `# ROLLBACK-OK:`, un `db_default=` o un `RunSQL … SET DEFAULT` que nombre la columna; `db_default` lo sumó el PR 3 de la Ola 1 —#590, Cambio 136— al encontrarse con que la forma correcta y corta de cumplir la regla daba hallazgo y empujaba a usar la marca de excepción, que dice lo contrario de lo que pasa), un `RemoveField`/`DeleteModel`/`RenameField`/`RenameModel` sin `# CONTRACT:` (regla `CONTRACT`, RED-19) y un `RunPython`/`RunSQL` sin reversa declarada o con reversa noop sin `# REVERSA-NOOP:` (regla `REVERSA`, RED-57). Corre como paso del job **`Migration Check`** de `pr-backend.yml`, que ya es obligatorio en el ruleset: **no se agregó un check nuevo**, y el motivo está escrito en el test —un `context` nuevo hay que sumarlo a mano al ruleset, que todavía no está aplicado (RED-20), así que sería un check que nadie exige; el paso es determinista y tarda menos de un segundo—. Tres desvíos de la propuesta, los tres code-first: (1) la regla `EXPAND` **no** mira `AlterField`, porque sin comparar contra el estado anterior no se puede distinguir «esta columna pasa a `NOT NULL` ahora» de un `AlterField` que solo cambia `choices` sobre una columna que ya era `NOT NULL` —la 0075 es exactamente ese caso— y el gate quedaría gritando siempre; (2) el piso del test de contrato es **por app** (`DESDE`) y apunta a `programas.0074` para que la 0075 de la Ola 1 entre en el conjunto medido; (3) el modo `--todas` existe solo como diagnóstico: hoy da 119 hallazgos históricos (73 `EXPAND` + 46 `CONTRACT`), que son migraciones ya aplicadas en producción y no se reescriben. **Test permanente:** `programas.tests.test_contrato_migraciones.MigracionesDelRepoTests.test_columnas_nuevas_toleran_codigo_viejo` (y `MotorDeReglasTests`, 17 casos sintéticos, más `GateDeLineaDeComandosTests`; `core.tests.test_gates_ci.ContratoDeMigracionesTests` fija que el paso corra en un job obligatorio). El paso D.2.0 del runbook ya estaba, de RED-60 (Cambio 117). **Dos agujeros que quedan abiertos y los tapa R-13**, porque son de ejecución y no de lectura del archivo: (a) un `AlterField` que pasa una columna de `null=True` a `null=False` no lo ve el gate, y rompe el alta igual que un `AddField`; (b) el gate mira solo las migraciones **agregadas** (`--diff-filter=A`), así que **editar una migración ya aplicada no tiene guard automático** —el forward de las existentes hay que compararlo contra la base, con `sqlmigrate` o con el roundtrip del Anexo B—. **Los dos los cerró el PR R-13** (Cambio 139, RED-17): (a) `manage.py verificar_columnas_obligatorias`, que compara `information_schema.COLUMNS` antes y después de las migraciones del PR contra el motor real —así se ve el `AlterField` sin el falso positivo que lo dejó afuera de acá—, y (b) `scripts/check_sqlmigrate.py`, que compara el `sqlmigrate` de cada migración **editada** entre el árbol del PR y el de la base. El gate estático no cambia: sigue siendo el que corre en menos de un segundo dentro de un job obligatorio.
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

**Resolución:** 🟡 La mitad nuestra, resuelta en el PR R-15 (Cambio 153), 06-oct-2026 — `publish-main.yml` etiqueta cada
release con `release-AAAA.MM.DD-<short>` (tag **anotado**, `$short` el de `development`, que es el commit que alguien
reconoce) sobre el commit de `main`, **después** del push y solo cuando hubo release nueva: el paso ya corta con
`exit 0` cuando «main al día». Se empuja `refs/tags/$tag` y no `--tags`, que arrastraría cualquier otro tag del runner,
y un tag repetido sale por `::warning::` en vez de dejar la publicación en rojo. **No hace falta permiso nuevo:**
`contents: write` ya estaba por el push de `main`. El runbook D.2.2 pasa a buscar «la release anterior» con
`git tag --list 'release-*' --sort=-creatordate` y la checklist pre-deploy pide anotarla. **Queda pendiente, y es de
ellos (D-RED-02, H-12):** el tag inmutable de **imagen** en el `.gitlab-ci.yml` de ECOM, redactado en
`docs/internal/propuesta-ecom-verify.md` §2, que es lo que convierte el rollback de PRD en segundos. Sin eso, el tag
nuestro da el SHA exacto para reconstruir, no la imagen para volver. **Test permanente:**
`core.tests.test_publish_guard.TagDeReleaseTests` (7 casos).

### RED-17 · Ninguna migración se prueba hacia atrás ni sobre datos; los tests de migración usan los modelos de hoy
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (ida y vuelta ejercida a mano: OK en SQLite, rota en MariaDB) · **Origen:** RS-R5-04 (VR2: CONFIRMADO), RS-R2-07 parte «modelos históricos» (VR1; el punto 1 amplía TST-01), RS-R5-11 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** M (8 h) + S (2 h) · **Decisión:** D-RED-03

**Resolución:** ✅ Resuelto en #596 (Cambio 139, PR R-13), 06-oct-2026 — el job **`Migrate ida y vuelta (<motor>)`** de `pr-performance.yml` corre, contra `mariadb:10.11` (con `MARIADB_INITDB_SKIP_TZINFO=1`, como `Motor real`) y `mysql:8.0`, la secuencia entera que la ficha pedía: ida hasta la base del PR **con el código de la base** (worktree), `seed_perf --scale 200` también con el código de la base, ida del PR **sobre esas filas**, vuelta app por app hasta la base, ida de nuevo y `migrate --check`. Lo orquesta `scripts/roundtrip_migraciones.py`, que **espera** el `IrreversibleError` de las ocho barreras de reversa (nota del Cambio 135 al Anexo B) en vez de tomarlo por rojo. Cierra además los **dos agujeros** que el Cambio 135 dejó anotados para este PR: (a) `core/management/commands/verificar_columnas_obligatorias.py` saca una foto de `information_schema.COLUMNS` antes y después, así que una columna que pasa a `NOT NULL` por `AlterField` —o que pierde su `DEFAULT`— se ve igual que un `AddField`, sin el falso positivo que obligó a dejar `AlterField` afuera del gate estático; (b) `scripts/check_sqlmigrate.py` compara el `sqlmigrate` de cada migración que el PR **edita** entre los dos árboles y falla si el SQL de ida cambió —editarlas se puede (el Cambio 135 editó diecinueve), reescribir su ida no—.

Cinco desvíos, los cinco code-first y medidos: (1) **«la release anterior» es la base del PR**, no un tag (RED-16 no existe todavía): es la misma referencia que usa `check_migraciones.py`, así que los dos gates miden el mismo conjunto; (2) **dos motores y no tres**: `mariadb:11` no corre en ningún ambiente y `Motor real` ya lo cubre hacia adelante; el roundtrip es el job más caro. **Medido en el CI de este PR: 1 m 36 s (MariaDB) y 1 m 51 s (MySQL)**, con el `migrate` desde cero en ~20 s y la semilla en ~17 s; en la máquina del implementador (Windows + Docker Desktop, que penaliza cada ida y vuelta al contenedor) eran 2 m 30 s y 10 min; (3) **sin `continue-on-error`**, al revés del Anexo B: las dos razones que lo pedían —RED-18 y las barreras sin declarar— las cerró el Cambio 135, y la propia nota del Anexo lo dice; (4) la base del job se llama **`chaco_perf_ci`** con `ENVIRONMENT=ci` y `PERFORMANCE_CI=1` (y un Redis), porque la guarda de `seed_perf` lo exige y hay que satisfacerla con el código **de la base**, que es el que siembra; (5) el `read_timeout` de 10 s de producción se sube con `.github/ci/settings_roundtrip.py`, **fuera de `config/`** para que el árbol de la base también lo encuentre por `PYTHONPATH` (desaparece cuando exista `DB_READ_TIMEOUT`, OPS-05). El paso final `verificar_esquema_migraciones` del Anexo no entra: ese comando es OPS-01 (PR R-15) y todavía no existe.

Del punto (2) de la propuesta —los tests de migración con el registro histórico— entran los **dos de `users`** (`core/tests/historico.py`); los dos de `programas` **no pueden**: la suite arma el esquema desde los modelos de hoy (`DJANGO_SYNCDB_PROJECT_APPS`), así que un `Programa` de la época de la `0012` escribe un `INSERT` sin `umbral_disponibilidad_verde`, que hoy es `NOT NULL`, y el test muere con un `IntegrityError` que es RED-14 visto desde adentro. Queda el motivo escrito en los dos archivos y, para todas las migraciones del repo, el chequeo sin base de que ninguna nombre un modelo que todavía no existía. **El job no es obligatorio todavía**, por el mismo motivo que `Motor real` (R-11): entra al ruleset cuando acumule corridas, y entonces se tocan `docs/internal/rulesets/ruleset-development.json` y `CHECKS_OBLIGATORIOS` en el mismo PR. **Test permanente:** `core.tests.test_roundtrip_migraciones` (`OrquestadorTests`, `JobDeRoundtripTests`), `core.tests.test_columnas_obligatorias`, `core.tests.test_check_sqlmigrate` y `core.tests.test_migraciones_estado_historico.EstadoHistoricoTests.test_ninguna_migracion_usa_un_modelo_que_todavia_no_existia`.
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

**Resolución:** ✅ Resuelto en #591 (Cambio 135, PR R-12), 06-oct-2026 — las reversas de `programas.0047`, `programas.0048` y `legajos.0007` normalizan a hex **siempre**, con el patrón y el comentario de la 0073. **Desvío (ampliación):** la ficha nombra tres, pero `users.0023` —escrita después, con el mismo `if has_native_uuid_field` en la reversa y sobre una columna `NOT NULL` y única— tiene el defecto idéntico, así que entró en el mismo arreglo: son cuatro. Verificado contra el motor de verdad: con `mysql:8.0.46` (donde `has_native_uuid_field` es falso, que es el caso que la ficha describe: base restaurada desde MariaDB) la reversa vieja muere con `(1265, "Data truncated for column 'token' at row 1")` y la nueva pasa; en `mariadb:10.11.19` el `migrate` completo hacia adelante sigue en verde. **Test permanente:** `programas.tests.test_migraciones_uuid.ReversaUuidTests.test_reversa_uuid_normaliza_antes_de_achicar` (orden del SQL de las cinco, con y sin UUID nativo, sin abrir conexión) y `users.tests.test_migracion_uuid_motor_real.ReversaUuidMotorRealTests.test_la_reversa_achica_sin_truncar_el_token` (`@tag("mysql")`, lo corre el job «Motor real» de R-11 contra los tres motores).
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

**Resolución:** ✅ Resuelto en #596 (Cambio 139, PR R-13), 06-oct-2026 — **(1) un solo migrador:** `docker/k8s/bootstrap-initcontainer.yaml` le pone `RUN_MIGRATIONS=false` al contenedor `web` y `docker/k8s/README.md` reemplaza «sin `command`/`args` en el pod (recomendado)» por una tabla de tres filas que dice cuándo vale cada forma; con `replicas > 1` la única válida es el **Job** nuevo `docker/k8s/bootstrap-job.yaml`, que corre una vez antes del rollout (`kubectl wait --for=condition=complete`, y si falla el rollout no se hace). **Desvío de la propuesta:** la ficha ofrecía «Job **o** initContainer» como equivalentes, y no lo son — un initContainer corre en **cada** pod, así que con varias réplicas sigue habiendo N migradores; queda escrito en las dos plantillas. **(2) expand/contract:** la regla está en `CLAUDE.md` (§Convenciones) con la clase que faltaba nombrada —un `AlterField` que pone `NOT NULL` o saca el `DEFAULT` es *contract*— y en `docker/k8s/README.md`; el gate `# CONTRACT:` ya lo exigía `scripts/check_migraciones.py` desde el Cambio 135 y ahora el job `Migrate ida y vuelta` mide el `AlterField` contra el esquema real. **(3)** el candado `GET_LOCK` sigue en OPS-07, como dice la ficha. **Pendiente operativo:** `.claude/agents/chaco-dev-reviewer.md` —el otro lugar que la propuesta nombra— no se pudo escribir desde la sesión del implementador; el bloque completo va en el cuerpo del PR y como archivo **sin trackear** en `docs/internal/bloque-chaco-dev-reviewer-r13.md`, para que lo aplique el juez y después lo borre. El bloque incluye la tabla de qué caso ve cada herramienta y cuáles **no ve ninguna** —`RemoveIndex` de un índice en uso, el `ALTER` sobre tabla grande, los lotes de pk, la idempotencia de las `atomic = False` y el cuerpo de un `RunPython` ya aplicado—, que son los que quedan en manos del revisor. Pedirle el manifiesto a ECOM (H-05) sigue siendo del PM. **Test permanente:** `core.tests.test_un_solo_migrador` (`UnSoloMigradorTests`, `ReglaExpandContractTests`).
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

**Resolución:** ✅ Resuelto en #591 (Cambio 135, PR R-12), 06-oct-2026 — cada reversa que no deshace nada declara arriba `# REVERSA-NOOP: <qué dato queda inconsistente al revertir>`, y `programas.0032`, `0056` y `0069` suman la barrera que faltaba: el bloque `# BARRERA-DE-REVERSA:` y la operación `RunPython(sin_cambios, bloquear_reversa)` al final de `operations`, igual que las cinco de UUID del Cambio 117. **Desvío (medición):** son **16 archivos y 17 operaciones**, no 15: el barrido encontró además `programas.0063`, cuya reversa es una función con solo docstring (el mismo patrón de `users/0007`, que VR2 sí había visto). Por eso el gate reconoce como noop tanto `RunPython.noop` como una función del archivo cuyo cuerpo es solo docstring o `pass`. **Segundo desvío (alcance de la barrera):** las tres barreras de datos abortan en **todos los motores**, no solo en MySQL/MariaDB como las de UUID —lo que se pierde son filas y columnas, y eso no depende del motor—; y `programas.0045` quedó **sin** barrera, con su pérdida nombrada en la marca: la ficha lo clasificó como «noop sin pérdida de esquema» pero sus `RemoveField` borran la foto congelada de SIIS del segmento, así que es la misma familia. No se le puso barrera porque está por debajo de `programas.0047`, que ya aborta antes en el plan de reversa, y porque la lista de ocho del runbook es la que decidió el PM (D-RED-05). Verificado contra `mariadb:10.11.19`: `migrate programas 0031` (desde 0032), `0055` (desde 0056) y `0068` (desde 0069) abortan con el mensaje de su barrera **sin tocar el esquema** ni `django_migrations`. **Test permanente:** `programas.tests.test_contrato_migraciones.MigracionesDelRepoTests.test_todas_las_migraciones_son_reversibles_o_lo_declaran` (repo entero, sin piso) y `core.tests.test_barreras_de_reversa.BarrerasDeReversaTests` (ahora 8 barreras, con `test_las_barreras_por_perdida_de_datos_bloquean_en_cualquier_motor`).
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

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — la plantilla es `core/migraciones.py`:
`nombre_de_fk` y `quitar_fk_si_existe` (por `KEY_COLUMN_USAGE`), `crear_fk_si_falta`, `tipo_de_columna` y
`modificar_columna` (por `COLUMNS`). El camino de **ida** de `legajos.0007` se reescribió sobre esos helpers y la regla
quedó en `CLAUDE.md` (§Convenciones), como el ítem 6 del Anexo A pedía. **Tres cosas que la ficha no decía:**
(1) la mejora no es solo «no explota el reintento»: si **ninguna** de las cuatro columnas está pendiente, la migración
ya **no baja las dos FK** —bajarlas y recrearlas por las dudas es trabajo caro sobre tablas en uso y deja la integridad
referencial abierta un rato por nada—, así que una segunda corrida completa manda **cero** `ALTER`; (2) la
normalización de los UUID corre aunque no haya hecho falta ningún `MODIFY`, porque un corte entre el `ALTER` y el
`UPDATE` deja filas a medias y es justo lo que hay que terminar (su `WHERE CHAR_LENGTH(…)` ya la hacía idempotente);
(3) la **reversa** se dejó como estaba, a propósito: está bloqueada por la barrera de RED-15 —el camino de vuelta es un
restore, no un reintento— y `programas/tests/test_migraciones_uuid.py` fija el orden del SQL que emite. Editar una
migración ya aplicada es legítimo acá: `scripts/check_sqlmigrate.py` compara el SQL de **ida** y un `RunPython` sale
como comentario, y el estado final es idéntico (verificado migrando desde base vacía contra `mariadb:10.11`).
**Verificación contra el motor real**, no sobre el banco de `scripts/perf_mysql/` (no agregaba nada: lo que se mide es
esquema, no volumen): sobre `mariadb:10.11` sin tzinfo y con las `OPTIONS` de prod se reprodujo el `ERROR 1091` del
segundo `DROP FOREIGN KEY`, y después, con la FK caída —el estado exacto que deja el corte—, dos corridas seguidas de
la función de ida dejaron las cuatro columnas en `char(36)` y las dos FK puestas, la segunda sin emitir un solo
`ALTER`. **Test permanente:** `core.tests.test_motor_real.MigracionReentranteTests.test_ampliar_uuid_es_idempotente`
(`@tag("mysql")`, dos llamadas seguidas) y `legajos.tests.test_migracion_uuid` (`AmpliarUuidReentranteTests`,
`PlantillaReentranteTests`), que corre en todos los PRs contra un `schema_editor` que simula `information_schema`.

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

**Resolución:** ✅ Resuelto en el PR R-15 (Cambio 153), 06-oct-2026 — los tres puntos. (1) `HEALTH_URL` por defecto pasa
a `http://localhost/health/ready/` (OPS-04), así que el criterio de éxito y el del rollback distinguen «vivo» de
«sirve»; (2) `post_deploy_checks()` corre después del health y antes de declarar éxito: `migrate --check`, el manifest
de `staticfiles.json` con más de `MANIFEST_MINIMO` (50) entradas —el archivo vacío existe igual y deja cada
`{% static %}` en 500— y `GET /login/` = 200; (3) `git checkout --force` pasa a
`git switch --force-create "rollback/$TIMESTAMP"`. Y el cuarto, que es el que más importa: el script toma la cuenta de
migraciones aplicadas **antes** de recrear los servicios, con el contenedor viejo todavía arriba, y si el deploy aplicó
alguna **aborta el rollback automático** nombrando el runbook y el commit anterior, porque volver solo el código deja el
esquema adelantado (RED-14). Si **no puede averiguarlo** —el contenedor no responde, que es justo lo que pasa con `web` en crash-loop— el rollback automático **tampoco procede**: lo pidió la revisión del PR, y con razón, porque la versión anterior leía el `0` que imprime `grep -c … || true` cuando el `exec` falla y lo tomaba por «el deploy no migró nada». Ahora `migraciones_aplicadas()` separa el exit del `exec` de la cuenta, y el caso sin lectura exige `ROLLBACK_SIN_COMPARAR=1`, que es una persona diciendo que ya verificó que no hubo migraciones. **Dos desvíos code-first:** la ficha
dice `GET /accounts/login/`, pero esa ruta no existe —el login del backoffice está en `/` y `/login/`
(`users/urls.py:24-25`)—, y `showmigrations --plan` se compara por cantidad de `[X]` antes y después, que es lo que se
puede medir desde el host sin parsear el plan entero. **Test permanente:** `core.tests.test_scripts_deploy.DeployProdTests`
(11 casos, incluidos `test_no_usa_checkout_force_ni_health_desnudo` y `test_deploy_prod_usa_ready`).

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

**Resolución:** ✅ Parte R resuelta en #591 (Cambio 135, PR R-12), 06-oct-2026; la migración sigue siendo de la Ola 4. `core/tests/test_indices_redundantes.py` recorre los modelos de las **siete apps del proyecto** (no solo `programas` y `legajos`) y marca todo índice declarado que sea prefijo exacto de otro del mismo modelo, mirando `db_index=True`, `unique=True`, `Meta.indexes`, `Meta.constraints` y `Meta.unique_together`. Los índices que Django crea solo por ser FK quedan afuera a propósito: son parte de la foreign key, no una decisión del modelo. **Desvío (medición):** el ratchet nace con **26** pares, no con 5. Los 5 de la ficha son los que la auditoría midió contra `information_schema`, pero miró solo `programas_formulario` y `legajos_ciudadano`; los otros 21 son el mismo defecto en tablas chicas (`conversaciones_conversacion` sola tiene 6). Están marcados en la lista: los cinco medidos llevan `# RED-83`. La lista **solo baja**, y hay un test que falla si queda una fila muerta, para que sacar un par obligue a sacarlo también de acá. **Test permanente:** `core.tests.test_indices_redundantes.IndicesRedundantesTests.test_no_hay_indices_prefijo_de_otro` (más `test_la_regla_detecta_un_prefijo_plantado`, que es el que impide que el ratchet se quede verde por un detector roto).
- **Ubicación:** `programas/models/__init__.py:2484-2490` (`estado` con `db_index=True`) vs `:2631`
  (`Index(fields=["estado"])`); `legajos/models/base.py:23` vs `:194` (`dni`, ya `unique`), `:29` vs `:202` (`email`),
  `:25` vs `:195` (`apellido`, cubierto por `apellido,nombre`), `:43` vs `:201` (`activo`, cubierto por
  `legajos_ciu_listado_idx`).
- **Propuesta:** **R:** `core/tests/test_indices_redundantes.py::test_no_hay_indices_prefijo_de_otro` (recorre los modelos
  de `programas` y `legajos`; falla si un `Index`/`db_index`/`unique` es prefijo exacto de otro del mismo modelo, con
  `REDUNDANTES_CONOCIDOS` = los 5 pares; la lista solo baja). **Ola 4:** `AlterField` (sin `db_index`) + `RemoveIndex`
  por par (`DROP INDEX` secundario es `INPLACE`/`LOCK=NONE`).

**Resolución:** ✅ (segunda parte, la migración) Resuelta en #648 (Cambio 194, Ola 4 PR 9), 08-10-2026 —
`legajos.0011_indices_redundantes_red83` y `programas.0085_indices_redundantes_red83` sacan los **cinco** pares
medidos, con la forma que pedía la ficha: `RemoveIndex` para los dos duplicados declarados en `Meta.indexes`
(`dni`, `email`) y `AlterField` sin `db_index` para los dos de columna (`activo`, `apellido`), más el `RemoveIndex` de
`estado` en `Formulario`. El ratchet baja de **26** a **21**; los que quedan son el mismo defecto en tablas chicas,
sin medir. **Verificado contra el banco MariaDB 10.11** (`scripts/perf_mysql`, 21.522 ciudadanos y una
`programas_formulario` de **362 MB**), que es lo que la ficha no pedía y el PR sí exigió: los cinco pares confirmados
en `information_schema.STATISTICS` y `EXPLAIN` de ocho consultas calientes **antes y después**. Siete dan el plan
idéntico —el listado de ciudadanos ya elegía `legajos_ciu_listado_idx` y no `activo`; el lookup por documento ya era
`const` por el UNIQUE; el de email y el conteo por estado ya usaban el superviviente; la bandeja por estado usa
`prog_formulario_creado_idx`—. La única que elegía un índice que se va es la **búsqueda por apellido**, y después del
`DROP` resuelve con el compuesto `(apellido, nombre)` con el mismo `type=range`, el mismo `key_len=482` y las mismas
filas estimadas: el prefijo izquierdo sirve el mismo rango. Ninguno estaba en uso exclusivo.
**Tres cosas medidas que la ficha no tenía:** (a) el costo real del DDL —31 + 31 + 27 + 32 ms en `legajos_ciudadano` y
**29 ms** en los 362 MB de `programas_formulario`, contra el `read_timeout` de 10 s de ECOM—; (b) el ciclo
**ida → vuelta → ida** corrido sobre los datos sembrados, las tres en verde, así que la reversa (que vuelve a crear
los cinco índices) está probada y no solo declarada; (c) ninguno de los cinco es el índice implícito de una FK, así
que no hay riesgo de `ERROR 1553`. No lleva marca `# CONTRACT:` y no es un descuido: durante el rolling la release
vieja no nombra índices —los elige el optimizador—, así que no hay código viejo que esto pueda romper, y
`check_migraciones.py` tampoco la pide.
**Test permanente:** `core.tests.test_indices_redundantes.IndicesRedundantesTests.test_la_lista_conocida_no_tiene_entradas_muertas`
(el que exige que los cinco pares hayan desaparecido de verdad de los modelos, junto con
`.test_no_hay_indices_prefijo_de_otro`).

### RED-84 · `requerimientos.py --check` no verifica la sección «Reversión»
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R5-13 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #591 (Cambio 135, PR R-12), 06-oct-2026 — `comando_check` suma `problemas_de_reversion`: para toda entrada desde el **Cambio 135** (`PRIMER_CAMBIO_CON_REVERSION`, el piso que deja el histórico como está) cuya fila `**Migración**` no diga «no requiere»/«no aplica», exige que `## Base de datos` nombre la migración declarada y que `## Reversión` tenga más de una línea con contenido. Una entrada desde el piso sin la fila `**Migración**` de la plantilla también cae. El `--check` es gate del CI desde RED-24 (job «Contratos del repo»), así que esto se vuelve bloqueante sin tocar ningún workflow. **Test permanente:** `core.tests.test_requerimientos_check.ReversionEnElCheckTests` (7 casos sobre documentos sintéticos: con reversión completa, vacía, de una sola línea, sin la migración en «Base de datos», sin migración, por debajo del piso y sin las secciones) y `ArchivoRealTests`, que corre el `--check` sobre el archivo del repo.
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

**Resolución:** 🟡 Parcial en #547 (Cambio 116, PR R-01), 04-oct-2026 — **la parte de código está hecha; el repo privado y la purga del historial los ejecuta el PM (D-RED-01)**. Hecho, en el orden de la propuesta: (1) los tres volcados salieron de `HEAD` con `git rm --cached` —quedan en el disco de quien los tenga, borrarlos de ahí no es parte de esto— y las **cuatro barreras** que impiden que vuelvan: `scripts/*.sql` en `.gitignore`, en `.dockerignore` (corta el `COPY . .` del `Dockerfile`) y como `export-ignore` en `.gitattributes` (corta el release de `main` y el espejo de ECOM), con `scripts/aprobados_materias_plantilla.sql` exceptuada explícitamente en las tres, porque es el molde que el operador necesita leer. `Localidades.sql` también salió: se verificó su cabecera y es un padrón indexado por DNI, no un nomenclador —el nomenclador es `core/fixtures/localidad_municipio_provincia.json`, que se queda—. (2) `DATOS_SIIS_DIR` (default `/datos-siis`) como fuente de los insumos, desde `programas/management/commands/_insumos_siis.py`, con `CommandError` que nombra la variable si el directorio no está montado —el modo de falla que importa es el pod sin el volumen, y saltearlo en silencio terminaba en «la tabla no existe» tres pasos después— y `scripts/README-datos-siis.md` versionado sin un solo dato. (4) el gate: **una sola** heurística de «esto es un volcado» en `scripts/check_datos_personales.py`, con tres reglas y techo de 512 KB, que usan el job `Sin datos personales` de `pr-datos.yml` (en PR **y en push** a `development`) y los **dos** pases de `publish-main.yml`, uno sobre los archivos versionados —antes de que `git archive` aplique el `export-ignore`— y otro sobre el árbol del release. Nunca imprime el contenido: solo ruta, tamaño y cantidad de filas. **Tres desvíos de la ficha, los tres por rondas de revisión y declarados en el Cambio 116:** una heurística en Python en lugar de las dos que proponía la ficha (una en el YAML, otra en el test), que se separan en el primer ajuste y marcan en rojo la plantilla sin datos; la detección del `mysqldump` **real** —sin lista de columnas y con todas las tuplas en una sola línea por `--extended-insert`—, que la propuesta no veía y por la que un volcado sintético de 5.000 personas pasaba los tres modos; y exenciones del techo por **ruta exacta** en vez de glob, porque `core/fixtures/*` era el escondite obvio del próximo volcado (un `padron.json` de 1,8 MB pasaba). Verificado que rechaza de verdad: los dos casos plantados en el árbol del release salieron con exit 1. **Test permanente:** `core.tests.test_release_sin_datos.ReleaseSinDatosTests.test_ningun_sql_versionado_tiene_volcado_de_personas` (14 tests en el módulo; daban 11 fallos y 1 error sobre `HEAD`) y `programas.tests.test_correr_alta_siis.InsumosDesdeDatosSiisDirTests`. **Queda operativo (PM, D-RED-01), en este orden:** repo a **privado**; avisar a ECOM **antes** de purgar, porque la purga reescribe `main` y su pipeline despliega PRD; `git filter-repo --invert-paths` de los tres archivos y force push de ramas y tags; pedido a GitHub Support por las referencias de PR y las vistas cacheadas; barrido con `gitleaks`/`trufflehog` sobre el historial completo; imagen de PRD reconstruida. **Y antes de la próxima corrida de alta SIIS:** montar `DATOS_SIIS_DIR` en icore y en ECOM. **Agujero conocido que sigue abierto:** un volcado chico en un formato que las tres reglas no reconocen (JSON, Parquet, un export binario); lo que lo ataja es el techo de 512 KB.
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

**Resolución:** 🟡 Parcial en #554 (Cambio 121, PR R-03), 04-oct-2026 — el repositorio quedó listo y **falta el paso del dueño del repo**. Hecho: los dos rulesets versionados como JSON en `docs/internal/rulesets/` (`ruleset-development.json` y `ruleset-main.json`) con el procedimiento, la verificación y el modo `evaluate` de emergencia en `docs/internal/rulesets.md`; los puntos 3, 4 y 5 completos. Punto 3: `pr-quality.yml` y `design-agent-contract.yml` perdieron el `paths:` del trigger y el filtro pasó adentro del job con `dorny/paths-filter@0e4a8c6` (v3.0.4, pineada: RED-85), con `pull-requests: read` y `tailwind.config.js`/`package*.json` sumados al filtro de diseño. Punto 4: `push: development` en `pr-backend.yml` y `pr-performance.yml` (`pr-datos.yml` ya lo tenía, Cambio 116). Punto 5: §«Gates de CI» de `CLAUDE.md` reescrita, con los nombres exactos de los checks y la aclaración de que hoy el merge no los exige. Verificado el 04-oct antes de empezar que `rulesets` sigue en `[]` y `branches/development/protection` en 404. **Dos desvíos declarados:** (a) la lista de obligatorios suma `Sin datos personales` (existe desde el Cambio 116) y `Validate inventory and authority` —el punto 3 de esta misma ficha justifica hacer obligatorio el contrato de diseño, y `CLAUDE.md` ya lo describía así—, o sea nueve contextos en vez de los seis literales; (b) `actor_id: 15368` verificado contra `/apps/github-actions` en vez de tomarlo de la ficha. **Test permanente:** `core.tests.test_gates_ci.RulesetsPropuestosTests` (10 tests, incluido el que afirma que todo `context` del JSON existe como job y que su workflow no filtra por `paths`) y `core.tests.test_gates_ci.PushDirectoADevelopmentTests`. **Queda operativo (PM / dueño del repo):** los dos `gh api … /rulesets -X POST --input …`, preferentemente después de mergear los PRs de la Ola R ya abiertos.
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

**Resolución:** ✅ Resuelto en #575 (Cambio 128, PR R-14), 05-oct-2026, con los dos puntos. **(1)** El denylist salió del
YAML: el guard recorre **el árbol del release** con `find -printf '%P\n'` y le pregunta a `git check-attr --stdin
export-ignore`, que es exactamente lo que aplicó el `git archive` de arriba. **Desvío medido respecto de la propuesta:**
la ficha decía derivarlo de `git ls-files`, y eso deja afuera los patrones de directorio —en `.gitattributes`, `/docs`
marca el directorio y **no** sus archivos: `check-attr docs/internal/x.md` contesta «unspecified»—, o sea 5 de los 17
patrones (`.claude`, `.amazonq`, `.github`, `docs`, `scripts/perf_mysql`). Recorriendo el release, el directorio aparece
como ruta propia y la pregunta da «set». Verificado contra un `git archive` real con un `docs/internal/x.md` y un
`NOTAS.md` inyectados a mano: los dos salen marcados. Además, todo `.md` de la raíz que viaje al release tiene que estar
en `DOCS_DE_RUNTIME` (hoy solo `README.md`) o marcado: `CONTEXT.md` —17 KB de documentación interna que viajaban a ECOM y
a la imagen de PRD— quedó con `export-ignore`. **(2)** El paso «Exigir que el commit venga de un PR con CI verde» busca
el PR del commit publicado (`commits/<sha>/pulls`, solo `merged_at != null`) y mira los check-runs **del head de ese
PR**, con `pull-requests: read` y `checks: read`; un `conclusion` en `null` (corriendo) también frena. **Segundo desvío:**
el snippet de la ficha usaba `[ cond ] && { …; exit 1; }`, que con el `set -e` de Actions aborta el paso cuando la
condición es **falsa** —el camino feliz—; va con `if … then … fi`, y hay un test que lo fija. `workflow_dispatch` saltea
el gate (es una persona con permiso de escritura decidiendo) pero ahora exige un `motivo` obligatorio que queda en el
log. No se autobloquea con el ruleset de `main`: ese ruleset no exige status checks, y `test_el_ruleset_de_main_no_exige_status_checks` lo custodia.
**Test permanente:** `core/tests/test_publish_guard.py::CIVerdeAntesDelReleaseTests.test_el_gate_mira_el_head_del_pr_y_no_el_commit_de_merge`
y `::DenylistDerivadoTests.test_ningun_md_de_la_raiz_viaja_al_release_sin_decidirlo`.

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

**Resolución:** 🟡 Parcial en #575 (Cambio 128, PR R-14), 05-oct-2026 — **lo nuestro está hecho y falta el paso del PM**.
La propuesta está escrita y lista para enviar en [`docs/internal/propuesta-ecom-verify.md`](../../propuesta-ecom-verify.md):
la etapa `verify` completa (imagen `python:3.12-slim`, las tres dependencias de sistema, `pip install -r
requirements.txt`, `check --deploy` + `makemigrations --check --dry-run` + `test`, misma regla `test || main`), por qué no
necesita base —`PYTEST_RUNNING=1` y `DJANGO_SYNCDB_PROJECT_APPS=True`—, el aviso de que `SIIS_API_URL` tiene que estar
definida aunque sea ficticia (Cambio 123, si no `check --deploy` falla), el tag inmutable `:${CI_COMMIT_SHORT_SHA}` de
RED-16 y el pedido del dump previo (H-11). **No se tocó `.gitlab-ci.yml`**: es de ECOM, nuestra copia tiene que quedar
byte a byte igual y editarla les revertiría el archivo en el próximo espejo; hay un test que lo fija. Mientras no lo
acepten, el equivalente de nuestro lado es el `release-gate.yml` de RED-23.
**Queda operativo (PM):** enviarla y traer la respuesta de H-12.
**Test permanente:** `core/tests/test_gates_ci.py::PropuestaAEcomTests.test_nuestra_copia_del_pipeline_sigue_intacta`

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

**Resolución:** 🟡 Parcial en #575 (Cambio 128, PR R-14), 05-oct-2026 — **los puntos 1 y 2 completos; del 3 falta que el
juez copie los tres archivos a `.claude/`** (la sesión que implementó esto no tiene permiso de escritura ahí; quedan
completos en `docs/internal/espejo-ecom-comandos/` del worktree, sin trackear, y en el cuerpo del PR). Punto 2: `.github/workflows/release-gate.yml`, `workflow_dispatch`
con input `sha` obligatorio y cuatro jobs — (a) `CI verde del PR de origen`, que deriva el commit de `development` del
asunto `release: … (development@<sha>)`, busca su PR y mira los checks **del head**; (b) `Suite completa (SQLite)`;
(c) `Migraciones sobre MariaDB` (`mariadb:10.11` hasta H-01) con `migrate --noinput`, `migrate --check` y
`makemigrations --check --dry-run`; (d)+(e) `Imagen y smoke HTTP`, con `docker build`, `collectstatic` adentro de la
imagen exigiendo `staticfiles/staticfiles.json`, y la imagen levantada contra MariaDB. **Tres desvíos declarados:**
(i) el smoke pega a `/health/`, `/login/`, `/inicio/` y `/becas/relevamientos/`, no a `/accounts/login/` y `/becas/` como
decía la ficha: medido contra el URLconf, `/accounts/login/` no existe (el login vive en la raíz, `users:login`, con
alias en `/login/`) y `/becas/` a secas **no resuelve**, así que ese smoke habría medido un 404 creyendo que medía la
pantalla; hay un test que resuelve cada ruta del workflow contra el URLconf. (ii) un 404 cuenta como fallo, no solo el
500. (iii) la suite (b) corre sobre el commit de `development`, no sobre el snapshot: el snapshot excluye `docs/`,
`.github/` y tres `scripts/*.py` por `export-ignore`, y **seis módulos de test** afirman cosas sobre exactamente esos
archivos, así que correrla sobre el árbol publicado daría rojo por construcción; el código de producción es el mismo en
los dos árboles. Punto 1 y 3: el procedimiento normativo quedó versionado en
[`docs/internal/espejo-ecom.md`](../../espejo-ecom.md) —partido en `/pushGitLabecomTEST` y `/pushGitLabecomPRD`, con el
árbol de `ecom/test` comparado por `^{tree}`, el `release-gate` verde exigido para ese SHA y la segunda confirmación
escribiendo `PRODUCCION`— y es lo que los dos comandos ejecutan.
**Test permanente:** `core/tests/test_gates_ci.py::ReleaseGateTests.test_el_smoke_pega_a_rutas_que_existen_de_verdad` y
`::EspejoEnDosPasosTests.test_el_paso_a_produccion_exige_lo_verificado_en_testing`

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

**Resolución:** ✅ Resuelto en #575 (Cambio 128, PR R-14), 05-oct-2026, con los cinco puntos. Job `contratos-repo` en
`pr-quality.yml`, nombre `Contratos del repo`, sin `continue-on-error`, `fetch-depth: 0`, Python 3.12 y
`pip install -r requirements.txt`: `compile_templates.py`, `requerimientos.py --check` (con `PYTHONIOENCODING=utf-8`),
`collectstatic --noinput` con `DJANGO_DEBUG=False` y `ENVIRONMENT=prd` —que es lo que enciende
`CompressedManifestStaticFilesStorage`, el que caza el «Missing staticfiles manifest entry»; verificado a mano que corre
sin base ni Redis y deja el manifest— fallando si no queda `staticfiles/staticfiles.json`, y el ratchet de `design_audit`
contra `.design-audit-ratchet` con el `|| true` que la ficha advierte. El aviso no bloqueante del título del PR quedó,
con `dorny/paths-filter` pineada. **Dos desvíos declarados:** (a) **el techo inicial del ratchet es 42, no 44**: medido
hoy sobre `fix/olaR-gates-release` con la corrida completa (`42 error(es), 28 warning(s)`); la ficha traía la medición de
RS-R6/VR2 sobre `ee0aafe`. (b) El job **no filtra por rutas**: casi cualquier archivo mueve alguna de las cuatro
comprobaciones y el check es obligatorio, así que tiene que terminar siempre. `Contratos del repo` se sumó a
`docs/internal/rulesets/ruleset-development.json` —diez contextos— como anticipaba RED-20.
**Test permanente:** `core/tests/test_gates_ci.py::ContratosDelRepoTests` (8 tests; uno corre `design_audit.py` de verdad
y afirma que la medición no supera el techo, y otro fija el formato de la línea de resumen, que es el contrato entre el
script y el job).

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

**Resolución:** ✅ Resuelto en el PR R-06 (Cambio 123), 04-oct-2026, con los tres puntos de la propuesta ajustada.
(1) `config/settings.py`: `os.getenv("SIIS_API_URL", "")`, y los dos `.env.*.example` explican de dónde sale el host y
que en PRD va el productivo. (2) `core/checks.py` nuevo, registrado en `CoreConfig.ready`, con
`@register(Tags.compatibility, deploy=True)`: `core.E001` si la variable está vacía con `DEBUG=False`, `core.E002` si
apunta a `*.ecomdev.ar` **y** `DATANACH_ES_PRODUCCION=1`, y `core.W001` si `RENAPER_TEST_MODE` sigue prendido sin
`DEBUG`. El host se compara por **dominio** (`hostname` del `urlparse`), no por substring: `siisapi.ecomdev.ar.atacante.com`
no es el SIIS de desarrollo, y la comparación no depende de mayúsculas. El job `Django check` de `pr-backend.yml` define
`SIIS_API_URL` con un host ficticio. (3) El proceso masivo muestra a qué host de SIIS va a escribir antes de lanzar, y
lo dice explícitamente si está vacía; `diagnosticar_siis` ya lo mostraba y su aviso pasó de `ENVIRONMENT == "prd"` —que
daba un falso positivo en QA e icore— al mismo `DATANACH_ES_PRODUCCION`.
`core/tests/test_checks_entorno.py` cubre los tres mensajes, los dos bordes del host, el silencio con `DEBUG=True` y que
el check esté registrado **solo** para `--deploy`. Verificado a mano: `check --deploy` sin la variable corta con
`core.E001`; con el host ficticio pasa.
**DECISIÓN CLIENTE (pendiente del PM, H-09):** confirmar con ECOM que PRD define `SIIS_API_URL` con el host productivo
y pedirles `DATANACH_ES_PRODUCCION=1` **solo en PRD**. Sin esa variable el chequeo de host nunca dispara; sin
`SIIS_API_URL` lo que queda rojo es el CI, no el deploy. Frenar el arranque exigiría llamar al check desde el
entrypoint: queda para R-15.
**Test permanente:** `core/tests/test_checks_entorno.py::ChecksDeEntornoTests.test_siis_de_desarrollo_en_produccion_es_error`

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

**Resolución:** ✅ Resuelta en #648 (Cambio 194, Ola 4 PR 9), 08-10-2026 — `scripts/check_perf_budgets.py` corre como
**primer** paso del job `Query Budgets & Smoke Time` (antes de medir: es barato, no necesita base y el mensaje es más
claro que el del presupuesto excedido), contra `github.event.pull_request.base.sha`, con `fetch-depth: 0` en el
checkout —sin eso, `git show <base>:…` no resuelve y el paso compararía contra nada— y con `HEAD^` de respaldo para el
disparo por `push`. `failure_multiplier` baja de `3.0` a `2.0`: con 3,0 la alarma recién saltaba a 4,3 s, casi el
triple de la referencia, y no había degradación capaz de encenderla (medido en este PR: 1.982 ms, ratio 1,38×).
**Tres desvíos, los tres hacia más estricto:** (1) la justificación no alcanza con ser una clave nueva, tiene que
**nombrar** el presupuesto que sube —con la regla original, una sola entrada tapaba cualquier cantidad de subidas en
el mismo PR, y la convención del archivo ya escribe el nombre de la ruta—, y una entrada vieja **ampliada** cuenta
igual que una nueva; (2) se miran también los `servicios` (`consultas_fijas` que sube, `casos_por_consulta` que
**baja**: las dos son «el servicio puede consultar más») y los dos multiplicadores de la alarma de tiempo, que son la
forma barata de correr el techo sin tocar la referencia —la puerta que quedaba abierta justo después de bajarlo—;
(3) bajar un techo y estrenar una ruta no piden nada, escrito como test, porque un gate que pide trámite en la
dirección buena genera justificaciones de trámite. Probado con las dos puntas que pedía el pedido: caso **rojo** —se
infla un techo del `perf_budgets.json` real sin tocar `adjustments` y el proceso sale con 1— y caso **verde** —el
archivo de este PR contra `origin/development`, salida 0—, más 16 casos sobre documentos sintéticos.
**Test permanente:** `core/tests/test_check_perf_budgets.py::CasoRojoTests.test_subir_max_queries_sin_justificacion_es_un_hallazgo`
(y `CasoVerdeTests` ×6, `ArchivoRealTests.test_inflar_un_presupuesto_del_repo_devuelve_1`,
`ElJobLoCorreTests.test_el_workflow_de_performance_corre_el_script_contra_la_base_del_pr`).

### RED-63 · Ruff y Bandit en `continue-on-error`; excepción de `pip-audit` sin vencimiento
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** RS-R6-12 (VR2: CONFIRMADO) · **Ola:** R · **Esfuerzo:** S (2 h)

**Resolución:** ✅ Resuelto en #554 (Cambio 121, PR R-03), 04-oct-2026 — `pr-quality.yml` pasa de `Ruff Lint`/`Ruff Format`/`Bandit` a `Ruff errores` (`ruff check . --select F --output-format=github`, **sin** `continue-on-error` y en la lista de obligatorios del ruleset), `Ruff estilo` (`E,W,I` más `ruff format --check`, no bloqueante; hoy da 0 y lo que falta para encenderlo es fijar la versión de Ruff, RED-85/Ola 7, porque se instala sin pin). Hay un detalle que la ficha no podía prever: un `--select` por línea de comandos **pisa también el `ignore` de `pyproject.toml`**, así que el job de estilo lleva `--ignore E501` explícito o reporta las 43 líneas largas que el repo ignora a propósito y `Bandit Security Scan` (no bloqueante, con versión fija `bandit[toml]==1.9.4`). Verificado antes de encenderlo, como pide la ficha: `ruff check . --select F` da **0 hallazgos** sobre el repo entero. Las excepciones de `pip-audit` salieron del YAML y viven en `security/excepciones.toml` con `{id, motivo, vence_el, ticket}`; `scripts/check_excepciones_seguridad.py` corre antes de auditar y emite las banderas `--ignore-vuln` desde el archivo (`read -r -a ignores <<< "$(… --ignore-args)"`). `PYSEC-2026-3447` resultó ser **setuptools 80.9.0** (CVE-2026-59890, corregido en 83.0.0), no DRF: quedó documentada con `vence_el = 2027-01-02` —90 días, default aplicado: la ficha no fijaba plazo— y ticket RED-85, que es donde se toca el pin. `vence_el` tiene que ser fecha TOML: escrita como texto no vencería nunca, y eso tiene su propia regla. **Test permanente:** `core.tests.test_gates_ci.RuffBloqueanteTests` y `core.tests.test_gates_ci.ExcepcionesDeSeguridadTests` (11 tests entre los dos; el de vencimiento es el que se pone rojo el día que la excepción caduca, en el PR y no en PRD).
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

**Resolución:** ✅ **La parte de la Ola R está hecha** en #575 (Cambio 128, PR R-14), 05-oct-2026; **la Ola 7 sigue
abierta** (sacar `docker/django/Dockerfile` y `scripts/startup.sh` de la lista, en el PR de OPS-10/OPS-14). El test está,
con el nombre exacto de la ficha: lee la variable `RUNTIME` del guard —que por eso pasó a ser una variable de shell en vez
de ir inline en el `for`— y afirma que cada ruta existe en el árbol. Lo acompañan tres más: que la lista no esté vacía
(vaciarla apagaría el guard dejando el módulo en verde), que ningún requerido esté marcado `export-ignore` (sería una
contradicción que rompe el release **siempre**, después del merge) y uno que prueba el centinela contra una lista con una
ruta inventada, para que no quede en verde por no mirar nada.
**Test permanente:** `core/tests/test_publish_guard.py::PublishGuardTests.test_los_requeridos_existen_en_el_arbol`

**Cerrada del todo** en el PR 1 de la Ola 7 (Cambio 195), 09-oct-2026 — `docker/django/Dockerfile` (OPS-14) y
`scripts/startup.sh` (OPS-10: arrancaba con `setup_system`) salieron del árbol y de la variable `RUNTIME` del guard en
el mismo diff, que es exactamente el modo de falla que la parte R anticipó. El piso de
`test_la_lista_de_runtime_no_esta_vacia` baja de 10 a 8, las ocho rutas que de verdad necesitan la imagen de PRD y el
pipeline de ECOM. Y se suma el **camino inverso**, que la ficha no pedía y es el que queda abierto después de esto:
sacar una ruta del guard **sin** borrar el archivo apagaría la red en silencio —el artefacto podría dejar de viajar al
release y `Publish main` seguiría verde—, así que un test afirma que las dos rutas retiradas no están en el árbol.
**Test permanente (Ola 7):** `core.tests.test_publish_guard.PublishGuardTests.test_lo_que_salio_de_la_lista_salio_porque_no_existe`.

### RED-85 · Herramientas del CI sin pinear y actions por tag en workflows con `contents: write`
**Severidad:** BAJA (era MEDIA) · **Estado:** CONFIRMADO (lectura: 7 `pip install` sin versión) · **Origen:** RS-R6-13 (VR2: CONFIRMADO) · **Ola:** R (pinear las actions con `contents: write`) + 7 (el resto) · **Esfuerzo:** S (2 h) + S (2 h)

**Resolución:** ✅ **Parte de la Ola R resuelta** en #554 (Cambio 121, PR R-03), 04-oct-2026; **la Ola 7 sigue abierta**. Pineadas por SHA, con el tag en comentario al lado: `actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09` (v5.1.0) en `publish-main.yml` y `docs-auto-deploy.yml`, `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1` (v6.3.0) en `docs-auto-deploy.yml`, y `dorny/paths-filter@0e4a8c6effa4802afeda77dc8d303f8176d7dfad` (v3.0.4) en sus cuatro usos nuevos (RED-20). Los SHA se resolvieron por API (`git/ref/tags` y, en `paths-filter`, dereferenciando el tag anotado), no de memoria. Bandit quedó con versión fija (`==1.9.4`) como adelanto de la parte de herramientas. **Sigue pendiente (Ola 7):** `requirements-ci.txt` con versiones fijas para los otros seis `pip install` sueltos (`ruff`, `coverage`, `pip-audit`, `mkdocs-material`) y el dependabot semanal sobre ese archivo; las actions de `pr-*.yml` siguen por tag, porque ninguno de esos workflows tiene `contents: write`. **Prioridad nueva, señalada por el revisor del PR R-03:** de los seis `pip install` sueltos, el que más urge es **`pip-audit`**, porque desde el Cambio 121 `Pip Audit` es un check **obligatorio** del ruleset y su base de advisories cambia sola: un advisory nuevo sobre cualquier dependencia de `requirements.txt`, o un release de `pip-audit` que estreche una regla, frena **todos** los merges abiertos, incluidos los PRs que no tocaron nada. Mientras tanto la salida no es destildar el check: es agregar la advisory a `security/excepciones.toml` con `motivo`, un `vence_el` corto y el ticket, en un PR de una línea —eso devuelve el verde y deja la deuda con fecha, que es el punto de RED-63—. Mismo razonamiento, un escalón más abajo, para `ruff`: `Ruff estilo` hoy da 0 y es candidato a bloquear, pero no se enciende hasta que Ruff esté pineado, o un release con una regla E/W nueva pone en rojo un PR que no cambió nada. **Test permanente:** `core.tests.test_gates_ci.ActionsPineadasTests` (4 tests; uno de ellos afirma que los workflows con `contents: write` siguen siendo esos dos, para que un tercero avise antes de que nadie lo pinee).
- **Ubicación:** `pr-quality.yml:30,48,68`, `pr-backend.yml:88`, `pr-security.yml:26`, `docs-auto-deploy.yml:32` (`pip install
  ruff|bandit|coverage|pip-audit|mkdocs-material`); `publish-main.yml:21` (`actions/checkout@v5`) y
  `docs-auto-deploy.yml:22,25`, los dos con `permissions: contents: write`.
- **Qué cambio lo rompería sin que nadie se entere:** un release de `ruff` o `coverage` vuelve rojo o mueve el `fail_under`
  de un PR que no cambió nada; un tag comprometido en una action de `publish-main.yml` es un camino directo al artefacto
  de PRD.
- **Propuesta:** **R:** pinear por SHA (con el tag en comentario) las actions de `publish-main.yml` y `docs-auto-deploy.yml`, y
  `dorny/paths-filter` de RED-20. **Ola 7:** `requirements-ci.txt` con versiones fijas y `pip install -r requirements-ci.txt`
  en todos los workflows, más un dependabot semanal sobre ese archivo.

**Resolución (parte Ola 7):** ✅ Cerrada en el PR 2 de la Ola 7 (Cambio 196), 09-oct-2026 — **`requirements-ci.txt`
con las cinco herramientas pineadas** (`ruff==0.16.10`, `coverage==7.16.2`, `pip-audit==2.10.1`,
`bandit[toml]==1.9.4`, `mkdocs-material==9.7.7`) y los **seis** `pip install` sueltos reemplazados por
`pip install -r requirements-ci.txt`: los dos de Ruff y el de Bandit en `pr-quality.yml`, el de `coverage` en
`pr-backend.yml`, el de `pip-audit` en `pr-security.yml` y el de `mkdocs-material` en `docs-auto-deploy.yml`. Las
versiones son **las que el CI ya venía instalando**, así que pinear no cambia ningún resultado: solo lo congela.
**`.github/dependabot.yml`** semanal contra `development` para los tres ecosistemas del repo: `pip` (los tres
`requirements*.txt` viven en la raíz, así que `directory: "/"` los toma a los tres, con las cinco herramientas
agrupadas en un solo PR), `github-actions` y `npm` (`tailwindcss`). Sin ningún `ignore`, a propósito: un mayor que no
convenga se cierra a mano y queda el registro; un `ignore` en el YAML se olvida.
**La prioridad que señaló el revisor del PR R-03 se atendió entera:** `pip-audit` deja de flotar, y además **se
retiró la excepción `PYSEC-2026-3447`** —era `setuptools` 80.9.0 (CVE-2026-59890) y el ticket de la excepción decía
«RED-85, que es donde se toca el pin»—: `setuptools` subió a 83.0.0, la primera corregida, y
`pip-audit -r requirements.txt` da «No known vulnerabilities found» **sin ningún** `--ignore-vuln`.
`security/excepciones.toml` queda vacío con la plantilla de cómo se agrega la próxima.
**Lo que faltaba para encender `Ruff estilo` ya está** (la versión fija); encenderlo —sacarle el `continue-on-error`
y sumarlo al ruleset— es decisión del PM y no se tomó acá. **Ningún job se renombró**, así que los nueve contextos
del ruleset siguen igual. **Verificación:** `actionlint` (Docker `rhysd/actionlint`) sobre los 9 workflows, 0
errores, incluido el shellcheck del paso de bash reescrito en `pr-performance.yml`.
**Test permanente:** `core.tests.test_gates_ci.HerramientasDelCiPineadasTests`
(`.test_ningun_workflow_instala_una_herramienta_sin_version`, `.test_requirements_ci_pinea_todas_sus_lineas`,
`.test_el_job_que_usa_una_herramienta_instala_el_archivo`, `.test_requirements_ci_no_trae_nada_de_la_aplicacion`)
y `core.tests.test_gates_ci.DependabotTests` (4 tests).

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

**Resolución:** ✅ Resuelto en el PR R-07 (Cambio 119), 04-oct-2026 — los tres tests propuestos, tal cual, en
`programas/tests/test_becas_api.py::TokenAuthTests`. **Mata la mutación M11:** con
`CampoBecasPermission.has_permission` sin `and puede(user, CAP)` los tres quedan en rojo (antes sobrevivía a 1.452
tests). El tercero cubre además que la capacidad se mira **en cada request**: el Token no caduca al sacarle el rol al
usuario.
**Test permanente:** `programas/tests/test_becas_api.py::TokenAuthTests.test_sesion_de_backoffice_sin_becas_campo_no_consulta_persona`.

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

**Resolución:** ✅ Resuelto en el PR R-07 (Cambio 119), 04-oct-2026 — los tres tests propuestos en
`programas/tests/test_becas_api.py::FormularioSyncTests`, más
`test_no_lista_los_adjuntos_de_un_formulario_ajeno` (el `GET …/adjuntos/`, que es el cuarto verbo que pasa por el
mismo `get_queryset`). **Mata la mutación M14:** con `Formulario.objects.all()` los cuatro quedan en rojo. El PATCH
deja anotado en el test que, si SEC-23 (Ola 2) saca `UpdateModelMixin`, el esperado pasa a 405.
**Test permanente:** `programas/tests/test_becas_api.py::FormularioSyncTests.test_no_actualiza_formulario_ajeno`.

### RED-27 · Promover desde la lista de espera con cupo exactamente 0 no está probado
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (mutación M19 sobrevive; la simétrica de aprobar, M20, muere con 3 tests) · **Origen:** RS-R7-04 · **Ola:** R · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/cupo.py:224-226` (`promover_lista_espera`, única guarda de cupo de la promoción). El único
  test que promueve (`test_becas_revision.py:1404-1415`) sube el cupo a 10 antes.
- **Qué cambio lo rompería sin que nadie se entere:** `<= 0` → `< 0`: se promueve con cupo 0, el segmento termina con más
  aprobados que `cupo_maximo` y, como aprobar dispara el alta, **el excedente se informa a SIIS, que no tiene baja**.
- **Propuesta:** `programas/tests/test_cupo_espera_reglas.py::PromoverRespetaElCupoTests(_BaseEsperaTest)`:
  `test_promover_sin_cupo_disponible_falla` (`cupo_maximo = 1` con un APROBADO; `assertRaises(ValidationError)` con «No hay
  cupo disponible»; el caso sigue ENVIADO y `promovido` en `False`) y `test_promover_con_el_ultimo_lugar_funciona`.

**Resolución:** ✅ Resuelto en el PR R-09 (Cambio 124), 04-oct-2026 — los dos tests propuestos más dos bordes que
aparecieron al leer el código: `cupo_maximo = 0` sin nadie aprobado y el segmento **ya excedido** (más aprobados que
lugares, dato heredado). El tercero importa porque `get_cupo_stats` devuelve `max(cupo_maximo - ocupado, 0)`: el
`cupo_disponible` nunca es negativo, así que la mutación `< 0` no es un borde mal puesto, es **la guarda borrada**.
Verificado a mano: M19 → 3 tests en rojo.
**Test permanente:** `programas/tests/test_cupo_espera_reglas.py::PromoverRespetaElCupoTests.test_promover_sin_cupo_disponible_falla`

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

**Resolución:** ✅ Capa 1 resuelta en el PR R-09 (Cambio 124), 04-oct-2026. La capa 2 (`TransactionTestCase` con dos
hilos, `@tag("mysql")`) sigue abierta dentro de TST-01 (PR R-11), que es la que trae el motor real al CI.
El espía no es `assert_called()` a secas: `core/tests/candados.py::candados_tomados` registra **desde qué función** se
pidió el candado, porque sobre el mismo manager hay más de un lock en juego —`Formulario.save()` bloquea el
relevamiento para numerar el caso— y un `assert_called()` quedaba verde con M43 aplicada (comprobado). Cubre los tres
caminos del segmento (`aprobar_o_poner_en_espera`, `promover_lista_espera`, `agregar_a_lista_espera`), el
`Relevamiento` del link público y el del POST de la app de campo, más el `Convocatoria` del duplicado, que la ficha no
nombraba y es el otro lock del mismo envío. Los del link viven en `portal/tests/` —no en
`test_candados_concurrencia.py` como decía la ficha— porque el fixture del paso 2 está ahí y moverlos obligaría a que
los tests de `programas` importen los de `portal`. Verificado a mano, borrando una línea por vez: `cupo.py:205` → 1 en
rojo, **M21** (`cupo.py:267`) → 2, `cupo.py:316` → 2, **M43** (`inscripcion_publica.py:89`) → 1,
`inscripcion_publica.py:134` → 1, `api/views.py:387` → 1.
**Capa 2 ✅ en el PR R-11 (Cambio 130), 05-oct-2026** — `core/tests/test_motor_real.py::CarreraDeCupoTests`
(`TransactionTestCase` con `@tag("mysql")`): dos hilos que arrancan juntos en una `threading.Barrier` sobre un segmento con
**un** lugar libre dan exactamente un APROBADO y una `ListaEspera`, y dos altas simultáneas a la lista reciben posiciones
1 y 2. Verificado borrando una línea por vez contra `mariadb:10.11`: **M21** (`cupo.py:267`, el `select_for_update` de
`aprobar_o_poner_en_espera`) → `['aprobado', 'aprobado']`, cupo excedido; `cupo.py:316` (el de `agregar_a_lista_espera`) →
`[1, 1]`, dos personas en la misma posición. O sea que M21 ahora muere por las dos capas: la de forma en SQLite y la de
efecto en MariaDB. Cinco corridas seguidas sin un solo falso rojo.
**Test permanente:** `programas/tests/test_candados_concurrencia.py::ContratoDeCandadosTests.test_aprobar_toma_el_candado_del_segmento`
· capa 2: `core/tests/test_motor_real.py::CarreraDeCupoTests.test_dos_aprobaciones_simultaneas_consumen_un_solo_lugar`

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

**Resolución:** ✅ Resuelto en el PR R-09 (Cambio 124), 04-oct-2026 — los tres tests propuestos, con el default de
**D-RED-11** (se fija la conducta de hoy, no se cambia). Se agregó un cuarto, `test_la_posicion_del_ultimo_promovido_se_reutiliza`,
porque al escribir `test_la_posicion_tras_promover` apareció que la conducta no es una sola: el máximo se calcula sobre
los **no promovidos**, así que sacar al primero de la lista deja su lugar sin reutilizar (el nuevo recibe 3, como decía
la ficha), pero sacar al **último** baja el máximo y la próxima alta **repite su posición** —quedan dos filas con la
misma posición en el segmento, una promovida y una activa—. Eso es lo que define cómo puede entrar la unicidad de
BEC-02: `UniqueConstraint(fields=["segmento", "posicion"])` sobre lo que hay hoy no cierra; hace falta liberar la
posición al promover (columna nullable). Verificado a mano: M23 (`posicion = max_pos`) → los 4 tests en rojo.
**Test permanente:** `programas/tests/test_cupo_espera_reglas.py::PosicionEnLaListaTests.test_las_altas_consecutivas_llevan_posiciones_correlativas`

### RED-69 · Fecha de nacimiento ausente o futura sin test en el payload SIIS
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (mutación M34 sobrevive; la rama `else` no la ejecuta ningún test) · **Origen:** RS-R7-09 · **Ola:** R (o Ola 1, que abre `siis_envio.py`) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/siis_envio.py:469-473` (`if nacimiento and nacimiento <= hoy`).
- **Qué cambio lo rompería sin que nadie se entere:** sacar `and nacimiento <= hoy` al mover la validación al form: un dedazo
  («2027-05-14») viaja a SIIS como alta real, sin baja; además `_edad` da negativo y dispara la rama de apoderado.
- **Propuesta:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_fecha_de_nacimiento_ausente_o_futura_falta`:
  `subTest` con `None`, `hoy + 1 día` (los dos en `faltantes` y `cargar_beneficiario` no se llama) y `hoy` (pasa: el borde);
  en el mismo test, los negativos de `apellido`, `nombre` y `dni` vacíos.

**Resolución:** ✅ Resuelto en el PR R-06 (Cambio 123), 04-oct-2026 —
`test_fecha_de_nacimiento_ausente_o_futura_falta` recorre con `subTest` las cuatro situaciones (`None`, `hoy + 1 día`,
`hoy` —el borde, que pasa— y `hoy - 1 día`), y `test_una_fecha_de_nacimiento_futura_no_llega_a_siis` cierra el otro lado:
con un faltante el envío queda INCOMPLETO y `cargar_beneficiario` **no se llama**. Los negativos de identidad que pedía
la ficha quedaron en dos tests propios (`test_los_datos_de_identidad_vacios_tambien_faltan` y
`test_sin_ciudadano_faltan_los_cuatro_datos_de_la_persona`) en vez de dentro del mismo: son otro borde y conviene que el
rojo diga cuál.
Mutación M34 verificada a mano (aplicar, correr, revertir): `if nacimiento:` → 3 tests en rojo.
**Test permanente:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_fecha_de_nacimiento_ausente_o_futura_falta`

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

**Resolución:** ✅ Resuelto en #604 (Cambio 156, PR R-16), 07-oct-2026 — `CeldaSeguraTests` (cinco tests) cubre las dos
cosas que hace la línea: que `respuesta_reporte(…, "xlsx")` y `respuesta_libro` devuelvan 200 con la celda limpia en vez
de morir con `IllegalCharacterError`, y que el **orden** importe —invertirlo deja que el carácter de control esconda la
fórmula del chequeo, porque el `lstrip()` de Python se lo come—. Se agregaron además el CSV y el alcance del libro, que
también pasan por la función.
**Mutación M49 verificada a mano** (aplicar, correr, revertir): borrar `ILLEGAL_CHARACTERS_RE.sub` deja los **cinco**
tests en rojo, tres de ellos con el `IllegalCharacterError` que es el 500 de la descarga.
**Nota:** `programas/services/exportacion_reportes.py` sigue con terminadores CR (RED-82, PR R-21) y **no se tocó**:
los tests viven en `programas/tests/test_reportes.py`.
**Test permanente:** `programas.tests.test_reportes.CeldaSeguraTests` (`test_celda_segura_limpia_y_prefija_a_la_vez` y
`test_un_caracter_de_control_no_rompe_el_xlsx`).

### RED-87 · El largo mínimo del barrio del payload SIIS no se prueba en su borde
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (mutación M33 sobrevive) · **Origen:** RS-R7-08 · **Ola:** R (mismo PR que RED-69) · **Esfuerzo:** S (2 h)
- **Ubicación:** `programas/services/siis_envio.py:502-505` (`len(barrio) >= BARRIO_MINIMO`, con `BARRIO_MINIMO = 4` en `:21`);
  el test existente usa `"108"` (→ `"Barrio 108"`) y `"Sur"` (3), nunca 4.
- **Qué cambio lo rompería sin que nadie se entere:** `>=` → `>`: todo barrio de 4 caracteres pasa a `faltantes`, el caso cae a
  INCOMPLETO y la pantalla pide corregir un dato correcto (bloqueo silencioso de altas).
- **Propuesta:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_el_barrio_de_cuatro_caracteres_es_el_minimo_aceptado`
  (`"Sur2"` aceptado, `"Sur"` en `faltantes`) y el mismo borde para `len(dni) <= 10` (`:450`) y `[:LARGO_TEXTO]` (`:503,518`).

**Resolución:** ✅ Resuelto en el PR R-06 (Cambio 123), 04-oct-2026 —
`test_el_barrio_de_cuatro_caracteres_es_el_minimo_aceptado` recorre 3, 4 y 5 caracteres (`"Sur"`, `"Sur2"`, `"Sur22"`),
y los otros dos bordes que pedía la ficha quedaron en tests propios:
`test_el_dni_de_diez_digitos_es_el_maximo_aceptado` (10 y 11) y
`test_los_textos_largos_se_recortan_en_el_maximo_sin_perder_el_borde` (`LARGO_TEXTO` exacto y uno más, en el barrio y en
la calle).
Mutación M33 verificada a mano (aplicar, correr, revertir): `>=` → `>` deja en rojo el `subTest` de 4 caracteres.
**Test permanente:** `programas/tests/test_siis_envio.py::ArmarPayloadTests.test_el_barrio_de_cuatro_caracteres_es_el_minimo_aceptado`

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

**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026 — bisecado hasta
`core.tests.test_performance_budgets`, y la causa **no era la que los candidatos de la ficha anticipaban**: no hay
ninguna excepción guardada como atributo de clase. `PerformanceBudgetTests.setUpTestData` llama a `seed_perf`, cuya
guarda comparaba el `NAME` de la base contra **dos literales**. Con `--parallel N` el runner clona la base por worker
y le pone un sufijo —medido: `file:memorydb_default_2?mode=memory&cache=shared`—, que no estaba en la lista. El
`CommandError` salía de `setUpTestData`, o sea como error **de clase**, y su `exc_info` arrastra un `traceback` que
`multiprocessing` no serializa: de ahí el `TypeError` y el aborto sin decir qué test falló. La guarda pasa al mismo
criterio que usa Django (`:memory:` o `mode=memory` en el nombre) y sigue rechazando un archivo en disco, que es lo
que existe para impedir. Medido después: **`core users portal --parallel 2` → 1.171 tests OK en 56 s**. El paso no
bloqueante que pide la ficha vive en el job nuevo `Orden y paralelo` de `pr-backend.yml`, junto con la pasada
`--shuffle` de TST-02.
**Test permanente:** `core/tests/test_seed_perf_guarda.py::GuardaDeSeedPerfTests.test_acepta_los_clones_que_crea_parallel`
(y `.test_acepta_la_base_en_memoria_sin_clonar`, `.test_rechaza_una_base_en_disco`,
`.test_un_nombre_que_solo_se_parece_no_alcanza`).

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

> **Implementado** en el PR R-13 (Cambio 139) como el job `Migrate ida y vuelta (<motor>)`
> de `pr-performance.yml`. Lo que sigue es la propuesta original; **los cinco desvíos
> —base del PR en vez de tag, dos motores en vez de tres, sin `continue-on-error`, base
> `chaco_perf_ci` por la guarda de `seed_perf` y el settings de CI fuera de `config/`—
> están explicados en la resolución de RED-17**, que es lo que vale. La orquestación vive
> en `scripts/roundtrip_migraciones.py`, no en el YAML.

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

**Nota de R-12 (Cambio 135), para quien escriba este job.** El paso «backward» ahora tiene **ocho** migraciones que
abortan a propósito con `IrreversibleError` (paso D.4 del runbook): `programas.0032`, `0047`, `0048`, `0056`, `0069`,
`0073`, `legajos.0007` y `users.0023`. Mientras «la release anterior» esté por encima de todas —hoy lo está: la última
barrera es de septiembre— el plan de reversa no las toca. Si alguna vez las cruza, el job tiene que **esperar** el
aborto, no tomarlo como rojo: ese es el comportamiento correcto. Y las dos razones por las que el Anexo pedía
`continue-on-error` ya no están: RED-18 (la reversa UUID truncaba) está cerrada y las barreras de RED-15/RED-57 están
declaradas, así que D-RED-03 se puede decidir con el job midiendo de verdad desde el primer día.

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
