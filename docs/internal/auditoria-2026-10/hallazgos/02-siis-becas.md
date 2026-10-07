# 4.2 SIIS, núcleo de Becas, app de campo y reportes (SIIS, BEC, G1, G2-01)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. PoC: `poc/test_repro_siis_becas.py` salvo
indicación.

**Hechos del entorno que condicionan todas las propuestas (verificados en V2):**
- DB con `isolation_level="read committed"` y **`read_timeout: 10`** (`config/settings.py:289,292`): un request que
  espera un row lock más de 10 s muere del lado del cliente (error 2013 → 500). **No se puede mantener un lock de fila
  durante el HTTP a SIIS** (connect 10 s + read 30 s, `settings.py:487-488`).
- **No hay cola de tareas** (ni Celery, RQ, huey, dramatiq ni APScheduler). Hay CronJobs de K8s
  (`docker/k8s/cronjobs.yaml`: `generar_alertas`, `procesar_vencimientos`, `limpiar_alertas_conversaciones`,
  `sincronizar_programas_siis`). **Ningún cron corre `reenviar_siis_pendientes`, `enviar_casos_siis` ni
  `procesar_casos_siis`**: hoy se corren a mano.
- SIIS no tiene endpoint para consultar si un beneficiario ya existe ni clave de idempotencia
  (`docs/internal/temas/siis-api.md`; pregunta 5 de `pendientes-ecom-siis-aprobacion-beneficiarios.md` abierta).
- El Cambio 88 decidió correr el masivo en un hilo del pod (no CronJob) y afirma que «es retomable por construcción»;
  SIIS-02 muestra que no lo es si el proceso muere entre el POST y el registro.

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| SIIS-01 | El alta en SIIS no tiene exclusión mutua | CRÍTICA | CONF. test | 1 | M | ✅ |
| SIIS-02 | Resultado ambiguo registrado como ERROR reintentable; proceso muerto sin rastro | ALTA | CONF. test | 1 | M | ✅ |
| SIIS-03 | Masivo: se da por muerto vivo, no se puede frenar, zombis, comandos sin candado | ALTA (MEDIA tras SIIS-01) | CONF. test | 1 | S | ✅ |
| SIIS-04 | El masivo informa casos que cambiaron de estado después de hidratarlos | ALTA | CONF. test | 1 | S | ✅ |
| SIIS-06 | Catálogo vacío de SIIS bloquea todos los programas | ALTA | CONF. test | 1 | S | ✅ |
| SIIS-07 | `token_publico` en `char(32)`: el arreglo está en una rama sin mergear | ALTA | CONF. (merge simulado) | 1 | S | ✅ |
| SIIS-08 | Identidad validada no corrige un legajo autodeclarado; a SIIS viajan datos sin validar | ALTA | CONF. lectura | 1 | M | ✅ |
| V2-NEW-03 | Medir altas duplicadas ya existentes en PRD antes de migrar | ALTA (operativo) | — | 1 (paso 0) | S | ⬜ |
| SIIS-05 | Mismo DNI y plan informados desde casos distintos | MEDIA | CONF. test | 1 | S | ✅ |
| SIIS-09 | Llamadas externas encadenadas que superan los 60 s de nginx | MEDIA | CONF. lectura | 1 | S-M | ✅ |
| SIIS-10 | `normalizar_persona` toma claves de objetos anidados | MEDIA | CONF. test | 3 | S | ⬜ |
| SIIS-11 | JSON de SIIS que no es objeto → `AttributeError` | MEDIA | CONF. test | 1 | S | ✅ |
| SIIS-12 | El payload no prevalida al apoderado | MEDIA | CONF. test | 1 | S | ✅ |
| SIIS-13 | Link abierto: un DNI ajeno bloquea al titular | MEDIA | CONF. ajustado | 3 | S | ⬜ |
| BEC-01 | Aprobar y promover no bloquean la fila del caso | MEDIA | CONF. test | 1 | S | ✅ |
| BEC-02 | Agregar a espera y dar de baja chequean antes del lock | MEDIA | CONF. test | 1 | S | ✅ |
| BEC-03 | La revisión reevalúa condiciones de edad con la fecha de hoy | MEDIA | CONF. lectura | 3 | S | ⬜ |
| BEC-04 | Condición con fuente fuera del canal queda colgando | MEDIA | CONF. lectura | 3 | S | ⬜ |
| BEC-05 | El cupo del subsegmento nunca se aplica | MEDIA | CONF. ajustado (decisión) | 3 | S | ⬜ |
| BEC-06 | Se puede cambiar segmento/subsegmento de una convocatoria con casos | MEDIA | CONF. lectura | 3 | S | ⬜ |
| BEC-07 | El cupo del segmento se puede bajar por debajo de los aprobados | MEDIA | CONF. lectura | 3 | S | ⬜ |
| BEC-09 | No se puede rechazar un caso sin ciudadano con DNI o sin programa SIIS | MEDIA | CONF. lectura | 3 | S | ⬜ |
| BEC-10 | Un relevamiento con casos en espera no se puede terminar | MEDIA | CONF. (decisión) | 3 | S | ⬜ |
| BEC-11 | El masivo aprueba a quien SIIS declaró incompatible | MEDIA | CONF. (decisión) | 1 | S | ✅ |
| G1-03 | La app lee solo la primera página (10) de casos y relevamientos | MEDIA | CONF. lectura | 3 | S | ⬜ |
| G1-04 | Captura offline que sincroniza después del corte de las 03:10 → 409 permanente | MEDIA | CONF. lectura (pendiente Cambio 54) | 3 | M | ⬜ |
| G1-05 | El servidor no valida lo que carga la app | MEDIA | CONF. lectura | 3 | M | ⬜ |
| G1-08 | El mapeo a SIIS lee el catálogo de hoy, no la foto del caso | MEDIA | CONF. lectura | 1 | M | ✅ |
| G1-09 | `pregunta_toggle_activo` saltea «una sola activa por destino SIIS» | MEDIA | CONF. lectura | 1 | S | ✅ |
| G2-01 | Excel de respuestas y dashboard leen `data`: faltan los campos propios del constructor | MEDIA | CONF. test | 3 | M | ⬜ |
| SIIS-14 | RENAPER: DNI en logs y token que no se invalida con 401 | BAJA | CONF. test (401) | 3 | S | ⬜ |
| SIIS-15 | Comprobante renderizado fuera del `try` | BAJA | CONF. lectura | 3 | S | ⬜ |
| SIIS-16 | Adjuntos anónimos validados solo por extensión | BAJA | CONF. lectura | 3 | S | ⬜ |
| SIIS-17 | «Completar datos para SIIS»: correcciones no se borran y se pisan | BAJA | CONF. lectura | 1 | S | ⬜ |
| SIIS-18 | Filtro de localidades por provincia con otras claves | BAJA | CONF. lectura | 3 | S | ⬜ |
| SIIS-19 | `diagnosticar_siis --alta` sin guarda de PRD y DNI por defecto | BAJA | CONF. lectura | 1 | S | ⬜ |
| SIIS-20 | `RENAPER_TEST_MODE` sin guarda en PRD | BAJA | CONF. lectura | 3 | S | ⬜ |
| SIIS-21 | Captcha aritmético deja agotar la cuota por DNI de un tercero | BAJA | CONF. ajustado | 3 | S | ⬜ |
| BEC-14 | Doble clic en «Aprobar» | BAJA | CONF. lectura | 1 | S | ✅ |
| BEC-15 | Carga de padrón concurrente | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-16 | Constructor: mutaciones sin candado y `reconciliar` en cada request | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-17 | Pausar/reanudar con doble envío duplica eventos | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-18 | Fechas UTC en Python fuera de Dispositivos | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-19 | Redirect a `POST['next']` sin validar | BAJA | CONF. lectura | 2 | S | ⬜ |
| BEC-20 | Convocatoria acepta fin anterior al inicio | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-21 | El masivo selecciona casos no aprobables y no mira pausas | BAJA | CONF. lectura | 1 | S | ✅ |
| BEC-23 | La solapa Becas del legajo muestra casos fuera de alcance | BAJA | CONF. ajustado (decisión) | 2 | S | ⬜ |
| BEC-24 | Edición de contacto/apoderado en revisión no atómica | BAJA | CONF. lectura | 3 | S | ⬜ |
| BEC-25 | `siguiente_nombre` calculado sin convocatoria y sin uso | BAJA | CONF. lectura | 7 | S | ⬜ |
| G1-06 | Fecha de nacimiento ilegible de la app → caso sin legajo y bucle de 500 | BAJA | CONF. lectura | 3 | S | ⬜ |
| G1-07 | Adjuntos de la app sin idempotencia ni control de pertenencia | BAJA | CONF. lectura | 3 | S | ⬜ |
| G1-10 | Entre requisitos con el mismo destino gana el de mayor `orden` | BAJA | CONF. lectura | 1 | S | ✅ |
| G1-11 | CUIL calculado aunque el caso tenga el real | BAJA | PLAUSIBLE | 3 | S | ⬜ |
| G1-12 | El padrón acepta fechas futuras o absurdas | BAJA | CONF. lectura | 3 | S | ⬜ |
| G1-13 | Personas: un 404 se informa como 502 | BAJA | CONF. lectura | 3 | S | ⬜ |
| G1-14 | El correo de resolución no deja registro | BAJA | CONF. lectura | 3 | S | ⬜ |
| G1-16 | Captura offline guardada con la foto del momento de sincronizar | BAJA | PLAUSIBLE | 3 | M | ⬜ |
| G1c-15 | Cliente RENAPER: `Retry(total=0)` convierte un 503 en «error de conexión» | BAJA | CONF. test | 3 | S | ⬜ |
| G3-06 | `corregir_datos_siis` pisa `datos_siis` con copia leída fuera de la transacción | BAJA | PLAUSIBLE | 1 | S | ⬜ |
| BEC-22 | Vencimientos: UPDATE por pk sin volver a filtrar estado | INFO (V2: BAJA) | CONF. lectura | 3 | S | ⬜ |
| R0-04 | La raíz `GET /api/becas/` responde 403 con `Authorization: Token` | BAJA (MINOR) | revisión Ola 0 | 3 (app de campo) | S | ⬜ |
| R0-06 | `_get_relevamiento` puede dar `MultipleObjectsReturned` (500) | BAJA (MINOR) | revisión Ola 0 | 3 (link público) | S | ⬜ |
| R0-07 | `q_uuid_en_texto` sin guarda de tipo | BAJA (MINOR) | revisión Ola 0 | 3 (link público) | S | ⬜ |

---

## CRÍTICA

