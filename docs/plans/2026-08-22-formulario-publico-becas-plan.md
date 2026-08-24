# Plan de desarrollo — Formulario público de autocompletado (Becas)

**Fecha:** 2026-08-22 (actualizado 24/08: padrón de habilitados) · **Cadena:** Épica #69 · Análisis #289 (Definido) · Tasks #290–#296 y #299
**Estimación total:** 48 h (~5-6 días efectivos de una persona) · **Mockup:** canvas de la sesión 21/08 (link en las tasks de UI)

## Qué se construye

Relevamientos de tipo **Formulario público**: un link con token que el programa distribuye, donde
la persona se identifica (DNI + sexo contra RENAPER/Gran Base), completa el mismo formulario
dinámico que la app de campo y su envío crea el `Formulario` y el legajo ciudadano en el acto.
La revisión, SIS, cupos y la app móvil **no se tocan**.

**Lanzamiento gateado por RBAC (RN-P13):** toda la superficie backoffice queda detrás de la
capacidad nueva `becas.relevamiento.publico`. Se puede desplegar a producción sin que los
usuarios del cliente vean nada; habilitarlo después es tildar la capacidad en Roles, sin deploy.

## Fases de desarrollo

Cuatro fases incrementales. Cada fase cierra con un **entregable demostrable**, sus tests en
verde y los gates de cierre del final de este documento; una fase no arranca hasta que la
anterior mergeó en `development`.

### Fase 1 — Base y backoffice (16 h · ~2 días) → #290, #292, #291

El backoffice completo del relevamiento público, sin portal todavía.

- **Entregable demostrable:** un operador con la capacidad crea un relevamiento público
  (sin territorial ni zona), ve el link generado y lo copia; el relevamiento nace En curso
  y se cierra solo al vencer; para un usuario sin la capacidad, el sistema se ve idéntico
  a hoy. La app de campo no muestra públicos.
- **Gate de salida:** migración aplicada y reversible en local, suite de Becas sin
  regresiones, `design_audit`/`compile_templates` en 0, casos TC-290/291/292 ejecutables.
- **Riesgo a vigilar:** consumidores de `territorial` no nulo (listados, export, admin, API).

### Fase 2 — Padrón + puerta de entrada pública (14 h · ~1,5 días) → #299, #293

La primera superficie pública: identificación y todas las pantallas de rechazo.

- **Entregable demostrable:** abrir el link real desde un celular; padrón cargado y
  aplicándose (habilitado pasa, no habilitado no, con normalización); "Ya estás inscripto",
  "Formulario no disponible" y 404 de token inválido funcionando; captcha y rate limit
  activos; match RENAPER dejando los datos básicos en sesión. (El paso 2 aún no existe:
  el avance termina en un placeholder.)
- **Gate de salida:** TC-299 completos y TC-293 ejecutables salvo los que dependen del
  paso 2; verificación manual de que un rechazo no consulta RENAPER.
- **Riesgo a vigilar:** exposición de datos (solo básicos) y costo de consultas RENAPER.

### Fase 3 — Formulario e ingesta end-to-end (15 h · ~2 días) → #294, #295

El corazón funcional: del link al legajo. Al cerrar esta fase la funcionalidad está completa.

- **Entregable demostrable:** flujo entero en test — identificarse, completar el formulario
  dinámico (preguntas, archivos, GPS, apoderado si menor), enviar, ver el comprobante, y del
  lado backoffice el formulario ENVIADO en la bandeja de revisión con su legajo ciudadano
  creado; aprobarlo/rechazarlo funciona idéntico a uno de campo.
- **Gate de salida:** TC-294/295 completos + los TC-293 que quedaron pendientes; prueba de
  concurrencia de cupo (test automatizado); revisión de diseño de las pantallas del portal.
- **Riesgo a vigilar:** paridad de validaciones con el serializer de campo (RN-22, requisitos).

### Fase 4 — Correo y cierre (3 h + cierre · ~1 día) → #296 + entrega

