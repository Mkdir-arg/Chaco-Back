# 4.5 Datos, operación, despliegue y tests (DAT, OPS, TST, G1c-12, G2-05, G3-04/05)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. PoC: `poc/test_repro_datos_operacion.py` y
`poc/test_repro_admin_cron_renaper.py` (seeds).

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| OPS-06 | **Seeds de arranque pisan configuración del ABM** (capacidades, roles, Operador de backoffice, programa Becas) | ALTA | CONF. test | **0** | S-M | 🟡 |
| DAT-01 | Borrar una pregunta o requisito borra los adjuntos de todos los casos | ALTA | CONF. test | 3 | S (+M fase 2) | ⬜ |
| OPS-03 | Los tracebacks de 500 no llegan a stdout | ALTA | CONF. test | **R** (antes 3) | S | ✅ |
| OPS-01 | Sin guarda de coherencia `django_migrations` ↔ esquema antes de `migrate` | MEDIA | CONF. código | **R** (antes 3) | M | ✅ |
| OPS-02 | `crear_usuarios_sistema` y seeds demo con claves conocidas viajan en el release | MEDIA | CONF. ajustado | 3 | S | ✅ |
| OPS-04 | `/health/` siempre 200 y tapa `health_check.urls` | MEDIA | CONF. test | **R** (antes 3) | S | ✅ |
| OPS-05 | `read_timeout=10 s` también corta `migrate` | MEDIA | PLAUSIBLE | 3 | S | ✅ |
| OPS-07 | Bootstrap frágil (`set -eu`, opcionales fatales, réplicas) | MEDIA | CONF. ajustado | 3 | S | ✅ |
| TST-01 | La CI no prueba MariaDB | MEDIA | CONF. ajustado (tesis central refutada) | **R** (antes 3) | M | ✅ |
| TST-02 | Configuración sin tests de comportamiento; tests que no prueban nada | MEDIA | CONF. | **R** (antes 3) | M (+S-M) | ✅ |
| G1c-12 | `debug_ciudadanos` hace `FLUSHDB` del Redis compartido | MEDIA | CONF. código | 3 | S | ✅ |
| DAT-02 | El admin de Django borra casos y relevamientos con su auditoría | BAJA | CONF. ajustado | 3 | S | ⬜ |
| DAT-03 | `dni_titular` desincronizado del DNI real | BAJA | PLAUSIBLE | 3 | S | ⬜ |
| DAT-05 | El Excel del padrón reemplazado/quitado queda en `media/` (o se borra antes del commit) | BAJA | CONF. | 3 | S | ⬜ |
| V2-NEW-05 | Un restore deja pks de legajo en hex que el ORM de MariaDB no encuentra | BAJA | a confirmar | 3 | S | ⬜ |
| OPS-10 | Módulos de «optimización» con DDL y `SET GLOBAL` en el release | BAJA | CONF. ajustado | 7 | S-M | ⬜ |
| OPS-11 | `migrate --run-syncdb` en el entrypoint | BAJA | CONF. ajustado | 3 | S | ✅ |
| OPS-12 | QA no reproduce el cache de PRD y declara `ENVIRONMENT=prd` | BAJA | CONF. | 3 | S | ✅ |
| OPS-13 | Dependencias sin uso en la imagen | BAJA | CONF. | 7 | S | ⬜ |
| OPS-14 | Código muerto o stub; un `.py` vivo que git trata como binario | BAJA | CONF. | 7 | S | ⬜ |
| TST-03 | Coverage global de 48 % sobre todo el repo | BAJA | CONF. | **R** (antes 3) | S | ✅ |
| G2-05 | `import_users_from_csv` reparte grupos de un usuario fijo y pisa cuentas | BAJA | CONF. lectura | 3 | S | ✅ |
| G3-04 | CronJobs de referencia sin deadlines, `backoffLimit` ni `timeZone` | BAJA | PLAUSIBLE | 3 | S | ✅ |
| G3-05 | Cron de icore sin versionar y sin vigilancia | BAJA | CONF. lectura | 3 | S | ✅ |
| R0-02 | `CLAUDE.md` y `docs/client/architecture.md` todavía nombran `portal:ciudadano_mi_perfil` | BAJA (MINOR) | revisión Ola 0 | 7 | S | ⬜ |
| R0-03 | Fecha fija en `programas/tests/test_becas_relevamientos.py:636-648` que vence el 01-ene-2027 | BAJA (MINOR) | revisión Ola 0 | **R** (antes 3; antes del 31-dic-2026) | S | ✅ |

---

## ALTA

### OPS-06 · Seeds de arranque pisan la configuración que el ABM deja editar
**Severidad:** ALTA (sube desde la MEDIA de OPS-06 de V6 por G1c-02) · **Estado:** CONFIRMADO con test (`poc/test_repro_admin_cron_renaper.py::G1c02SeedPisaCapacidadesTests`; `poc/test_repro_usuarios.py::G2OperadorBackofficeSeedTests`); impacto en PRD PLAUSIBLE con alta probabilidad · **Origen:** A8-08, G1c-02, G1c-03, G2-02 · **Ola:** **0** · **Esfuerzo:** S-M (M si se agrega `RolMeta.clave`) · **Decisión:** D-O06

**Resolución:** 🟡 Parcial en #508 (Cambio 104), 01-oct-2026 — puntos 1-3: las opt-in (`seed_becas.CAPACIDADES_OPT_IN`) sobreviven al seed; de un rol existente no se pisan descripción, activo ni protegido; «Operador de backoffice» se siembra solo al crearlo; `crear_programas` busca por `codigo` y no toca un programa existente (cubre G1c-03); tests en `users/tests/test_seed_datos_base.py`. DECISIÓN PM 01-oct (D-O06): «Operador de backoffice» queda como está (no protegido, conserva sus capacidades). Falta: la fase 2 (`RolMeta.clave`: un rol renombrado sigue generando un segundo rol en el arranque, escenario 3) → Ola 2, PR 1 (+4 h); P-05 en PRD y volver a tildar `becas.relevamiento.publico` donde el deploy del 28/09 la haya borrado (operativo, PM).
- **Ubicación:** `programas/management/commands/seed_becas.py:296-325` (`group.permissions.set(...)` por rol, línea 325; `:56-61` excluye `becas.relevamiento.publico`), `:313-325` (`asegurar_roles_becas`: `update_or_create(... "activo": True, "protegido": False ...)`); `users/management/commands/seed_rbac.py:86-111` (`RolMeta.update_or_create(... "protegido": False, "activo": True)` + `permissions.set` con `usuario.administrar` y `rol.administrar` sobre «Operador de backoffice», línea 110); `legajos/management/commands/crear_programas.py:28-40` (`update_or_create(tipo=BECAS, defaults={estado ACTIVO, nombre, color, orden})`); `users/views/roles.py:80-127` (el ABM permite renombrar, desactivar y borrar roles); `configuracion/views/programas.py:430-452` (permite cambiar el estado del programa); `docker-entrypoint.sh:61-62` (default `seed_datos_base crear_programas seed_catalogo_siis` en cada arranque).
- **¿Corre en cada arranque en ECOM?** Sí según lo documentado: Historial del Cambio 30 (27/08) dice que ECOM usa el initContainer `bootstrap`; `docker/k8s/bootstrap-initcontainer.yaml` corre `args: ["bootstrap"]` → `LOCAL_BOOTSTRAP_COMMANDS` = `seed_datos_base crear_programas` (`.env.qa.example:95`) o el default. **Todo pod nuevo (deploy, reschedule, reinicio) lo ejecuta.** En icore, en cada `up` de `web`. El manifiesto real de ECOM no está en el repo (por eso PLAUSIBLE).
- **Escenarios:**
  1. (G1c-02, reproducido) El 25/09 se tildó `becas.relevamiento.publico` en «Becas — Referente» en PRD (Cambio 91, «se enciende tildándola en Roles, sin deploy», Cambio 41). El 28/09 se desplegó el release hasta el Cambio 94 y el initContainer corrió `seed_datos_base`: **el Referente probablemente volvió a no ver nada** del link público en convocatoria, Relevamientos ni Revisión. Cada deploy repite el incidente, con cualquier capacidad agregada a mano a un rol de Becas o al Operador de backoffice. Verificar con P-05 (README §3).
  2. (G2-02, reproducido) Se desactiva «Operador de backoffice» y se le vacían las capacidades → `seed_rbac` lo vuelve a `activo=True` con `usuario.administrar` y `rol.administrar`. El rol no es protegido; esas dos capacidades equivalen a admin total (crea un rol con todo y se lo asigna), así que el «menú acotado» del #59 es cosmético. El log dice «6 capacidades» y siembra 5. No hay decisión registrada.
  3. (A8-08) Si se renombra un rol de Becas, el arranque siguiente crea un **segundo** rol por `get_or_create(name=...)`; un rol desactivado vuelve a activo; `crear_programas` fuerza `estado=ACTIVO`; icono y color: `seed_becas` siembra `school/#0ea5e9` y `crear_programas` deja `graduation-cap/#5059BC`.
  4. (G1c-03) `Programa.tipo` no es único (`models:121`) y `ProgramaAdmin` deja editarlo: un segundo programa `tipo=BECAS` cargado por `/admin/` produce `MultipleObjectsReturned` y con `set -eu` el contenedor no arranca (camino que hoy nadie usa).