### SIIS-01 · El alta en SIIS no tiene exclusión mutua
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SiisAltaSinExclusionTests.test_reentrada_con_primero_en_vuelo_duplica_alta`: 2 POST y 2 `ENVIADO`) · **Origen:** A1-01, A2-02, A8-S1 (comandos), A4-01 (punto 3), V2-NEW-04 · **Ola:** 1 · **Esfuerzo:** M · **Decisión:** — (SIIS-05 tiene la suya)

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 127), 05-oct-2026 — `EnvioSIIS.vigente` (nullable) dentro del índice único `(formulario, vigente)` más la reserva de `_reservar()`: lock corto de la fila del `Formulario`, relectura de `vigente` y `EN_PROCESO` commiteado **antes** del POST, que queda fuera de toda transacción. Las siete vías pasan por la misma reserva, incluida `sincronizar_tabla_intermedia`, y las tres listas de candidatos excluyen con `~Exists(vigente)`. La pantalla deja de ofrecer reenviar lo que el servicio no mandaría, con guard de un solo envío en el form. Migración `programas.0075_enviosiis_vigente`, probada ida y vuelta contra **MariaDB 10.11 real** con 40.100 envíos (6,9 s / 4,0 s) y duplicados sembrados de los dos tipos. **Test permanente:** `programas/tests/test_siis_un_solo_envio.py::UnSoloEnvioVigenteTests.test_segundo_envio_con_primero_en_vuelo_no_llama_a_siis` (y `test_indice_unico_rechaza_un_segundo_vigente`, `test_la_tabla_intermedia_no_manda_un_caso_ya_tomado`).

**⚠ Actualizar (03-oct-2026):** #517/#518 (01-oct) sumaron una **séptima vía** de alta sin exclusión: `sincronizar_tabla_intermedia` (`siis_envio.py:759`), que `procesar_casos_siis --destino siis` y `correr_alta_siis` corren antes de los candidatos, con el mismo check-then-act (`envios_sis.filter(ENVIADO).exists()` → `_mandar_a_siis`). El POST quedó en `_mandar_a_siis` (`:667`) y `enviar_beneficiario_a_siis` está en `:624`. La migración de SIIS-01 ya no puede ser la `0074` (la ocupa `0074_altaintermediasiis`): es la siguiente libre. La reserva tiene que cubrir también la sincronización de la tabla intermedia.
- **Ubicación:** `programas/services/siis_envio.py:592-631` (`enviar_beneficiario_a_siis`: lee `envios_sis.filter(estado=ENVIADO)` sin lock → `armar_payload` → `cargar_beneficiario` (HTTP de hasta 40 s) → recién después `EnvioSIIS.objects.create(ENVIADO)`); modelo `programas/models/__init__.py:2824` (`EnvioSIIS`).
- **Las seis vías de envío, todas sin exclusión:** botón «Informar/Reenviar» (`revision.py:798-810`), aprobar (`revision.py:980`), promover desde Cupo (`views/cupo.py:45,194`), hilo del masivo (`proceso_masivo.py:270`) y los comandos `reenviar_siis_pendientes` (:41), `enviar_casos_siis` (:258) y `procesar_casos_siis` (:237 vía `procesar_caso`). `diagnosticar_siis --alta` llama a `cargar_beneficiario` directo (SIIS-19). El form de la plantilla (`formulario_detalle.html:657-660`) no tiene guard de doble envío.
- **Escenario:** doble clic, masivo + botón, o un comando a mano mientras el primer POST espera a SIIS → dos altas del mismo beneficiario, **irreversibles** (SIIS no tiene baja).
- **Causa raíz:** check-then-act sin fila «en curso», sin constraint y sin lock.
- **Lo que NO hay que hacer:** mantener un `select_for_update` durante el HTTP (la «opción mínima» de A1-01): el `read_timeout` de 10 s mata al segundo request. Tampoco es cierto que en MariaDB «solo el candado da unicidad» (A2-02): una columna nullable dentro de un índice único la emula.
- **Propuesta** (una migración junto con SIIS-02 y SIIS-05; si antes se mergea SIIS-07, es la `programas.0074`, que depende de la `0073`):
  1. **Modelo `EnvioSIIS`:** `Estado` + `EN_PROCESO` e `INCIERTO` (entran en `max_length=15`); `vigente = models.BooleanField(null=True, default=None, editable=False)` (True en `EN_PROCESO`, `INCIERTO` y `ENVIADO`; NULL en el resto); `Meta.constraints += [UniqueConstraint(fields=["formulario", "vigente"], name="uniq_enviosiis_vigente_caso")]` **sin `condition`** (MariaDB, MySQL y SQLite admiten varios NULL en un índice único: emula el índice parcial y no depende de `supports_partial_indexes`); `resuelto_en = DateTimeField(null=True, blank=True)`; el docstring deja de decir «inmutable» y pasa a «un intento; `EN_PROCESO` se cierra una sola vez en su estado final».
  2. **Migración de datos (RunPython):** `vigente=True` en el `ENVIADO` **más viejo** de cada formulario y NULL en el resto; si un formulario tiene más de un `ENVIADO`, imprimir sus pk y **no fallar** (ver V2-NEW-03).
  3. **Servicio** `enviar_beneficiario_a_siis(formulario, solicitado_por, catalogos=None, exigir_aprobado=True)`:
     ```python
     # 1) Payload FUERA de toda transacción (armar_payload puede ir a SIIS por catálogos)
     try:
         payload, faltantes = armar_payload(formulario, catalogos=catalogos)
     except CatalogoNoDisponible:
         return EnvioSIIS.objects.create(estado=ERROR, codigo_error="ERROR_TECNICO", ..., vigente=None)
     # 2) Reserva: transacción de milisegundos, lock solo de la fila del caso
     with transaction.atomic():
         estado = (Formulario.objects.select_for_update()
                   .filter(pk=formulario.pk).values_list("estado", flat=True).get())
         if exigir_aprobado and estado != Formulario.Estado.APROBADO:      # SIIS-04
             raise ValueError("Solo se informan a SIIS los casos aprobados.")
         vigente = EnvioSIIS.objects.filter(formulario_id=formulario.pk, vigente=True).first()
         if vigente:
             return vigente                       # ENVIADO / EN_PROCESO / INCIERTO: no se llama a SIIS
         if faltantes:
             return EnvioSIIS.objects.create(estado=INCOMPLETO, ..., vigente=None)
         if EnvioSIIS.objects.filter(documento=doc, id_programa=plan, vigente=True).exists():   # SIIS-05
             return EnvioSIIS.objects.create(estado=RECHAZADO, codigo_error="DUPLICADO_LOCAL", ..., vigente=None)
         try:
             with transaction.atomic():           # savepoint: el IntegrityError no envenena la externa
                 envio = EnvioSIIS.objects.create(estado=EN_PROCESO, vigente=True, payload=payload, **base)
         except IntegrityError:
             return EnvioSIIS.objects.get(formulario_id=formulario.pk, vigente=True)
     # 3) HTTP FUERA de la transacción (el EN_PROCESO ya está commiteado)
     resultado = cargar_beneficiario(payload)
     # 4) Cierre condicional: si una conciliación ya lo tocó, no se pisa
     final, vig = _estado_final(resultado)        # SIIS-02
     EnvioSIIS.objects.filter(pk=envio.pk, estado=EN_PROCESO).update(
         estado=final, vigente=vig, siis_id=..., codigo_error=..., detalles=..., respuesta=..., resuelto_en=now())
     envio.refresh_from_db(); return envio
     ```
     Con READ COMMITTED, el segundo request espera el lock de la fila `Formulario` (milisegundos) y después ve el `EN_PROCESO` commiteado; el índice único cubre lo que el lock no cubre.
  4. **Selección de pendientes:** en `candidatos()` (`proceso_masivo.py:140-147`), `reenviar_siis_pendientes._casos` y `enviar_casos_siis._casos`, agregar `.exclude(envios_sis__vigente=True)` (NOT EXISTS sobre el índice nuevo). Resuelve V2-NEW-04 (`reenviar_siis_pendientes.py:21` ordena `-creado` sin desempate).
  5. **`mensaje_envio`:** `EN_PROCESO` → `("info", "El alta ya se está informando a SIIS (desde HH:MM). Recargá en un minuto.")`; `INCIERTO` → `("warning", "No sabemos si SIIS registró el alta: no se reenvía hasta verificarlo con SIIS.")`.
  6. **Plantilla** `formulario_detalle.html:650-660`: botón visible solo si no hay envío vigente (hoy compara `!= 'ENVIADO'`); guard de un solo envío con el patrón `form.dataset.enviando` de `:95-129` y botón deshabilitado (resuelve también BEC-14).
- **Tests a agregar** (`programas/tests/test_siis_envio.py`, `test_candados_concurrencia.py`): `test_segundo_envio_con_primero_en_vuelo_no_llama_a_siis` (el de la PoC invertido: `cargar.call_count == 1`, un solo `vigente=True`); `test_indice_unico_rechaza_segundo_vigente` (dos `create(vigente=True)` → `IntegrityError`; dos con `None` pasan); `test_envio_en_proceso_no_es_candidato` para `candidatos()`, `reenviar_siis_pendientes` y `enviar_casos_siis`; `test_cierre_no_pisa_conciliacion`; test de la migración (2 `ENVIADO` → `vigente` solo en el más viejo).
- **Verificación:** V-STD + V-UI + `manage.py test programas`. **En MariaDB real** (contenedor 3308, `scripts/perf_mysql/`): el `UniqueConstraint` con varios NULL y la migración.
- **Dependencias:** SIIS-07 (0073) antes; V2-NEW-03 antes del deploy; SIIS-02, SIIS-04, SIIS-05 y BEC-14 en el mismo PR.

## ALTA

### SIIS-02 · Un resultado ambiguo se registra como ERROR reintentable, y un proceso muerto entre el POST y el registro no deja rastro
**Severidad:** ALTA · **Estado:** CONFIRMADO-AJUSTADO con test (`ResultadoAmbiguoTests`) · **Origen:** A2-03, A1-03, A8-S1 (ReadTimeout), A2-15 · **Ola:** 1 · **Esfuerzo:** M · **Decisión:** D-S02 (contrato 5xx con ECOM)

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 127), 05-oct-2026 — `cargar_beneficiario` devuelve `resultado` con la tabla de D-S02 completa (token fuera del `try` del POST; `ConnectTimeout` antes que `ConnectionError`; la cadena de urllib3 distingue «no conectó» de «se cortó a mitad»; 401 con un reintento interno). `INCIERTO` queda `vigente` y **no reintentable**; `EN_PROCESO` vencido a los 5 min se ve incierto. Comando nuevo `conciliar_envios_siis` (`--listar` / `--confirmar` / `--liberar --motivo`, en lote y desde el CSV que vuelve de ECOM, en seco por defecto) con traza, tope de 5 errores por caso y el procedimiento corregido en `docs/internal/procedimiento-alta-siis.md`. **Ronda 2:** el freno de las corridas pasa a contar los inciertos —`proceso_masivo.Freno`, una sola pieza para las cuatro vías, con `--max-inciertos` (default 3) y las dos rachas en paralelo—, porque si no, con SIIS caído la corrida no cortaba nunca y cada vuelta dejaba un caso más tomado. **Ronda 3:** `reenviar_siis_pendientes` también lo honra —heredaba los flags y los ignoraba— y el test ejercita las tres vías con SIIS contestando mal, no solo que acepten el flag. La tabla de desenlaces, con el 503 sin cuerpo y el 500 con JSON roto marcados como decisión nuestra y no contrato, quedó en `docs/internal/temas/siis-api.md`. **Test permanente:** `programas/tests/test_siis_un_solo_envio.py::ResultadoInciertoTests.test_un_resultado_incierto_no_se_reintenta_por_ninguna_via` (y `programas/tests/test_siis_service.py::ResultadoDelAltaTests`, la tabla entera).

**⚠ Actualizar (03-oct-2026):** la fila «Ctrl+C a mitad: Seguro» del punto 5 está hoy en `docs/internal/procedimiento-alta-siis.md:210` (el archivo entró a `development` con #513), y el docstring de `correr_alta_siis` repite «volver a lanzarlo… no duplica nada»: corregir los dos.
- **Ubicación:** `programas/services/siis.py:326-381` (`cargar_beneficiario` mete en `ERROR_TECNICO, reintentable=True` toda `RequestException`, cualquier 5xx y cualquier HTTP sin código; 404/409/422/429 → `ERROR_INTERNO`, en `CODIGOS_REINTENTABLES`; `_token()` dentro del mismo `try`).
- **Ajuste:** no hay cron nocturno que reintente (A2-03 lo afirmaba). El reintento automático existe igual: `candidatos()` toma todo APROBADO cuyo último envío ≠ ENVIADO, así que **la próxima corrida del masivo** reenvía los ERROR; también el botón «Reenviar» y los comandos a mano. A1-03 se confirma por el mecanismo: gunicorn `--max-requests 1000 --max-requests-jitter 100 --graceful-timeout 30` (`docker-entrypoint.sh:115-122`) recicla el worker y mata el hilo daemon; igual cada deploy o reinicio.
- **Propuesta:**
  1. Obtener el token **antes** del `try` del POST, en su propio `try` (fallo → `resultado="NO_ENVIADO"`).
  2. Campo nuevo `resultado` en el dict devuelto:

     | Situación | `resultado` | Estado `EnvioSIIS` | `vigente` |
     |---|---|---|---|
     | 200/201 | `OK` | ENVIADO | True |
     | `ConnectTimeout`; `ConnectionError` por `NewConnectionError`/`NameResolutionError`; `_SiisConfigurationError`; fallo del token | `NO_ENVIADO` | ERROR (reintentable) | NULL |
     | 401 | `NO_ENVIADO`: borrar token y **reintentar una vez** adentro | ERROR si vuelve a fallar | NULL |
     | 400 `DATOS_INVALIDOS`; otros 4xx ≠ 401/408/429 sin código | `RECHAZADO` (`codigo="CONFIGURACION"` en los sin código) | RECHAZADO | NULL |
     | 503 con `error == "ERROR_BD_LEGACY"` | `NO_ENVIADO` | ERROR | NULL |
     | `ReadTimeout`, otros `ConnectionError`, `ChunkedEncodingError`, 408/429, 500, 502, 504, 5xx sin código reconocido | `INCIERTO` (`codigo="RESULTADO_INCIERTO"`, `reintentable=False`) | INCIERTO | **True** |

     `requests.ConnectTimeout` hereda de `ConnectionError`: su `except` va primero.
  3. `EN_PROCESO` huérfano: `EnvioSIIS.EN_PROCESO_VENCE = timedelta(minutes=5)` (> 2 × (10 + 30) s + margen); propiedad `EnvioSIIS.incierto` = estado `INCIERTO` o `EN_PROCESO` con `creado` viejo; la pantalla lo muestra como incierto.
  4. Comando nuevo `conciliar_envios_siis`: `--listar` (CSV con pk, DNI, plan, fecha, `siis_id`) para mandar a ECOM; `--confirmar <pk> [--siis-id N]` → ENVIADO; `--liberar <pk> --motivo "..."` → ERROR con `vigente=NULL`, `codigo_error="INCIERTO_LIBERADO"` y traza en `TracaFormulario` (solo con la confirmación de ECOM). UI opcional (S): botón «Liberar para reenvío» con motivo, detrás de una capacidad nueva del módulo `becas_admin` en `core/rbac.py:CATALOGO`.
  5. Corregir `docs/internal/procedimiento-alta-siis.md:156` («Ctrl+C a mitad: Seguro» → `EN_PROCESO` → incierto → se concilia).
  6. Contador de reintentos (A2-15): `reenviar_siis_pendientes` y `candidatos()` saltean casos con 5 o más `ERROR` seguidos y los listan para revisión.
- **Tests a agregar** (`test_siis_service.py`, `test_siis_envio.py`): parametrizar `requests.post` (`ReadTimeout` → `INCIERTO`; `ConnectTimeout` → `NO_ENVIADO`; 401 y después 201 → `OK` con 2 llamadas; 404/422 → `RECHAZADO/CONFIGURACION`; 503 `ERROR_BD_LEGACY` → `NO_ENVIADO`; 502 sin body → `INCIERTO`); `test_incierto_no_se_reintenta_por_ninguna_via`; `test_en_proceso_viejo_se_ve_incierto`; `test_conciliar_liberar_permite_reenvio_y_deja_traza`; `test_muerte_despues_del_post_deja_en_proceso` (mock que lanza `SystemExit`).
- **Verificación:** V-STD + V-UI (mensajes).
- **Dependencias:** SIIS-01 (estado y `vigente`). Va **antes** de SIIS-09. D-S02: default 503 `ERROR_BD_LEGACY` se reintenta y 500 es `INCIERTO`; pedir a ECOM una clave de idempotencia (`id_externo` = pk del formulario), que es la solución de fondo.

### SIIS-03 · Proceso masivo: se da por muerto estando vivo, no se puede frenar, un zombi convive con la corrida nueva y los comandos ignoran el candado
**Severidad:** ALTA (MEDIA con SIIS-01 resuelto) · **Estado:** CONFIRMADO con test (`LatidoTests`, `test_comando_reenviar_ignora_corrida_viva`) · **Origen:** A1-02, A4-01, A8-S2, A8-S1 (comandos), V2-NEW-01, V2-NEW-02, A5-33 · **Ola:** 1 · **Esfuerzo:** S (puntos 1-6) / M (punto 7) · **Decisión:** D-S03 (CronJob)

**Resolución:** ✅ Resuelto en #590 (Cambio 136), 06-oct-2026 — puntos 1 a 6. `_latir()` (un `UPDATE` de una columna) antes de `ids_de`, cada 100 candidatos mirados en `elegir_completos(..., al_mirar=)` y **por caso** en `correr()`; `LATIDO_VENCIDO` de 2 a 5 min, atado por test a `SIIS_API_CONNECT_TIMEOUT + SIIS_API_TIMEOUT` × 3; por caso se relee `cancelacion_pedida` y `estado` —cancelar corta en el caso, no al cerrar el lote, y un hilo cuya corrida ya fue reemplazada se retira **sin escribir**—; `crear_corrida` cierra como `DETENIDA` la que quedó sin señal («sin señal desde las HH:MM; la reemplaza la corrida #N»); `proceso_masivo_frenar` marca por **programa** (A5-33) y **sin** filtrar por latido (V2-NEW-01), y la pantalla no ofrece el botón cuando la corrida viva es de otro programa. El candado de corrida viva quedó en `ComandoSiisBase.exigir_sin_corrida_viva` —lo piden los cuatro comandos, con `--ignorar-corrida`— y `correr_alta_siis` lo pide en su paso 1; se pregunta con el candado tomado (`proceso_masivo.exigir_sin_corrida_viva`), no leyendo la tabla. **Punto 7 (CronJob) no se hace:** default de D-S03. **Ronda 2 de la revisión:** `--ignorar-corrida` pasa a exigir `--motivo` y deja rastro (log + nota en la corrida que pisa, `registrar_corrida_ignorada`); la guarda solo corre con `--aplicar` también en `correr_alta_siis`; y queda escrito —en el docstring de `exigir_sin_corrida_viva` y en el procedimiento— que la exclusión es **de una sola dirección**: cubre «la pantalla ya corre y alguien lanza un comando», no la inversa, porque el candado se suelta en el commit y no se puede sostener una hora contra un `read_timeout` de 10 s. Lo irreversible sigue cubierto por la reserva de SIIS-01. Migración `programas.0076_corridasiis_incompatibles` (es de BEC-11). **Test permanente:** `programas/tests/test_proceso_masivo.py::LatidoTests.test_una_corrida_lenta_nunca_se_ve_interrumpida` (y `LatidoTests.test_hay_latido_antes_de_empezar_a_elegir`, `CorridaReemplazadaTests` ×2, `PantallaProcesoMasivoTests.test_frenar_alcanza_a_una_corrida_sin_latido` y `.test_frenar_solo_afecta_a_la_corrida_de_este_programa`, `CorrerTests.test_frenar_corta_en_el_caso_y_no_al_cerrar_el_lote`, `test_siis_un_solo_envio.py::ParidadComandosSiisTests.test_los_cuatro_abortan_con_una_corrida_viva`, `test_correr_alta_siis.py::PrecondicionesTests.test_con_una_corrida_viva_no_arranca` y, contra motor real, `test_candados_concurrencia.py::CarreraDeCorridaMasivaTests`).

**⚠ Actualizar (03-oct-2026):** `correr()` hoy en `proceso_masivo.py:395` (`ids_de` + `hidratar_por_lotes` en `:410`). #513 sumó `correr_alta_siis`, que encadena `procesar_casos_siis` por tandas de 500 (`_por_tandas`) sin `_tomar_candado()` ni `en_curso()`: es otro comando que ignora la corrida viva (punto 6).
- **Ubicación:** `programas/services/proceso_masivo.py:356-358` (primer latido recién después de `ids_de + hidratar_por_lotes + elegir_completos` sobre todos los candidatos), `:360-389` (latido, `MAX_ERRORES` y freno evaluados por lote de 40), `:367`; `programas/models/__init__.py:3103` (`LATIDO_VENCIDO = 2 min`); `programas/views/proceso_masivo.py:97` (`proceso_masivo_frenar` usa `en_curso()`), `:101-106`.
- **Escenario (reproducido):** dentro de `elegir_completos` el latido es `None` (con 7.496 candidatos × 6-8 consultas por `armar_payload`, la selección tarda ~40-65 s según V4 y **se acerca** a los 2 min, ver PERF-01); por caso: token, validar y alta, hasta 40 s cada uno; `en_curso()` devuelve `None` y `crear_corrida` crea otra **con el hilo viejo vivo** (2 corridas EN_CURSO). V2-NEW-01: una corrida viva pero lenta aparece «interrumpida» y **no se puede frenar**. V2-NEW-02: con SIIS caído siguen hasta 30 casos más tras el décimo error (más de 40 min golpeando un servicio caído). Comandos `reenviar_siis_pendientes`, `enviar_casos_siis --aplicar` y `procesar_casos_siis --aplicar` no toman `_tomar_candado()` ni miran `en_curso()`. A5-33: «Frenar» detiene la corrida global aunque sea de otro `ProgramaSiis`.
- **Propuesta (se respeta el hilo del Cambio 88):**
  1. `_latir(corrida)` = `CorridaSiis.objects.filter(pk=corrida.pk).update(latido=timezone.now())`: antes de `ids_de`; cada 100 mirados en `elegir_completos` (parámetro `al_mirar=None`); **por caso** en `correr()`.
  2. `CorridaSiis.LATIDO_VENCIDO = timedelta(minutes=5)`, con comentario que lo derive de `SIIS_API_CONNECT_TIMEOUT + SIIS_API_TIMEOUT` × 3 llamadas.
  3. Por caso: `corrida.refresh_from_db(fields=["cancelacion_pedida", "estado"])`; `cancelacion_pedida` → CANCELADA; `estado != EN_CURSO` → `return` sin escribir; `seguidos >= max_errores` después de cada caso.
  4. `crear_corrida`: con el candado tomado, las EN_CURSO con latido vencido → `update(estado=DETENIDA, finalizada=now, mensaje="Interrumpida: sin señal desde HH:MM; reemplazada por la corrida #N")`.
  5. `proceso_masivo_frenar`: `CorridaSiis.objects.filter(estado=EN_CURSO, programa=programa).update(cancelacion_pedida=True)` (incluye las que parecen interrumpidas y solo las del programa, A5-33).
  6. Comandos: helper `proceso_masivo.exigir_sin_corrida_viva()` = `with transaction.atomic(): _tomar_candado(); if CorridaSiis.en_curso(): raise CorridaEnCurso`, llamado al empezar `handle()` de los 3 comandos (→ `CommandError`), con `--ignorar-corrida` para emergencias.
  7. Opcional (D-S03, default no): `CorridaSiis.Estado.PENDIENTE` + CronJob `procesar_corridas_siis` cada minuto con `select_for_update(skip_locked=True)` (MariaDB ≥10.6: confirmar versión PRD).
- **Tests a agregar** (`test_proceso_masivo.py`): `test_latido_durante_elegir_completos`, `test_latido_por_caso` (reloj +10 s por caso, `interrumpida is False` tras 20 casos), `test_crear_corrida_detiene_la_interrumpida`, `test_hilo_reemplazado_se_retira`, `test_frenar_alcanza_a_corrida_sin_latido`, `test_frenar_solo_afecta_la_corrida_del_programa`, `test_max_errores_corta_en_el_caso_y_no_al_final_del_lote`, `test_<comando>_aborta_con_corrida_viva` (×3).
- **Verificación:** V-STD.
- **Dependencias:** SIIS-01 y SIIS-02 primero. PERF-01 baja el tiempo hasta el primer latido.

### SIIS-04 · El masivo informa casos que cambiaron de estado después de hidratarlos
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`EstadoViejoEnMasivoTests`) · **Origen:** A1-04, V2-NEW-06 · **Ola:** 1 · **Esfuerzo:** S (dentro de SIIS-01)

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 127), 05-oct-2026 — la reserva de SIIS-01 relee el estado con `select_for_update` y lanza `ValueError`; `procesar_caso` lo captura y cuenta `no_aprobable`, `enviar_casos_siis` lo cuenta aparte (con `estados_permitidos` cuando se levanta la guarda, V2-NEW-06) y `sincronizar_tabla_intermedia` deja la fila pendiente contándola como `no_aprobables`. **Test permanente:** `programas/tests/test_siis_un_solo_envio.py::EstadoRelidoBajoLockTests.test_un_caso_dado_de_baja_despues_de_hidratar_no_se_informa`.

**⚠ Actualizar (03-oct-2026):** #517 sumó dos caminos: `guardar_en_tabla_intermedia` chequea el estado sobre el objeto hidratado y `sincronizar_tabla_intermedia` manda el payload guardado **sin releer el estado**, así que un caso que pasó a BAJA después de guardarse en la tabla se informa igual. La relectura bajo lock de SIIS-01 tiene que cubrir ese camino.
- **Escenario (reproducido):** se hidrata un APROBADO, pasa a BAJA por `update()` y `procesar_caso` lo manda igual a SIIS. Igual en `enviar_casos_siis` (ventana menor). V2-NEW-06: con `--estados ENVIADO,RECHAZADO --si-entiendo` (`exigir_aprobado=False`) un caso que pasó a BAJA entre el listado y su lote se informa igual.
- **Propuesta:** la reserva de SIIS-01 relee `estado` con `select_for_update` y lanza `ValueError` si no es APROBADO; en `procesar_caso` (`proceso_masivo.py:270`) capturarlo → `cuenta.no_aprobable += 1; return None`. Con `exigir_aprobado=False`, la función recibe `estados_permitidos` y exige que el estado releído siga dentro.
- **Tests a agregar:** el de la PoC invertido (`cargar.call_count == 0`, `cuenta.no_aprobable == 1`); `test_enviar_casos_estado_cambiado_no_se_informa`.

### SIIS-06 · `sincronizar_programas_siis` bloquea todos los programas ante un catálogo vacío
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SyncCatalogoVacioTests`) · **Origen:** A2-04, A8-S4 · **Ola:** 1 · **Esfuerzo:** S · **Decisión:** D-S06 (umbral)

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 151), 06-oct-2026 — `sincronizar_estado_programas(dry_run=False, forzar=False)` recorre entero y **recién después escribe**, porque la guarda necesita el total y no «cuántos vi hasta acá»: catálogo vacío → `SiisCatalogError` sin tocar nada, y si los que pasarían a `DESCONOCIDO` son todos los vinculados o más del 50 % (default de **D-S06**), lo mismo, con el mensaje contando cuántos de cuántos y cómo salir (`--forzar`, que es el flag nuevo del comando). La guarda **no se aplica con un solo programa vinculado**: ahí «todos» y «más de la mitad» son siempre ciertos y dejaría de poder detectarse nunca una baja real. La ausencia parcial —lo normal, un programa dado de baja— se sigue escribiendo sola. `listar_programas` y `listar_programas_todos` dejan de cachear la lista vacía, que multiplicaba el error por los cinco minutos del TTL. El `CommandError` deja el CronJob de las 04:00 en rojo, que es la forma de que se entere alguien. **Cambia a propósito la caracterización de R-06:** `test_catalogo_vacio_marca_todo_desconocido` existía «para que la Ola 1 lo decida a la vista» y hoy es `test_catalogo_vacio_no_escribe_nada`. **Test permanente:** `programas/tests/test_siis_catalogo_y_payload.py::SincronizacionDefensivaTests.test_un_catalogo_vacio_no_escribe_nada` (y `.test_mas_de_la_mitad_ausentes_no_se_escribe_sin_forzar`, `.test_una_ausencia_de_una_entre_tres_se_escribe_sola`, `.test_con_forzar_la_ausencia_masiva_se_escribe`, `.test_con_un_solo_programa_vinculado_la_guarda_no_se_aplica`, `.test_un_catalogo_vacio_no_queda_cacheado`, y `programas/tests/test_comandos_siis_caracterizacion.py::SincronizarProgramasSiisTests.test_catalogo_vacio_no_escribe_nada`).

