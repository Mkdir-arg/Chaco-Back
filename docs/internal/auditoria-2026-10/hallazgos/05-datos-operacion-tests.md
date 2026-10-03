# 4.5 Datos, operación, despliegue y tests (DAT, OPS, TST, G1c-12, G2-05, G3-04/05)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. PoC: `poc/test_repro_datos_operacion.py` y
`poc/test_repro_admin_cron_renaper.py` (seeds).

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| OPS-06 | **Seeds de arranque pisan configuración del ABM** (capacidades, roles, Operador de backoffice, programa Becas) | ALTA | CONF. test | **0** | S-M | 🟡 |
| DAT-01 | Borrar una pregunta o requisito borra los adjuntos de todos los casos | ALTA | CONF. test | 3 | S (+M fase 2) | ⬜ |
| OPS-03 | Los tracebacks de 500 no llegan a stdout | ALTA | CONF. test | 3 (adelantable) | S | ⬜ |
| OPS-01 | Sin guarda de coherencia `django_migrations` ↔ esquema antes de `migrate` | MEDIA | CONF. código | 3 | M | ⬜ |
| OPS-02 | `crear_usuarios_sistema` y seeds demo con claves conocidas viajan en el release | MEDIA | CONF. ajustado | 3 | S | ⬜ |
| OPS-04 | `/health/` siempre 200 y tapa `health_check.urls` | MEDIA | CONF. test | 3 | S | ⬜ |
| OPS-05 | `read_timeout=10 s` también corta `migrate` | MEDIA | PLAUSIBLE | 3 | S | ⬜ |
| OPS-07 | Bootstrap frágil (`set -eu`, opcionales fatales, réplicas) | MEDIA | CONF. ajustado | 3 | S | ⬜ |
| TST-01 | La CI no prueba MariaDB | MEDIA | CONF. ajustado (tesis central refutada) | 3 | M | ⬜ |
| TST-02 | Configuración sin tests de comportamiento; tests que no prueban nada | MEDIA | CONF. | 3 | M | ⬜ |
| G1c-12 | `debug_ciudadanos` hace `FLUSHDB` del Redis compartido | MEDIA | CONF. código | 3 | S | ⬜ |
| DAT-02 | El admin de Django borra casos y relevamientos con su auditoría | BAJA | CONF. ajustado | 3 | S | ⬜ |
| DAT-03 | `dni_titular` desincronizado del DNI real | BAJA | PLAUSIBLE | 3 | S | ⬜ |
| DAT-05 | El Excel del padrón reemplazado/quitado queda en `media/` (o se borra antes del commit) | BAJA | CONF. | 3 | S | ⬜ |
| V2-NEW-05 | Un restore deja pks de legajo en hex que el ORM de MariaDB no encuentra | BAJA | a confirmar | 3 | S | ⬜ |
| OPS-10 | Módulos de «optimización» con DDL y `SET GLOBAL` en el release | BAJA | CONF. ajustado | 7 | S-M | ⬜ |
| OPS-11 | `migrate --run-syncdb` en el entrypoint | BAJA | CONF. ajustado | 3 | S | ⬜ |
| OPS-12 | QA no reproduce el cache de PRD y declara `ENVIRONMENT=prd` | BAJA | CONF. | 3 | S | ⬜ |
| OPS-13 | Dependencias sin uso en la imagen | BAJA | CONF. | 7 | S | ⬜ |
| OPS-14 | Código muerto o stub; un `.py` vivo que git trata como binario | BAJA | CONF. | 7 | S | ⬜ |
| TST-03 | Coverage global de 48 % sobre todo el repo | BAJA | CONF. | 3 | S | ⬜ |
| G2-05 | `import_users_from_csv` reparte grupos de un usuario fijo y pisa cuentas | BAJA | CONF. lectura | 3 | S | ⬜ |
| G3-04 | CronJobs de referencia sin deadlines, `backoffLimit` ni `timeZone` | BAJA | PLAUSIBLE | 3 | S | ⬜ |
| G3-05 | Cron de icore sin versionar y sin vigilancia | BAJA | CONF. lectura | 3 | S | ⬜ |
| R0-02 | `CLAUDE.md` y `docs/client/architecture.md` todavía nombran `portal:ciudadano_mi_perfil` | BAJA (MINOR) | revisión Ola 0 | 7 | S | ⬜ |
| R0-03 | Fecha fija en `programas/tests/test_becas_relevamientos.py:636-648` que vence el 01-ene-2027 | BAJA (MINOR) | revisión Ola 0 | 3 (CI y tests) | S | ⬜ |

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
- **Ubicación:** `docker-entrypoint.sh:38-41` (comentario `:31-37`, Cambio 78).
- **Escenario:** en icore, el deploy de `development` aplica 0057-0059 (índices) y muere en `0060_catalogo_grupos_origen_canal` con 1050 `Table already exists`: CrashLoop críptico.
- **Propuesta:** (1) comando de solo lectura `verificar_esquema_migraciones`: `MigrationLoader(connection)`, `applied - disk` (filas sin archivo) y, para cada migración no aplicada del plan, las `CreateModel` cuya `db_table` ya está en `connection.introspection.table_names()` → `CommandError` con la lista y la instrucción («renombrar en `django_migrations`…» / «borrar las tablas huérfanas, NUNCA `--fake`»); (2) en el entrypoint, antes de la línea 40, `python manage.py verificar_esquema_migraciones` (salteable con `SKIP_SCHEMA_GUARD=true`); (3) script SQL versionado para icore: `UPDATE django_migrations SET name='0060_catalogo_grupos_origen_canal' WHERE app='programas' AND name='0057_catalogo_grupos_origen_canal';` y así con las 6 (consultar antes con P-13). **Descartado:** `replaces` (0060 depende de 0059; muy probablemente `InconsistentMigrationHistory`; no se probó).
- **Tests:** `TransactionTestCase` que inserta `programas.0099_fantasma` en `django_migrations` → el comando falla; test unitario de la función que cruza el plan con `table_names`.