- **Contradicción registrada:** el Cambio 29 decide que «`seed_becas` reemplaza el conjunto… correrlo en cada arranque mantiene los roles alineados»; los Cambios 41 y 91 dicen que `becas.relevamiento.publico` se enciende a mano «sin deploy». No pueden convivir. El Cambio 24 acepta que se reemplacen capacidades; la desactivación y el renombre no están decididos.
- **Propuesta (un PR, Ola 0):**
  1. `asegurar_roles_becas`: separar base y opt-in:
     ```python
     OPT_IN = {"becas.relevamiento.publico"}
     base = {_perm(c) for c in cfg["capacidades"]}
     conservar = set(group.permissions.filter(codename__in=[rbac.codename_de(c) for c in OPT_IN]))
     group.permissions.set(base | conservar)
     ```
     Crear con `activo=True` solo si es nuevo (`defaults` sin `activo`; `create_defaults` de Django 5 para el alta); no pisar `activo` ni `name` de un rol existente (default D-O06: respetar activo/nombre y sincronizar solo capacidades base). Fase 2 (M): identificar el rol por `RolMeta.clave` (programa + clave estable, con migración) en vez de por `name`.
  2. `seed_rbac`, «Operador de backoffice»: `set()` solo si el grupo se acaba de crear (`created`); si existía, no tocar `activo` ni capacidades (o `add(*caps_operador)`); D-O06 decide además si se marca `protegido=True` y se le **sacan** `usuario.administrar`/`rol.administrar` (si la intención del #59 era un operador acotado).
  3. `crear_programas`: `get_or_create(codigo="BECAS", defaults={…})` sin pisar `estado` (se usa `codigo`, que es único, en vez del `tipo=…` que proponía V6: evita el `MultipleObjectsReturned` de G1c-03), y una sola fuente de icono y color.
  4. Registrar en `requerimientos.md` la regla «las capacidades opt-in sobreviven al seed» (actualiza el Cambio 29) y pedirle al PM que verifique (P-05) y, si hace falta, vuelva a tildar la capacidad en PRD **después** del deploy de este fix.
- **Tests a agregar:** `users/tests/test_seed_datos_base.py`: tildar `becas.relevamiento.publico` en el Referente → `call_command("seed_datos_base")` → la sigue teniendo; quitar a mano una capacidad base → vuelve (preserva el Cambio 29); desactivar un rol de Becas → sigue inactivo; renombrarlo → no aparece duplicado; programa en `SUSPENDIDO` → `crear_programas` no lo toca; «Operador de backoffice» desactivado → sigue desactivado y sin las capacidades quitadas (los dos PoC invertidos). Hoy `seed_datos_base` no tiene ningún test.
- **Verificación:** V-STD + `manage.py test users programas`; en DEV, tildar a mano, reiniciar `web` y comprobar.
- **Dependencias:** SEC-22 (RN-P13 depende de que la capacidad sobreviva).

### DAT-01 · Borrar una pregunta general o un requisito nativo borra los adjuntos de todos los casos
**Severidad:** ALTA (era CRÍTICA; sube a CRÍTICA si PRD no tiene backups de base con retención) · **Estado:** CONFIRMADO-AJUSTADO con test (`A801CascadeTests`) · **Origen:** A8-01, G1c-01 (aporte); relacionado: V6-NEW-02 (Dispositivos, patrón opuesto) · **Ola:** 3 · **Esfuerzo:** S (fase 1) / M (fase 2) · **Decisión:** D-D01

**⚠ Actualizar (03-oct-2026):** `seed_becas.py` cambió con #508: `ADJUNTOS_OBLIGATORIOS` está hoy en `:150` y su alta en `:209`; las preguntas ARCHIVO siguen sin `protegido`.
- **Ubicación:** `programas/models/__init__.py:2706-2721` (`AdjuntoFormulario.pregunta_global` y `.requisito_nativo` con `on_delete=CASCADE`); `programas/views/configuracion.py:682-695` (`requisito_eliminar`, sin guarda), `:1046-1057` (`pregunta_eliminar`, solo frena `protegido`); admin `PreguntaGlobalAdmin`, `RequisitoNativoAdmin`, `ProgramaSiisAdmin` (`RequisitoNativo.programa` CASCADE); `seed_becas.py:133-139`, `:163-176` (siembra las 5 preguntas ARCHIVO —«Foto DNI - Frente/Dorso», «Certificado de domicilio»…— **sin `protegido`** y las busca por `get_or_create(texto=…)`); `_pregunta_row.html:72-79` (botón Eliminar si `not p.protegido`).
- **Escenario (reproducido):** pregunta ARCHIVO con adjunto en un caso FINALIZADO + un `ItemDiseno` que la usa → POST → 302; `adjunto existe: False`, `item diseno existe: False`, `archivo en storage: True`, `data residual: {'globales': {'18': {'archivo_adjunto': True}}}`. Igual con el requisito. Agravantes: la revisión arma la vista desde la foto (`respuestas.py:_adjuntos_por_clave`), así que el revisor ve el documento **como faltante**, no como borrado; el modal del requisito dice «deja de pedirse… No se puede deshacer» (`_requisitos_panel.html:51`); si se borra «Foto DNI - Frente», el próximo arranque la recrea con otro pk y la pantalla se ve sana (G1c-01).
- **Lo que NO hay que hacer:** pasar `ItemDiseno.pregunta/requisito` a PROTECT: el Cambio 58 decidió «el diseño sigue al catálogo (auto-append, remove)».
- **Propuesta:**
  1. Migración `AlterField` de `AdjuntoFormulario.pregunta_global` y `.requisito_nativo` a `on_delete=models.PROTECT` (en MySQL/MariaDB Django no emite DDL por un cambio de `on_delete`: solo estado, sin costo en PRD).
  2. En `pregunta_eliminar` y `requisito_eliminar`: `try: obj.delete() except ProtectedError as e: messages.error(f"Está en uso en {len({a.formulario_id for a in e.protected_objects})} caso(s). Desactivala en lugar de borrarla.")` (patrón de `subsegmento_eliminar`, `:566-572`).
  3. Texto del modal del requisito: «Si algún caso ya subió este documento, no se va a poder eliminar».
  4. (G1c-01) `protegido=True` para `ADJUNTOS_OBLIGATORIOS` en `seed_becas` + migración de datos que lo marque en las existentes; las vistas ofrecen desactivar si hay adjuntos/ítems.
  5. Fase 2 (M): `RequisitoNativo.activo` (AddField con default: INSTANT en MariaDB 10.3+, tabla chica) filtrado en `definicion_formulario`, la API y la validación. D-D01: ¿un requisito en uso se desactiva (default) o se prohíbe tocarlo?
- **Tests a agregar:** (a) pregunta con adjunto → POST → siguen la pregunta y el adjunto y aparece el mensaje; (b) pregunta sin adjuntos → se borra con su `ItemDiseno` (preserva Cambio 58); (c) ídem requisito; (d) admin: POST de borrado de `PreguntaGlobal` con adjuntos no borra nada; (e) `seed_becas` deja `protegido=True` en las ARCHIVO obligatorias.
- **Verificación:** V-STD + V-UI. Revisar `diseno.py:279,410` (borra ítems, no adjuntos).

### OPS-03 · Los tracebacks de 500 no llegan a stdout
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`A804LoggingTests`: `django.request` con handlers `[error_file, warning_file]` y `propagate=False`) · **Origen:** A8-04 · **Ola:** 3 (independiente; se recomienda adelantarlo al primer release porque sin tracebacks no se diagnostica el resto) · **Esfuerzo:** S

**Ampliado por RS-R4-21 (04-oct-2026, frente Red de seguridad):** pasa a la **Ola R** (PR R-15) junto con RED-55: los dos `except Exception` de los context processors (`core/context_processors.py:41`, `conversaciones/context_processors.py:20`) deben loguear con `logger.exception`, y sin este cambio esos logs tampoco llegarían a ECOM.

**Resolución:** ✅ Resuelto en el PR R-15 (Cambio 153), 06-oct-2026 — `LOGGING` sale de `core/logging_config.py::construir_logging`, que es una función y por eso se puede probar con y sin archivos. `django.request` queda **sin handlers propios y propagando**, así que el traceback de cada 500 llega a `console` por la raíz: eso es lo que recogen `docker compose logs` y `kubectl logs`, donde antes solo se veía la línea `core.requests … status=500`. Los cinco handlers de archivo pasan a depender de `LOG_TO_FILES` (encendida en `docker-compose.prod.yml` para `web` y `websocket`, que es icore, donde `./logs` está montado), y `purgar_logs_viejos` borra las carpetas diarias con más de `LOG_RETENTION_DAYS` (14) al arrancar. **Un desvío:** la ficha proponía reemplazar `DailyFileHandler` por `TimedRotatingFileHandler`; no se hizo, porque cambiar el layout a `logs/info.log` rompe `core/management/commands/perf_report_requests.py`, que lee `logs/<fecha>/info.log`. La retención —el motivo del cambio— se resolvió sin tocar el layout. Con `LOG_TO_FILES` apagada tampoco se crea el directorio, que en un filesystem de solo lectura era un arranque fallido. El aviso a ECOM por el volumen en stdout quedó escrito en `docs/internal/propuesta-ecom-verify.md` §4, para que lo mande el PM. **Test permanente:** `core.tests.test_logging_stdout` (`CadenaHastaStdoutTests`, `TracebackDeUn500Tests.test_el_500_emite_el_traceback`, `ArchivosOpcionalesTests`, `RetencionTests`) y, por RED-55, `core.tests.test_context_processors`.

- **Ubicación:** `config/settings.py` (`LOGGING`; `:557` es `"django.request": {"handlers": ["error_file", "warning_file"], …, "propagate": False}`); `settings_production.py` no lo toca; `.dockerignore` excluye `logs`; en k8s `logs/` es efímero; en icore está montado (`./logs:/app/logs`) y crece sin retención. `kubectl logs` solo muestra la línea `core.requests … status=500` del middleware.
- **Propuesta:**
  ```python
  LOG_TO_FILES = os.environ.get("LOG_TO_FILES", "False") == "True"   # icore: True en compose
  _file_handlers = ["info_file", "error_file", "warning_file", "critical_file", "data_file"] if LOG_TO_FILES else []
  # handlers *_file: "logging.handlers.TimedRotatingFileHandler", when="midnight", backupCount=14,
  #                   filename=LOG_DIR / "<x>.log" (sin subcarpeta por día)
  "root": {"handlers": ["console", *_file_handlers], "level": ...},
  "loggers": {
      "django": {"handlers": [], "level": ..., "propagate": True},
      "django.request": {"handlers": [], "level": "WARNING", "propagate": True},   # llega a console vía root
      "core.requests": {"handlers": [], "level": "INFO", "propagate": True},
  }
  ```
  `LOG_TO_FILES=True` en `docker-compose.prod.yml` (icore). Con varios workers el rollover compite (aceptable en icore; si molesta, `WatchedFileHandler` + logrotate del host). Avisar a ECOM por el volumen en stdout.
- **Tests a agregar:** `assertLogs("django.request", "ERROR")` sobre una vista que lanza; test de config que recorra la cadena de `django.request` y afirme que alcanza un `StreamHandler` (es el PoC `A804LoggingTests` invertido).
- **Verificación:** V-STD; con `LOG_TO_FILES` sin setear no se crean archivos en `logs/`; en DEV (icore, `LOG_TO_FILES=True`) siguen apareciendo los archivos diarios; forzar un 500 en DEV y ver el traceback en `docker compose logs web`.
- **Dependencias:** ninguna. Avisar a ECOM del aumento de volumen en stdout antes del release.

## MEDIA

### OPS-01 · Sin guarda de coherencia entre `django_migrations` y el esquema antes de `migrate`
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO en código; el estado de icore es PLAUSIBLE (filas viejas `0057_catalogo_grupos_origen_canal`…`0062_padron_relevamiento_herencia` de `a9fc4ee`; `development` las numera 0060-0065) · **Origen:** A8-02 · **Ola:** 3 · **Esfuerzo:** M

**Ampliado por RS-VR2-NEW-03 y RS-R5-02 (04-oct-2026):** pasa a la **Ola R** (PR R-15). Un rollback fallido en MariaDB es un segundo origen de tablas huérfanas, distinto del restore (RED-15): `verificar_esquema_migraciones` tiene que incluir también el chequeo **inverso** (tablas que existen en la base y no corresponden a ningún modelo del estado final, p. ej. `legajos_derivacion`). El job `migration-roundtrip` (RED-17, Anexo B de `08-red-de-seguridad.md`) lo corre como último paso.

- **Ubicación:** `docker-entrypoint.sh:38-41` (comentario `:31-37`, Cambio 78).
- **Escenario:** en icore, el deploy de `development` aplica 0057-0059 (índices) y muere en `0060_catalogo_grupos_origen_canal` con 1050 `Table already exists`: CrashLoop críptico.
- **Propuesta:** (1) comando de solo lectura `verificar_esquema_migraciones`: `MigrationLoader(connection)`, `applied - disk` (filas sin archivo) y, para cada migración no aplicada del plan, las `CreateModel` cuya `db_table` ya está en `connection.introspection.table_names()` → `CommandError` con la lista y la instrucción («renombrar en `django_migrations`…» / «borrar las tablas huérfanas, NUNCA `--fake`»); (2) en el entrypoint, antes de la línea 40, `python manage.py verificar_esquema_migraciones` (salteable con `SKIP_SCHEMA_GUARD=true`); (3) script SQL versionado para icore: `UPDATE django_migrations SET name='0060_catalogo_grupos_origen_canal' WHERE app='programas' AND name='0057_catalogo_grupos_origen_canal';` y así con las 6 (consultar antes con P-13). **Descartado:** `replaces` (0060 depende de 0059; muy probablemente `InconsistentMigrationHistory`; no se probó).
- **Tests:** `TransactionTestCase` que inserta `programas.0099_fantasma` en `django_migrations` → el comando falla; test unitario de la función que cruza el plan con `table_names`.