**Ampliado por #PENDIENTE (Cambio 154), 06-oct-2026 — los dos MINOR que dejó la revisión del PR 4.** (a) La guarda contaba los `DESCONOCIDO` **nuevos** de la corrida y se salteaba por goteo: diez programas vinculados y tres catálogos parciales seguidos (4 ausentes de 10 → 5 → 1) los dejaban a los diez bloqueados sin que saltara nunca. Pasa a contar el estado **resultante**, que es lo que esta ficha pide confirmar («si pasarían a DESCONOCIDO todos los vinculados o más del 50 %»); eso **corrige** la línea «se cuentan las transiciones nuevas» del Cambio 151 y tiene como efecto buscado que el CronJob quede en rojo todas las noches mientras SIIS siga devolviendo catálogos parciales. (b) `--forzar` deja de ser un flag pelado: exige `--motivo`, acepta `--usuario` y deja rastro con el mismo mecanismo que `--ignorar-corrida` (log con quién, cuándo y por qué), solo cuando el forzado hizo falta de verdad. El CronJob corre sin el flag y no cambia. **Test permanente:** `programas/tests/test_siis_catalogo_y_payload.py::SincronizacionDefensivaTests.test_el_goteo_no_saltea_la_guarda` (y `.test_un_programa_que_ya_estaba_bloqueado_sigue_contando`, `.test_el_forzado_queda_en_el_log`, `.test_un_forzar_que_no_hacia_falta_no_ensucia_el_log`, `.test_el_forzar_del_comando_exige_motivo`, `.test_el_motivo_en_blanco_no_cuenta`, `.test_el_usuario_del_comando_llega_al_log`, `.test_el_cronjob_corre_sin_motivo_porque_no_fuerza`).
- **Ubicación:** `programas/services/siis_sync.py:25-38`; `programas/models/__init__.py:1378` (`DESCONOCIDO` es bloqueante); `programas/services/siis.py:140` (`_items`, sin seguir `next`) usado por `_catalogo_programas` (`:180-185`), `:201-212` (`listar_programas_todos` cachea también la lista vacía). Corre a las 04:00 (`cronjobs.yaml:78-90`).
- **Escenario (reproducido):** con `listar_programas_todos → []` el programa pasa a `DESCONOCIDO` y `pausa_efectiva` deja de ser `None`: Becas queda bloqueado.
- **Propuesta** (`sincronizar_estado_programas(dry_run=False, forzar=False)`): (1) `if not catalogo: raise SiisCatalogError("SIIS devolvió un catálogo vacío: no se sincroniza.")`; (2) si pasarían a DESCONOCIDO **todos** los vinculados (con 2 o más) o más del 50 % (default D-S06) y no se pasó `forzar`, lanzar sin escribir; (3) `--forzar` en el comando; (4) no cachear una lista vacía.
- **Tests a agregar:** vacío → lanza y no cambia nada; 1 de 3 ausente → ese pasa a DESCONOCIDO; 3 de 3 → lanza, y con `forzar` escribe.

### SIIS-07 · `token_publico` en `char(32)`: el arreglo está en una rama sin mergear
**Severidad:** ALTA · **Estado:** CONFIRMADO-AJUSTADO (merge simulado: tests OK y `makemigrations --check` limpio) · **Origen:** A1-05, A2-05, A8-S3 · **Ola:** 1 (primer PR) · **Esfuerzo:** S · **Decisión:** pregunta abierta H-03 (¿la rama quedó sin PR a propósito?)

**Resolución:** ✅ Resuelto en #515 (Cambio 99), 01-oct-2026 — migración `programas.0073_ampliar_relevamiento_token_publico` (`char(36)`; normaliza a guiones solo si el motor tiene UUID nativo) y búsqueda en las dos formas con `q_uuid_en_texto` / `relevamiento_publico_por_token` (portal y `diagnosticar_integraciones --token`). Queda operativo: P-11/P-12 y confirmar en testing de ECOM el alta y un link viejo después del deploy (no consta la prueba contra MariaDB 10.7+ real). Seguimientos: R0-06 y R0-07.
- **Ubicación:** `programas/models/__init__.py:1812`; `development` busca con `token_publico=token` (`portal/views/inscripcion.py:110`, `diagnosticar_integraciones.py:286`). El resto de los `UUIDField` ya están ampliados (0047/0048, users 0023, legajos 0007): **solo falta este**.
- **Escenario:** con MariaDB ≥10.7, Django 5 manda UUID con guiones a una columna `char(32)` → «Data too long» al crear un relevamiento público y fallos al buscar el link. Si PRD es ≥10.7, **el alta pública hoy da 500 en PRD** (confirmar con P-11).
- **Estado de `origin/fix/token-publico-uuid-mariadb`:** 4 commits sobre `5a210cf` (`e94f85b` código, `8c598a3` y `59b7352` requerimientos, `fad9f07` CLAUDE.md). Migración `programas/0073_ampliar_relevamiento_token_publico.py` (`RunPython` solo en MySQL/MariaDB: `MODIFY char(36) NULL` y normalización a guiones si `has_native_uuid_field`; reversa a hex y `char(32)`; `atomic=False`; depende de `0072_formulario_dni_titular`, que **sigue siendo la última de `development`**); `q_uuid_en_texto` y `relevamiento_publico_por_token` en `programas/services/becas.py`; `_get_relevamiento` del portal; `--token` de `diagnosticar_integraciones`; tests en `portal/tests/test_inscripcion.py`, `test_becas_models.py`, `test_diagnosticar_integraciones.py`. Merge simulado: **conflicto solo en `docs/internal/requerimientos.md`**.
- **Propuesta (para mergear):**
  1. Renumerar el requerimiento: «Cambio 95» ya existe en `development` («Datos del ciudadano fuera de los handlers inline») y el último era el 98 al 01-oct. Pasa al **siguiente número libre** (Cambio 99 si nadie registró otro antes; confirmarlo con `scripts/requerimientos.py`): fila del índice, título y referencias «Cambio 95» del CLAUDE.md de la rama, `portal/views/inscripcion.py:104`, `diagnosticar_integraciones.py:295`, `portal/tests/test_inscripcion.py:350` y `test_diagnosticar_integraciones.py:281`. Resolver el conflicto del índice y correr `requerimientos.py --check`.
  2. Probar la 0073 **contra MariaDB 10.7+ real** (en SQLite `UUIDExternosMySQLTests` se saltea): con una fila en hex, migrar, crear un relevamiento público y abrir el link viejo.
  3. Opcional: system check (A8-S3) con allowlist de `UUIDField` ampliados para que no se repita.
- **Tests a agregar:** los de la rama.
- **Verificación:** V-STD + prueba en MariaDB (banco `scripts/perf_mysql/`, contenedor 3308).
- **Dependencias:** va **antes** de la migración de SIIS-01 (0074). Un restore posterior vuelve a traer filas en hex: `q_uuid_en_texto` cubre token y `client_uuid` (ver V2-NEW-05 para legajos).

### SIIS-08 · Una identidad validada no corrige un legajo autodeclarado, y a SIIS viajan los datos sin validar
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Origen:** A2-06 · **Ola:** 1 · **Esfuerzo:** M · **Decisión:** D-S08

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 158), 07-oct-2026 — **default de D-S08** (opción mínima, sin migración): `resolver_ciudadano_offline` compara el legajo que ya existía contra la identidad que acreditó el padrón o Base de Personas y, si difieren, deja la **identidad acreditada** en `datos_siis["_identidad_acreditada"]` y una traza por campo; `armar_payload` la vuelve a comparar y, mientras no coincida, deja `faltantes["identidad"]`, así que el caso queda INCOMPLETO y no llega a `cargar_beneficiario`. **Un desvío de la ficha, a favor:** se guarda la identidad acreditada y no una marca «hay conflicto». Con la marca, un caso quedaba bloqueado para siempre salvo que alguien se acordara de borrarla a mano después de corregir el legajo; guardando la identidad, la comparación se rehace contra el legajo **de ahora** y el caso se destraba solo. Solo se comparan los campos donde los dos lados tienen valor: que al legajo le falte la fecha de nacimiento no es un conflicto de identidad —el payload ya lo reclama por su cuenta— y marcarlo mandaría a revisar la identidad de alguien por un dato que no está. Lo autodeclarado (`origen` = `manual`) nunca marca nada. **La opción de fondo (`Ciudadano.identidad_origen` con migración) no se hizo:** quién manda sobre el legajo es la decisión abierta de D-S08 y la opción mínima es su default registrado. **Test permanente:** `programas/tests/test_siis_que_viaja.py::IdentidadAcreditadaTests.test_un_legajo_en_conflicto_no_llega_a_llamar_a_siis` (y `.test_la_identidad_acreditada_queda_registrada_y_frena_el_envio`, `.test_corregir_el_legajo_destraba_el_caso_sin_tocar_la_marca`, `.test_un_legajo_que_coincide_no_deja_marca_ni_traza`, `.test_una_identidad_autodeclarada_nunca_marca_conflicto`, `.test_un_campo_vacio_en_el_legajo_no_es_un_conflicto_de_identidad`, `.test_un_legajo_nuevo_se_crea_con_la_identidad_acreditada`).