### OPS-02 · `crear_usuarios_sistema` y los seeds demo con claves conocidas viajan en el release
**Severidad:** MEDIA (era ALTA: requiere que un operador con `exec` lo corra) · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A8-03, V6-NEW-06, G1c-18 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `users/management/commands/crear_usuarios_sistema.py` (viaja en `origin/main`: `.gitattributes` solo excluye docs y auditorías; nadie lo invoca); deja `admin`/`admin123` superusuario y `admin1..3`/`admin123` en el rol **«Administrador» real** (`rbac.ROL_ADMINISTRADOR`, protegido con todas las capacidades, `seed_rbac.py:73-83`), con `is_staff=True`, y les resetea la clave si existen. `seed_relevamientos_periodo_demo.py:16-49` (`set_password` sobre el `--username` que se pase, default `territorial_demo`/`demo1234`, `is_active=True`); `seed_becas_demo_mobile.py:320-325` (`terri123`); `legajos/management/commands/setup_roles_contactos.py` (10 grupos `Psicologo`, `Director`, … sin `RolMeta`, con permisos de modelo sobre `historialcontacto`; `seed_rbac:56-64` los convierte en roles con `RolMeta` activa: roles fantasma) y `setup_groups.py` (`Responsable`). Refutado: `seed_perf`, `prepare_perf_http_probe` y `seed_aceptacion_reportes` ya exigen base efímera.
- **Propuesta:** `git rm users/management/commands/crear_usuarios_sistema.py`, `setup_roles_contactos.py` y `setup_groups.py`; helper `core/management/guardas.py::exigir_entorno_demo()` = `if not (settings.DEBUG or os.environ.get("CHACO_PERMITIR_SEED_DEMO") == "1"): raise CommandError(...)` al inicio de `seed_becas_demo_mobile`, `seed_relevamientos_periodo_demo` y `seed_busqueda_ciudadanos_demo`, que además no deben resetear la clave de usuarios existentes. **No** usar `settings.ENVIRONMENT` (icore DEV vale `prd`; QA lo pisa a `prd`, OPS-12). Contar con P-09 las cuentas que ya existan en PRD.
- **Tests:** `call_command("crear_usuarios_sistema")` → `CommandError: Unknown command`; cada seed demo con `DEBUG=False` y sin la variable → `CommandError`.