**Resolución:** ✅ Resuelto en el PR R-15 (Cambio 153), 06-oct-2026 — comando de solo lectura `core/management/commands/verificar_esquema_migraciones.py` con los **tres** chequeos: (a) `applied - disk`, las filas sin archivo, que es el estado de icore; (b) las `CreateModel` del plan pendiente cuya `db_table` ya existe, que es el `1050 Table already exists` del deploy y también lo que deja un restore encima; y (c) el **inverso de RED-15** que pedía el «Ampliado por»: tablas que existen y que ningún modelo del estado final nombra. El (c) avisa pero no frena —hay bases con tablas ajenas por motivos legítimos— salvo con `--estricto`, que es como lo corre el paso 8/8 nuevo de `scripts/roundtrip_migraciones.py`, donde la base es efímera. **Y el (a) tampoco frena por sí solo** (revisión del PR, ronda 2): una fila sin archivo casi nunca anuncia una rotura —`silk.0001`-`0008` aparecen en toda base migrada con `DJANGO_DEBUG=True` y arrancada con `False`, `turnos` está borrada, `tramites` ya no tiene paquete de migraciones y `programas.0046_formulario_fecha_aprobacion_formulario_fecha_rechazo` se borró el 18/08 con su número reusado—, y abortar por ellas dejaba ambientes que **no vuelven a arrancar nunca**, que es peor que el problema original. Frena **solo la renumeración**: la misma migración en disco con otro número y sin aplicar, que es exactamente lo que `migrate` va a volver a correr. El resto sale por `logger.warning` + stderr con su motivo. El daño de icore lo cubren las dos barreras juntas: la renumeración y la colisión de tablas. El estado final se calcula con la unión de los modelos vivos y los del `project_state()` de las migraciones: solo con los vivos, una tabla del grafo cuyo modelo ya no está en el código daría un falso positivo. Un detalle que el CI de este PR encontró y que la ficha no podía prever: **una migración *reemplazada* por un squash figura aplicada y no tiene archivo propio**, así que el chequeo (a) tiene que unir las claves de disco con las que cubre cada `replaces`. El caso vivo del repo es `django-health-check` —su `db.0001_initial` declara `replaces = [("health_check_db", "0001_initial")]`, o sea dos filas en `django_migrations` y un archivo en disco, bajo un tercer label—. Sin esa unión, la guarda abortaría el arranque en **todos** los ambientes, y lo haría también con cualquier squash futuro del proyecto. El entrypoint lo corre antes del `migrate`, salteable con `SKIP_SCHEMA_GUARD=true`, y tiene un modo `--solo-reporte` que imprime lo mismo y **termina siempre en 0**: es el que se corre contra icore y contra testing y PRD de ECOM **antes** de desplegar o espejar (paso 0 nuevo de `espejo-ecom.md` y checklist pre-deploy de `processes.md`). El punto (3) de la propuesta quedó en [`core/sql/2026-10-06_renombrar_migraciones_icore.sql`](../../../../core/sql/2026-10-06_renombrar_migraciones_icore.sql) con las seis filas verificadas contra el árbol de `a9fc4ee` (0057-0062 → 0060-0065), el `SELECT` de verificación previo y el de después; lo corre una persona en icore, nunca automáticamente, y **no** es un sustituto de `--fake`: no marca nada como aplicado, corrige el nombre con el que se registró lo que sí se aplicó. **Test permanente:** `core.tests.test_verificar_esquema_migraciones` (`ColisionDeTablasTests`, `FilasSinArchivoTests`, `TablasHuerfanasTests`, `ClasificarFilasSinArchivoTests`, `ClavesConocidasTests`, `MigracionesPendientesTests`, `ComandoTests.test_una_renumeracion_de_verdad_si_lo_frena`, `ComandoTests.test_una_fila_sin_archivo_suelta_avisa_y_deja_arrancar`, `ComandoTests.test_solo_reporte_no_corta_aunque_haya_hallazgos`, `EntrypointTests`, `ScriptDeIcoreTests`).

### OPS-02 · `crear_usuarios_sistema` y los seeds demo con claves conocidas viajan en el release
**Severidad:** MEDIA (era ALTA: requiere que un operador con `exec` lo corra) · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A8-03, V6-NEW-06, G1c-18 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `users/management/commands/crear_usuarios_sistema.py` (viaja en `origin/main`: `.gitattributes` solo excluye docs y auditorías; nadie lo invoca); deja `admin`/`admin123` superusuario y `admin1..3`/`admin123` en el rol **«Administrador» real** (`rbac.ROL_ADMINISTRADOR`, protegido con todas las capacidades, `seed_rbac.py:73-83`), con `is_staff=True`, y les resetea la clave si existen. `seed_relevamientos_periodo_demo.py:16-49` (`set_password` sobre el `--username` que se pase, default `territorial_demo`/`demo1234`, `is_active=True`); `seed_becas_demo_mobile.py:320-325` (`terri123`); `legajos/management/commands/setup_roles_contactos.py` (10 grupos `Psicologo`, `Director`, … sin `RolMeta`, con permisos de modelo sobre `historialcontacto`; `seed_rbac:56-64` los convierte en roles con `RolMeta` activa: roles fantasma) y `setup_groups.py` (`Responsable`). Refutado: `seed_perf`, `prepare_perf_http_probe` y `seed_aceptacion_reportes` ya exigen base efímera.
- **Propuesta:** `git rm users/management/commands/crear_usuarios_sistema.py`, `setup_roles_contactos.py` y `setup_groups.py`; helper `core/management/guardas.py::exigir_entorno_demo()` = `if not (settings.DEBUG or os.environ.get("CHACO_PERMITIR_SEED_DEMO") == "1"): raise CommandError(...)` al inicio de `seed_becas_demo_mobile`, `seed_relevamientos_periodo_demo` y `seed_busqueda_ciudadanos_demo`, que además no deben resetear la clave de usuarios existentes. **No** usar `settings.ENVIRONMENT` (icore DEV vale `prd`; QA lo pisa a `prd`, OPS-12). Contar con P-09 las cuentas que ya existan en PRD.
- **Tests:** `call_command("crear_usuarios_sistema")` → `CommandError: Unknown command`; cada seed demo con `DEBUG=False` y sin la variable → `CommandError`.

**Resolución:** ✅ Resuelto en el PR 3 de la Ola 3 (Cambio 171), 07-oct-2026 — los tres comandos **se borraron**, que es
el remedio que el Cambio 28 ya había elegido para `crear_superadmin` y por el mismo motivo: cualquier variante que los
deje creando usuarios vuelve a poner una credencial por defecto en un ambiente servido. `crear_usuarios_sistema` era
además el peor de los tres —`admin`/`admin123` superusuario y `admin1..3` en el rol «Administrador» real, **reseteando
la clave si ya existían**—. Los tres seeds de demo que quedan pasan por `core/management/guardas.py::exigir_entorno_demo()`
(`DEBUG` o `CHACO_PERMITIR_SEED_DEMO=1`, **no** `settings.ENVIRONMENT`), y `seed_relevamientos_periodo_demo` dejó de
pisarle la clave —y de reactivar— a un `territorial_demo` que ya exista: ahora avisa y sigue. **Lo que la ficha no
pedía y es lo que impide que vuelva por otra puerta:** dos ratchets AST sobre `*/management/commands/*.py`. Uno exige
que todo comando que llame a `set_password`/`create_user`/`create_superuser` llame también a `exigir_entorno_demo`, con
un allowlist de cuatro archivos y su motivo escrito; el otro es el de G1c-12. Sin ellos, borrar cuatro archivos no
impide que mañana el quinto haga lo mismo. **Desvío medido:** la ficha nombraba tres comandos con guarda propia de base
efímera (`seed_perf`, `prepare_perf_http_probe`, `seed_aceptacion_reportes`) y el ratchet confirmó los tres, así que
entraron al allowlist en vez de recibir la guarda de demo —la suya es más fuerte—. `docs/internal/onboarding.md` dejó
de mandar a leer `setup_groups.py` para saber los roles (apuntaba a un archivo borrado y además la respuesta era
equivocada: los roles salen del `CATALOGO` de `core/rbac.py`). **Pendiente operativo, no de código:** contar con P-09
las cuentas que hayan quedado en PRD (`admin`, `admin1..3`, `territorial_demo`) y darlas de baja o cambiarles la clave;
borrar el comando no borra lo que ya creó. **Test permanente:** `core.tests.test_comandos_peligrosos`
(`ComandosBorradosTests.test_los_cuatro_comandos_peligrosos_ya_no_existen`,
`SeedsDemoExigenEntornoDeDemoTests.test_sin_debug_ni_variable_los_tres_cortan`,
`SeedsDemoExigenEntornoDeDemoTests.test_no_le_cambia_la_clave_ni_reactiva_a_un_usuario_que_ya_existe`,
`NingunComandoSiembraCredencialesSinGuardaTests.test_todo_comando_que_toca_claves_tiene_su_guarda`).

### OPS-04 · `/health/` siempre 200 y tapa `health_check.urls`
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO con test (`A805HealthTests`: `resolve('/health/')` → `healthcheck.views.basic`; con la DB caída responde `200 OK`) · **Origen:** A8-05 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-O04

**Ampliado por RS-R6-06 y RS-R5-09 punto 2 (04-oct-2026, duplicados):** pasa a la **Ola R** (PR R-15). Consecuencia operativa que la ficha no decía: `/health/` es el gate de éxito **y** del rollback automático de `scripts/deploy_prod.sh` (`:15` `HEALTH_URL`, `:18` `ROLLBACK_ON_FAIL`, `:78-90` `health_check()`, `:92-109` `rollback`), así que ese rollback nunca se dispara por un esquema roto ni por un `collectstatic` fallido. El cambio de `HEALTH_URL` a `/health/ready/` y los `post_deploy_checks()` están en RED-59; test extra `core/tests/test_scripts_deploy.py::DeployProdTests.test_deploy_prod_usa_ready` (lee el script y afirma que el default termina en `/health/ready/`).

- **Ubicación:** `config/urls.py:40` (gana sobre `:59`, `health_check.urls`, inalcanzable); sondas de compose y de `docker/k8s/bootstrap-initcontainer.yaml` apuntan a `/health/`; `nginx.conf:41,119` la expone sin login.
- **Propuesta:** `/health/` queda como liveness sin I/O (no romper las sondas de ECOM); agregar `/health/ready/`: `connection.ensure_connection(); with connection.cursor() as c: c.execute("SELECT 1")` y, si `ENVIRONMENT=="prd"`, `caches["sessions"].get("health")` (acotados por los timeouts ya configurados); 503 con JSON `{db, cache}` si algo falla. Borrar `path("health/", include("health_check.urls"))` y sacar `health_check*` de `INSTALLED_APPS` y `requirements.txt` (OPS-13). No publicarla en nginx. D-O04: usarla como readinessProbe (default: solo monitoreo; nunca como liveness: con una sola base, sacaría todos los pods a la vez).
- **Tests:** `/health/ready/` → 503 con `ensure_connection` parcheado; `/health/` → 200 igual.

**Resolución:** ✅ Resuelto en el PR R-15 (Cambio 153), 06-oct-2026 — `/health/` queda **idéntica** (liveness sin I/O: ninguna sonda de compose, de k8s ni de ECOM cambia) y se agrega `healthcheck.views.ready` en `/health/ready/`, que hace `ensure_connection` + `SELECT 1` y, solo con `ENVIRONMENT=="prd"`, `caches["sessions"].get("health")` —en prd las sesiones viven en Redis, así que sin cache nadie se loguea aunque la base conteste—. Devuelve `{"db": …}` / `{"db": …, "cache": …}` con 200 o **503**, y en el 503 el valor es el **nombre de la clase** de la excepción y nada más (`"OperationalError"`): la vista es pública y sin sesión, y el mensaje del motor trae el host interno de la base y, en un 1045, el usuario con el que Django se conecta. El detalle entero va a `logger.exception`. Se retiró el `path("health/", include("health_check.urls"))` de `config/urls.py` —que el include de `healthcheck.urls` tapaba, así que sus vistas eran inalcanzables—. **El paquete sigue en `INSTALLED_APPS` y en `requirements.txt`, contra lo que decía la ficha.** Sacarlo se probó y lo frenó la guarda de OPS-01 en el CI de este mismo PR: `django-health-check` tiene dos migraciones aplicadas (`db.0001_initial` y `health_check_db.0001_initial`) y la tabla `health_check_db_testmodel` en todos los ambientes donde ya corrió. Sin el paquete, esas dos filas quedan sin archivo y esa tabla sin modelo, que es exactamente lo que `verificar_esquema_migraciones` aborta: el entrypoint dejaría de arrancar en icore, en testing y en PRD. Retirar el paquete es **OPS-13** y tiene que venir con esa limpieza (borrar la tabla y las dos filas), que es información que esta ficha no tenía y ahora sí. **D-O04 aplicada:** no se declara como readinessProbe en ningún manifiesto ni se publica en nginx (cae en el `location /`). La consecuencia operativa del «Ampliado por» la cierra RED-59: `HEALTH_URL` de `scripts/deploy_prod.sh` pasa a `/health/ready/`. `core/tests/test_superficie_publica.py` suma la ruta nueva a la allowlist pública con su motivo (18 y 32 en los ratchets). **Test permanente:** `healthcheck.tests.test_ready` (`HealthLivenessTests`, `HealthReadyTests`) y `core.tests.test_scripts_deploy.DeployProdTests.test_deploy_prod_usa_ready`.