**⚠ Actualizar (03-oct-2026):** `resolver_ciudadano_offline` hoy en `programas/services/becas.py:262` (#515 sumó `q_uuid_en_texto` más arriba).
- **Ubicación:** `programas/services/becas.py:241-279` (`resolver_ciudadano_offline`: si el ciudadano existe, solo completa `genero`/`localidad` y descarta `datos_identificacion` de origen padrón o personas); `armar_payload` usa `formulario.ciudadano`.
- **Escenario:** un legajo creado antes con datos autodeclarados (o falsos, G1-01) recibe un caso validado por padrón o Gran Base; el caso queda validado pero el alta a SIIS sale con el nombre del legajo.
- **Propuesta (default D-S08 = opción mínima, sin migración):** en `resolver_ciudadano_offline`, si `not creado` y `datos.get("origen") in ("padron", "personas")`, comparar nombre, apellido y fecha normalizados; si difieren, `registrar_traza(... "Identidad del legajo distinta a la validada" ...)` y `formulario.datos_siis["_identidad_en_conflicto"] = {campo: (legajo, validado)}`; en `armar_payload`, si existe la clave, `faltantes["identidad"] = "El legajo no coincide con la identidad validada: corregir antes de informar"`. De fondo (con migración): `Ciudadano.identidad_origen` (`manual`/`padron`/`personas`/`renaper`) seteado en todas las altas; si el legajo es `manual` y llega una identidad validada, se actualiza.
- **Tests a agregar:** legajo manual + caso validado con otro nombre → traza, faltante y `cargar_beneficiario` no se llama; legajo igual al validado → sin faltante.
- **Dependencias:** la API de campo usa la misma función. Relacionado con G1-01 y G1c-08.

### V2-NEW-03 · Antes de migrar SIIS-01 hay que medir si ya hay altas duplicadas en PRD
**Severidad:** ALTA (operativo) · **Estado:** — (consulta a correr) · **Origen:** V2-NEW-03 · **Ola:** 1 (paso 0) · **Esfuerzo:** S
- **Propuesta:** correr en PRD, en solo lectura, las consultas P-01 de README §3. Si hay filas, el duplicado ya ocurrió: el listado va a ECOM para depurar en SIIS. La migración de SIIS-01 no falla por ellos (deja `vigente` solo en el más viejo).

## MEDIA

### SIIS-05 · Mismo DNI y mismo plan informados desde casos distintos
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`test_mismo_dni_en_otro_caso_se_informa_otra_vez`: 2 POST) · **Origen:** A2-07 · **Ola:** 1 · **Esfuerzo:** S · **Decisión:** D-S05

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 127), 05-oct-2026 — columna derivada `clave_persona_plan` (`"<documento>:<id_programa>"` mientras el envío esté vigente, `NULL` si no) dentro de un índice único: la misma técnica que `vigente`, una fila más arriba. La consulta en Python se queda solo para el mensaje («ya informado en el caso #N»); la regla la garantiza el motor, y la reserva traduce el `IntegrityError` a `DUPLICADO_LOCAL`. **Ronda 2 de la revisión:** sin el índice, `_duplicado_local` era un check-then-act y dos procesos sobre el mismo DNI y plan pasaban los dos (19 de 25 en MariaDB real). La migración resuelve además los duplicados cruzados que ya existen en PRD sin liberar ninguno (ver la entrada del Cambio 127). Aplicado el default de **D-S05**. **Test permanente:** `programas/tests/test_siis_un_solo_envio.py::DuplicadoLocalTests.test_con_dos_procesos_a_la_vez_igual_sale_una_sola_alta` (y `test_el_mismo_dni_y_plan_en_otro_caso_no_se_informa_otra_vez`).
- **Causa:** RN-P5 deduplica por convocatoria, no por programa; la idempotencia es por formulario.
- **Propuesta:** en la reserva de SIIS-01, `EnvioSIIS.objects.filter(documento=doc, id_programa=plan, vigente=True).exclude(formulario=f).exists()` → `RECHAZADO` local con `codigo_error="DUPLICADO_LOCAL"` y `detalles={"_": ["Ya informado en el caso #N"]}`, sin llamar a SIIS; índice `(documento, id_programa)` en la misma migración; el masivo cuenta los `DUPLICADO_LOCAL` aparte. Solo si D-S05 = «nunca»: columna `clave_persona_plan = CharField(max_length=40, null=True, unique=True)` = `f"{documento}:{id_programa}"` cuando está vigente (NULL si no). Si D-S05 = «sí, con otra función», la clave pasa a `(documento, id_programa, id_funcion)`.
- **Tests a agregar:** el de la PoC invertido; `test_duplicado_local_no_bloquea_si_el_otro_no_es_vigente`.

### SIIS-09 · Llamadas externas encadenadas y síncronas que superan los 60 s de nginx
**Severidad:** MEDIA · **Estado:** CONFIRMADO (configuración) · **Origen:** A2-08, A4-10, A4-17 (= PERF-09) · **Ola:** 1 · **Esfuerzo:** S-M · **Decisión:** D-S09 (timeouts, pendiente del Cambio 91)

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 154), 06-oct-2026 — **PERF-09 se cierra con esta misma ficha**. Un timeout por tipo de llamada (default de D-S09): conexión 5 s en las tres integraciones, lectura 10 s para las consultas (compatibilidad y catálogos de SIIS, Base de Personas, RENAPER), 20 s **solo** para el alta en la tabla intermedia, y `EMAIL_TIMEOUT` 5. El alta se queda dentro del request de `formulario_aprobar` con el timeout corto, como pide el punto 2: lo que no contesta queda INCIERTO y se concilia (SIIS-02). El presupuesto **se declara y se verifica**: `core/integraciones.py::CADENAS` dice qué llamadas encadena cada request y `core.checks.presupuesto_de_llamadas_externas` (`check --deploy`, o sea el CI) falla con `core.E003` si alguna pasa los 55 s —los 60 de nginx menos 5 para lo que no es red—; «Aprobar un caso» queda **justo en 55**, así que la próxima llamada que alguien encadene ahí deja el check en rojo. Cortacircuito en caché (3 fallas de red seguidas → 60 s sin consultar) sobre Base de Personas —el *tope en `identificar`* del punto 4: el resultado ya era `manual`, lo que se ahorra es el hilo retenido— y sobre la consulta de compatibilidad; **no** sobre el alta, que es lo irreversible. `requests.Session` por módulo con `HTTPAdapter(pool_maxsize=10)` en `siis.py` y `personas.py`. **Desvío de la ficha (uno):** el token lleva su propio `SIIS_API_TIMEOUT_TOKEN` de 5 s, que D-S09 no nombra; con `(5, 10)` la cadena de «Aprobar» daba 60 s y no entraba. **No se hizo:** cortacircuito para RENAPER (la ficha solo le pide timeouts; se consulta detrás de login y de a uno) y sesión por módulo en RENAPER (ya tiene la suya, por instancia, con su `Retry` colgando del adaptador). Las líneas de nginx son `:97` y `:172`, no `:92`/`:164`. **Paso operativo:** las variables del entorno de ECOM mandan sobre los defaults; si quedan en 30/20/20/10 el presupuesto no se cumple y `check --deploy` lo marca. **Test permanente:** `programas/tests/test_llamadas_externas.py::PresupuestoDeclaradoTests.test_con_los_timeouts_de_antes_el_check_corta` (y `GranBaseCaidaTests.test_la_cuarta_consulta_no_toca_la_red`, `.test_identificar_cae_a_manual_con_el_cortacircuito_abierto`, `SiisCaidoTests.test_la_cuarta_validacion_de_compatibilidad_no_toca_la_red`, `.test_el_alta_sale_igual_con_el_cortacircuito_de_consultas_abierto`, `TimeoutsQueSalenALaRedTests` ×4, `CortacircuitoTests` ×4 y el resto de `PresupuestoDeclaradoTests`).

**Ampliado por #PENDIENTE (Cambio 158), 07-oct-2026 — los cuatro MINOR que dejó la revisión del PR 5.**
(a) **Los catálogos maestros no estaban en ninguna cadena y «Aprobar» los pedía con la caché fría**
(`armar_payload` → `Catalogos` → `siis.catalogo`, TTL un día): tres GET de 15 s sobre una cadena que ya
estaba **justo en 55**, o sea 100 s de los 60 que aguanta nginx, sin que `core.E003` lo viera. Declararlos no
era opción —no hay un solo segundo libre en esa cadena, con ningún timeout—, así que la llamada **salió del
request**: el backoffice lee una **copia local** (`programas.models.CatalogoSiisLocal`, migración
`programas.0077_catalogo_siis_local`, tabla nueva y vacía) por `siis.catalogo_local`, y las dos vistas que dan
de alta usan `Catalogos.sin_red()`. La copia **no podía ser solo la caché**: es Redis únicamente en `prd` y en
el resto de los ambientes es LocMem por proceso, que se vacía en cada reciclado de worker de gunicorn
(`--max-requests 1000`), así que un «precalentar» por cron no habría llegado nunca a los workers de QA. La
mantienen al día cualquier lectura exitosa del catálogo —masivo y comandos, que no están detrás de nginx— y el
CronJob de `sincronizar_programas_siis`, que suma ese paso (secundario: si un catálogo no se baja, informa y
sigue; un catálogo vacío no pisa la copia buena, mismo criterio que SIIS-06). Con la copia vacía el alta queda
ERROR **reintentable** y el mensaje dice cómo destrabarla. **Queda abierto, de la misma familia:** la pantalla
«Completar datos para SIIS» (`forms.py:283-308`) pide **cinco** catálogos en un GET y tampoco está declarada —
es el mismo agujero en una pantalla que no es irreversible—; se anota como seguimiento, no entró en este PR.
(b) Con `--parallel` y *spawn* (el default en Windows) la guarda sin red **no se instalaba en los workers**:
Django llama ahí al `setup_test_environment` del módulo, no al método del runner, así que la suite paralela
corría con la red abierta. `SuiteParalelaSinRed` la instala en cada worker después del `_init_worker` de
Django. (c) La docstring prometía «ningún test abre HTTP» y era cierto solo para `requests`: `urllib.request` y
`http.client` salían de verdad —los dos tests nuevos lo muestran fallando con un `getaddrinfo` real—; se corta
también `http.client.HTTPConnection.connect`, que cubre los dos esquemas y deja intactas base, Redis y SMTP.
(d) `_SiisConfigurationError` lleva `falta_configuracion`: «Configuración SIIS incompleta» queda para la
variable de entorno vacía y un token que SIIS devolvió mal se loguea como tal, en `validar_compatibilidad` y en
`_cargar_catalogo`. **El cortacircuito no cambia:** ninguno de los dos cuenta como falla, y eso ya tenía test.
**Test permanente de la ronda:** `programas/tests/test_siis_que_viaja.py::CatalogosFueraDelRequestTests.test_las_vistas_que_dan_de_alta_usan_los_catalogos_sin_red`
(y `.test_sin_copia_local_el_catalogo_falla_sin_tocar_la_red`, `.test_la_copia_local_se_lee_sin_cache_y_sin_red`,
`.test_cada_lectura_del_catalogo_deja_la_copia_al_dia`, `.test_un_catalogo_vacio_no_pisa_la_copia_buena`,
`.test_los_catalogos_sin_red_resuelven_el_payload`; `core/tests/test_sin_red.py::ClientesQueNoSonRequestsTests` ×2
y `GuardaEnLosWorkersParalelosTests` ×3; `programas/tests/test_llamadas_externas.py::SiisMalConfiguradoTests.test_un_token_que_no_sirve_no_se_loguea_como_configuracion_incompleta`
y `.test_el_catalogo_distingue_los_dos_motivos`).

**Ronda 2 de la revisión (07-oct-2026).** Cinco hallazgos, dos de ellos del propio arreglo. (a) Mover los clientes a una `Session` de módulo movió el punto de parcheo de los tests, y uno de seguridad del portal se quedó parcheando `programas.services.personas.requests.get`: el mock quedaba en **cero llamadas**, el cliente salía a resolver `personas.example` de verdad y la regresión que cuidaba —que el DNI no viaje en el log— pasaba **por accidente**. Se corrigió el parche, se corrigió la PoC (`poc/test_repro_siis_becas.py`) y, sobre todo, la suite entera pasa a correr **con la red cortada**: `core/tests/runner.py` (`TEST_RUNNER`) sustituye `HTTPAdapter.send`. La sustitución es una asignación y no un `patch(...).start()` porque trece tests usan `addCleanup(patch.stopall)`, que apagaba la guarda a mitad de la corrida. (b) La cadena del paso 1 del link público **no declaraba el reCAPTCHA**, que es su llamada más lenta: decía 30 s cuando el peor caso eran 45. Su timeout era además un escalar —`requests` lo aplica a conectar y a leer— congelado en el import; pasa a ser el par `(RECAPTCHA_CONNECT_TIMEOUT, RECAPTCHA_TIMEOUT)` = `(5, 10)` leído en cada llamada. Se declararon además tres cadenas que faltaban (promover desde la lista de espera, agregar a la lista, alta de usuario). (c) La `Session` de módulo guardaba cookies y las habría reenviado entre personas distintas del mismo proceso: política `SinCookies`. (d) `_SiisConfigurationError` (una variable de entorno que falta) deja de contar como falla del cortacircuito y de loguear «falló 3 veces seguidas». **Test permanente de la ronda:** `core/tests/test_sin_red.py::SinRedEnLosTestsTests.test_la_guarda_sobrevive_a_un_patch_stopall` (y `.test_una_llamada_sin_mock_falla_en_vez_de_salir_a_internet`, `.test_una_sesion_propia_tampoco_sale`; `test_llamadas_externas.py::PresupuestoDeclaradoTests.test_el_paso_1_del_link_cuenta_el_captcha`, `.test_subir_el_timeout_del_captcha_deja_el_check_en_rojo`, `SesionCompartidaTests` ×3, `SiisMalConfiguradoTests` ×2; `portal/tests/test_seguridad_publica.py::LogsSinSecretosTests.test_el_documento_no_viaja_en_el_error_de_gran_base`).
- **Ubicación:** `config/settings.py:428-429`, `:477-478`, `:487-488` frente a `nginx.conf:92,164` (`proxy_read_timeout 60s`); «Aprobar» encadena validar SIIS → aprobar → alta SIIS → SMTP: SIIS 2 × (10+30) s + token + SMTP 10 s > 120 s. `programas/services/personas.py:107-176` (`requests` sueltos, 10 + 20 s, sin `Session` ni cortacircuito; con Gran Base caída cada paso 1 retiene un hilo hasta 30-60 s).
- **Escenario:** el 504 en «Aprobar» empuja al reintento manual (hoy SIIS-01; con SIIS-01, el reintento devuelve «en proceso»).
- **Propuesta:** (1) timeouts de consulta (compatibilidad, Personas, RENAPER) en `(5, 10)` con variables nuevas `SIIS_API_TIMEOUT_CONSULTA` etc., y el alta en `(5, 20)`; (2) el alta sigue dentro del request de `formulario_aprobar`, con el timeout corto: si SIIS no contesta, el INCIERTO resultante se concilia (SIIS-02); (3) `requests.Session()` por módulo con `HTTPAdapter(pool_maxsize=10)`; cortacircuito en caché (3 fallas seguidas → 60 s sin consultar → «manual»); `EMAIL_TIMEOUT = 5`; (4) tope en `identificar` desde el link público.
- **Tests a agregar:** `test_presupuesto_timeouts` (suma ≤ 55 s por request); mock que falla 3 veces → la cuarta llamada no toca la red.
- **Dependencias:** SIIS-02 **primero** (más timeouts sin SIIS-02 = más reintentos ambiguos).