### OPS-04 · `/health/` siempre 200 y tapa `health_check.urls`
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO con test (`A805HealthTests`: `resolve('/health/')` → `healthcheck.views.basic`; con la DB caída responde `200 OK`) · **Origen:** A8-05 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-O04
- **Ubicación:** `config/urls.py:40` (gana sobre `:59`, `health_check.urls`, inalcanzable); sondas de compose y de `docker/k8s/bootstrap-initcontainer.yaml` apuntan a `/health/`; `nginx.conf:41,119` la expone sin login.
- **Propuesta:** `/health/` queda como liveness sin I/O (no romper las sondas de ECOM); agregar `/health/ready/`: `connection.ensure_connection(); with connection.cursor() as c: c.execute("SELECT 1")` y, si `ENVIRONMENT=="prd"`, `caches["sessions"].get("health")` (acotados por los timeouts ya configurados); 503 con JSON `{db, cache}` si algo falla. Borrar `path("health/", include("health_check.urls"))` y sacar `health_check*` de `INSTALLED_APPS` y `requirements.txt` (OPS-13). No publicarla en nginx. D-O04: usarla como readinessProbe (default: solo monitoreo; nunca como liveness: con una sola base, sacaría todos los pods a la vez).
- **Tests:** `/health/ready/` → 503 con `ensure_connection` parcheado; `/health/` → 200 igual.

### OPS-05 · `read_timeout=10 s` también corta `migrate`
**Severidad:** MEDIA · **Estado:** PLAUSIBLE (la 0072 ya pasó en PRD sin cortarse) · **Origen:** A8-06 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-O05 (choca con el Cambio 91)
- **Ubicación:** `config/settings.py:291`. En MySQL/MariaDB `can_rollback_ddl=False`: una migración cortada deja el esquema a medias (un ALTER que espera el metadata lock > 10 s → error 2013 → el ALTER se aplica igual en el servidor).
- **Propuesta:** `"read_timeout": int(os.environ.get("DB_READ_TIMEOUT", "10"))` (ídem `write_timeout`); en el entrypoint, `DB_READ_TIMEOUT="${MIGRATE_DB_READ_TIMEOUT:-600}" DB_WRITE_TIMEOUT=… python manage.py migrate --noinput`. Mantener migraciones de datos por lotes (patrón 0072) y, en índices, `ALGORITHM=INPLACE, LOCK=NONE` vía `RunSQL` con `state_operations`. El Cambio 91 dice «no se sube el `read_timeout`, es el límite acordado con ECOM»: D-O05 (default: subirlo solo para `migrate`).
- **Tests:** settings con `DB_READ_TIMEOUT=600` → `OPTIONS["read_timeout"] == 600`; ensayo en `scripts/perf_mysql` de un `AddIndex` sobre Formulario con `read_timeout=1`.

### OPS-07 · Bootstrap frágil
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A8-09, V6-NEW-04 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `docker-entrypoint.sh:2`, `:22-25` (`set -eu`, sin `|| true`); `docker-compose.prod.yml:56` (`LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS=procesar_vencimientos`); `programas/management/commands/procesar_vencimientos.py:49-62` (no aísla reglas); `docs/internal/processes.md:105` dice que los opcionales «pueden fallar sin abortar el arranque» (falso: V6-NEW-04). Carrera entre réplicas si el pod web corre el bootstrap y hay más de una (ECOM usa un Job/initContainer, Cambio 78); un CSV incoherente de `seed_catalogo_siis` también impide arrancar.
- **Propuesta:** opcionales no fatales: `for c in $LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS; do python manage.py "$c" || echo "AVISO: $c falló; se sigue"; done` (alinea código y doc); en `procesar_vencimientos`, `try/except Exception` por regla con `logger.exception` y `CommandError` al final si alguna falló; para varias réplicas, `SELECT GET_LOCK('datanach_bootstrap', 600)` (MySQL y MariaDB) desde un comando `bootstrap_lock`, o documentar «réplicas > 1 ⇒ Job único».
- **Tests:** dos reglas, la primera lanza → la segunda aplica y el comando termina en `CommandError`.