### OPS-05 · `read_timeout=10 s` también corta `migrate`
**Severidad:** MEDIA · **Estado:** PLAUSIBLE (la 0072 ya pasó en PRD sin cortarse) · **Origen:** A8-06 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-O05 (choca con el Cambio 91)
- **Ubicación:** `config/settings.py:291`. En MySQL/MariaDB `can_rollback_ddl=False`: una migración cortada deja el esquema a medias (un ALTER que espera el metadata lock > 10 s → error 2013 → el ALTER se aplica igual en el servidor).
- **Propuesta:** `"read_timeout": int(os.environ.get("DB_READ_TIMEOUT", "10"))` (ídem `write_timeout`); en el entrypoint, `DB_READ_TIMEOUT="${MIGRATE_DB_READ_TIMEOUT:-600}" DB_WRITE_TIMEOUT=… python manage.py migrate --noinput`. Mantener migraciones de datos por lotes (patrón 0072) y, en índices, `ALGORITHM=INPLACE, LOCK=NONE` vía `RunSQL` con `state_operations`. El Cambio 91 dice «no se sube el `read_timeout`, es el límite acordado con ECOM»: D-O05 (default: subirlo solo para `migrate`).
- **Tests:** settings con `DB_READ_TIMEOUT=600` → `OPTIONS["read_timeout"] == 600`; ensayo en `scripts/perf_mysql` de un `AddIndex` sobre Formulario con `read_timeout=1`.

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — `config/settings.py` lee `DB_READ_TIMEOUT`
y `DB_WRITE_TIMEOUT` del entorno con **default 10**, que es el límite acordado con ECOM y el que sigue valiendo para el
tráfico (D-O05: se sube solo para `migrate`). El `docker-entrypoint.sh` pone las dos en **1200** —no 600— **solo** en la
invocación del bloque de migraciones y sembrado, sin exportarlas: verificado en un contenedor efímero, el proceso del
server las ve vacías. **Desvío (medido):** la ficha proponía 600 y a la vez un `GET_LOCK(…, 900)` en OPS-07, y los dos
números no conviven — `SELECT GET_LOCK` es una consulta que **bloquea**, así que con `read_timeout=600` el cliente se
cae con un 2013 a los 600 s esperando un candado de 900. El candado queda en 900 (lo que dice la ampliación de OPS-07)
y el timeout en 1200; `bootstrap_lock` además **aborta con el motivo** si la espera no entra en el `read_timeout`, en
vez de morir con un 2013 que no explica nada. El ensayo del `AddIndex` con `read_timeout=1` no entró: lo que hace falta
demostrar —que el `ALTER` se aplica igual después del corte del cliente— ya está medido en RED-14/RED-17 y el banco de
`scripts/perf_mysql/` no agrega información sobre eso. **Pendiente que esta ficha habilita:**
`.github/ci/settings_roundtrip.py` (el settings de CI que sube el `read_timeout` para el job `Migrate ida y vuelta`)
puede retirarse recién **cuando este PR esté en `development`**: el job corre `manage.py` también en el árbol de la
base, y hasta entonces ese árbol no entiende `DB_READ_TIMEOUT`. **Test permanente:**
`core.tests.test_settings_entorno_y_timeouts.TimeoutsDeLaConexionTests` y
`core.tests.test_entrypoint_bootstrap.EntrypointBootstrapTests.test_las_migraciones_corren_con_el_read_timeout_levantado`.

### OPS-07 · Bootstrap frágil
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A8-09, V6-NEW-04 · **Ola:** 3 · **Esfuerzo:** S

**Ampliado por RS-R5-07 (04-oct-2026):** lo que corre en carrera entre réplicas no es solo el seed: es el **`migrate`** mismo (reproducido en MariaDB 11.8: dos `migrate` en paralelo, uno muere con 1050/1060). El comando `bootstrap_lock` con `GET_LOCK` tiene que envolver también el `migrate` (`GET_LOCK('datanach_migrate', 900)`); el resto (un solo migrador, regla expand/contract) es RED-19 en la Ola R.