### SIIS-10 · `normalizar_persona` toma claves de objetos anidados
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`PersonasAplanadoTests`: `nombre == "Resistencia"`) · **Origen:** A2-09 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/personas.py:30-49` (`_aplanar` con `setdefault`: gana la primera aparición a cualquier nivel), `:69-79`, `:178`.
- **Escenario:** `{"data": {"domicilio": {"localidad": {"nombre": "Resistencia"}}, "nombres": "Ana", ...}}` → nombre «Resistencia», marcado **validado** y fijo en el paso 2 del link; dos registros en `data.personas` mezclan datos; no compara el `dni` devuelto.
- **Propuesta:** extracción por ruta: si `data` tiene `persona` (dict) o `personas` (lista), elegir **un** registro con `dni == pedido` y `sexo == pedido` (ninguno o más de uno → `success=False, error="respuesta ambigua"`); leer solo el primer nivel; `nombres` antes que `nombre`; `dni` distinto → error.
- **Tests a agregar:** respuesta con `domicilio.localidad.nombre` → el nombre sale de `nombres`; dos registros → ambigüedad; `dni` distinto → error.
- **Dependencias:** tener la respuesta real de la fuente 13 (task #243).

### SIIS-11 · JSON de SIIS que no es un objeto → `AttributeError` sin capturar
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`CompatibilidadBodyListaTests`) · **Origen:** A2-11 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 151), 06-oct-2026 — el cuerpo se normaliza **antes** del primer `.get`, en los tres lugares que faltaban: `validar_compatibilidad` (`body = {}` si no es dict), `_token` (un cuerpo que no es objeto no puede tener `access_token`: `_SiisConfigurationError`, que todos sus llamadores ya capturan) y `validar_formulario_en_siis` (`data = {}`). Ahí mismo, los dos campos estructurados que se guardan de esa respuesta dejan de poder reventar al escribirlos: `id_consulta` pasa por `uuid.UUID(str(...))` —es un `UUIDField`— y `fecha_hora` por un `parse_datetime` envuelto, que con una fecha bien formada pero imposible (`2026-13-45`) lanza `ValueError`. El intento igual se registra: es la constancia de que SIIS contestó cualquier cosa. **Desvío de la ficha:** no se agrega `AttributeError` a los `except`; con el cuerpo normalizado no hay `AttributeError` que capturar, y un `except` de más taparía uno de verdad. El alta ya estaba cubierta por el Cambio 127. **Test permanente:** `programas/tests/test_siis_catalogo_y_payload.py::RespuestaQueNoEsObjetoTests.test_una_compatibilidad_que_contesta_una_lista_no_revienta` (y `.test_un_token_que_contesta_una_lista_no_revienta`, `.test_una_compatibilidad_que_contesta_un_texto_no_revienta`, `.test_un_catalogo_que_contesta_una_lista_de_strings_no_revienta`, y `ValidacionConDatosIlegiblesTests` ×4).

**Ampliado por #PENDIENTE (Cambio 154), 06-oct-2026 — MINOR de la revisión del PR 4.** Normalizar el cuerpo a `{}` evitaba el 500 pero **tiraba lo que SIIS había contestado**: en la fila registrada, «SIIS no contestó» y «SIIS contestó el HTML de error de un proxy» quedaban indistinguibles, y esa fila es lo único que mira después quien tiene que entender por qué el caso no avanzó. Lo que no es un objeto se guarda ahora en `respuesta["_crudo"]`, recortado a 500 caracteres (`siis.crudo()`), tanto en `validar_compatibilidad` como en el registro de la validación. Se revisaron los lectores de `ValidacionSIS.respuesta`: el único estructurado es `_detalle_validacion_siis` (detalle de la revisión), que ya lee con `isinstance` + `.get` y sigue mostrando lo mismo. No se loguea: no entran datos personales nuevos al log. **Test permanente:** `programas/tests/test_siis_catalogo_y_payload.py::ValidacionConDatosIlegiblesTests.test_lo_que_contesto_siis_queda_guardado_aunque_no_sea_un_objeto` (y `.test_una_respuesta_enorme_se_recorta`, `.test_el_detalle_de_la_pantalla_sobrevive_al_crudo`).
- **Ubicación:** `programas/services/siis.py:234-249` (`validar_compatibilidad`), `:86-87` (`_token`); `programas/services/validacion_siis.py:22-36`. En el masivo cae en el `except Exception` de `correr` → DETENIDA; en `formulario_rechazar` solo se captura `ValueError` → 500.
- **Propuesta:** `body = body if isinstance(body, dict) else {}` y `AttributeError` al `except` en `validar_compatibilidad` y `_token`; en `validar_formulario_en_siis`, `parse_datetime` en `try/except ValueError` e `id_consulta` validado con `uuid.UUID(str(...))` (None si falla).
- **Tests a agregar:** `response.json()` → `[]` da `{"success": False, ...}` sin excepción; `id_consulta="abc"` y `fecha_hora="2026-13-45T00:00:00"` → el registro se crea con esos campos en None.

### SIIS-12 · El payload no prevalida al apoderado
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`ApoderadoTests`: apoderado de 10 años con el DNI del titular → `faltantes == {}`) · **Origen:** A2-13 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 151), 06-oct-2026 — `_apoderado(formulario, faltantes, correcciones=None, hoy=None, dni_titular=None)` prevalida los tres casos que SIIS ya nos venía rechazando: fecha futura, menor de 18 (mismo `_edad`/`MAYORIA_DE_EDAD` que usa el titular, así que el borde «cumple 18 hoy» pasa) y apoderado con el DNI del titular. Se valida **después** de aplicar las correcciones de `datos_siis` (Cambio 98): lo que viaja es lo corregido y es lo que tiene que pasar el control, así que el coordinador tiene salida desde «Completar datos para SIIS» sin tocar el legajo. La fecha inválida no entra al payload —no hay valor válido que mandar—; el DNI sí, porque el payload no sale igual con `faltantes` y el operador ve el cuadro completo. **Cambia a propósito** `test_siis_envio.ArmarPayloadTests.test_la_correccion_del_caso_pisa_la_fecha_del_apoderado`, del Cambio 98: su primera mitad afirmaba `faltantes == {}` para un apoderado de 17 años que era además el titular —justo los dos casos que el Cambio 98 midió en PRD, 265 y 448—; hoy afirma los dos faltantes, y su segunda mitad (la corrección manda) sigue igual. **Test permanente:** `programas/tests/test_siis_catalogo_y_payload.py::ApoderadoPrevalidadoTests.test_un_apoderado_invalido_no_llega_a_siis` (y `.test_un_apoderado_menor_de_18_es_un_faltante`, `.test_una_fecha_de_nacimiento_futura_es_un_faltante`, `.test_el_titular_cargado_como_su_propio_apoderado_es_un_faltante`, `.test_el_borde_de_los_18_cumplidos_hoy_pasa`, `.test_la_correccion_del_coordinador_destraba_el_apoderado`, y 4 más de la clase).

**⚠ Actualizar (03-oct-2026):** `_apoderado` hoy en `siis_envio.py:349` (las líneas de `siis_envio.py` posteriores a `Catalogos.estado_civil_id` corrieron +16 con #513).
- **Ubicación:** `programas/services/siis_envio.py:333-378` (`_apoderado`). El Cambio 98 midió 265 rechazos (248 «debe ser mayor de 18», 17 «fecha futura») y 448 casos con el alumno como apoderado; corrigió datos, no el payload.
- **Propuesta:** `_apoderado(formulario, faltantes, correcciones, hoy, dni_titular)`: fecha futura → `faltantes["fecha_nacim_apoderado"] = "Fecha futura"`; menor de 18 → `"El apoderado debe ser mayor de 18 años"`; mismo DNI → `faltantes["dni_apoderado"] = "El apoderado no puede ser el propio titular"`. Validar después de aplicar las correcciones de `datos_siis` (Cambio 98).
- **Tests a agregar:** tres casos (15 años, fecha futura, mismo DNI) → `faltantes` con la clave y `cargar_beneficiario` sin llamar.

### SIIS-13 · Link abierto: un DNI ajeno bloquea al titular en la convocatoria
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (la docstring de `dni_en_convocatoria` lo marca «pendiente de confirmar») · **Origen:** A2-14; parte de SEC-28 de V1 · **Ola:** 3 · **Esfuerzo:** S (a) / M (b) · **Decisión:** D-S13 (decisión pendiente del Cambio 41)
- **Ubicación:** `programas/services/inscripcion_publica.py:54-71`, `:135-136`; `portal/views/inscripcion.py:175-179`.
- **Escenario:** alguien carga DNI de terceros en un link sin padrón; quedan formularios `manual` que ocupan el DNI en toda la convocatoria y, aunque el backoffice los rechace, **siguen bloqueando** porque RN-P5 cuenta los RECHAZADO.
- **Propuesta (default D-S13 = sí, opción a):** en `dni_en_convocatoria`, excluir los `RECHAZADO` con `validado_renaper=False`. (b) para después: si el que llega se valida y el existente es `manual`, crear la carga como `conflicto_duplicado`. La parte de captcha va en SIIS-21.
- **Tests a agregar:** con un `RECHAZADO` no validado del DNI X, el paso 1 del DNI X deja pasar.
- **Dependencias:** toca RN-P5 (análisis #289): confirmar con el programa antes de implementar.

### BEC-01 · Aprobar y promover no bloquean la fila del caso
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`AprobarPisaRechazoTests`: un RECHAZADO commiteado entre la relectura y el `save` queda APROBADO) · **Origen:** A1-06 (ya en pendientes de 96.16) · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 151), 06-oct-2026 — las cuatro operaciones de `cupo.py` releen el estado con `Formulario.objects.select_for_update()` (orden **segmento → caso**; rechazar, el descarte por duplicado y la reserva del alta toman solo el caso, así que no hay ciclo) y, además, **escriben condicionadas**: `_escribir_estado` es un `UPDATE … WHERE estado = <el que leímos>` que devuelve `False` si otro ya lo movió. El candado solo es el que serializa en MariaDB; el compare-and-set es lo que hace que la decisión se pueda afirmar también en SQLite, donde `select_for_update()` es un no-op. La consulta del estado se separó de la de la lista de espera a propósito: un `select_for_update` con el `Exists` correlacionado llevaba el candado a las filas de `ListaEspera`, que no es lo que hay que bloquear (cuesta una consulta más en aprobar, que no tiene presupuesto de performance). El `select_for_update` va escrito a mano en cada operación y no detrás de un helper, para que `candados_tomados` registre la función que lo pide (RED-67). **Test permanente:** `programas/tests/test_candados_concurrencia.py::CandadoDelCasoAlAprobarTests.test_un_rechazo_que_entro_mientras_contabamos_el_cupo_no_se_pisa` (y `.test_aprobar_toma_el_candado_de_la_fila_del_caso`, `.test_promover_no_pisa_un_rechazo_que_entro_mientras_contabamos_el_cupo`, `.test_dar_de_baja_no_pisa_una_baja_que_ya_entro`, +3; contra motor real, `core/tests/test_motor_real.py::CarreraDelMismoCasoTests` ×3).
- **Ubicación:** `programas/services/cupo.py:272-277` (`aprobar_o_poner_en_espera`), `:209-211` (`promover_lista_espera`), `dar_baja_beneficiario`.
- **Propuesta:** después del lock del segmento, releer con `Formulario.objects.select_for_update().filter(pk=...)`; orden de locks segmento → caso (rechazar, el descarte por duplicado y la reserva de SIIS-01 toman solo el caso: no hay ciclo); en `dar_baja_beneficiario`, releer el estado con `select_for_update`.
- **Tests a agregar:** el de la PoC invertido (`ValidationError` y el caso queda RECHAZADO).

### BEC-02 · Agregar a lista de espera y dar de baja chequean antes del lock
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`EsperaDobleTests`: 2 filas activas) · **Origen:** A1-17 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 151), 06-oct-2026 — en `agregar_a_lista_espera` el `select_for_update` del segmento pasa al principio y los dos chequeos —estado y espera activa— se hacen **adentro**, releídos con el candado del caso de BEC-01. La guarda temprana con el objeto en memoria queda: cuando ya está resuelto, no hace falta molestar al candado; la que decide es la relectura. `dar_baja_beneficiario` hace lo mismo y su escritura también es condicional, así que dos clics dejan una traza y no dos. Verificado contra **MariaDB 10.11 real sin tzinfo**: con `cupo.py` de `development` los dos hilos crean **2 filas activas** y las **2 bajas pasan**; con el arreglo, una fila y un `ValidationError`. **Test permanente:** `programas/tests/test_candados_concurrencia.py::CandadoListaEsperaTests.test_un_alta_que_entro_mientras_esperabamos_el_candado_frena_la_nuestra` (y `.test_un_caso_que_cambio_de_estado_bajo_el_candado_no_entra_a_la_lista`; contra motor real, `core/tests/test_motor_real.py::CarreraDelMismoCasoTests.test_dos_altas_del_mismo_caso_a_la_lista_dejan_una_sola_fila` y `.test_una_baja_y_una_aprobacion_a_la_vez_no_se_pisan`).
- **Ubicación:** `programas/services/cupo.py:302-316` (estado en memoria + `ya_en_espera` antes del `select_for_update`), `:173-182`; `programas/views/cupo.py:217-235` (correo después).
- **Escenario:** doble clic en «Agregar a lista de espera» → dos filas (posición +1) y dos correos; o un caso aprobado por otro entre la carga y el POST entra a la espera siendo APROBADO.
- **Propuesta:** mover el `select_for_update` del segmento al principio y, bajo el lock, releer estado y espera activa (la misma consulta de `aprobar_o_poner_en_espera:272-277`).
- **Tests a agregar:** el de la PoC invertido; `test_segundo_alta_con_estado_cambiado_bajo_lock_falla`.

### BEC-03 · La revisión reevalúa las condiciones de edad con la fecha de hoy y oculta respuestas que la persona sí dio
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A1-07 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/respuestas.py:284` (`aplicar(definicion, respuestas)` sin `hoy`); `programas/services/condiciones.py:115-121`, `:170-180` (`edad_*` con `date.today()`); `revision/formulario_detalle.html:409-414`.
- **Escenario:** grupo con condición «edad menor a 18»; la persona lo completa con 17 y al mes cumple 18: la revisión muestra «No se pidió» y «—». Contradice D3 del Cambio 58. (Aclaración V2: el bug es la **fecha de referencia**, no la zona horaria.)
- **Propuesta:** `respuestas_legibles(formulario, ...)` pasa `hoy=timezone.localdate(formulario.capturado_en or formulario.creado)` a `aplicar`. Revisar el mismo patrón en el sync de la app y en la exportación de respuestas (G2-01).
- **Tests a agregar:** `test_respuestas.RespuestasLegiblesTests.test_condicion_de_edad_se_evalua_a_la_fecha_de_carga`.

### BEC-04 · Una condición cuya fuente no se pide en el canal queda colgando
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A1-08 · **Ola:** 3 · **Esfuerzo:** S (V2: `items_planos(items, canal=None)` ya admite canal)
- **Ubicación:** `programas/views/diseno.py:222-229` (`_asegurar_coherencia` valida sin canal); `programas/services/diseno.py:537-543`, `:600-632`; `condiciones.py:145-147`.
- **Escenario:** campo propio con canal APP es fuente de un grupo obligatorio canal AMBOS: en el link público el grupo queda oculto siempre y el servidor tampoco lo exige.
- **Propuesta:** en `_asegurar_coherencia`, `for canal in (APP, LINK): cond.validar_coherencia(items_planos(items, canal))`, rechazando con «la fuente no se pide en el canal X»; en `items_vigentes`/`serializar`, anular (con aviso en el constructor) las reglas cuya fuente no está en el canal servido.
- **Tests a agregar:** `test_diseno.CoherenciaPorCanalTests.test_condicion_con_fuente_solo_app_en_item_ambos_se_rechaza` y `test_definicion_link_no_trae_condiciones_con_fuente_fuera_de_canal`.
- **Riesgo:** diseños existentes pueden empezar a fallar al editar: correr un chequeo sobre los diseños guardados antes de desplegar.

### BEC-05 · El cupo del subsegmento nunca se aplica
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (sin decisión registrada) · **Origen:** A1-09 · **Ola:** 3 · **Esfuerzo:** S (default) / M (tope duro) · **Decisión:** D-B05
- **Ubicación:** `programas/services/cupo.py:16-27` (`get_cupo_stats` por segmento), `:224-226`, `:283`; `programas/models/__init__.py:1592-1643` (`Subsegmento.cupo_maximo`, RN-40 solo valida la suma).
- **Propuesta (default D-B05 = no es tope duro):** mostrarlo como referencia y documentarlo. Si es tope duro: `get_cupo_stats(segmento, subsegmento=None)` que cuente APROBADO de convocatorias del subsegmento contra su `cupo_maximo` y devuelva `min(disponible_segmento, disponible_subsegmento)`, con lock adicional sobre la fila del subsegmento.
- **Tests a agregar (si tope duro):** subsegmento con cupo 1 y segmento con 10 → el segundo caso cae en espera.