### TST-01 · La CI no prueba MariaDB
**Severidad:** MEDIA (era ALTA) · **Estado:** CONFIRMADO-AJUSTADO; **la tesis central de A8-07 está refutada**: el job «Ephemeral MySQL Redis Contract» (`pr-performance.yml` → `ephemeral-stack-contract`, `mysql:8.0`) corre `migrate` real en cada PR (log del run 36751292857: `legajos.0007`, `programas.0047`, `0048`, `0072`, `users.0023` → OK) · **Origen:** A8-07 · **Ola:** 3 · **Esfuerzo:** M · **Decisión:** pregunta H-01 (versión MariaDB)
- **Lo que sí falta:** (1) la rama `features.has_native_uuid_field` (solo MariaDB 10.7+, `legajos/0007:57-58`: el bug de septiembre); (2) ningún test de la suite corre sobre MySQL/MariaDB (solo probes de performance): `KeyTransform`, `Trunc*`/`CONVERT_TZ` y UUID con guiones sin red; (3) migraciones sobre datos (el migrate arranca de base vacía).
- **Propuesta:** matriz en `ephemeral-stack-contract`: `mysql:8.0` y `mariadb:<versión de ECOM; 10.11 por default hasta confirmar con P-11>`, más un paso `python manage.py test --tag mysql` (sin `PYTEST_RUNNING`, usa la base del servicio) con 3-4 tests marcados: guardar y buscar por `token_publico`/`client_uuid`, `q_uuid_en_texto`, un `JSON_EXTRACT` con clave numérica y dashboard sin `Trunc*`; sumar los de DIS-01 (`__date`) y SIIS-01 (`UniqueConstraint` con NULL).
- **Verificación:** el job falla con un `__date` sobre DateTimeField introducido a propósito en una rama de prueba. Costo: 2-4 min más de CI.

### TST-02 · Configuración sin tests de comportamiento; tests que no prueban nada
**Severidad:** MEDIA · **Estado:** CONFIRMADO · **Origen:** A8-14 · **Ola:** 3 · **Esfuerzo:** M