- **Ubicación:** `docker-entrypoint.sh:2`, `:22-25` (`set -eu`, sin `|| true`); `docker-compose.prod.yml:56` (`LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS=procesar_vencimientos`); `programas/management/commands/procesar_vencimientos.py:49-62` (no aísla reglas); `docs/internal/processes.md:105` dice que los opcionales «pueden fallar sin abortar el arranque» (falso: V6-NEW-04). Carrera entre réplicas si el pod web corre el bootstrap y hay más de una (ECOM usa un Job/initContainer, Cambio 78); un CSV incoherente de `seed_catalogo_siis` también impide arrancar.
- **Propuesta:** opcionales no fatales: `for c in $LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS; do python manage.py "$c" || echo "AVISO: $c falló; se sigue"; done` (alinea código y doc); en `procesar_vencimientos`, `try/except Exception` por regla con `logger.exception` y `CommandError` al final si alguna falló; para varias réplicas, `SELECT GET_LOCK('datanach_bootstrap', 600)` (MySQL y MariaDB) desde un comando `bootstrap_lock`, o documentar «réplicas > 1 ⇒ Job único».
- **Tests:** dos reglas, la primera lanza → la segunda aplica y el comando termina en `CommandError`.

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — los tres puntos. **(1) Opcionales no
fatales:** `run_optional_management_commands` corre cada comando de `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` por separado y
el que falla deja `AVISO: el comando opcional <x> fallo; el arranque sigue` en stderr. Los **obligatorios** siguen
siendo fatales a propósito y ahora están en otra función: sin roles ni capacidades el sistema arranca pero no sirve.
`docs/internal/processes.md` dejó de prometer lo contrario de lo que hacía el código (era V6-NEW-04) y ahora dice
también qué sí se puede poner en cada lista. **(2) `procesar_vencimientos`:** cada regla corre aislada (`_correr_regla`),
lo que falla va con traceback a `logger.exception` y a stderr, y el comando **igual termina en `CommandError`** al
final nombrando las que fallaron — el rojo del cron es la única notificación que hay, lo que cambió es que ahora se
pone rojo después de correr todo lo que podía. Se aisló también el `pendientes().count()`, que la ficha no nombraba y
corre fuera de la `atomic`. **(3) El candado:** comando nuevo `manage.py bootstrap_lock`, que toma
`GET_LOCK('datanach_bootstrap', 900)` y corre con él una lista de `--comando`. **Dos desvíos, los dos code-first:**
(a) la ficha pedía `datanach_bootstrap` para los seeds y la ampliación `datanach_migrate` para el `migrate`, y **dos
candados distintos no sirven**: una réplica sembraría contra el esquema que otra está migrando, y la guarda de esquema
de OPS-01 abortaría el arranque por una foto a medias que no es un problema real. Va **un solo candado** envolviendo
guarda + `migrate` + sembrado; `collectstatic` queda afuera porque no toca la base y no tiene sentido hacer esperar a
las demás réplicas mientras se comprime CSS. (b) La espera del candado tiene que entrar en el `read_timeout` (ver
OPS-05): el comando lo verifica y aborta con el motivo en vez de morir con un 2013. `GET_LOCK` es de la **conexión**,
así que un pod matado a mitad del bootstrap lo suelta solo —es la razón de usarlo y no una fila de control—.
**Ronda 2 de la revisión:** eso mismo lo volvía inútil para el sembrado. `seed_datos_base` llama a `loaddata`, que
termina con `connections[alias].close()` —un workaround de Django para un bug viejo de MySQL (#7572)—, así que el
candado tomado sobre `connections["default"]` **se soltaba a mitad del sembrado**: con dos arranques simultáneos
sobre una base vacía, el segundo lo tomaba y sembraba en paralelo, y los dos imprimían el aviso de candado perdido
inclusive con **un solo** contenedor. El candado pasó a una conexión **dedicada**, que ningún comando toca y que
solo se cierra al final; y el aviso distingue ahora los dos casos que antes mezclaba —que el candado lo tenga **otro**
`CONNECTION_ID` (entró un segundo bootstrap) y que no lo tenga nadie (se cayó la conexión dedicada)—, así que el falso
positivo con un solo contenedor desapareció. Medido contra `mariadb:10.11`: con el patrón viejo un tercero tomaba el
candado después del `close()` (devuelve 1) y con el nuevo no lo consigue (devuelve 0); y dos bootstrap en paralelo
sobre una base vacía ahora serializan —uno aplica las 138 migraciones y el otro no encuentra nada que aplicar—. No reemplaza a
la regla de RED-19 (`RUN_MIGRATIONS=false` + Job único), y `docker/k8s/README.md` lo dice. Verificado en contenedores
efímeros: el entrypoint con un `python` de mentira (seis casos: default, `RUN_MIGRATIONS=false`, `SKIP_SCHEMA_GUARD`,
opcional que falla, `ENVIRONMENT=prd`, guarda de gevent) y un `migrate` completo desde base vacía contra
`mariadb:10.11` a través del candado. **Ronda 3 de la revisión:** la conexión dedicada tiene una contracara —queda **ociosa** todo el bootstrap, 141-218 s
medidos—, y si el servidor la cierra en el medio (un `wait_timeout` global apretado, un `KILL`, un firewall que corta
ociosos) el `SELECT IS_USED_LOCK` del `finally` levantaba un 2013: el comando salía con **exit 1 sobre un esquema
correcto** —Job en `Failed`, initContainer en CrashLoop— y encima el aviso escrito justo para ese caso no llegaba a
imprimirse. Reproducido por el revisor con `SET GLOBAL wait_timeout=30` (139 migraciones OK, exit 1) y acá con el
mecanismo aislado contra `mariadb:10.11`: con `wait_timeout` global en 2 s y 5 s de bootstrap, sin el arreglo da
`OperationalError (2013)` y con él el candado sobrevive y se suelta bien. Dos mitades: **que no se caiga** —la sesión del
candado pide `wait_timeout = 28800`, que es el default de fábrica de los dos motores, así que no se pide nada
extraordinario, solo que un global apretado por el DBA no la mate; si el usuario no puede tocar la variable, avisa y
sigue— y **que caerse no haga fallar nada** —`_soltar_candado` atrapa `OperationalError`/`InterfaceError`, emite el AVISO
de que el servidor liberó el candado solo y **no toca el exit code**; el `close()` final también, porque cerrar una
conexión ya cerrada puede levantar—. Lo que sí sigue mandando es el error del comando: si el `migrate` falló, el que sale
es ese. **Test permanente:** `core.tests.test_bootstrap_lock.BootstrapLockTests`,
`core.tests.test_motor_real.CandadoDeBootstrapTests`, `CandadoSobreviveAlLoaddataTests` y
`CandadoConLaConexionMuertaTests` (`@tag("mysql")`; esta última mata la conexión del candado con un `KILL` de verdad y
verifica que el bootstrap sale en 0, y aprieta el `wait_timeout` global para fijar que la sesión sobrevive),
`core.tests.test_procesar_vencimientos_aislado.ReglasAisladasTests` y
`core.tests.test_entrypoint_bootstrap.EntrypointBootstrapTests`.

### TST-01 · La CI no prueba MariaDB
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO-AJUSTADO; **la tesis central de A8-07 está refutada**: el job «Ephemeral MySQL Redis Contract» (`pr-performance.yml` → `ephemeral-stack-contract`, `mysql:8.0`) corre `migrate` real en cada PR (log del run 36751292857: `legajos.0007`, `programas.0047`, `0048`, `0072`, `users.0023` → OK) · **Origen:** A8-07 · **Ola:** 3 · **Esfuerzo:** M · **Decisión:** pregunta H-01 (versión MariaDB)

**Ampliado por RS-R2-03 parte (a), RS-R2-07 punto 1, RS-R5-11 y RS-R7-05 capa 2 (04-oct-2026, duplicados):** pasa a la **Ola R** (PR R-11). Lo que agregan: (1) el caso concreto de un test ya escrito que **nunca corre**: `programas/tests/test_becas_models.py::UUIDExternosMySQLTests` da `OK (skipped=1)` en todos los jobs; se marca `@tag("mysql")` y entra al paso `--tag mysql`; (2) migraciones sobre datos: lo resuelve el job `migration-roundtrip` (RED-17), que comparte los servicios de esta matriz; (3) carrera real del cupo: `TransactionTestCase` `@tag("mysql")` con dos hilos sobre `aprobar_o_poner_en_espera` con un lugar libre → un APROBADO y una `ListaEspera` (RED-67); (4) en el paso `--tag mysql` corren también los casos de SQL compilado de RED-07, RED-08 y RED-09 contra el motor real.

- **Lo que sí falta:** (1) la rama `features.has_native_uuid_field` (solo MariaDB 10.7+, `legajos/0007:57-58`: el bug de septiembre); (2) ningún test de la suite corre sobre MySQL/MariaDB (solo probes de performance): `KeyTransform`, `Trunc*`/`CONVERT_TZ` y UUID con guiones sin red; (3) migraciones sobre datos (el migrate arranca de base vacía).
- **Propuesta:** matriz en `ephemeral-stack-contract`: `mysql:8.0` y `mariadb:<versión de ECOM; 10.11 por default hasta confirmar con P-11>`, más un paso `python manage.py test --tag mysql` (sin `PYTEST_RUNNING`, usa la base del servicio) con 3-4 tests marcados: guardar y buscar por `token_publico`/`client_uuid`, `q_uuid_en_texto`, un `JSON_EXTRACT` con clave numérica y dashboard sin `Trunc*`; sumar los de DIS-01 (`__date`) y SIIS-01 (`UniqueConstraint` con NULL).
- **Verificación:** el job falla con un `__date` sobre DateTimeField introducido a propósito en una rama de prueba. Costo: 2-4 min más de CI.

**Resolución:** ✅ Resuelto en el PR R-11 (Cambio 130), 05-oct-2026 — job **`Motor real (<motor>)`** en `pr-performance.yml`
con la matriz `mariadb:10.11` / `mariadb:11` / `mysql:8.0` corriendo `manage.py test --tag mysql` **sin `PYTEST_RUNNING` y
sin `DJANGO_SYNCDB_PROJECT_APPS`** (o sea: migraciones reales sobre el motor real, que era el otro punto de la ficha), y
`core/tests/test_motor_real.py` nuevo con 15 casos marcados, más el `@tag("mysql")` en el test que nunca corría
(`UUIDExternosMySQLTests.test_columnas_uuid_externas_admiten_36_caracteres`). Cierra los cuatro «Ampliado por»: el test
saltado entra (1), las migraciones se aplican de verdad —el roundtrip con datos sigue siendo RED-17/R-13, que comparte
estos servicios (2)—, la **capa 2 de RED-67** corre la carrera real del cupo con dos hilos (3) y los casos de RED-07/08/09
se ejecutan contra el motor además de compilarse (4). **Tres desvíos, todos medidos:**
(a) **la imagen oficial de MariaDB carga las tablas de zona horaria** y la de `mysql:8.0` las trae de fábrica, al revés de
lo que suponía el README §0: con ellas `CONVERT_TZ` funciona y la familia de bugs que motiva la matriz **no se manifiesta**,
así que el servicio lleva `MARIADB_INITDB_SKIP_TZINFO` y la matriz queda asimétrica a propósito (MariaDB = ECOM sin tablas;
MySQL = icore con ellas), fijado por `test_mariadb_corre_sin_las_tablas_de_zona_horaria_como_ecom`;
(b) el job es **nuevo** y no una matriz sobre `ephemeral-stack-contract`, porque ese nombre es un check obligatorio del
ruleset y una matriz lo partiría en tres contextos distintos, rompiendo el gate de RED-20;
(c) `UniqueConstraint(condition=…)` quedó caracterizada acá (DIS-02) porque es exactamente lo que SQLite esconde.
`SIIS-01` no entró: su `UniqueConstraint` con NULL todavía no existe (Ola 1). **El job todavía no es obligatorio**: entra al
ruleset cuando tenga corridas suficientes (la lista exacta vive en `core/tests/test_gates_ci.py::CHECKS_OBLIGATORIOS`).
Medido: 1 min 45 s por pata en MariaDB y 3 min 10 s en MySQL de punta a punta, casi todo migraciones.
**Test permanente:** `core/tests/test_motor_real.py::UuidEnElMotorRealTests.test_el_link_publico_encuentra_una_fila_restaurada_con_la_otra_forma`

### TST-02 · Configuración sin tests de comportamiento; tests que no prueban nada
**Severidad:** MEDIA · **Estado:** CONFIRMADO · **Origen:** A8-14 · **Ola:** 3 · **Esfuerzo:** M

**Ampliado por RS-R1-09, RS-R1-13, RS-R2-08 y RS-R7 (04-oct-2026):** pasa a la **Ola R** (PR R-20) y suma S-M (4 h). (1) Ítem 3 del Top-5 con el detalle cerrado (RS-R1-09: `generar_alertas` 0 %, `legajos/services/alertas.py` 35 %): `legajos/tests/test_generar_alertas.py::GenerarAlertasTests` con `test_un_ciudadano_sin_contacto_reciente_genera_su_alerta`, `test_dos_pasadas_seguidas_no_duplican_la_alerta`, `test_la_alerta_que_ya_no_aplica_se_desactiva`, `test_un_ciudadano_sin_legajo_no_rompe_la_pasada` y `test_el_envio_por_websocket_se_llama_una_vez_por_alerta_nueva` (`patch` de `_enviar_notificacion_alerta`); el de `assertNumQueries` va con PERF-20 (Ola 4). (2) Configuración, medido (RS-R1-13): 3 tests para 30 rutas, `configuracion/views/programas.py` 22 %; mínimo en R: `configuracion/tests/test_wizard_programas.py::WizardDeProgramaTests` (`test_los_cuatro_pasos_crean_el_programa_con_todo`, `test_entrar_al_paso_3_sin_haber_hecho_el_1_redirige`, `test_sin_config_administrar_los_ocho_pasos_dan_403`, `test_activar_un_programa_sin_naturaleza_avisa_y_no_activa`) y `configuracion/tests/test_secretarias.py::BorradoDeSecretariaTests`; es el piso que SEC-07 necesita. (3) Los comandos sin test `completar_casos_renaper`, `validar_casos_siis` y `sincronizar_programas_siis` están en RED-32. (4) Los «tests que faltan» que midió la prueba de mutación (bordes y particiones) están en RED-25 a RED-29, RED-66 a RED-70 y RED-87.

**⚠ Actualizar (03-oct-2026):** el ítem (2) del Top-5 (`seed_datos_base` idempotente y respetuoso del ABM) ya existe: `users/tests/test_seed_datos_base.py` (#508). En el mapa de cobertura, `seed_datos_base` y `crear_programas` ya tienen test.

**⚠ Hallazgo nuevo (06-oct-2026, ronda 2 del PR R-11): cinco módulos de `programas/tests/` solo pasan si otro módulo
corrió antes.** Medido módulo por módulo sobre los 77 de `programas/tests/` (`manage.py test programas.tests.<módulo>`):
`test_becas_handlers_inline` (12 fallas), `test_pausa_form` (6), `test_becas_cupo_diseno` (4),
`test_becas_convocatoria_subsegmentos` (3) y `test_pausas` (1) fallan **corridos solos**, casi todas con `403 != 200`.
Causa única: desde **RED-56** (Cambio 123) los guards de Becas fallan cerrados —sin la fila `Programa` con `codigo="BECAS"`,
`_programa_o_denegar` levanta `PermissionDenied` **incluso para un superusuario**— y estos módulos no la siembran: pasan
porque un módulo anterior corre `seed_becas` y deja el Programa en la clave de proceso `programas:becas`, que **sobrevive
al rollback de la base** (LocMem, nadie la limpia entre tests). Con `manage.py test --shuffle` la suite se pone roja: 21
fallas con la semilla 1234 y 26 con la 777, todas en esos cinco módulos. El arreglo es el mismo que se aplicó en R-11 a
`test_becas_convocatorias_diseno` (Cambio 130): `cache.clear()` + `call_command("crear_programas")` en el `setUp`. Entra en
el **PR R-20** junto con el resto de TST-02; mientras tanto `--shuffle` no sirve como gate.
- **Ubicación:** `configuracion/views/*.py` (~942 LOC; `models/`, `services/` y `migrations/` vacíos); único test que toca rutas `configuracion:` es `users/tests/test_menu_rbac.py` (solo el menú); `configuracion/tests/test_services_actividades.py:5-6` y `tramites/tests/test_package_exports.py:6` (`assertTrue(True)`); el wizard crea `Programa` (`configuracion/views/programas.py:197`) y el ABM borra secretarías (`secretaria.py:108,218`) sin tests.
- **Propuesta:** borrar los dos `assertTrue(True)`; tests de RBAC de cada vista (sin `config.administrar` → redirect/403), del wizard de 4 pasos con estado en sesión, de `programa_cambiar_estado` (activar sin naturaleza → error) y del borrado de secretaría con subsecretarías (mensaje y no se borra).
- **Verificación:** coverage de `configuracion/` de ~0 % de vistas a > 60 %.
- **Top-5 de tests faltantes por valor (V6):** (1) DAT-01; (2) `seed_datos_base` idempotente y respetuoso del ABM (OPS-06); (3) `generar_alertas`/`AlertasService` con `assertNumQueries` y dos pasadas (PERF-20/LEG-01; el servicio no tiene ningún test y corre cada hora); (4) `procesar_vencimientos` con una regla que falla y un `FINALIZANDO` dentro de la gracia (OPS-07, G1-04); (5) contrato de operación: `django.request` llega a un `StreamHandler` y `/health/ready/` → 503 con la DB caída (OPS-03, OPS-04).
**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026 — las cuatro patas. (1) **Los cinco
módulos que solo pasaban si otro corría antes** heredan de `programas/tests/base_becas.BecasPantallaTestCase`, una
sola definición del `cache.clear()` + `crear_programas` que el Cambio 130 había dejado copiado en
`test_becas_convocatorias_diseno` (ese módulo pasa a heredarla también). Verificado como pide la ficha: los **77
módulos de `programas/tests/` corridos uno por uno** dan 0 en rojo —antes, 12 + 6 + 4 + 3 + 1 = 26 fallas— y
`--shuffle` queda en verde con las dos semillas medidas (1234 y 777, que daban 21 y 26). (2) `generar_alertas`, que
corre **cada hora** y estaba al 0 %, estrena `legajos/tests/test_generar_alertas.py` (8 tests): genera, **no duplica
en dos pasadas**, desactiva lo que ya no aplica sin apagar las ALTA, tolera un ciudadano sin legajo y avisa por
WebSocket una vez por alerta **nueva**. Cuatro mutaciones de control lo verifican. (3) Configuración estrena
`test_wizard_programas.py` (12 tests) y `test_secretarias.py` (6), y los dos `assertTrue(True)` pasan a afirmar algo
real en vez de borrarse. **Dos desvíos code-first:** el wizard lo gobierna `programa.configurar` y no
`config.administrar`, y sin capacidad el backoffice **redirige**, no da 403 (el 403 es solo para AJAX, igual que ya
se registró en RED-73). (4) **Un sexto módulo con el mismo defecto, que la ficha no tenía** —midió solo
`programas/tests/`—: `legajos.tests.test_adjuntos_robustez` fallaba solo con `4 != 3` porque el `ContentType` de
`LegajoAtencion` quedaba frío; ahora se calienta explícitamente. Barrido completo de las once apps: **0 módulos en
rojo corridos solos**. **(5) Y un séptimo, que el barrido módulo por módulo
no podía encontrar:** `legajos.tests.test_consulta_renaper_encoding.RenaperTestModeTests` pasa corrido solo —en el
orden alfabético el acoplamiento juega a favor— y falla con la semilla aleatoria del CI (2529168576), porque
`consultar_datos_renaper` cachea por DNI en LocMem (de proceso) y el segundo test pegaba en la caché sin llamar al
servicio; en el orden de siempre eso dejaba al otro test **pasando por el motivo equivocado**. Lo encontró el job
`Orden y paralelo` en su **primera** corrida, que es exactamente para lo que está. El `assertNumQueries` de la pasada sigue siendo PERF-20 (Ola 4). El gate de orden quedó como
el job **no bloqueante** `Orden y paralelo` y no como test estructural: el detector AST que se probó primero marca
10 módulos que en realidad pasan solos, y un gate que miente es peor que no tenerlo.
**Test permanente:** `programas/tests/test_aislamiento_modulos.py::ModulosMedidosTests.test_todas_las_clases_de_los_modulos_medidos_heredan_el_mixin`
(y `MecanismoDelGuardTests` ×3, `MixinSiembraTests` ×2, `legajos/tests/test_generar_alertas.py::GenerarAlertasTests`
×8, `configuracion/tests/test_wizard_programas.py::WizardDeProgramaTests` ×7 y `::CambiarEstadoDePrograma` ×5,
`configuracion/tests/test_secretarias.py::BorradoDeSecretariaTests` ×6).

- **Mapa de cobertura (confirmado por grep):** sin ningún test: `legajos.services.alertas` (268 LOC, cron horario), `linking`, `ciudadanos`, `contactos`, `programas`, `filtros_usuario`, `ml_predictor`; `users.services.listing` y `filter_config`; `core.services.cache`; vistas de `configuracion`. Comandos sin test: `generar_alertas`, `sincronizar_programas_siis` (solo el servicio), `seed_datos_base`, `crear_programas`, `completar_casos_renaper`, `validar_casos_siis`, `import_users_from_csv`. **Sí tienen test** (corrección a A8): `reenviar_siis_pendientes` y `enviar_casos_siis` (`test_siis_envio.py:624-678`), `cerrar_espera_colgada` (`test_cupo_espera_reglas.py:263`).

### G1c-12 · `debug_ciudadanos` vacía el Redis compartido
**Severidad:** MEDIA · **Estado:** CONFIRMADO (código y librería) · **Origen:** G1c-12 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `legajos/management/commands/debug_ciudadanos.py:36-37` (`cache.clear()`; además imprime DNI y nombre de 3 ciudadanos); en `prd`, `default`, `sessions` y `CHANNEL_LAYERS` usan el mismo `REDIS_URL` (`settings.py:312-337`, `:381-385`); `django_redis` 5.4.0 `DefaultClient.clear()` → `flushdb()`.
- **Escenario:** un «debug» desloguea a todo el backoffice, corta los pasos en curso de la inscripción pública (viven en sesión) y borra los grupos de Channels.
- **Propuesta:** borrar el comando (no lo usa nada ni ningún documento) o reemplazar `cache.clear()` por `CiudadanosService.invalidate_ciudadanos_cache()`; defensa en profundidad: sesiones y channel layer en otra DB lógica de Redis (PERF-10).
- **Test:** `call_command("debug_ciudadanos")` con `patch("django.core.cache.cache.clear")` → `assert_not_called` (o `Unknown command` si se borra).

**Resolución:** ✅ Resuelto en el PR 3 de la Ola 3 (Cambio 171), 07-oct-2026 — **se borró el comando**, que es la primera
opción de la propuesta. No lo invocaba nada: ni el entrypoint, ni `docker/k8s/cronjobs.yaml`, ni `chaco-cron.sh`, ni
ningún documento (verificado con un barrido del repo entero). La segunda opción —cambiar `cache.clear()` por
`CiudadanosService.invalidate_ciudadanos_cache()`— se descartó por dos motivos: no arregla la otra mitad del hallazgo
(el comando imprimía DNI y nombre de tres ciudadanos, que es un volcado de datos personales a una terminal), y
`legajos/services/ciudadanos.py` está tomado por el PR 2 de esta misma ola. **Lo que queda de pie en vez del archivo:**
`core.tests.test_comandos_peligrosos` barre con AST **todos** los `*/management/commands/*.py` y falla si alguno vuelve
a llamar `cache.clear()`; el único permitido es `seed_perf`, que no puede correr fuera de una base efímera. La defensa
en profundidad que nombra la propuesta —sesiones y channel layer en otra DB lógica de Redis— **no entra acá**: es
PERF-10 (Ola 4) y depende de H-06, la configuración del Redis de ECOM. **Test permanente:**
`core.tests.test_comandos_peligrosos` (`ComandosBorradosTests.test_los_cuatro_comandos_peligrosos_ya_no_existen`,
`NingunComandoVaciaElCacheCompartidoTests.test_ningun_comando_llama_a_cache_clear`).

## BAJA

### DAT-02 · El admin de Django borra casos y relevamientos con su auditoría
**Severidad:** BAJA (era MEDIA: solo un superusuario borra desde `/admin/` y la confirmación lista la cascada) · **Origen:** A8-12; aporte de G1c-10 · **Ola:** 3 · **Esfuerzo:** S
- **Propuesta:** `has_delete_permission → False` en `RelevamientoAdmin`, `FormularioAdmin`, `TracaFormularioAdmin` y `ListaEsperaAdmin`; `disable_action("delete_selected")`; `readonly_fields` en los campos de estado de `FormularioAdmin` (`estado`, `validado_renaper`, `identidad_forzada`, `origen_validacion`, `datos_siis`, `data`: hoy se editan sin traza) y en el contador de `CupoSegmentoAdmin`. Con DAT-01 se cubren también `PreguntaGlobalAdmin`/`RequisitoNativoAdmin`.

### DAT-03 · `Formulario.dni_titular` se puede desincronizar del DNI real
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Origen:** A8-19 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/models/__init__.py:2650-2668` (`_dni_titular_actual`); edición de `Ciudadano.dni` en Legajos sin propagar (G1c-08 muestra que se puede cambiar el DNI de un titular).
- **Escenario:** se corrige un DNI mal tipeado en el legajo; el DNI erróneo sigue ocupado en la convocatoria y bloquea a su verdadero titular en el link.
- **Propuesta:** en el servicio de edición de ciudadano (o `Ciudadano.save()`), si cambia `dni`, `Formulario.objects.filter(ciudadano=self).update(dni_titular=self.dni[:20])`; opcional: comando de reconciliación por lotes.
- **Test:** cambiar `Ciudadano.dni` y verificar `dni_titular` de sus formularios.

### DAT-05 · El Excel del padrón reemplazado queda en `media/`, y `quitar_padron_propio` lo borra antes del commit
**Severidad:** BAJA · **Origen:** A8-22, A1-20 (parte Excel), V6-NEW-05 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/padron.py:325-331` (reasigna el `FileField` sin borrar el anterior: cada recarga deja otro Excel con DNI, nombre y nacimiento de miles de personas, expuesto con SEC-09); `:337-346` (`quitar_padron_propio`: `padron_archivo.delete(save=False)` dentro de la transacción; si el `save` falla, la fila apunta a un archivo que ya no existe).
- **Propuesta:** `viejo = duenio.padron_archivo.name` antes de reasignar y `transaction.on_commit(lambda: storage.delete(viejo))`; igual en `quitar_padron_propio`.
- **Test:** cargar dos veces → el primer archivo no existe en el storage; `save` que falla en `quitar_padron_propio` → el archivo sigue.

### V2-NEW-05 · Un restore posterior a `legajos.0007` deja pks de legajo en hex que el ORM de MariaDB no encuentra
**Severidad:** BAJA · **Estado:** a confirmar con P-12 · **Origen:** V2-NEW-05 · **Ola:** 3 · **Esfuerzo:** S

**⚠ Actualizar (03-oct-2026):** `q_uuid_en_texto` (#515) cubre `token_publico` y `client_uuid`, no los pk de legajo: este ítem sigue igual.
- **Ubicación:** `legajos/migrations/0007_ampliar_uuid_legajos.py` normaliza una sola vez; si se restaura una base con filas en hex (dump de un motor sin UUID nativo), `LegajoAtencion.objects.get(pk=uuid)` manda guiones y no encuentra: 404 en el detalle del legajo.
- **Propuesta:** comando idempotente que re-corra `_normalizar_uuid` (misma función de la migración) y agregarlo al procedimiento de restore (memoria: «Restore de PRD deja tablas huérfanas»).

### OPS-10 · Módulos de «optimización» con DDL y `SET GLOBAL` en el release
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO (no es código muerto en runtime: `core/views/performance.py:8-9` importa `system_monitor` y `phase2_manager`, que instancian singletons al importar; `core/urls.py:55-64` expone 9 endpoints de lectura) · **Origen:** A8-13, V6-NEW-03, A5-39 (parte), G1c-13 · **Ola:** 7 · **Esfuerzo:** S-M
- **Ubicación:** `core/performance/database_optimizations.py:14-28` (`SET GLOBAL innodb_flush_log_at_trx_commit=2`…; exige SUPER, probablemente ausente en ECOM); `database_partitioning.py:41-69` (`archive_old_data` con `INSERT IGNORE` + `DELETE` fuera de transacción sobre tablas inexistentes; `CREATE INDEX IF NOT EXISTS` no es MySQL); comandos `optimize_db`, `setup_system` (además `collectstatic clear=True`), `initialize_phase2` (`--auto-create-indexes` crea índices en la base viva), `optimize_database`; `/run-phase2-tests-api/` con `IsAdminUser` (`core/views/performance.py:293-294`, autoriza por `is_staff`, contra la regla de capacidades).
- **Propuesta:** borrar esos comandos; los módulos `advanced_*`, `database_*`, `intelligent_*`, `phase2_manager`, `performance_analyzer` y `monitoring`; las vistas y URLs `phase2-*`, `system-metrics`, `alerts`, `realtime-metrics` y su bloque de `templates/core/performance_dashboard.html`. Revisar `core/tests/test_package_exports.py`. Conservar `query_observability`, `cache_utils` y `ci_external_stubs`.
- **Verificación:** suite completa, `manage.py check`, `git grep -n "phase2\|core.performance.monitoring"` vacío; V-UI si se toca el template.

### OPS-11 · `migrate --run-syncdb` en el entrypoint
**Severidad:** BAJA (hoy no-op: las 12 apps sin migraciones tienen 0 modelos, verificado con `MigrationLoader`) · **Origen:** A8-15 · **Ola:** 3 · **Esfuerzo:** S
- **Propuesta:** sacar `--run-syncdb` de `docker-entrypoint.sh:38-40` (`health_check.db` trae migraciones propias). Verificación: bootstrap sobre base vacía del banco sin `--run-syncdb` → migra OK.

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — el `migrate` del entrypoint es
`migrate --noinput` a secas. Verificación hecha tal como la pide la ficha: `migrate` completo sobre una base vacía de
`mariadb:10.11`, las 24 migraciones aplicadas OK. Lo que la ficha no decía y ahora importa más que el no-op: con la
guarda de esquema de OPS-01 en el entrypoint (PR R-15), una tabla creada por `--run-syncdb` —sin migración que la
respalde— es exactamente lo que esa guarda **aborta** en el arranque siguiente. **Test permanente:**
`core.tests.test_entrypoint_bootstrap.EntrypointBootstrapTests.test_el_migrate_ya_no_lleva_run_syncdb`.

### OPS-12 · QA no reproduce el cache de PRD y declara `ENVIRONMENT=prd`
**Severidad:** BAJA (MEDIA si se agregan guardas que lean `settings.ENVIRONMENT`) · **Estado:** CONFIRMADO con la plantilla `.env.qa.example`; lo de ECOM testing es PLAUSIBLE · **Origen:** A8-16, V6-NEW-01 · **Ola:** 3 · **Esfuerzo:** S
- **Evidencia (runtime con `ENVIRONMENT=qa` + `DJANGO_SETTINGS_MODULE=config.settings_production`):** `ENV prd | cache LocMemCache | session db | prefijo '[QA] '`. `config/settings_production.py:5` pisa `ENVIRONMENT="prd"` **después** de que `settings.py` derivó todo de la variable real: QA corre con cache y `InMemoryChannelLayer` locales al proceso (el throttle cuenta por proceso; las invalidaciones solo limpian un worker) y `diagnosticar_siis`/`diagnosticar_correo` informan mal. En icore (DEV) también vale `prd`.
- **Propuesta:** en `settings_production.py`, **no** reasignar `ENVIRONMENT` (o `if ENVIRONMENT not in ("prd", "qa"): raise ImproperlyConfigured`); en `settings.py`, `USE_REDIS = ENVIRONMENT in ("prd", "qa") or PERFORMANCE_CI or os.getenv("USE_REDIS_CACHE") == "True"` para `CACHES` y `CHANNEL_LAYERS`. QA pasa a depender de Redis (lo tiene por Channels). Ver SEC-35.
- **Test:** settings con `ENVIRONMENT=qa` + `settings_production` → `settings.ENVIRONMENT == "qa"` y backend Redis.

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — `config/settings_production.py` **ya no
reasigna** `ENVIRONMENT`, y `config/settings.py` deriva `USE_REDIS = ENVIRONMENT in ("prd", "qa") or PERFORMANCE_CI or
USE_REDIS_CACHE == "True"` para las `CACHES`. **Tres precisiones sobre la propuesta, todas medidas:** (a) en vez del
`raise ImproperlyConfigured` que la ficha ofrecía como alternativa va un **system check**, `core.W002`: con H-09
abierta —nadie confirmó todavía qué vale `ENVIRONMENT` en testing y en PRD de ECOM— un `raise` convierte un olvido de
configuración en un pod que no arranca, y eso es peor que el problema. El check corre con `manage.py check --deploy`,
que es el CI y la etapa `verify` de ECOM. (b) El `CHANNEL_LAYERS` queda atado a `ENVIRONMENT in ("prd", "qa")` y **no**
a `USE_REDIS`: el CI de performance y la escotilla `USE_REDIS_CACHE` encienden el cache, y ahí no hay websockets que
cruzar — meterlos en la misma condición le pondría un `RedisChannelLayer` al Performance Guard por nada. (c)
`SESSION_ENGINE` **no** cambia: QA sigue con sesiones en la base. Moverlas a Redis desloguea a todo el mundo en el
deploy y no es lo que la ficha pide; el `CACHES["sessions"]` de Redis queda configurado y sin uso en qa, igual que
hoy. Lo demás ya estaba bien derivado de la variable real desde siempre (el prefijo `[QA] ` del asunto de los correos,
el `ManifestStaticFilesStorage`): lo único que el override cambiaba era lo que el código lee **en runtime**.
**Consecuencia operativa, para el PM:** QA pasa a depender de Redis. Está escrito en `docs/internal/espejo-ecom.md`
como las dos preguntas que hay que hacerle a ECOM antes de espejar este release (es la pregunta H-09 más «¿el pod de
`web` llega al Redis?»), y en `.env.qa.example`. **Ronda 2 de la revisión:** el runbook decía que sin Redis «la app arranca igual porque `django_redis` no se conecta
hasta el primer uso», y **era falso**: el primer uso es el propio arranque. Medido con `ENVIRONMENT=qa` y el Redis
inalcanzable, el bootstrap terminaba en **exit 1** en `seed_becas` —un `cache.delete("programas:becas")` incondicional—
y el pod quedaba en CrashLoopBackOff, igual que el Job de migración de R-13. O sea: el cambio de ambiente de OPS-12
convertía un caché caído, que antes degradaba, en algo que **impedía arrancar**. Dos cosas: esa invalidación pasó a ser
*best-effort* (`invalidar_programa_becas`, con `WARNING` en el log y la clave venciendo sola en 300 s) —y **solo esa**:
`programa_becas()` sigue fallando fuerte, porque un ambiente sirviendo tráfico con el caché roto es una caída y taparla
la escondería—; y el runbook de `espejo-ecom.md` dejó de mentir y ahora es un **gate explícito**, con la tabla de qué pasa
en cada momento y el `cache.set/get` de verificación desde el pod. **Test permanente:**
`core.tests.test_settings_entorno_y_timeouts.EntornoDeclaradoTests` (arranca Django en un subproceso con el entorno de
QA), `EntornoDeclaradoCheckTests` y `programas.tests.test_seed_becas_cache_caido.InvalidacionToleranteTests`.

### OPS-13 · Dependencias sin uso en la imagen de producción
**Severidad:** BAJA · **Origen:** A8-17 · **Ola:** 7 · **Esfuerzo:** S

**Ampliado por el PR R-15 (Cambio 153, 06-oct-2026), medido en el CI:** sacar una app de `INSTALLED_APPS` **no es
gratis si tiene migraciones aplicadas**. Se intentó con `django-health-check` (lo pedía OPS-04) y lo frenó la guarda
nueva de OPS-01: deja dos filas sin archivo en `django_migrations` (`db.0001_initial` y `health_check_db.0001_initial`
—el `app_label` cambió entre versiones del paquete, por eso son dos—) y la tabla `health_check_db_testmodel` sin
modelo. En los ambientes donde ya corrió —icore, testing y PRD— eso **aborta el arranque del contenedor**. Así que esta
ficha tiene que incluir, por cada app que salga, el borrado de su tabla y de sus filas de `django_migrations`, como
operación de *contract* (N+2) y con su reversa declarada. Las que solo son `pip` sin app (`openai`, `httpx`, `debugpy`,
`structlog`, `gevent`…) no tienen este problema.
- **Ubicación:** `requirements.txt` (`openai==1.3.8` —subido solo para parchear CVEs de `anyio`—, `httpx`, `anyio`, `structlog`, `gevent`, `greenlet`, `django-simple-history`, `debugpy`, `pymysql` —solo en `core/performance/advanced_connection_pool.py`, OPS-10—, `django-health-check` —OPS-04—); `config/settings.py:85` (`django_extensions` en `INSTALLED_APPS` también en prod). Verificado: 0 imports.
- **Propuesta:** sacarlas; pasar `debugpy`, `django-extensions`, `django-silk`, `django-zeal` a `requirements-dev.txt`; `django_extensions` solo con `DEBUG`. Confirmar que ningún operador usa `shell_plus` en ECOM. Verificación: build de la imagen, suite completa y `pip-audit`.

### OPS-14 · Código muerto o stub; un `.py` vivo que git trata como binario
**Severidad:** BAJA (la conversión a LF conviene ya) · **Origen:** A8-18 · **Ola:** 7 · **Esfuerzo:** S

**Ampliado por RS-R4-20 y RS-R7 (04-oct-2026):** la conversión de `exportacion_reportes.py` a LF y la regla `*.py text eol=lf` se adelantan a la **Ola R** como RED-82 (con un test que impide un `.py` con CR solitario); además del diff ilegible, pylint lo omite sin fallar. El resto de esta ficha sigue en la Ola 7.

- **Ubicación:** `programas/services/exportacion_reportes.py` con fin de línea CR: `git ls-files --eol` lo marca `i/-text` (**binario**: los diffs de PR no muestran su contenido) y es código vivo (lo importan `views/dashboard_becas.py`, `reportes.py`, `reportes_becas.py`); `tramites/` (app en `INSTALLED_APPS` con `urlpatterns = []`); `docker/django/entrypoint_final.py` (dice «SISOC», corre un script inexistente); `core/services/cache.py` (sin importadores); capacidad `ciudadano.eliminar` (`core/rbac.py:41`, rol «Gestión de Ciudadanos» en `seed_datos_base.py:51`) sin ninguna vista que la use; `legajos/services/ml_predictor.py` (heurística sobre legajos que no se crean).
- **Propuesta:** convertir `exportacion_reportes.py` a LF y agregar `*.py text eol=lf` en `.gitattributes`; borrar `tramites`, `docker/django/`, `core/services/cache.py` y la capacidad `ciudadano.eliminar` (con migración de `users` `AlterModelOptions`, como 0015/0018/0021/0026; ojo con G1c-08 punto 3, que la menciona como alternativa). Verificación: suite, `manage.py check`, `makemigrations --check`.

### TST-03 · El coverage de 48 % se mide sobre todo el repo
**Severidad:** BAJA · **Origen:** A8-20 · **Ola:** 3 · **Esfuerzo:** S

**Ampliado por RS-R1-14 (04-oct-2026, duplicado):** pasa a la **Ola R** (PR R-20). Medido sobre las apps del producto el coverage es **76 %** (21.746 stmts), 28 puntos sobre el `fail_under`. El paso por módulo cubre los 9 de los flujos críticos, hoy entre 91 % y 98 %: `coverage report --fail-under=90 --include=programas/services/siis_envio.py,programas/services/proceso_masivo.py,programas/services/cupo.py,programas/services/inscripcion_publica.py,programas/services/padron.py,programas/services/respuestas.py,programas/api/views.py,portal/views/inscripcion.py,core/rbac.py`. Con el `omit`, subir `fail_under` a 74 y activar `branch = true` midiendo de nuevo antes de fijarlo.

- **Ubicación:** `pyproject.toml:24-39` (`source=["."]`, `fail_under = 48`).
**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026 — el `omit` suma `core/performance/*`
(muerto, OPS-10), `scripts/*`, `awslabs-mcp/*` y `docker/*`, nada de lo cual viaja en la imagen de release. Con ese
alcance, remedido el 07-oct con la suite completa: **83 %** de sentencias (23.315) y **81 %** contando ramas (6.192),
no el 76 % del 04-oct —los PRs de las olas R, 1 y 5 lo subieron—. Se activa **`branch = true`**, como pedía la ficha
«midiendo de nuevo antes de fijarlo», y el `fail_under` queda en **79**: dos puntos abajo de lo medido **con ramas**,
que es el número que vale (sin ramas, un `if` que siempre toma el mismo camino cuenta como 100 %). El paso por módulo
va adentro del job `Tests & Coverage`, que ya es obligatorio, con `--fail-under=90` sobre los **nueve** módulos de los
flujos críticos (la ficha nombraba cuatro en la propuesta y nueve en la ampliación: se tomaron los nueve), hoy entre
92 % y 98 % con ramas, TOTAL 94 %. **Dos desvíos:** el techo es 79 y no 74 porque se remidió, y los «comandos demo» no
se agregaron al `omit` —cada uno necesitaría su justificación propia y OPS-02 los va a borrar—. `Tests & Coverage`
sube su `timeout-minutes` de 15 a 20: medir ramas pasa la corrida de 480 s a 744 s.
**Ronda 2 de la revisión:** el gate no tenía test que lo sostuviera. Son **tres números y una lista**, repartidos entre
`pyproject.toml` y `pr-backend.yml`, así que borrar el paso del piso por módulo o volver `fail_under` a 48 dejaba todo
en verde —el mismo modo de falla que TST-03 venía a cerrar—. Lo cubre `core/tests/test_gates_ci.py::CoberturaTests`
(9 tests, calcado de `ContratoDeMigracionesTests`, que ya parsea `pr-backend.yml`): exige el paso «Coverage por módulo
crítico» con los nueve módulos y `--fail-under=90`, `branch = true` y `fail_under = 79` en `pyproject.toml`, el `omit`
de lo que no es producto, y **que las nueve rutas del `--include` existan** —un módulo renombrado desaparece del
`--include` en silencio: `coverage` no se queja de una ruta inexistente, simplemente mide menos, y con ocho de nueve el
TOTAL sigue arriba de 90 y el gate queda verde midiendo de menos—.
**Test permanente:** `core/tests/test_gates_ci.py::CoberturaTests.test_el_fail_under_global_sigue_en_el_techo_medido`
(y `.test_existe_el_paso_del_piso_por_modulo_critico`, `.test_el_piso_por_modulo_sigue_en_noventa`,
`.test_el_paso_nombra_exactamente_los_nueve_modulos_criticos`, `.test_los_nueve_modulos_criticos_existen`,
`.test_el_coverage_mide_ramas`, `.test_el_omit_deja_afuera_lo_que_no_es_producto`,
`.test_el_job_mide_cobertura`, `.test_el_paso_va_en_un_job_que_el_ruleset_exige`).

- **Propuesta:** sumar `core/performance/*` muerto, `scripts/*`, `awslabs-mcp/*`, `docker/*` y los comandos demo al `omit`; paso separado en `pr-backend.yml`: `coverage report --include=programas/services/siis_envio.py,programas/services/proceso_masivo.py,programas/services/cupo.py,programas/services/inscripcion_publica.py --fail-under=80`.

### G2-05 · `import_users_from_csv`: copia los grupos de un usuario fijo (id 368) y pisa grupos, email y clave de cuentas existentes
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-05, G3-07 · **Ola:** 3 (con OPS-02) · **Esfuerzo:** S
- **Ubicación:** `users/management/commands/import_users_from_csv.py:19-24` (`--reference-user-id` con default `368`), `:70-89` (`get_or_create` por username; en los existentes cambia email y clave y hace `groups.set(reference_groups)`; sin `validate_password`, sin `transaction.atomic`, sin `--dry-run`, sin `debe_cambiar_contrasena`, sin `asegurar_admin_restante`; claves en texto plano en el CSV).
- **Propuesta:** borrarlo junto con OPS-02, o exigir `--reference-user-id` sin default, ensayo por defecto (`--aplicar`), no tocar existentes salvo `--actualizar`, `validate_password`, `debe_cambiar_contrasena=True` en los creados y todo dentro de `transaction.atomic()`.
- **Test (si se conserva):** un usuario existente en el CSV conserva sus grupos sin `--actualizar`.

**Resolución:** ✅ Resuelto en el PR 3 de la Ola 3 (Cambio 171), 07-oct-2026 — **se conserva endurecido**, que es la
segunda opción de la propuesta (`DECISIÓN CLIENTE`: borrarlo es una línea y lo decide el PM; conservarlo no cuesta nada
porque todos sus caminos peligrosos quedaron cerrados). Entra todo lo que pedía la ficha: `--reference-user-id` es
**obligatorio y sin default** (el 368 es otra persona en cada base), **ensayo por defecto** con escritura en
`--aplicar`, los usuarios que ya existen **no se tocan** salvo `--actualizar`, `validate_password` por fila,
`debe_cambiar_contrasena=True` en todo aquel a quien el comando le fija la clave —no solo en los creados: la clave
viajó en texto plano en un CSV, así que es provisoria igual— y la escritura entera en `transaction.atomic()`. Entra
también el `asegurar_admin_restante` que la ficha listaba como faltante, acotado al caso que lo necesita (si
`--actualizar` pisó a alguien, el `groups.set` pudo haberle quitado el rol al único que administra; el `CommandError`
revierte la tanda). **Tres cosas que la ficha no pedía.** (1) `--actualizar` **exige `--motivo`**, que queda en el log
con el archivo y el usuario de referencia: es la forma destructiva del comando y el repo ya trata así a
`--ignorar-corrida` y a `--si-entiendo-prd` (`ComandoSiisBase`). (2) La planificación y la validación de claves corren
**también en el ensayo**, así que un CSV con una clave débil en la fila 40 corta antes de escribir la 1, y el ensayo
sirve de verdad para revisar. (3) La columna **`Rol` dejó de ser obligatoria**: estaba entre las requeridas y **no la
leía nadie** —los grupos salen del usuario de referencia—, así que exigirla hacía creer que asignaba el rol; si viene,
se avisa que se ignora. La salida nombra usuarios y nada más: ni la contraseña ni el correo quedan en la terminal.
**Test permanente:** `users.tests.test_import_users_from_csv`
(`ImportUsersFromCsvTests.test_un_usuario_existente_conserva_grupos_clave_y_email_sin_actualizar`,
`ImportUsersFromCsvTests.test_reference_user_id_es_obligatorio`,
`ImportUsersFromCsvTests.test_sin_aplicar_no_escribe_nada`,
`ImportUsersFromCsvTests.test_actualizar_exige_motivo`,
`ImportUsersFromCsvTests.test_una_clave_debil_corta_y_no_deja_nada_escrito`,
`ImportUsersFromCsvTests.test_actualizar_no_puede_dejar_al_sistema_sin_administrador`).

### G3-04 · CronJobs de referencia sin `activeDeadlineSeconds`, `startingDeadlineSeconds`, `backoffLimit` ni `timeZone`
**Severidad:** BAJA · **Estado:** PLAUSIBLE (manifiesto de referencia; el real de ECOM no está en el repo) · **Origen:** G3-04 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** pregunta ECOM (manifiestos)
- **Ubicación:** `docker/k8s/cronjobs.yaml` (4 CronJobs, `schedule` en las líneas 18, 38, 58 y 80; 93 líneas en total).
- **Escenario:** con `concurrencyPolicy: Forbid` y sin deadline, una corrida colgada bloquea en silencio todas las siguientes (vencimientos, sincronización SIIS); sin `backoffLimit`, un `sincronizar_programas_siis` que falla se reintenta hasta 6 veces contra SIIS; sin `timeZone`, el horario corre en UTC (hoy 03:10 UTC = 00:10 ART, no rompe).
- **Propuesta:** por CronJob, `timeZone: America/Argentina/Buenos_Aires`, `startingDeadlineSeconds: 600`, `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 5`; en `jobTemplate.spec`, `backoffLimit: 1` y `activeDeadlineSeconds` (alertas 1800, vencimientos 900, SIIS 1800, limpieza 900). Pedir a ECOM su manifiesto real (`kubectl get cronjob -o yaml`).

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — los cuatro CronJobs de
`docker/k8s/cronjobs.yaml` llevan exactamente lo que pide la propuesta, con los cuatro `activeDeadlineSeconds` que
nombra. La `timeZone` además **arregla una incoherencia que el propio archivo declaraba**: la cabecera decía desde
siempre que «los horarios replican el cron de la VM en hora argentina» y sin esa clave corrían en UTC, así que las
03:10 caían a las 00:10 ART; con ella, los dos ambientes corren a la misma hora local y eso queda fijado por un test.
Se dejó escrito que un cluster anterior a Kubernetes 1.27 no entiende `timeZone` y hay que correr los horarios tres
horas. **Sigue siendo la plantilla de referencia:** el manifiesto real de ECOM no está en el repo y pedirlo es H-05,
del PM. **Test permanente:** `core.tests.test_tareas_programadas.CronJobsDeKubernetesTests`.

### G3-05 · Cron de icore sin versionar y sin vigilancia
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G3-05 · **Ola:** 3 (con OPS-07) · **Esfuerzo:** S
- **Ubicación:** `docker/cron/` solo tiene `procesar_vencimientos.cron` y `sincronizar_programas_siis.cron`; esos mismos archivos citan «los crons ya existentes (generar_alertas / limpiar_alertas_conversaciones)»; `docs/internal/processes.md:215-221` los da por instalados. Todos son `docker exec chaco-web-1 … >> ~/cron-chaco.log`, sin `flock`, `timeout`, fecha en el log, rotación ni aviso.
- **Propuesta:** versionar `generar_alertas.cron` y `limpiar_alertas_conversaciones.cron`; cada línea como `flock -n /tmp/chaco-<cmd>.lock timeout 1h docker compose -f … exec -T web python manage.py <cmd> 2>&1 | ts >> …` (o `date` antes de cada corrida); `logrotate` del archivo.

**Resolución:** ✅ Resuelto en el PR 1 de la Ola 3 (Cambio 165), 07-oct-2026 — están los cuatro snippets (faltaban
`generar_alertas.cron` y `limpiar_alertas_conversaciones.cron`, que los otros dos nombraban como «los crons ya
existentes» sin que su línea estuviera escrita en ninguna parte) y los cuatro pasan por un **envoltorio único**,
`docker/cron/chaco-cron.sh`, más `docker/cron/logrotate-cron-chaco.conf` para la rotación.
**Desvío de la propuesta:** la línea inline que proponía la ficha se repetía cuatro veces con `flock`, `timeout`, `ts`
y la redirección; un envoltorio deja los snippets en una línea legible y, sobre todo, permite distinguir en el log los
tres finales que importan, que inline no se distinguen: `flock -n -E 99` hace que «ya hay una corrida en curso»
(SALTEADA) no se confunda con un exit 1 del comando, y `timeout` devuelve 124 (CORTADA). Cada corrida escribe fecha de
inicio, de fin y motivo de salida. `ts` no se usó porque viene en `moreutils`, que no está instalado en el host.
Los límites son por comando (25 min alertas, 15 min vencimientos y limpieza, 30 min SIIS), alineados con los
`activeDeadlineSeconds` de G3-04. `docs/internal/processes.md` lleva la tabla con los cuatro, el límite de cada uno y
la instalación (incluida la del logrotate, que es el único paso que necesita root). **Test permanente:**
`core.tests.test_tareas_programadas.CronDeIcoreTests`.

---

## Inventario de comandos programados (G3)

| Command | Dónde se programa | Frecuencia | Lock | Riesgo |
|---|---|---|---|---|
| `generar_alertas` | k8s `cronjobs.yaml:16-31` (referencia); icore: crontab del host, **sin snippet versionado** (G3-05) | horaria | k8s `Forbid`; icore no | MEDIA: recrea y re-notifica (LEG-01), 3 consultas por ciudadano activo (PERF-20), ráfaga por WS (G1c-04). Sin deadline (G3-04). |
| `procesar_vencimientos` | k8s 03:10 (UTC); icore `docker/cron/procesar_vencimientos.cron` 03:10; **arranque** de `web` (compose prod, opcional) | diaria + cada arranque | k8s `Forbid`; resto no | BAJA: idempotente, una `atomic` por regla (BEC-22 INFO). Bajo `set -eu` en el arranque (OPS-07). Revierte reaperturas (pendiente Cambio 54, G1-04). |
| `limpiar_alertas_conversaciones` | k8s 03:30; icore crontab, **sin snippet** | diaria | k8s `Forbid` | BAJA: un `DELETE … WHERE creado < X` sin lotes; si la tabla creciera podría pasar los 10 s de `read_timeout`. App sin uso. |
| `sincronizar_programas_siis` | k8s 04:00; icore `docker/cron/sincronizar_programas_siis.cron` 04:00 | diaria | k8s `Forbid` | SIIS-06 (catálogo vacío); `CommandError` si SIIS cae; en k8s se reintenta hasta 6 veces (G3-04). |
| `seed_datos_base` (→ `seed_rbac`, `seed_becas`, roles de menú, `loaddata` si vacío) | `docker-entrypoint.sh:61-62` → web de icore en cada `up`; initContainer `bootstrap` de ECOM en cada pod | cada arranque o deploy | no (réplicas: OPS-07) | **ALTA: OPS-06** (🟡 al 03-oct: #508 dejó de pisar opt-in, activo y Operador; falta `RolMeta.clave`). `seed_becas` en `@transaction.atomic`. |
| `crear_programas` | ídem | cada arranque | no | OPS-06 (pisaba estado/nombre/color/orden; `MultipleObjectsReturned` con dos `tipo=BECAS`). ✅ al 03-oct: #508 lo crea solo si falta, por `codigo`, y frena con `CommandError` si hay otro de tipo Becas. |
| `seed_catalogo_siis` | ídem | cada arranque | no | BAJA: ~700 consultas en una `atomic` (`update_or_create` hace UPDATE siempre); un CSV incoherente impide arrancar (OPS-07). |
| `migrate --run-syncdb` / `collectstatic` | ídem (`RUN_MIGRATIONS`, `RUN_COLLECTSTATIC`) | cada arranque | no | OPS-05, OPS-07, OPS-11; restore de PRD con tablas huérfanas (nunca `--fake`). |
| Proceso masivo SIIS (hilo en `web`, `CorridaSiis`) | pantalla `/becas/config/programas/<pk>/proceso-masivo/` | a pedido | latido | SIIS-01/02/03. |

**No programados** (manuales; riesgo si se corren en PRD): ~~`debug_ciudadanos` (G1c-12)~~, ~~`crear_usuarios_sistema`~~,
~~`setup_roles_contactos`~~ y ~~`setup_groups`~~ (OPS-02) **borrados en el Cambio 171**; los seeds demo quedan detrás de
`exigir_entorno_demo` y `import_users_from_csv` (G2-05) detrás de `--aplicar` / `--actualizar --motivo`; `optimize_db`,
`optimize_database`, `setup_system`, `initialize_phase2` (OPS-10); `corregir_datos_siis` (G3-06); `reenviar_siis_pendientes`
(el Cambio 27 lo pensó para cron, no está programado), `enviar_casos_siis`, `procesar_casos_siis`, `validar_casos_siis` y
`completar_casos_renaper` (SIIS-01/03, PERF-06); `correr_alta_siis` (#513, 01-oct: encadena los `.sql` del organismo, `seed_catalogo_siis`, `completar_casos_renaper`, `corregir_datos_siis --aplicar` y `procesar_casos_siis` por tandas de 500, sin candado de corrida; SIIS-01/03/04, G3-06); `cerrar_espera_colgada` (correcto: ensayo por defecto y
`select_for_update`); `verificar_usuarios` (inocuo); `load_fixtures`, `load_initial_data`, `cargar_config_dispositivos`,
`import_padron_dispositivos` (sin revisar en profundidad) y `diagnosticar_*` (SIIS-19).

## Seguimientos de la revisión de la Ola 0 (agregados el 03-oct-2026)

Observaciones MINOR que dejaron los revisores de los PRs de la Ola 0. No son de la base auditada (`917e583`):
las líneas son de `origin/development @ 7393c41`.

### R0-02 · `CLAUDE.md` y `docs/client/architecture.md` todavía nombran `portal:ciudadano_mi_perfil`
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 7 · **Esfuerzo:** S
- **Ubicación:** `CLAUDE.md:165` y `docs/client/architecture.md:203` dicen que `PortalCiudadanoMiddleware` redirige a `portal:ciudadano_mi_perfil`; desde #511 (SEC-29) redirige a `portal:home` y esa ruta no existe.
- **Propuesta:** actualizar los dos textos (documentación; `CLAUDE.md` no viaja en el release).

### R0-03 · Fecha fija en `programas/tests/test_becas_relevamientos.py:636-648` que vence el 01-ene-2027
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 3 (CI y tests) · **Esfuerzo:** S

**Ampliado (04-oct-2026):** pasa a la **Ola R** (PR R-20, cobertura y regresión). El plazo sigue siendo antes del 31-dic-2026.

- **Ubicación:** `ConvocatoriaTests.test_crear_convocatoria` manda `fecha_fin = "2026-12-31"` con `activo: "on"`; desde el 01-ene-2027 `ConvocatoriaForm.clean()` la rechaza y el Backend CI de todos los PRs queda rojo (mismo patrón que el Cambio 105).
- **Propuesta:** fechas relativas (`timezone.localdate()` ± `timedelta`), como el Cambio 105; buscar otras fechas fijas con `grep -rn '"202[6-9]-' */tests/`.
- **Plazo:** antes del 31-dic-2026.
**Resolución:** ✅ Resuelto en #612 (Cambio 163, PR R-20), 07-oct-2026, **56 días antes del plazo** — las fechas del
alta pasan a ser relativas a `timezone.localdate()` (±30 días), como el Cambio 105. El guard es
`test_crear_convocatoria_sigue_andando_pasado_el_01_ene_2027`, que corre el mismo POST con **el reloj congelado en
2027**: con la fecha literal puesta de vuelta da `200 != 302` (el form rechaza la convocatoria activa con fecha de fin
vencida), que es exactamente lo que iba a pasar el 01-ene-2027 en todos los PRs. El helper
`core/tests/reloj.py::reloj_en` es nuevo y no agrega dependencias: parchea `django.utils.timezone.now`, de donde salen
`localtime()` y `localdate()`. El `grep -rn '"202[6-9]-' */tests/` que pedía la ficha se corrió: las otras fechas
literales de ese archivo son los **límites de la convocatoria del fixture** y los bordes que se prueban contra ellos,
que no dependen de hoy y por eso no vencen.
**Test permanente:** `programas/tests/test_becas_relevamientos.py::ConvocatoriaTests.test_crear_convocatoria_sigue_andando_pasado_el_01_ene_2027`