### BEC-06 · Se puede cambiar el segmento/subsegmento de una convocatoria que ya tiene casos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A1-10 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/forms.py:1300-1397` (`ConvocatoriaForm`); `programas/views/relevamientos.py:343-367`; `Convocatoria.clean` (`models:1745-1750`).
- **Escenario:** convocatoria con 300 APROBADO y 20 en espera en S1 pasa a S2: libera 300 lugares en S1, sobrepasa S2, la espera sigue con `segmento=S1`, cambian requisitos y programa SIIS.
- **Propuesta:** en `ConvocatoriaForm.__init__`, si `instance.pk` y `instance.relevamientos.exists()`, `disabled=True` en `segmento` y `subsegmento`; validarlo también en `clean()`. Si hace falta mover una convocatoria, un comando que migre también `ListaEspera.segmento`.
- **Tests a agregar:** `test_convocatorias.ConvocatoriaEdicionTests.test_no_cambia_segmento_con_relevamientos`.

### BEC-07 · El cupo máximo del segmento se puede bajar por debajo de los beneficiarios reales
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A1-11 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/models/__init__.py:1559-1563` (`Segmento.clean` compara contra `CupoSegmento.cupo_ocupado`, estático); `programas/services/cupo.py:3-5`.
- **Propuesta:** en `Segmento.clean`, `ocupado = get_cupo_stats(self)["cupo_ocupado"]` (import local para evitar el ciclo) y usarlo en el mensaje.
- **Tests a agregar:** 3 APROBADO y `cupo_maximo=2` → `ValidationError`.

### BEC-09 · No se puede rechazar un caso sin ciudadano con DNI o de un segmento sin programa SIIS
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A1-13 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/views/revision.py:1085-1089` (`validar_formulario_en_siis` antes de rechazar; el `ValueError` corta); `programas/services/validacion_siis.py:13-16`. El Cambio 34 decidió que un error de consulta no impide documentar la decisión local.
- **Escenario:** el caso queda ENVIADO para siempre y `relevamiento_terminar` (`revision.py:1324`) nunca puede cerrar el relevamiento.
- **Propuesta:** en `formulario_rechazar`, capturar el `ValueError`, seguir con el rechazo y registrar en la traza «Sin consulta SIIS: <motivo>».
- **Tests a agregar:** `test_becas_revision.RechazoSinSiisTests.test_rechaza_caso_sin_ciudadano`.

### BEC-10 · Un relevamiento con casos en lista de espera no se puede terminar nunca
**Severidad:** MEDIA · **Estado:** CONFIRMADO (requiere decisión) · **Origen:** A1-14 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-B10
- **Ubicación:** `programas/views/revision.py:1324-1326` (cuenta todo ENVIADO; un caso en espera es ENVIADO); `programas/services/cupo.py:302`.
- **Propuesta (default D-B10 = «en espera» cuenta como revisado):** `.exclude(lista_espera__promovido=False)` y mensaje «Quedan N sin revisar (M en lista de espera no cuentan)».
- **Tests a agregar:** `test_becas_revision.TerminarRelevamientoTests.test_casos_en_espera_no_bloquean_terminar`.

### BEC-11 · El proceso masivo aprueba e informa a personas que SIIS declaró incompatibles
**Severidad:** MEDIA · **Estado:** CONFIRMADO (decisión) · **Origen:** A1-15 · **Ola:** 1 · **Esfuerzo:** S · **Decisión:** D-B11

**Resolución:** ✅ Resuelto en #590 (Cambio 136), 06-oct-2026 — aplicado el default de **D-B11**: en `procesar_caso`, un `ValidacionSIS.Estado.RECHAZADO` suma `cuenta.incompatibles` y devuelve sin aprobar ni informar; el caso queda como estaba, para que lo mire una persona desde la revisión. **No cuenta para el freno**: SIIS contestó, y bien. El contador tiene columna propia (`CorridaSiis.incompatibles`, migración `programas.0076_corridasiis_incompatibles`) porque la pantalla es donde el coordinador lo ve; también sale en el resumen de `procesar_casos_siis` y en el procedimiento. **Ronda 2 de la revisión:** no alcanzaba con no aprobarlo. Un incompatible seguía siendo candidato, así que la corrida siguiente lo volvía a consultar y la que venía también: con 200 adelante por pk, una corrida de 100 gastaba sus 100 llamadas a SIIS y daba cero altas, para siempre. Ahora `candidatos()` los deja afuera por su **veredicto vigente** —la última validación que corresponde al DNI y al plan de hoy, los dos que `motivo_bloqueo_aprobacion` exige que coincidan—, con una sola subconsulta correlacionada; vuelven solos si los revalidan con OK o si cambia el DNI o el plan. Siguen contados en la pantalla («Incompatibles según SIIS», `candidatos(solo_incompatibles=True)`) para que no desaparezcan. Convive con la lista de exclusión del Cambio 138: son preguntas distintas y se acumulan —quien está en `siis_enviar` no es un incompatible pendiente de resolver, es alguien a quien no hay que mandar—. Extiende el Cambio 81, que sacó el bloqueo **en la pantalla**, donde sí hay revisor. **Test permanente:** `programas/tests/test_proceso_masivo.py::IncompatiblesNoVuelvenACandidatosTests.test_doscientos_incompatibles_no_se_comen_la_corrida` (y `IncompatiblesTests.test_un_rechazado_por_siis_no_se_aprueba_en_lote`, `IncompatiblesNoVuelvenACandidatosTests` ×5, `PantallaProcesoMasivoTests.test_la_pantalla_cuenta_los_incompatibles_aparte`).

**⚠ Actualizar (03-oct-2026):** `procesar_caso` hoy en `proceso_masivo.py:276` (#517 le sumó el parámetro `destino`).
- **Ubicación:** `programas/services/proceso_masivo.py:238-268` (`RECHAZADO` no corta; solo `ERROR`). El Cambio 81 quitó el bloqueo porque «la aprobación es una decisión técnica del revisor»; en la corrida no hay revisor.
- **Propuesta (default D-B11 = no aprobar en lote):** en `procesar_caso`, si `validacion.estado == RECHAZADO`, `cuenta.incompatibles += 1` y dejar el caso para revisión manual (contador en `mensaje` o columna nueva en `CorridaSiis` con migración). Registrar la decisión (extiende el Cambio 81).
- **Tests a agregar:** `test_proceso_masivo.IncompatiblesTests.test_rechazado_por_siis_no_se_aprueba_en_lote`.

### G1-03 · La API pagina de a 10 y la app lee solo la primera página
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura, backend y app) · **Origen:** G1-03 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `config/settings.py:405-406` (`PageNumberPagination`, `PAGE_SIZE: 10`); `programas/api/views.py:257-281`, `:358-366`; app `relevamientoService.js:1349-1351`, `:1653-1657`, `:1671-1678` (`dniYaRelevado` recorre esa lista); el backend tiene `dni-existe` (`views.py:432-438`) sin uso.
- **Escenario:** relevamiento con 40 casos: la app no avisa «DNI ya relevado» si está del 11 en adelante y el servidor crea un `conflicto_duplicado` para descartar a mano; con más de 10 relevamientos vigentes la agenda y la caché offline muestran solo 10.
- **Propuesta:** `pagination_class = None` en `RelevamientoViewSet` (la agenda ya viene filtrada por `fecha_hasta >= ahora`); para `formularios` GET, serializer liviano (`id, numero, client_uuid, estado, ciudadano_dni, ciudadano_nombre, ciudadano_apellido, creado`) sin paginar (hoy `FormularioSerializer` arrastra `data`, ~7 KB/caso). La app vieja ya acepta lista plana. En la app (release aparte): consultar `dni-existe` si hay conexión.
- **Tests a agregar:** relevamiento con 15 casos → `GET …/formularios/` devuelve 15; territorial con 12 relevamientos vigentes → la agenda devuelve 12.

### G1-04 · Captura offline hecha en fecha que sincroniza después del corte de las 03:10: 409 y error permanente en la app
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; pendiente registrado en el Cambio 54) · **Origen:** G1-04, A8-21 (= DAT-04 de V6) · **Ola:** 3 · **Esfuerzo:** M · **Decisión:** D-G04 (gracia)
- **Ubicación:** `programas/api/views.py:393-397` (exige `EN_CURSO`) frente a `:56-62` (`_captura_habilitada` acepta un `capturado_en` pasado); `programas/services/vencimientos.py:62-92` (el cron pasa a `EN_REVISION` lo `EN_CURSO`/`FINALIZANDO` vencido con `QuerySet.update()`, sin traza: `FINALIZANDO` está en `ESTADOS_RELEVAMIENTO_ABIERTOS`, `:31-36`); app `relevamientoService.js:1480-1527` (409 no-pausa → `FAILED_PERMANENT`).
- **Escenario:** último día, zona sin señal, 15 personas cargadas; al día siguiente el relevamiento ya está en `EN_REVISION` y los 15 envíos quedan en el teléfono sin rastro en el backoffice.
- **Propuesta:** aceptar el alta si `capturado_en` cae dentro del período y el relevamiento está en `EN_CURSO | FINALIZANDO | FINALIZADO | EN_REVISION` (no `TERMINADO`) y dentro de la gracia (default D-G04: 24 h desde `fecha_fin`, según V6; G1 sugería 72 h), marcando el caso `sincronizado_tarde` visible en revisión; registrar la transición automática del cron en la traza del relevamiento; opcional: endpoint `POST /api/becas/rechazos/` (client_uuid + motivo) para que el backoffice vea lo que la app no pudo subir.
- **Tests a agregar:** `test_becas_api`: relevamiento `EN_REVISION` con `fecha_hasta` ayer, POST con `capturado_en` de ayer → 201 con la bandera; con `capturado_en` posterior → 400; `procesar_vencimientos` con un `FINALIZANDO` dentro de la gracia no cambia.

### G1-05 · El servidor no valida lo que carga la app (obligatorios, tipos, DNI, sexo, GPS, condiciones)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1-05 · **Ola:** 3 · **Esfuerzo:** M
- **Ubicación:** `programas/api/serializers.py:116-177` (solo DNI no vacío y apoderado del menor); `programas/api/views.py:376`; `programas/services/respuestas.py:219-238` (`sincronizar_desde_legacy` sin validar ni aplicar condiciones); `respuestas.aplicar` solo se llama desde `portal/forms/inscripcion.py:299` y para mostrar; `requiere_gps` (`programas/services/becas.py:128`) no se exige en el servidor.
- **Escenario:** una app vieja o un cliente con token manda un caso sin obligatorias, con DNI `"1"`, sexo `"X"`, opciones inexistentes o sin GPS: se crea; las respuestas de ítems ocultos se guardan y `respuestas_por_destino` las lee de `data` para SIIS.
- **Propuesta:** en `RelevamientoViewSet.formularios` (POST), después de `respuestas_desde_legacy`, correr la validación del link: `aplicar(foto, respuestas)` → descartar ocultas, exigir obligatorias visibles, validar tipo/opciones, `len(dni) in (7, 8)`, sexo F/M, GPS si `requiere_gps`. **No rechazar** capturas legítimas: guardar con `observaciones_carga` visible en revisión; rechazar solo lo imposible (DNI inválido).
- **Tests a agregar:** POST sin una obligatoria visible → caso creado con la observación; respuesta a un ítem oculto → no queda en `respuestas` ni en `data`; DNI de 3 dígitos → 400.
- **Dependencias:** G1-04 (mismo criterio «aceptar y marcar»); SEC-24.

### G1-08 · El mapeo a SIIS lee el catálogo de hoy, no la foto del caso
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1-08 · **Ola:** 1 · **Esfuerzo:** M

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 158), 07-oct-2026 — la foto del caso declara sus destinos. `_campo_dict` agrega `destino_siis` **solo a los campos marcados** (la foto son ~27 KB por caso y `programas_formulario` pesa 283 MB en PRD: una clave vacía por campo se paga en cada caso), `foto_definicion` arma con eso la lista `destinos_siis` de la foto —`{clave, id, destino, alcance, orden}`— y `respuestas_por_destino` la usa cuando existe. Se guardan los **hechos** (nivel y orden del campo), no la precedencia ya resuelta: así una corrección de la regla —G1-10 fue una— alcanza también a los casos ya guardados. La presencia de la clave `destinos_siis` es lo que distingue una foto nueva de una vieja; los casos anteriores siguen leyendo el catálogo de hoy, que para ellos es la única fuente que hay, y eso queda **caracterizado** en un test. **La mitigación «mientras tanto» no se hizo** y queda sin sentido: la ficha pedía una confirmación explícita en `pregunta_toggle_activo` porque el catálogo vivo reinterpretaba los casos; con la foto, desactivar o remarcar una pregunta ya no toca ningún caso guardado. **Test permanente:** `programas/tests/test_siis_que_viaja.py::FotoDelDestinoTests.test_desactivar_la_pregunta_no_cambia_lo_que_ya_se_respondio` (y `.test_cambiarle_el_destino_a_la_pregunta_no_reinterpreta_el_caso`, `.test_la_foto_declara_los_destinos_de_los_campos_marcados`, `.test_desactivar_la_pregunta_si_alcanza_a_un_caso_sin_foto`, `.test_una_foto_vieja_sin_destinos_cae_al_catalogo`, `.test_el_payload_es_el_mismo_por_los_dos_caminos` —contrato: el payload completo de los 23 campos, idéntico por los dos caminos—).

**⚠ Actualizar (03-oct-2026):** líneas de `siis_envio.py` corridas +16 (#513): `respuestas_por_destino` en `:323`, el `CALLE_SIN_NUMERO` en `:507-516`. Ojo con #517: la tabla intermedia guarda el payload ya mapeado y la sincronización lo manda tal cual, sin recalcularlo.
- **Ubicación:** `programas/services/siis_envio.py:307` (`PreguntaGlobal.objects.filter(activo=True).exclude(destino_siis="")`), `:491-500` (sin `calle_altura` → `CALLE_SIN_NUMERO` + altura 1); `programas/views/configuracion.py:1008-1041` (`pregunta_toggle_activo`, `PreguntaGlobalUpdateView` deja cambiar `destino_siis`). El Cambio 58 (D3) guarda la foto para que «un caso viejo nunca se reinterprete».
- **Escenario:** el admin desactiva «Calle y altura» para reemplazarla: todos los casos aún no informados salen a SIIS como «Planta urbana sin número», altura 1, sin error ni faltante (Cambio 89); con barrio o estado civil pasan a INCOMPLETO de golpe. Irreversible en SIIS.
- **Propuesta:** guardar `destino_siis` en la foto (`diseno.serializar`) y que `respuestas_por_destino` lo tome de `formulario.definicion`, con el catálogo vivo solo como respaldo para casos sin foto. Mientras tanto, en `pregunta_toggle_activo`, confirmación explícita si la pregunta tiene `destino_siis` y hay casos APROBADO sin envío ENVIADO (P-14 da el número).
- **Tests a agregar:** `test_siis_envio.py`: caso con respuesta a «Calle y altura», desactivar la pregunta → `armar_payload` sigue mandando la calle real.
- **Dependencias:** mismo módulo que SIIS-01/12 (coordinar PRs); PERF-01 (memo de destinos).

### G1-09 · `pregunta_toggle_activo` saltea la regla «una sola pregunta activa por destino SIIS»
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1-09 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 158), 07-oct-2026 — `pregunta_toggle_activo` chequea la misma regla del form **solo al activar**: si ya hay otra activa con ese destino, no activa y lo dice con el texto del form más qué hacer. Desactivar nunca se bloquea por esta regla, porque dos activas con el mismo destino es un estado que ya puede existir en la base y la salida tiene que seguir abierta. **Code-first, un punto de la ficha quedó desactualizado:** el `values_list` de `respuestas_por_destino` no estaba «sin `order_by`» —`PreguntaGlobal.Meta.ordering` es `["orden", "id"]` y el ORM lo aplica igual—, así que el orden ya era determinista; lo que sí cambió, por G1-10, es el criterio con el que se ordena. **Test permanente:** `programas/tests/test_siis_que_viaja.py::ToggleDeDestinoOcupadoTests.test_reactivar_con_el_destino_ocupado_no_activa_y_lo_dice` (y `.test_desactivar_la_vigente_libera_el_destino`, `.test_una_pregunta_sin_destino_se_activa_sin_mirar_a_nadie`, `.test_desactivar_nunca_se_bloquea_por_esta_regla`).