**⚠ Actualizar (03-oct-2026):** el ítem (2) del Top-5 (`seed_datos_base` idempotente y respetuoso del ABM) ya existe: `users/tests/test_seed_datos_base.py` (#508). En el mapa de cobertura, `seed_datos_base` y `crear_programas` ya tienen test.
- **Ubicación:** `configuracion/views/*.py` (~942 LOC; `models/`, `services/` y `migrations/` vacíos); único test que toca rutas `configuracion:` es `users/tests/test_menu_rbac.py` (solo el menú); `configuracion/tests/test_services_actividades.py:5-6` y `tramites/tests/test_package_exports.py:6` (`assertTrue(True)`); el wizard crea `Programa` (`configuracion/views/programas.py:197`) y el ABM borra secretarías (`secretaria.py:108,218`) sin tests.
- **Propuesta:** borrar los dos `assertTrue(True)`; tests de RBAC de cada vista (sin `config.administrar` → redirect/403), del wizard de 4 pasos con estado en sesión, de `programa_cambiar_estado` (activar sin naturaleza → error) y del borrado de secretaría con subsecretarías (mensaje y no se borra).
- **Verificación:** coverage de `configuracion/` de ~0 % de vistas a > 60 %.
- **Top-5 de tests faltantes por valor (V6):** (1) DAT-01; (2) `seed_datos_base` idempotente y respetuoso del ABM (OPS-06); (3) `generar_alertas`/`AlertasService` con `assertNumQueries` y dos pasadas (PERF-20/LEG-01; el servicio no tiene ningún test y corre cada hora); (4) `procesar_vencimientos` con una regla que falla y un `FINALIZANDO` dentro de la gracia (OPS-07, G1-04); (5) contrato de operación: `django.request` llega a un `StreamHandler` y `/health/ready/` → 503 con la DB caída (OPS-03, OPS-04).
- **Mapa de cobertura (confirmado por grep):** sin ningún test: `legajos.services.alertas` (268 LOC, cron horario), `linking`, `ciudadanos`, `contactos`, `programas`, `filtros_usuario`, `ml_predictor`; `users.services.listing` y `filter_config`; `core.services.cache`; vistas de `configuracion`. Comandos sin test: `generar_alertas`, `sincronizar_programas_siis` (solo el servicio), `seed_datos_base`, `crear_programas`, `completar_casos_renaper`, `validar_casos_siis`, `import_users_from_csv`. **Sí tienen test** (corrección a A8): `reenviar_siis_pendientes` y `enviar_casos_siis` (`test_siis_envio.py:624-678`), `cerrar_espera_colgada` (`test_cupo_espera_reglas.py:263`).

### G1c-12 · `debug_ciudadanos` vacía el Redis compartido
**Severidad:** MEDIA · **Estado:** CONFIRMADO (código y librería) · **Origen:** G1c-12 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `legajos/management/commands/debug_ciudadanos.py:36-37` (`cache.clear()`; además imprime DNI y nombre de 3 ciudadanos); en `prd`, `default`, `sessions` y `CHANNEL_LAYERS` usan el mismo `REDIS_URL` (`settings.py:312-337`, `:381-385`); `django_redis` 5.4.0 `DefaultClient.clear()` → `flushdb()`.
- **Escenario:** un «debug» desloguea a todo el backoffice, corta los pasos en curso de la inscripción pública (viven en sesión) y borra los grupos de Channels.
- **Propuesta:** borrar el comando (no lo usa nada ni ningún documento) o reemplazar `cache.clear()` por `CiudadanosService.invalidate_ciudadanos_cache()`; defensa en profundidad: sesiones y channel layer en otra DB lógica de Redis (PERF-10).
- **Test:** `call_command("debug_ciudadanos")` con `patch("django.core.cache.cache.clear")` → `assert_not_called` (o `Unknown command` si se borra).

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

### OPS-12 · QA no reproduce el cache de PRD y declara `ENVIRONMENT=prd`
**Severidad:** BAJA (MEDIA si se agregan guardas que lean `settings.ENVIRONMENT`) · **Estado:** CONFIRMADO con la plantilla `.env.qa.example`; lo de ECOM testing es PLAUSIBLE · **Origen:** A8-16, V6-NEW-01 · **Ola:** 3 · **Esfuerzo:** S
- **Evidencia (runtime con `ENVIRONMENT=qa` + `DJANGO_SETTINGS_MODULE=config.settings_production`):** `ENV prd | cache LocMemCache | session db | prefijo '[QA] '`. `config/settings_production.py:5` pisa `ENVIRONMENT="prd"` **después** de que `settings.py` derivó todo de la variable real: QA corre con cache y `InMemoryChannelLayer` locales al proceso (el throttle cuenta por proceso; las invalidaciones solo limpian un worker) y `diagnosticar_siis`/`diagnosticar_correo` informan mal. En icore (DEV) también vale `prd`.
- **Propuesta:** en `settings_production.py`, **no** reasignar `ENVIRONMENT` (o `if ENVIRONMENT not in ("prd", "qa"): raise ImproperlyConfigured`); en `settings.py`, `USE_REDIS = ENVIRONMENT in ("prd", "qa") or PERFORMANCE_CI or os.getenv("USE_REDIS_CACHE") == "True"` para `CACHES` y `CHANNEL_LAYERS`. QA pasa a depender de Redis (lo tiene por Channels). Ver SEC-35.
- **Test:** settings con `ENVIRONMENT=qa` + `settings_production` → `settings.ENVIRONMENT == "qa"` y backend Redis.

### OPS-13 · Dependencias sin uso en la imagen de producción
**Severidad:** BAJA · **Origen:** A8-17 · **Ola:** 7 · **Esfuerzo:** S
- **Ubicación:** `requirements.txt` (`openai==1.3.8` —subido solo para parchear CVEs de `anyio`—, `httpx`, `anyio`, `structlog`, `gevent`, `greenlet`, `django-simple-history`, `debugpy`, `pymysql` —solo en `core/performance/advanced_connection_pool.py`, OPS-10—, `django-health-check` —OPS-04—); `config/settings.py:85` (`django_extensions` en `INSTALLED_APPS` también en prod). Verificado: 0 imports.
- **Propuesta:** sacarlas; pasar `debugpy`, `django-extensions`, `django-silk`, `django-zeal` a `requirements-dev.txt`; `django_extensions` solo con `DEBUG`. Confirmar que ningún operador usa `shell_plus` en ECOM. Verificación: build de la imagen, suite completa y `pip-audit`.

### OPS-14 · Código muerto o stub; un `.py` vivo que git trata como binario
**Severidad:** BAJA (la conversión a LF conviene ya) · **Origen:** A8-18 · **Ola:** 7 · **Esfuerzo:** S
- **Ubicación:** `programas/services/exportacion_reportes.py` con fin de línea CR: `git ls-files --eol` lo marca `i/-text` (**binario**: los diffs de PR no muestran su contenido) y es código vivo (lo importan `views/dashboard_becas.py`, `reportes.py`, `reportes_becas.py`); `tramites/` (app en `INSTALLED_APPS` con `urlpatterns = []`); `docker/django/entrypoint_final.py` (dice «SISOC», corre un script inexistente); `core/services/cache.py` (sin importadores); capacidad `ciudadano.eliminar` (`core/rbac.py:41`, rol «Gestión de Ciudadanos» en `seed_datos_base.py:51`) sin ninguna vista que la use; `legajos/services/ml_predictor.py` (heurística sobre legajos que no se crean).
- **Propuesta:** convertir `exportacion_reportes.py` a LF y agregar `*.py text eol=lf` en `.gitattributes`; borrar `tramites`, `docker/django/`, `core/services/cache.py` y la capacidad `ciudadano.eliminar` (con migración de `users` `AlterModelOptions`, como 0015/0018/0021/0026; ojo con G1c-08 punto 3, que la menciona como alternativa). Verificación: suite, `manage.py check`, `makemigrations --check`.

### TST-03 · El coverage de 48 % se mide sobre todo el repo
**Severidad:** BAJA · **Origen:** A8-20 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `pyproject.toml:24-39` (`source=["."]`, `fail_under = 48`).
- **Propuesta:** sumar `core/performance/*` muerto, `scripts/*`, `awslabs-mcp/*`, `docker/*` y los comandos demo al `omit`; paso separado en `pr-backend.yml`: `coverage report --include=programas/services/siis_envio.py,programas/services/proceso_masivo.py,programas/services/cupo.py,programas/services/inscripcion_publica.py --fail-under=80`.

### G2-05 · `import_users_from_csv`: copia los grupos de un usuario fijo (id 368) y pisa grupos, email y clave de cuentas existentes
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-05, G3-07 · **Ola:** 3 (con OPS-02) · **Esfuerzo:** S
- **Ubicación:** `users/management/commands/import_users_from_csv.py:19-24` (`--reference-user-id` con default `368`), `:70-89` (`get_or_create` por username; en los existentes cambia email y clave y hace `groups.set(reference_groups)`; sin `validate_password`, sin `transaction.atomic`, sin `--dry-run`, sin `debe_cambiar_contrasena`, sin `asegurar_admin_restante`; claves en texto plano en el CSV).
- **Propuesta:** borrarlo junto con OPS-02, o exigir `--reference-user-id` sin default, ensayo por defecto (`--aplicar`), no tocar existentes salvo `--actualizar`, `validate_password`, `debe_cambiar_contrasena=True` en los creados y todo dentro de `transaction.atomic()`.
- **Test (si se conserva):** un usuario existente en el CSV conserva sus grupos sin `--actualizar`.

### G3-04 · CronJobs de referencia sin `activeDeadlineSeconds`, `startingDeadlineSeconds`, `backoffLimit` ni `timeZone`
**Severidad:** BAJA · **Estado:** PLAUSIBLE (manifiesto de referencia; el real de ECOM no está en el repo) · **Origen:** G3-04 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** pregunta ECOM (manifiestos)
- **Ubicación:** `docker/k8s/cronjobs.yaml` (4 CronJobs, `schedule` en las líneas 18, 38, 58 y 80; 93 líneas en total).
- **Escenario:** con `concurrencyPolicy: Forbid` y sin deadline, una corrida colgada bloquea en silencio todas las siguientes (vencimientos, sincronización SIIS); sin `backoffLimit`, un `sincronizar_programas_siis` que falla se reintenta hasta 6 veces contra SIIS; sin `timeZone`, el horario corre en UTC (hoy 03:10 UTC = 00:10 ART, no rompe).
- **Propuesta:** por CronJob, `timeZone: America/Argentina/Buenos_Aires`, `startingDeadlineSeconds: 600`, `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 5`; en `jobTemplate.spec`, `backoffLimit: 1` y `activeDeadlineSeconds` (alertas 1800, vencimientos 900, SIIS 1800, limpieza 900). Pedir a ECOM su manifiesto real (`kubectl get cronjob -o yaml`).

### G3-05 · Cron de icore sin versionar y sin vigilancia
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G3-05 · **Ola:** 3 (con OPS-07) · **Esfuerzo:** S
- **Ubicación:** `docker/cron/` solo tiene `procesar_vencimientos.cron` y `sincronizar_programas_siis.cron`; esos mismos archivos citan «los crons ya existentes (generar_alertas / limpiar_alertas_conversaciones)»; `docs/internal/processes.md:215-221` los da por instalados. Todos son `docker exec chaco-web-1 … >> ~/cron-chaco.log`, sin `flock`, `timeout`, fecha en el log, rotación ni aviso.
- **Propuesta:** versionar `generar_alertas.cron` y `limpiar_alertas_conversaciones.cron`; cada línea como `flock -n /tmp/chaco-<cmd>.lock timeout 1h docker compose -f … exec -T web python manage.py <cmd> 2>&1 | ts >> …` (o `date` antes de cada corrida); `logrotate` del archivo.

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

**No programados** (manuales; riesgo si se corren en PRD): `debug_ciudadanos` (G1c-12); `optimize_db`, `optimize_database`,
`setup_system`, `initialize_phase2` (OPS-10); `crear_usuarios_sistema` y seeds demo (OPS-02); `setup_roles_contactos` y
`setup_groups` (OPS-02); `import_users_from_csv` (G2-05); `corregir_datos_siis` (G3-06); `reenviar_siis_pendientes`
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
- **Ubicación:** `ConvocatoriaTests.test_crear_convocatoria` manda `fecha_fin = "2026-12-31"` con `activo: "on"`; desde el 01-ene-2027 `ConvocatoriaForm.clean()` la rechaza y el Backend CI de todos los PRs queda rojo (mismo patrón que el Cambio 105).
- **Propuesta:** fechas relativas (`timezone.localdate()` ± `timedelta`), como el Cambio 105; buscar otras fechas fijas con `grep -rn '"202[6-9]-' */tests/`.
- **Plazo:** antes del 31-dic-2026.