- **Entregable demostrable:** correo de confirmación llegando con el toggle activo (en test
  si #245 ya está; si no, demo con backend local y queda documentado).
- **Cierre de la funcionalidad:** ejecución completa de los 65 casos TC-* por QA, entrada en
  `docs/internal/requerimientos.md` (con `--check` OK), actualización del mockup si hubo
  desvíos, y deploy a test para la demo interna. El encendido al cliente (asignar la
  capacidad) queda como decisión del PM, posterior y sin deploy.

Dependencias externas: #245 (SMTP) solo condiciona la verificación real de la Fase 4.

### Detalle de orden y dependencias

```
Fase 1                  Fase 2                Fase 3                     Fase 4
#290 modelo+capacidad ─┬─ #299 padrón ──┬─ #293 paso 1 ── #294 paso 2 ── #295 ingesta ── #296 correo*
                       ├─ #291 backoffice (en Fase 1, tras #290)
                       └─ #292 ciclo de vida (en Fase 1, chico)
* #296 requiere #245 (SMTP) para verificarse fuera de local.
```

| Orden | Task | Horas | Depende de | Notas |
|---|---|---:|---|---|
| 1 | #290 Modelo: tipo, token, toggle correo, territorial nullable + capacidad en `core/rbac.py` | 6 | — | La migración es el único cambio de esquema de toda la épica. |
| 2 | #291 Backoffice: alta con selector de tipo, link copiable, listados — todo gateado | 7 | #290 | Paralelo con #292/#293. Mockup como referencia de interfaz. |
| 3 | #292 Ciclo de vida: nace En curso + cierre por `procesar_vencimientos` | 3 | #290 | Chica; puede ir en el mismo PR que #290. |
| 4 | #299 Padrón de habilitados por Excel: modelo, parser (openpyxl), carga/reemplazo, servicio `esta_habilitado` | 6 | #290 | Paralelo con #291/#292; #293 consume el servicio. Lista blanca configurable: sin padrón, el link es abierto. |
| 5 | #293 Portal paso 1: token, captcha, rate limit, **padrón**, RENAPER, duplicado por convocatoria | 8 | #290, #299 | Primera pantalla pública; define la sesión entre pasos. Orden del paso 1: captcha → padrón → duplicado → RENAPER. |
| 6 | #294 Portal paso 2: form dinámico, apoderado, archivos, GPS | 10 | #293 | La más grande; el render sale de `definicion_formulario`. |
| 7 | #295 Ingesta: Formulario ENVIADO + legajo, idempotencia, cupo bajo lock | 5 | #294 | Reusa los servicios de la API de campo; no duplicar lógica. |
| 8 | #296 Correo de confirmación configurable | 3 | #295, #245* | Falla de SMTP nunca rompe la inscripción. |

Los detalles, criterios y casos de prueba de cada paso viven en su issue; este plan no los duplica.

## Decisiones técnicas tomadas en el plan

- **Captcha: autoalojado** (`django-simple-captcha` o equivalente), no un servicio externo
  (reCAPTCHA/Turnstile exigirían salida a internet desde icore-srv y claves por ambiente).
  Pin en `requirements` siguiendo `docs/internal/venv-setup.md`.
- **Rate limiting: contadores en el cache de Django.** Producción ya usa Redis (`CACHES`
  en `config/settings.py`), así que no hace falta dependencia nueva. Límite por IP con
  ventana temporal en el paso 1; los rechazos no consultan RENAPER.
- **Gateo por capacidad, no por env flag** (decisión 22/08): per-usuario, sin deploy para
  encender. El link público en sí no se gatea (es público por diseño).
- **Padrón de habilitados (decisión 24/08, RN-P14):** lista blanca opcional por relevamiento
  vía Excel de dos columnas (documento, sexo), parseado al subir con `openpyxl` (ya en
  requirements) hacia una tabla indexada — nunca se lee el Excel por request. El chequeo va
  antes de RENAPER (ahorra consultas de no habilitados). Reemplazo total desde el detalle.
- **PRs chicos por task contra `development`**, uno por fila de la tabla (#290+#292 pueden
  compartir PR). `main` es release automática y no se toca a mano.

## Gates de cierre (por PR y al final)

Por cada PR: `manage.py check` (venv del repo) · tests del módulo tocado ·
`makemigrations --check` · si toca UI: `design_audit.py --changed` **0 errores** +
`compile_templates.py` 0 errores + agentes de diseño (`chaco-design-system` antes,
`chaco-design-reviewer` después).

Al cerrar la funcionalidad completa:

1. Suite de Becas sin regresiones contra la línea de base (47 errores preexistentes documentados).
2. Ejecutar los 65 casos `TC-*` de las tasks (QA humano tilda; el gate de Ready ya está cumplido).
3. Registrar la entrada en `docs/internal/requerimientos.md` (+ fila en el índice, `--check` OK).
4. Considerar un smoke E2E Playwright del flujo público (harness en `tests/e2e/`), opcional.

## Puesta en producción

- **Deploy estándar** en icore-srv (pull → build → restart + nginx), **con migración**:
  correr `manage.py migrate` en el contenedor tras el build. La migración es aditiva
  (los relevamientos existentes quedan TERRITORIAL) y de bajo riesgo.
- **Post-deploy:** la funcionalidad queda invisible para el cliente (nadie tiene la capacidad).
  Verificación: login como superusuario → crear un relevamiento público de prueba en **test**,
  no en producción (un envío de prueba en prod aparecería en la bandeja de revisión del cliente).
- **Encendido para el cliente:** asignar `becas.relevamiento.publico` a los roles que
  corresponda desde la pantalla de Roles. Sin deploy.
- **Correo:** el toggle de confirmación queda funcional recién cuando #245 (SMTP) esté
  resuelta en el ambiente; hasta entonces, crear los relevamientos públicos con el toggle apagado.
- El catálogo de localidades no interviene (los públicos no piden zona); no hay seeds nuevos.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Lugares que asumen `territorial` no nulo rompen con públicos | #290 los releva de forma exhaustiva (API, listados, export, admin) y TC-290-06 lo verifica. |
| Abuso del endpoint anónimo (spam, enumeración de DNIs) | Captcha + rate limit por IP + pantalla única sin motivo + solo datos básicos en la respuesta (TC-293-09/10/11/12). |
| El mensaje "no estás habilitado" permite sondear pertenencia al padrón | Asumido como parte del requerimiento (la persona debe saber por qué no entra); acotado por captcha + rate limit. |
| RENAPER caído en horario de inscripción | El flujo degrada a carga manual no validada (RN de análisis); no bloquea. |
| Envío de prueba contamina producción | Regla operativa: pruebas end-to-end solo en test. |
| SMTP no configurado al desplegar | El correo es toggle por relevamiento y su falla no rompe la inscripción (TC-296-03). |

---

*Épica #69 · Análisis #289 · Tasks #290–#296 · Plan generado el 2026-08-22.*