**⚠ Actualizar (03-oct-2026):** `respuestas_por_destino` hoy en `siis_envio.py:323-327` (+16, #513).
- **Ubicación:** `programas/forms.py:1161-1175` (regla solo en `PreguntaGlobalForm.clean`); `programas/views/configuracion.py:1028-1041`; `programas/services/siis_envio.py:307-311` (`values_list` sin `order_by`).
- **Escenario:** dos preguntas activas con destino `est_civil`: lo informado depende del orden físico de la tabla.
- **Propuesta:** al activar, rechazar si `PreguntaGlobal.objects.filter(activo=True, destino_siis=pregunta.destino_siis).exclude(pk=pk).exists()` (mismo mensaje del form); en `respuestas_por_destino`, `order_by("orden", "id")`.
- **Tests a agregar:** reactivar una pregunta con destino ocupado → mensaje de error y sigue inactiva.

### G2-01 · El Excel «respuestas por persona» y el dashboard leen `data` (contrato viejo): los campos propios del constructor no aparecen
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`poc/test_repro_dashboard_campos_propios.py`) · **Origen:** G2-01 · **Ola:** 3 · **Esfuerzo:** M
- **Ubicación:** `programas/services/dashboard_becas.py:1156` (columnas desde `get_campos_formulario`), `:1205` (valores desde `f["data"]`), `:674` (`preguntas_graficables`: solo `PreguntaGlobal` y `RequisitoNativo`), `:776` y `:826` (`respuesta_de`, `distribuciones_respuestas` sobre `data`); `programas/services/respuestas.py:163-178` (`legacy_desde_respuestas` no escribe los `cp-…` en `data`). **Contradice el Cambio 58** (`docs/internal/requerimientos.md:6117`, Pendientes: «si algún día exportan respuestas, tienen que leer `respuestas` + la foto, no `data`»); los Cambios 64 y 65 exportan desde `data`.
- **Escenario:** una convocatoria con preguntas propias (situación del hogar): el Excel y el dashboard que baja el ministerio no las tienen; además el dashboard cuenta respuestas que el motor de condiciones ocultó.
- **Propuesta:** (1) `respuestas_por_persona`: columnas desde las fotos (`definicion`) de los casos de la convocatoria, deduplicadas por `clave`, y valores con `respuestas` + `legible()`; leer `respuestas`/`definicion` en una segunda pasada por lotes de pk (`values_list("pk", "respuestas")` de a 500) y tomar **una** foto por `huella_definicion` para los encabezados (hoy se excluyen por el `read_timeout`, comentario `:1112-1116`). (2) Dashboard: sumar al catálogo los `cp-` de tipo selector de las fotos del recorte y extraer de `respuestas` con `JSON_EXTRACT(respuestas, '$."cp-xxx"')` (técnica de `_ValorJson`; ruta explícita: `KeyTransform` trata claves numéricas como índice en MariaDB). (3) Mientras tanto, rotular Excel y dashboard: «no incluye campos propios del constructor».
- **Tests a agregar:** el de la PoC invertido (la columna aparece con «Sí») + una pregunta oculta por condición que no cuente en la distribución.
- **Verificación:** V-STD + medir la segunda pasada en el banco `scripts/perf_mysql/` (20k casos, MariaDB).
- **Dependencias:** PERF-03 y PERF-11 (filas anchas); BEC-03.

## BAJA

### SIIS-14 · RENAPER: DNI en logs y token que no se invalida con un 401
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura; el 401 con test `poc/test_repro_admin_cron_renaper.py::RenaperClienteTests.test_401_no_invalida_el_token`: dos 401 seguidos → `logins=1`) · **Origen:** A2-16, G3-02 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `legajos/services/consulta_renaper.py:282-287` (`logger.exception` con `RequestException`: con `RENAPER_HTTP_METHOD=get` la URL lleva `?dni=…&sexo=…`), `:202-203` y `:251-252` (`response.text` del login al log), `:218-238` (`get_token` confía en `token_expiration`), `:289-299` (401 sin invalidar `self.token` ni `TOKEN_CACHE_KEY`).
- **Escenario:** RENAPER rota el token antes del vencimiento: cada alta de ciudadano del backoffice da «Error HTTP 401» durante horas (hoy este cliente solo lo usa el alta de ciudadanos; Becas usa Personas).
- **Propuesta:** `logger.error("RequestException RENAPER (%s)", type(exc).__name__)` sin el texto del login; con 401/403 y sin modo API key: `self.token = None; cache.delete(TOKEN_CACHE_KEY); self.login()` y **un** reintento. Mismo PR que G1c-15.
- **Tests a agregar:** el de la PoC invertido (`logins == 2` y segunda consulta OK); `assertLogs` sin el DNI.

### SIIS-15 · El comprobante de inscripción se renderiza fuera del `try`
**Severidad:** BAJA · **Origen:** A2-17 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/inscripcion_publica.py:258-266` (el `try` empieza en `:267`); contraste: `avisos_resolucion.py:314-327` ya lo corrigió.
- **Escenario:** un error de plantilla da 500 después de commiteada la inscripción; la persona reintenta, la idempotencia devuelve `creado=False` y no recibe el correo.
- **Propuesta:** `render_to_string` ×2 y `EmailMultiAlternatives` dentro del `try`.
- **Test:** patch de `render_to_string` que lanza → el paso 2 redirige al comprobante con `correo_enviado=False`.

### SIIS-16 · Adjuntos anónimos del link validados solo por extensión
**Severidad:** BAJA · **Origen:** A2-18 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `portal/forms/inscripcion.py:52-57`; `config/settings.py:443-449` (el comentario promete un tope que no existe: `DATA_UPLOAD_MAX_MEMORY_SIZE` no cuenta archivos); `nginx.conf:38,107` (`client_max_body_size 100M`).
- **Propuesta:** firma por magic bytes (`%PDF-`, `\x89PNG`, `\xFF\xD8\xFF`) en `_validar_archivo` (reusar `core/validators.py` de SEC-15); `client_max_body_size` de ~25-30 MB en la location `/portal/inscripcion/` (medir antes los envíos reales); corregir el comentario.
- **Test:** un `.pdf` con contenido HTML → error de validación.

### SIIS-17 · «Completar datos para SIIS»: una corrección no se puede borrar y dos se pisan
**Severidad:** BAJA (pero un `id_plan_soc` mal corregido va a SIIS de forma irreversible) · **Origen:** A2-19 · **Ola:** 1 · **Esfuerzo:** S
- **Ubicación:** `programas/forms.py:303-318` (`_validar_localidad` sin provincia en el POST no valida), `:335-343` (`como_datos_siis` descarta lo vacío); `programas/views/revision.py:831-840` (merge `{**anteriores, **nuevos}` sin lock).
- **Propuesta:** opción «Quitar corrección» por campo (centinela que hace `pop` de la clave); merge dentro de `transaction.atomic()` con `Formulario.objects.select_for_update()`; en `_validar_localidad`, `prov = cleaned.get(campo_provincia) or datos_siis_actuales.get(campo_provincia)`. Es UI: V-UI.
- **Test:** POST con «quitar» → la clave desaparece; localidad de otra provincia con la provincia guardada antes → error.
- **Dependencias:** G3-06 (el comando que pisa lo mismo desde el otro lado).

### SIIS-18 · `siis_localidades_json` filtra por provincia con otras claves que `Catalogos._provincia_de`
**Severidad:** BAJA · **Origen:** A2-20 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/views/revision.py:852-865`; contraste `programas/services/siis_envio.py:145-155`; `programas/forms.py:316`.
- **Propuesta:** exponer `Catalogos._provincia_de` como función pública y usarla en la vista y en el form; excluir ítems sin provincia al filtrar.
- **Test:** ítems `{"provincia": {"id": 22}}` y `{"prov_id": 5}` → solo vuelven los de la 22.

### SIIS-19 · `diagnosticar_siis --alta` sin guarda de PRD y con DNI por defecto
**Severidad:** BAJA · **Origen:** A2-21 · **Ola:** 1 · **Esfuerzo:** S
- **Ubicación:** `programas/management/commands/diagnosticar_siis.py:72-85` (`--alta-dni` default `35111222`), `:292-342`. Además no deja `EnvioSIIS` (queda fuera de SIIS-01).
- **Propuesta:** con `--alta`, exigir `--si-entiendo-prd` si la URL no contiene `ecomdev` (no usar `settings.ENVIRONMENT`: ver OPS-12/V6-NEW-01) y hacer `--alta-dni` obligatorio.
- **Test:** `--alta` contra URL productiva sin la bandera → `CommandError` y `cargar_beneficiario` sin llamar.

### SIIS-20 · `RENAPER_TEST_MODE` sin guarda en PRD
**Severidad:** BAJA · **Origen:** A2-22 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `config/settings.py:426`; `legajos/services/consulta_renaper.py:376-423` (identidades al azar con `success=True`, cacheadas 10 min).
- **Propuesta:** system check en `core/checks.py`: `Error` si `ENVIRONMENT == "prd" and RENAPER_TEST_MODE` (con la salvedad de OPS-12: QA también declara `prd`; si eso se corrige primero, el check queda exacto).
- **Test:** check con `ENVIRONMENT=prd` y `RENAPER_TEST_MODE=True` → error.

### SIIS-21 · El captcha aritmético deja agotar la cuota por documento de un tercero
**Severidad:** BAJA (solo en ambientes sin `RECAPTCHA_*`) · **Origen:** A2-23; parte de SEC-28 de V1 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `portal/services/inscripcion.py:87-104` (15 intentos/h por DNI, sin IP), `:128-146` (el desafío se lee del HTML); `portal/views/inscripcion.py:164-173`.
- **Propuesta:** check `Warning` con `ENVIRONMENT=prd` y captcha aritmético (análogo a SIIS-20); en modo aritmético, contar la cubeta del documento también por IP.

### BEC-14 · Doble clic en «Aprobar»: segunda consulta a SIIS y aviso de error junto al de éxito
**Severidad:** BAJA · **Origen:** A1-19 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 127), 05-oct-2026 — guard `data-un-solo-envio` en los forms de acción irreversible del detalle, botón deshabilitado en el `onConfirm` del modal (que ModernModal deja vivo 300 ms) y relectura del estado en `formulario_aprobar` antes de consultar a SIIS. **Desvío de la ficha:** el test no es E2E con Playwright (que no corre en el CI) sino el POST repetido contra la vista, que es donde está el costo (la segunda consulta a SIIS). **Test permanente:** `programas/tests/test_becas_revision.py::PantallaEnvioSiisTests.test_el_segundo_post_de_aprobar_no_consulta_a_siis`.
- **Ubicación:** `revision/formulario_detalle.html:998-1009` (`onConfirm` sin guard; ModernModal deja vivo el botón 300 ms); `programas/views/revision.py:946-947`.
- **Propuesta:** el guard `enviando` del form de duplicados (mismo PR que SIIS-01, punto 6); en la vista, releer el estado antes de consultar SIIS.
- **Test:** E2E Playwright `test_aprobar_doble_clic_un_solo_post`.

### BEC-15 · Carga de padrón concurrente: 500 por unique o filas duplicadas
**Severidad:** BAJA · **Origen:** A1-20, A8-S6 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/padron.py:282-331` (`@transaction.atomic` sin lock del dueño); `models:2098-2106` (unique con `relevamiento` NULL no aplica en MySQL/MariaDB).
- **Propuesta:** `select_for_update()` sobre la Convocatoria/Relevamiento al entrar a `cargar_padron`. Opcional (A8-S6): columna real `alcance` (no generada) con `UniqueConstraint(convocatoria, alcance, dni)`. El Excel viejo huérfano es DAT-05.
- **Test:** dos cargas simuladas en paralelo (mock en la ventana) → sin filas duplicadas.

### BEC-16 · Constructor: mutaciones sin candado del diseño y `reconciliar` escribiendo en cada request
**Severidad:** BAJA · **Origen:** A1-21 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/views/diseno.py:68-71`, `:232-245`; `programas/services/diseno.py:287-294`, `:387-470`.
- **Escenario:** dos operadores a la vez dejan un diseño con la fuente después del destino (RN-6 roto); dos aperturas simultáneas → `IntegrityError` (`uniq_item_diseno_clave`) → 500.
- **Propuesta:** `DisenoFormulario.objects.select_for_update().get(pk=diseno.pk)` al empezar `_mutar` y `reconciliar`; no reconciliar en los POST de mutación.
- **Test:** `test_diseno.ConcurrenciaTests.test_reconciliar_dos_veces_no_duplica_claves`.

### BEC-17 · Pausar/reanudar con doble envío deja dos eventos en el historial
**Severidad:** BAJA · **Origen:** A1-22 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/views/pausas.py:52-56`; `programas/services/pausas.py:6-29`.
- **Propuesta:** en `cambiar_pausa`, tras el `select_for_update`, `if objeto.pausado == pausar: return objeto`.
- **Test:** `test_pausas.CambiarPausaTests.test_pausar_dos_veces_un_solo_registro`.

### BEC-18 · Fechas UTC en Python donde se espera hora de Argentina (fuera de Dispositivos)
**Severidad:** BAJA · **Origen:** A1-23 (parte `solapas`), V3-NEW-04 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/solapas.py:192,195`; `dashboard/views/home.py:49`; `dashboard/utils.py:78-81` (compara con `fecha_inscripcion`, DateField en hora local); `dashboard/api_views/__init__.py:32`, `:203`; `legajos/services/alertas.py:84`, `:110`; `legajos/services/programas.py:46`. (La parte de `indicadores.py` está en DIS-08.)
- **Escenario:** entre las 21:00 y las 24:00 ART «hoy» pasa a ser mañana: contadores «de hoy» en 0, `fecha_cierre` corrida un día.
- **Propuesta:** `timezone.localdate()` y `timezone.localtime(...)`. Sin efecto en las consultas (V4).
- **Test:** `freeze_time("2026-10-10 01:30Z")` → fecha 09/10.

### BEC-19 · Redirect a `POST['next']` sin validar
**Severidad:** BAJA · **Origen:** A1-24, A5-27 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/relevamientos.py:375`, `:384`, `:391`, `:401`, `:417` (`convocatoria_toggle_activo`, `convocatoria_reactivar`).
- **Propuesta:** `url_has_allowed_host_and_scheme` (como `RelevamientoCreateView:693-695`) y fallback `"becas:convocatorias"`.
- **Test:** `next=https://evil.com` → `/becas/convocatorias/`.

