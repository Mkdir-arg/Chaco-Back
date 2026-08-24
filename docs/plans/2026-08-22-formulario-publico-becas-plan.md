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

## Etapas y orden

```
Etapa 1 (base)          Etapa 2 (portal)                 Etapa 3 (cierre)
#290 modelo+capacidad ─┬─ #293 paso 1 ── #294 paso 2 ── #295 ingesta ── #296 correo*
                       ├─ #291 backoffice (paralelo a #293)
                       ├─ #292 ciclo de vida (paralelo, chico)
                       └─ #299 padrón Excel (paralelo; #293 consume su servicio)
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