### BEC-20 · La convocatoria acepta fecha de fin anterior a la de inicio
**Severidad:** BAJA · **Origen:** A1-25 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/forms.py:1368-1385`; `programas/models/__init__.py:1745-1750`.
- **Propuesta:** `add_error("fecha_fin", ...)` si `fecha_fin < fecha_inicio` en el form y en `Convocatoria.clean`.

### BEC-21 · Proceso masivo: selecciona casos que no se pueden aprobar y no mira pausas ni el bloqueo SIIS
**Severidad:** BAJA · **Origen:** A1-26 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Completado en #PENDIENTE (Cambio 151), 06-oct-2026 — con SIIS-06 cerrado se agregó la línea que faltaba: `_sin_pausa_vigente` excluye también los casos cuyo programa tiene `siis_programa_estado` en `ProgramaSiis.ESTADOS_SIIS_BLOQUEANTES` (`INACTIVO` o `DESCONOCIDO`), que es la otra mitad de `pausa_efectiva` y lo único que el masivo seguía ignorando. Ya no hay riesgo de frenar todo por un error de SIIS: un catálogo vacío no escribe. Un programa recién vinculado tiene el estado en `""`, que no bloquea —nadie preguntó todavía— y sigue siendo candidato. **Test permanente:** `programas/tests/test_proceso_masivo.py::CandidatosTests.test_no_toma_casos_de_un_programa_bloqueado_en_siis` (y `.test_un_programa_sin_sincronizar_todavia_sigue_siendo_candidato`). Lo de abajo es la parte que cerró el #590.

**Resolución:** 🟡 Parcial en #590 (Cambio 136), 06-oct-2026 — `candidatos()` pasa por dos helpers nuevos: `_solo_los_aprobables` (un `ENVIADO` sin `validado_renaper` o sin ciudadano con DNI no entra: la aprobación lo iba a rechazar igual, después de gastarle una consulta de compatibilidad a SIIS) y `_sin_pausa_vigente` (`pausado=True` en relevamiento, convocatoria, segmento, subsegmento o programa). Solo sobre los `ENVIADO`: un `APROBADO` ya pasó ese gate y lo que le falta es el alta. **Queda afuera el bloqueo por estado del programa en SIIS** (`siis_bloqueado`), a propósito: mientras SIIS-06 esté abierto, un catálogo vacío deja todos los programas en `DESCONOCIDO` y esa exclusión frenaría el masivo entero por un error de SIIS. Cuando SIIS-06 cierre (PR 4), es una línea en `_sin_pausa_vigente`. **Test permanente:** `programas/tests/test_proceso_masivo.py::CandidatosTests.test_excluye_enviados_sin_identidad_validada` (y `.test_un_aprobado_sin_validar_sigue_siendo_candidato`, `.test_excluye_al_enviado_sin_ciudadano_con_dni`, `.test_no_toma_casos_de_una_pausa_vigente`).

**⚠ Actualizar (03-oct-2026):** `candidatos` hoy en `proceso_masivo.py:132-203` (#517 le sumó `destino`) y `elegir_completos` en `:252-273`.
- **Ubicación:** `programas/services/proceso_masivo.py:118-177` (`candidatos`), `:209-230`.
- **Propuesta:** para ENVIADO exigir `validado_renaper=True` y `ciudadano__dni` no vacío; excluir los de pausa efectiva (al menos `pausado=True` en relevamiento/convocatoria/segmento/programa). Confirmar si la pausa frena el masivo (el Cambio 15 solo habla de campo).
- **Test:** `test_proceso_masivo.CandidatosTests.test_excluye_enviados_sin_identidad_validada`.

### BEC-23 · La solapa Becas del legajo muestra casos fuera del alcance del usuario
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO (decisión) · **Origen:** A1-28, A5-32 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-B23
- **Ubicación:** `programas/views/solapas_becas.py:14-17`, `:205-212` (solo `ciudadano.ver`); `programas/services/solapas.py:263-308`.
- **Propuesta (default D-B23):** ocultar los casos de relevamientos públicos sin `CAP_RELEVAMIENTO_PUBLICO` (RN-P13) y mostrar el resto (el legajo es transversal).
- **Test:** `test_solapas_becas.AlcanceTests.test_no_muestra_casos_publicos_sin_capacidad`.

### BEC-24 · La edición de contacto/apoderado en revisión no es atómica
**Severidad:** BAJA · **Origen:** A1-29 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/views/revision.py:644-663`.
- **Propuesta:** envolver el bloque del POST en `transaction.atomic()`.
- **Test:** `test_becas_revision.EdicionContactoTests.test_falla_en_resolver_revierte_todo`.

### BEC-25 · `siguiente_nombre` se calcula sin convocatoria y nadie lo usa
**Severidad:** BAJA · **Origen:** A1-30 · **Ola:** 7 · **Esfuerzo:** S
- **Ubicación:** `programas/views/relevamientos.py:294`, `:617`.
- **Propuesta:** borrar las dos líneas.

### G1-06 · Una fecha de nacimiento ilegible de la app deja el caso sin legajo y en bucle de 500
**Severidad:** BAJA · **Estado:** CONFIRMADO (mecanismo; frecuencia PLAUSIBLE) · **Origen:** G1-06 · **Ola:** 3 · **Esfuerzo:** S

**⚠ Actualizar (03-oct-2026):** el texto crudo de la fecha llega al ORM en `programas/services/becas.py:281-290` (antes `:260-269`).
- **Ubicación:** `programas/api/serializers.py:128-133` (`parse_date` → None para `"1/2/2000"`; `ValueError` tragado para `"2000-02-30"`); `programas/services/becas.py:260-269` (pasa el texto crudo al ORM); app `RelevamientoDetailScreen.js:247-253`.
- **Escenario:** el caso se inserta, `_completar_alta` explota después del commit → 500 → la app reintenta (5xx) 8 veces; el caso queda sin legajo y RN-22 no se evaluó.
- **Propuesta:** en `FormularioSerializer.validate`, normalizar con `programas.services.personas.fecha_iso` y 400 si queda vacía habiendo texto; `parse_date` defensivo en `resolver_ciudadano_offline`.
- **Test:** `"31/02/2000"` → 400; `"15/03/2010"` → 201 y legajo con `2010-03-15`.

### G1-07 · Adjuntos de la app sin idempotencia ni control de pertenencia
**Severidad:** BAJA · **Origen:** G1-07 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/api/views.py:467-490`; `programas/api/serializers.py:193-216`; `programas/models/__init__.py:2696-2736`; `respuestas.py:316-324` (`_adjuntos_por_clave` se queda con el **más viejo**). El link público sí deduplica (`inscripcion_publica.py:191-201`).
- **Propuesta:** si ya existe un adjunto del formulario para esa referencia, reemplazar el archivo (borrado con `transaction.on_commit`) o devolver 200 con el existente; validar que `pregunta_global`/`requisito_nativo` estén en `formulario.definicion` como `ARCHIVO`; en `_adjuntos_por_clave`, quedarse con el más nuevo.
- **Test:** dos POST iguales → una fila; pregunta fuera de la foto → 400.

### G1-10 · Entre requisitos de distinto nivel con el mismo destino SIIS gana el de mayor `orden`
**Severidad:** BAJA · **Origen:** G1-10 · **Ola:** 1 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #PENDIENTE (Cambio 158), 07-oct-2026 — `respuestas_por_destino` ordena por especificidad (`NIVEL_DESTINO`: pregunta general → programa → segmento → subsegmento) y recién después por `orden` e id, y aplica del más general al más específico, así que el que pisa es el más específico. Vale igual por los dos caminos: leyendo la foto (el `alcance` de cada campo viene en ella) y leyendo el catálogo. La regla del Cambio 80 —un requisito le gana a una pregunta general— no cambia: es el piso de la escala. **Test permanente:** `programas/tests/test_siis_que_viaja.py::EspecificidadDelDestinoTests.test_el_requisito_del_subsegmento_le_gana_al_del_programa` (y `.test_el_del_segmento_le_gana_al_del_programa_y_pierde_con_el_subsegmento`, `.test_dentro_del_mismo_nivel_sigue_desempatando_el_orden`, `.test_el_requisito_le_sigue_ganando_a_la_pregunta_general`, `.test_la_especificidad_tambien_vale_leyendo_la_foto`).

**⚠ Actualizar (03-oct-2026):** el orden de requisitos hoy en `siis_envio.py:329-346` (+16, #513).
- **Ubicación:** `programas/services/siis_envio.py:313-330`; `programas/forms.py:1234-1245`.
- **Propuesta:** ordenar por especificidad (programa → segmento → subsegmento) y después por `orden`.
- **Test:** requisito de programa y de subsegmento con el mismo destino → el payload lleva el del subsegmento.

### G1-11 · El CUIL se calcula por módulo 11 aunque el caso tenga el CUIL real
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Origen:** G1-11 · **Ola:** 3 · **Esfuerzo:** S · **Decisión:** D-G11 (Cambio 80)

**⚠ Actualizar (03-oct-2026):** `calcular_cuil` hoy en `siis_envio.py:56`; los usos en `:385-387` y `:463-466` (+16, #513).
- **Ubicación:** `programas/services/siis_envio.py:54-70`, `:369-371`, `:447-450`; decisión del Cambio 80 y Cambio 79.
- **Propuesta:** medir primero cuántos casos con respuesta «Cuit Alumno» difieren de `calcular_cuil`; si hay diferencias, preferir el CUIL respondido cuando sus 8 dígitos centrales coinciden con el DNI.
- **Test:** CUIL real `23-…` válido para el DNI → el payload lleva ese prefijo y dígito.

### G1-12 · El padrón acepta fechas de nacimiento futuras o absurdas y el cruce las escribe en el legajo
**Severidad:** BAJA · **Origen:** G1-12 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/padron.py:56` (`"%d/%m/%y"`: `"05/06/30"` → 2030), `:76-99` (serial 0 → 1899-12-30), `:466-480`.
- **Propuesta:** contar como `fechas_invalidas` las posteriores a hoy o anteriores a 1900; año de dos dígitos con pivote en el año actual.
- **Test:** filas `05/06/30` y `0` → se cargan sin fecha y el resumen informa 2.

### G1-13 · Base de Personas: un 404 se informa como «falló el servicio» (502)
**Severidad:** BAJA · **Origen:** G1-13 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `programas/services/personas.py:158-159`; `identidad.py:93`; `programas/api/views.py:240-242`.
- **Propuesta:** `"not_found": True` en la rama del 404.
- **Test:** mock de `requests.get` con 404 → `consultar_persona_becas` responde 404.

### G1-14 · El correo de resolución no deja registro
**Severidad:** BAJA · **Origen:** G1-14 · **Ola:** 3 · **Esfuerzo:** S

**⚠ Actualizar (03-oct-2026):** en el masivo, el retorno de `enviar_aviso_resolucion` se descarta hoy en `proceso_masivo.py:307` y `:311`.
- **Ubicación:** `programas/services/avisos_resolucion.py:123-142`; llamadas en `revision.py`, `views/cupo.py`, `proceso_masivo.py:263-268` (se descarta el retorno).
- **Propuesta:** `registrar_traza` «Aviso por correo: enviado / falló» y botón «Reenviar aviso» en el detalle (UI: V-UI); en el masivo, una conexión SMTP por lote (`get_connection()`).
- **Test:** `EmailMultiAlternatives.send` que lanza → la traza registra «falló».

### G1-16 · Una captura offline se guarda con la foto de la definición del momento de sincronizar
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Origen:** G1-16 · **Ola:** 3 · **Esfuerzo:** M
- **Ubicación:** `programas/services/respuestas.py:228-229`, `:129-160`, `:63-69` (el link compara huella; la app no manda versión).
- **Propuesta:** la app manda la `version` con la que capturó (ya la recibe); si difiere, el servidor guarda la foto de esa versión (historial de versiones del diseño) o marca «capturado con otra versión del formulario». Requiere release de la app.
- **Test:** alta con `version` anterior → caso marcado.

### G1c-15 · Cliente RENAPER: `Retry(total=0, status_forcelist=…)` convierte cualquier 429/5xx en «error de conexión»
**Severidad:** BAJA · **Estado:** CONFIRMADO con test (`RenaperClienteTests.test_503_se_informa_como_error_de_conexion`) · **Origen:** G1c-15 · **Ola:** 3 · **Esfuerzo:** S
- **Ubicación:** `legajos/services/consulta_renaper.py:139-150`, `:280-299`; `_get_client` `:349-357`.
- **Escenario (reproducido):** ante un 503 real, `consultar_datos_renaper` devuelve `"Error interno de conexion al servicio."` con `status_code: None` (la rama `status_code != 200` nunca corre). El cliente compartido sin lock es PLAUSIBLE e inocuo.
- **Propuesta:** `raise_on_status=False`, `status_forcelist` solo si `retry_count > 0`, `respect_retry_after_header=False`; `threading.Lock` en `get_token`/`login`. Mismo PR que SIIS-14.
- **Test:** el de la PoC invertido (503 → `status_code == 503` y mensaje de servicio).

### G3-06 · `corregir_datos_siis` pisa `datos_siis` con una copia leída fuera de la transacción y sin traza
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Origen:** G3-06 · **Ola:** 1 · **Esfuerzo:** S

**⚠ Actualizar (03-oct-2026):** #513 lo encadena: el paso 5 de `correr_alta_siis` corre `corregir_datos_siis --aplicar --limite 999999` en cada corrida, así que la ventana de pisada ya no es solo manual. La lectura de pendientes está hoy en `corregir_datos_siis.py:557` y el `bulk_update` en `:614-618`.
- **Ubicación:** `programas/management/commands/corregir_datos_siis.py:476-526` (lee el lote sin `select_for_update`, `datos = dict(caso.datos_siis); datos.update(nuevos)` y `bulk_update` del JSON completo).
- **Escenario:** mientras corre `--aplicar`, un coordinador guarda una corrección desde la ficha (`revision.py:815`) o el masivo informa el caso: la corrección manual se pierde sin traza.
- **Propuesta:** por lote, `select_for_update()` de los ids dentro de la `atomic`, releer y mergear ahí; saltear casos con `EnvioSIIS` vigente (o `ENVIADO`) releídos en ese momento; `TracaFormulario(campo="datos_siis", editado_por=<--usuario>)` por caso.
- **Test:** modificar `datos_siis` entre lectura y escritura (patch en `_corregir_localidad`) → la clave manual sobrevive.

## INFO

### BEC-22 · Vencimientos: el UPDATE por pk no vuelve a filtrar el estado
**Severidad:** INFO (V2 la dejó BAJA; G3 la baja a INFO: ids leídos y escritos en la misma `atomic`, separados por milisegundos) · **Origen:** A1-27, G1c-14 · **Ola:** 3 · **Esfuerzo:** S (una línea)
- **Ubicación:** `programas/services/vencimientos.py:75-93`.
- **Propuesta:** agregar `estado__in=ESTADOS_RELEVAMIENTO_ABIERTOS` a los dos `update()` y devolver la suma de filas afectadas en vez de `len(ids)`. Se hace en el mismo PR que G1-04.

## Seguimientos de la revisión de la Ola 0 (agregados el 03-oct-2026)

Observaciones MINOR que dejaron los revisores de los PRs de la Ola 0. No son de la base auditada (`917e583`):
las líneas son de `origin/development @ 7393c41`.

### R0-04 · La raíz `GET /api/becas/` responde 403 con `Authorization: Token`
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 3 (app de campo) · **Esfuerzo:** S
- **Ubicación:** `programas/api_urls.py` (`DefaultRouter` → `APIRootView`). Desde #509 (SEC-01) hereda `SessionAuthentication` + `IsAuthenticated`: con Token responde 403 (antes 200, `AllowAny`).
- **Propuesta:** confirmar en `Chaco-mobile` que la app no la consulta; si no la usa, dejarla así (o `DefaultRouter(include_root_view=False)`); si la usa, declarar `TokenAuthentication` en la vista raíz.
- **Test:** `GET /api/becas/` con Token → el código decidido.

### R0-06 · `_get_relevamiento` puede dar `MultipleObjectsReturned` (500)
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 3 (link público) · **Esfuerzo:** S
- **Ubicación:** `portal/views/inscripcion.py:100-114` (`get_object_or_404(relevamiento_publico_por_token(...))`).
- **Escenario:** el índice único compara texto: después de un restore pueden convivir el mismo UUID en hex y con guiones en dos filas. El `OR` de `q_uuid_en_texto` trae las dos y `get_object_or_404` lanza `MultipleObjectsReturned` → 500 en el link público.
- **Propuesta:** `.order_by("pk").first()` + `Http404` si es `None` (como `formulario_por_client_uuid`), o registrar el duplicado.
- **Test:** dos relevamientos con el mismo token en las dos formas → el link responde 200 (o 404), nunca 500.

### R0-07 · `q_uuid_en_texto` sin guarda de tipo
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 3 (link público) · **Esfuerzo:** S
- **Ubicación:** `programas/services/becas.py:155-169`. Usa `valor.hex`: con `None` o un `str` lanza `AttributeError`. Hoy los llamadores le pasan un `uuid.UUID` (conversor de la URL, `uuid.UUID(...)` en `diagnosticar_integraciones`), pero no está protegido.
- **Propuesta:** aceptar `str` (`uuid.UUID(str(valor))`) y devolver `Q(pk__in=[])` con `None` o un valor inválido.
- **Test:** `q_uuid_en_texto("token_publico", None)` y con un texto inválido → sin excepción y sin resultados.
