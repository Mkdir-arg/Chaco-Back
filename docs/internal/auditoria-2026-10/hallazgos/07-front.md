# 4.7 Front del backoffice (FE, V5A-NEW)

Fichas completas del dominio. Convenciones, `V-STD` y `V-UI`: README §0. Todo ítem de esta lista es UI: **V-UI siempre**
(y, una vez hecha la Ola 6, el protocolo del agente de diseño). Lista completa de clases inexistentes y diff del build:
`../anexo-front-clases-inexistentes.md`. Verificación de V5a: Playwright (`.venv-e2e`) sobre `runserver` con SQLite, a
1440 y 390 px; las capturas no se conservan: cada ficha dice qué medir.

**Orden obligatorio (V5a):** FE-07 **después de la Ola 6 paso 3** (clona el modal golden ya saneado; no necesita las
fichas del paso 4); FE-01 en el mismo PR que FE-07 o después (sin el script, los botones sin tamaño se achican más) y
FE-10 después de FE-01 (swipe): por arrastre, **FE-07, FE-01 y FE-10 van después de la Ola 6 paso 3**. FE-13 y
V5A-NEW-01 (herramientas, Ola 6 paso 2) antes del primer PR de front, porque vuelven medibles FE-06 y FE-10; FE-14
(borrado de JS muertos) antes de medir los WARN de CLASSDEF; las migraciones a piezas canónicas (FE-11, FE-12, FE-17,
FE-20, FE-23, FE-24) **después** de la Ola 6 paso 4 (goldens saneadas + fichas), clonando la golden. FE-03 no está en
este archivo: se absorbió en LEG-03 (D-L03, `03-dispositivos-merenderos-legajos.md`).
Dispositivos y Merenderos: si D-V1 = no se operan antes de la v2, sus pantallas solo reciben los fixes de bug (FE-10,
FE-18, FE-19); las migraciones de estilo de esos dos módulos las hereda la v2.

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| FE-02 | `toastr` no cargado en el legajo: «Subir archivos» no envía nada | ALTA | CONF. navegador | 5 | S | ✅ |
| FE-04 | Geografía pagina de a 20 sin controles de paginación | ALTA | CONF. navegador | 5 | S | ✅ |
| FE-05 | Wizard «Nuevo programa»: el JS está en un bloque sin destino | ALTA | CONF. navegador | 5 | S | ✅ |
| FE-06 | Clases que el build no genera: botones invisibles, backdrop transparente | ALTA | CONF. ajustado (navegador) | 5 | S | ⬜ |
| FE-01 | `mobile-enhancements.js` global altera controles, modales y swipe | MEDIA (A6: ALTA) | CONF. ajustado | 5 | S | ⬜ |
| FE-07 | Modales de Configuración en la esquina y con botones sin tamaño | MEDIA | CONF. navegador | 5 | M | ⬜ |
| FE-08 | Errores no de campo invisibles | MEDIA | CONF. | 5 | S | ✅ |
| FE-09 | Links a `/legajos/<id>/`, ruta inexistente | MEDIA | CONF. ajustado | 5 | S | ✅ |
| FE-10 | Prestación mensual ilegible en celular | MEDIA | CONF. navegador | 5 | S | ⬜ |
| FE-11 | Componentes canónicos solo en Becas | MEDIA | CONF. | 5 | L | ⬜ |
| FE-12 | Tablas con estilos en línea e iconografía mezclada | MEDIA | CONF. | 5 | M | ⬜ |
| FE-13 | `design_audit`: decodificador roto y sin regla «clase sin definición» | MEDIA | CONF. ajustado | 6 | S | ✅ |
| FE-17 | Paginaciones falsas o copiadas | MEDIA | CONF. | 5 | M | ⬜ |
| FE-18 | Badges de estado incoherentes | MEDIA | CONF. | 5 | S | ⬜ |
| FE-19 | Confirmaciones con colores invertidos y handler copiado | MEDIA | CONF. ajustado | 5 | S | ⬜ |
| FE-20 | Wrapper legacy `includes/main.html`: contenido desplazado; 403/404/500 sin estilo | MEDIA | CONF. navegador | 5 | M | ⬜ |
| FE-21 | Modales de Legajos sin Escape ni foco | MEDIA | CONF. | 5 | S | ✅ |
| V5A-NEW-01 | `tailwind.css` committeado desactualizado y sin gate | MEDIA | CONF. | 6 | S | ✅ |
| V5A-NEW-07 | Deuda de accesibilidad en las pantallas candidatas a referencia | MEDIA | CONF. | 6 (a) / 5 (b) | (a) en paso 3 · (b) 2 × S | 🟡 (a) ✅ |
| FE-14 | 29 JS y 1 CSS huérfanos | BAJA (A6: MEDIA) | CONF. ajustado | 7 | S | ⬜ |
| FE-16 | «Gestión de Programas» de Legajos con KPIs sin valor | BAJA | CONF. | 5 | S | ⬜ |
| FE-22 | Dashboards fuera de canon | BAJA | CONF. | 5 | M | ⬜ |
| FE-23 | `_field.html` duplicado | BAJA | CONF. ajustado | 5 | S | ⬜ |
| FE-24 | Solapas sin ARIA ni teclado | BAJA | CONF. | 5 | S | ⬜ |
| FE-25 | Avisos paralelos en `alertas_websocket.js` | BAJA | CONF. código | 5 | S | ⬜ |
| FE-26 | Doble envío en formularios clásicos | BAJA | PLAUSIBLE | 5 | S | ⬜ |
| V5A-NEW-04 | Edición del ciudadano: hero fuera de canon y texto técnico visible | BAJA | CONF. navegador | 5 | S | ⬜ |
| V5A-NEW-08 | `compile_templates.py` compila templates de terceros | BAJA | CONF. | 6 | S | ✅ |

---

## ALTA

### FE-02 · `toastr` no cargado en el legajo: «Subir archivos» y «Agregar vínculo» no envían nada
**Severidad:** ALTA · **Estado:** CONFIRMADO en navegador (`typeof toastr === 'undefined'`; el submit de `#formArchivos` tira `toastr is not defined` y sale 0 POST a `/subir-archivos/`) · **Origen:** A6-02 · **Ola:** 5 · **Esfuerzo:** S
- **Contexto:** figuraba como pendiente en los Cambios 95/96 (`requerimientos.md:10525`, 96.6) solo por «Copiar DNI»; no se registró que bloquea la subida y el alta de vínculo.
- **Propuesta:** en `legajos/templates/legajos/ciudadano_detail.html`, sacar las 4 líneas `toastr.options = …` (1175, 1178, 1466, 1628); `toastr.success|warning|error(x)` → `window.toast('success'|'warning'|'error', x)` en 1176, 1179, 1469, 1493, 1499, 1502 y 1643; los `Swal.fire('Error', …)` de 1453, 1456, 1617, 1620, 1645 y 1648 son avisos: → `window.toast('error', …)`; en `core/tests/js_harness.py:138`, quitar `var toastr = __stub('toastr')`.
- **Verificación:** test JS con el harness sin el stub; Playwright: subir un archivo → POST 200 y toast; cerrar el pendiente del Cambio 95/96 en `requerimientos.md`.
- **Dependencias:** SEC-10 y LEG-04 tocan el mismo flujo. **LEG-03 / D-L03:** las líneas del flujo de vínculos (1443-1502) desaparecen con el default B (retirar la solapa); con la opción A, «Agregar vínculo» sigue en 404 hasta montar la API. Hacer FE-02 en el mismo PR que LEG-03 y no corregir esas líneas si se retiran.

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — fuera las cuatro líneas `toastr.options = …` y
todos los `toastr.success|warning|error`, reemplazados por `window.toast(tipo, mensaje)`, el único sistema de avisos
del repo. Los `Swal.fire('Error', …)` que eran **avisos** (no confirmaciones) también pasaron a `window.toast`; las
dos confirmaciones destructivas siguen en SweetAlert2, que la pantalla carga de verdad. En
`core/tests/js_harness.py` se retiró `var toastr = __stub('toastr')`: sin el stub, cualquier script que vuelva a
usar la biblioteca revienta en los tests y no en producción. **Las líneas del flujo de vínculos (1443-1502) no se
corrigieron: desaparecieron** con el default B de LEG-03, como pedía la ficha.
**Test permanente:** `legajos.tests.test_ciudadano_detail_ola5.AvisosConToastTests.test_subir_archivos_manda_el_post`
(corre el script real de la página con `node` y exige el POST a `/subir-archivos/` más el aviso;
+ `test_la_pagina_no_usa_toastr` y `test_los_avisos_usan_window_toast`).

### FE-04 · Provincias, Municipios y Localidades paginan de a 20 pero no muestran paginación
**Severidad:** ALTA · **Estado:** CONFIRMADO en navegador (`/configuracion/localidades/`: 20 filas, 0 enlaces `?page=`; `?page=2` tiene 11 filas inalcanzables) · **Origen:** A6-04 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** en `configuracion/templates/configuracion/{provincia,municipio,localidad}_list.html`, al pie de la card de la tabla, `{% include "components/_paginacion.html" with page_obj=page_obj entidad="localidad" entidad_plural="localidades" %}` (entidad según pantalla); en `configuracion/views/geografia.py`, cada `form_invalid` (46, 69, 118…) arma el contexto con el mismo queryset paginado (helper `_contexto_lista(request, form, **extra)` con `Paginator(qs, 20).get_page(request.GET.get("page"))`).
- **Tests:** con 21 localidades, la página 1 tiene `?page=2`; un POST inválido devuelve `page_obj`.

**Resolución:** ✅ Resuelto en el PR #600 (Cambio 152), 06-10-2026 — `{% include "components/_paginacion.html" %}`
al pie de la card de las tres pantallas, en la misma posición que la golden de listado, y
`configuracion/views/geografia.py` con un `_queryset(modelo)` único para el `ListView` y para los seis
`form_invalid`, más un `_contexto_lista(...)` que arma el contexto paginado. **Desvío de la propuesta:**
paginar el `form_invalid` a secas metía un bug nuevo —el error de edición de la fila 21 volvía a una página 1
donde esa fila no está y el modal no se renderizaba nunca—, así que el helper devuelve la **página que
contiene el registro destacado**. De paso, el listado de provincias deja de salir por `id` mientras el
reintento tras un error salía por `nombre`.
**Test permanente:** `configuracion.tests.test_configuracion_ola5.GeografiaPaginacionTests.test_la_pagina_1_ofrece_la_2`
(+ `test_la_ultima_fila_es_alcanzable`, `test_el_post_invalido_devuelve_la_lista_paginada` y
`test_el_error_de_edicion_abre_el_modal_de_la_fila_aunque_no_esté_en_la_página_1`).

### FE-05 · Wizard «Nuevo programa»: la cascada Secretaría → Subsecretaría nunca se ejecuta
**Severidad:** ALTA · **Estado:** CONFIRMADO en navegador (el HTML de `/configuracion/programas/nuevo/paso1/` no contiene `ajax_load_subsecretarias`; el select de subsecretaría tiene solo la opción vacía) · **Origen:** A6-05 · **Ola:** 5 · **Esfuerzo:** S
- **Causa:** `configuracion/templates/configuracion/programa_wizard_paso1.html:96` usa `{% block extra_js %}`, que ningún ancestro declara (el bloque de JS del shell es `customJS`). Otros bloques sin destino con efecto: `legajos/dashboard_simple.html:content` y `legajos/historial_contactos.html:extra_css/extra_js` (se van con LEG-06).
- **Propuesta:** `{% block extra_js %}` → `{% block customJS %}`; en el `fetch`, `if (!r.ok) throw new Error()` y `.catch(() => window.toast('error', 'No se pudieron cargar las subsecretarías'))`; convertir `poc/herramientas/bloques_sin_destino.py` en un flag `--bloques` de `scripts/compile_templates.py` que falle si un hijo define un bloque de primer nivel que ningún ancestro declara.
- **Tests:** render del paso 1 contiene `ajax/load-subsecretarias`; Playwright: elegir una secretaría → al menos 1 opción de subsecretaría.

**Resolución:** ✅ Resuelto en el PR #600 (Cambio 152), 06-10-2026 — `{% block extra_js %}` pasa a
`{% block customJS %}`, el `fetch` corta con `if (!r.ok) throw` y el `catch` avisa con
`window.toast('error', 'No se pudieron cargar las subsecretarías')` además de dejar el texto en el select.
La PoC `poc/herramientas/bloques_sin_destino.py` se convirtió en el flag **`--bloques` de
`scripts/compile_templates.py`**, que corre en el job «Contratos del repo» y falla con cualquier bloque de
primer nivel que ningún ancestro declare. La allowlist nace con **seis** entradas, cada una con la ficha que
la mata (`menu-adicional` de `403/404/500.html` → FE-20; `content` y `extra_css`/`extra_js` de
`legajos/dashboard_simple.html` e `historial_contactos.html` → LEG-06), y un test exige que no queden
entradas muertas. **El wizard no se rediseñó:** D4 (Cambio 129) dice que ese arquetipo no está definido.
**Test permanente:** `configuracion.tests.test_configuracion_ola5.WizardCascadaTests.test_el_paso_1_incluye_el_script_de_la_cascada`
(+ `core.tests.test_compile_templates_bloques.BloquesSinDestinoTests.test_el_repo_no_tiene_bloques_sin_destino_nuevos`).

### FE-06 · Clases que el build no genera: controles invisibles
**Severidad:** ALTA · **Estado:** CONFIRMADO-AJUSTADO en navegador · **Origen:** A6-06, A6-11, V5A-NEW-09 · **Ola:** 5 · **Esfuerzo:** S
- **Evidencia:** «← Volver al Dashboard» en `/legajos/dashboard-contactos/`: fondo `rgba(0,0,0,0)` con texto blanco (invisible); «Cancelar» de `/configuracion/localidades/crear/` sin caja; backdrop del sidebar a 390 px transparente; tarjetas del hero de `/legajos/ciudadanos/1/editar/` (`bg-white/78`, `/90`) transparentes.
- **Causa:** `tailwind.config.js` declara `extend.backgroundColor.gray` como string y eso pisa la escala `gray` solo para `bg-*` (`text-gray-*` sí existe); `bg-white/NN` no se genera porque `white` es `var(--bg-white)` sin `<alpha-value>`. Lista completa en el anexo.
- **Propuesta (por componente, template por template):**
  - «Cancelar» y links de volver (`bg-gray-200/300` + `hover:bg-gray-300/400`) → `btn-nodo btn-tertiary btn-base` (17 archivos de Configuración y `users/templates/rol/rol_form.html`); acción principal cruda (`bg-blue-600`, `bg-indigo-600`) → `btn-nodo btn-brand btn-base`.
  - «Volver» de los 3 `*_contactos_simple.html` y `legajos/reportes.html` (`bg-gray-500 hover:bg-gray-600 text-white`) → `btn-nodo btn-secondary btn-sm` con `<i class="fas fa-arrow-left" aria-hidden="true"></i>`, o `page_header` con `volver_url` (FE-11).
  - `templates/legajos/alertas_dashboard.html:151` «Cerrar» (`bg-gray-600 … hover:bg-gray-700`) → `btn-nodo btn-secondary btn-sm`; `:147` «Ver legajo» (`bg-red-600`) → `btn-nodo btn-tertiary btn-sm` (ver FE-09); el `bg-gray-400` → `badge badge-gray`.
  - Backdrop `templates/includes/sidebar/base.html:68`: `bg-gray-900/80` → `bg-black/50` (ya compilado).
  - `templates/includes/base.html:3`: sacar `bg-gray-50` del `<html>` (el fondo lo da `--fondo-principal`).
  - `bg-gray-50` de los forms de Legajos (`ciudadano_confirmar_form`, `ciudadano_edit_form`, `ciudadano_manual_form`, `derivar_programa`, `historial_contactos_simple`) y de `rol_form` → `bg-secondary`.
  - `legajos/ciudadano_edit_form.html:20,31,35,39`: `bg-white/78` y `bg-white/90` → `bg-white` (o sacar el hero, V5A-NEW-04).
  - `programas/templates/programas/dispositivos/legajo/detail.html:131`: `border-fg-brand` → `border-brand`.
  - `divide-border` (`dispositivos/config/_tipo_detail_content.html:45`, `config/tipo_list.html:34`, `legajo/list.html:36`) → `divide-y` con `[&>*]:border-light` o migrar a `nodo-td` (FE-12).
  - `badge-nodo` (`legajos/programas/programa_detail.html`) → `badge`.
  - **No** agregar la escala `gray` al build (va contra los tokens).
- **Verificación:** regla CLASSDEF (FE-13) en 0 para estos archivos; a 390 px, `getComputedStyle(backdrop).backgroundColor !== "rgba(0, 0, 0, 0)"`; capturas de las 4 pantallas.

## MEDIA

### FE-01 · `mobile-enhancements.js` (cargado en todo el backoffice) altera controles, modales y gestos
**Severidad:** MEDIA (A6: ALTA) · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A6-01, A6-27 (parte `showToast`), V5A-NEW-05, V5A-NEW-06 · **Ola:** 5, con FE-07 (después de la Ola 6 paso 3) · **Esfuerzo:** S · **Decisión:** D-F01 (swipe)
- **Confirmado:** `enhanceTouchNavigation()` corre en todos los anchos: entre 11 y 54 controles por página quedan con `min-height:44px; display:inline-flex` en línea, también en escritorio (sidebar 40 → 44 px). `#modal-cancel` queda con `display:inline-flex` y se ve en un `ModernModal` `type:'success'` (hoy el backoffice solo usa `type:'confirm'`: síntoma latente, pero rompe el contrato del inventario). Riesgos de código: `enhanceModals` observa cualquier `[class*="modal"]` y en ≤768 px un `touchstart` en `#modal-overlay` lo oculta sin resolver la promesa ni devolver el foco; `addSwipeSupport` abre/cierra el sidebar con **cualquier** swipe > 100 px en ≤1024 px, incluido el scroll horizontal de una tabla (V5A-NEW-05); `templates/includes/navbar.html:35-42` tiene un `display:none !important` para `.mobile-menu-btn` justificado como «race de Tailwind CDN» cuya causa real es este script (V5A-NEW-06). **No reproducido:** `body{overflow:hidden}` pegado y botones `x-show` que reaparecen. Sin el script no hay errores de consola ni consumidores de su API.
- **Propuesta:**
  1. Quitar el `<script>` de `templates/includes/base.html:172-173` y borrar `static/custom/js/mobile-enhancements.js`.
  2. Rescatar el área táctil solo en táctil: en `static/custom/css/nodo-buttons.css`, `@media (pointer: coarse) { .btn-nodo, .nodo-icon-btn { min-height: 44px; min-width: 44px; } }`; en el `<style>` `.ds-snav` de `templates/includes/sidebar/base.html`, `@media (pointer: coarse) { .ds-snav a, .ds-snav button { min-height: 44px; } }`. El anti-zoom de iOS ya está en `static/custom/css/mobile-forms.css:4-17`.
  3. Quitar el workaround de `navbar.html:35-42` (confirmar a 1440 px que `lg:hidden` alcanza).
  4. D-F01: swipe del sidebar. Default: no. Si se quiere: Alpine en el `<body>` de `base.html` (`@touchstart`/`@touchend`), solo desde el borde (`startX < 24`) y nunca dentro de `.overflow-x-auto`.
  5. Hacer FE-07 antes o en el mismo PR.
- **Verificación:** `core/tests/test_modern_modal_contrato.py`: `base.html` no contiene `mobile-enhancements.js`; Playwright: `ModernModal.show({type:'success'})` deja `#modal-cancel` con `display:none`; a 390 px con `has_touch`, `.nodo-icon-btn` ≥ 44 px; a 1440 px, ítems del sidebar de 40 px; `design_audit` baja 3 errores (HEX, GRADLEG, ZINDEX de este archivo).

### FE-07 · Modales de Configuración: se abren en la esquina y con botones sin tamaño
**Severidad:** MEDIA · **Estado:** CONFIRMADO en navegador (con `x-show` + `display:flex` en línea, al abrir Alpine borra el `display` y el overlay queda `block` con el panel en (16,16); los botones del pie con `btn-nodo btn-tertiary` sin tamaño: `padding-left: 0px`) · **Origen:** A6-07 · **Ola:** 5, después de la Ola 6 paso 3 (clona el modal golden saneado; arrastra a FE-01 y FE-10) · **Esfuerzo:** M
- **Propuesta (cada modal de alta y edición de `configuracion/templates/configuracion/{localidad,municipio,provincia,secretaria,subsecretaria}_list.html`):** overlay `<div x-show="modalCrear" x-cloak x-becas-modal="modalCrear" class="fixed inset-0 z-50 flex items-center justify-center p-4">` sin `style=`; fondo `<div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="modalCrear=false"></div>`; panel `relative bg-white rounded-2xl shadow-xl w-full max-w-[560px] max-h-[90vh] flex flex-col overflow-hidden` con `role="dialog" aria-modal="true" aria-labelledby`; encabezado `{% include "programas/becas/_modal_header.html" with titulo=… titulo_id=… icono="fa-plus" cerrar="modalCrear=false" %}`; pie `{% include "programas/becas/_modal_footer.html" with cancelar="modalCrear=false" accion_texto="Guardar" %}`; `becas-modal.js` en `{% block customJS %}`; en edición con `<template x-if>`, la directiva va igual sobre el overlay con una booleana derivada (`modalEditarPk === pk`). Sidebar (`templates/includes/sidebar/opciones.html:118,330,440,614,695`): `style="display:flex;flex-direction:column;gap:2px"` → `class="flex flex-col gap-0.5"`.
- **Verificación:** molde `programas/tests/test_becas_modal.py`; Playwright: panel centrado (`|x − (vw − w)/2| < 2`), Escape cierra, Tab no sale del panel.

### FE-08 · Errores no de campo invisibles (p. ej. duplicado nombre + municipio)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`non_field_errors` en 0 templates de Configuración salvo `programa_wizard_paso2/3`, y en 0 de los forms de Legajos y Dispositivos; el `unique_together` está en `core/models/base.py:67,87`) · **Origen:** A6-08 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** `templates/components/_form_errores.html`: si hay `form.non_field_errors`, `<div class="mb-4 rounded-lg bg-danger-soft border border-danger-subtle p-4 text-sm" role="alert"><strong class="text-heading">Revisá el formulario</strong>` + cada error `<p class="text-body mt-1">{{ e }}</p>` (sin el `<ul class="errorlist">`). Incluirlo en los 5 modales de Geografía y Secretarías, `programa_wizard_paso1.html` y `paso4.html`, `legajos/ciudadano_{edit,manual,confirmar}_form.html`, `derivar_programa.html` y `programas/dispositivos/legajo/form.html`; migrar `segmento_form.html:15-20` (golden de formulario: actualizar su ficha en el mismo PR, ver anexo del agente). Es pieza nueva: registrar en el inventario canónico (`check_design_agent.py`).
- **Test:** POST de una localidad duplicada → el texto del error aparece.

**Resolución:** ✅ Resuelto en el PR #600 (Cambio 152), 06-10-2026 — `templates/components/_form_errores.html`
es pieza canónica nueva, con contrato en la cabecera, test propio, ficha y fila de inventario (paso 7 del
protocolo del agente). La incluyen los **diez** modales de Geografía y Secretarías —en el de edición,
acotada a la fila que falló, porque el `form` del contexto es uno solo—, los **cuatro** pasos del wizard
(los pasos 2 y 3 migran su markup propio con paleta cruda), `legajos/derivar_programa.html`,
`dispositivos/legajo/form.html` y la **golden del arquetipo Formulario** (`segmento_form.html`), con su
ficha actualizada en el mismo PR. En `design_audit.py` el marcador del arquetipo Formulario pasa a ser el
include y **obligatorio**, y `non_field_errors` a mano queda prohibido.
**Desvío de la propuesta (code-first):** `legajos/ciudadano_{edit,manual,confirmar}_form.html` **no** se
tocaron. No usan `non_field_errors`, pero vuelcan `form.errors.items`, que incluye la clave `__all__`: el
error no de campo ahí ya se ve. Agregar la pieza encima lo duplicaría y reemplazar el resumen borraría los
errores de campo, que en esas tres pantallas no se rinden junto a su control; su migración es FE-11/FE-12.
**Test permanente:** `configuracion.tests.test_configuracion_ola5.ErroresNoDeCampoTests.test_localidad_duplicada_muestra_el_motivo`
(+ `test_municipio_duplicado_muestra_el_motivo`, `test_subsecretaria_duplicada_muestra_el_motivo`,
`test_el_wizard_muestra_el_error_de_la_lista_de_espera_sin_cupo`, `test_las_pantallas_de_configuracion_usan_la_pieza_unica`
y el contrato de la pieza en `core.tests.test_nodo_ui_piezas.FormErroresTest`).

### FE-09 · Links a `/legajos/<id>/`, una ruta que no existe
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (`resolve('/legajos/<uuid>/')` → 404; no existe ninguna ruta de detalle de `LegajoAtencion`) · **Origen:** A6-09 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** `templates/legajos/alertas_dashboard.html:147` → `{% url 'legajos:ciudadano_detalle' alerta.ciudadano_id %}` (`AlertaCiudadano.ciudadano` existe, `legajos/models/base.py:423`); en el JS de `ciudadano_detail.html:1545` y `:1680`, reemplazar el link por texto (`<span class="cd-muted">Acompañamiento</span>` o el código del legajo) hasta que exista una vista de legajo.
- **Verificación:** test que renderiza el dashboard de alertas con una alerta y el `href` resuelve; `git grep -n '"/legajos/\${' legajos/templates` vacío.

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — en `templates/legajos/alertas_dashboard.html`
el botón pasa a `{% url 'legajos:ciudadano_detalle' alerta.ciudadano_id %}` («Ver ciudadano») y **deja de depender de
`{% if alerta.legajo %}`**: el ciudadano siempre está, el legajo no, y el destino que existía era el del ciudadano.
En `ciudadano_detail.html`, el origen «Acompañamiento» de la tabla de archivos y el código de legajo de la tabla de
actividades pasan a `<span class="cd-muted">`: no se inventa una vista de detalle de `LegajoAtencion`, que es trabajo
de producto. El `href` armado hacia `/legajos/<id>/archivos/<n>/eliminar/` **se conserva**: esa ruta sí resuelve.
**Test permanente:** `legajos.tests.test_ciudadano_detail_ola5.AlertasDashboardLinkTests.test_el_boton_apunta_al_detalle_del_ciudadano`
(+ `LinksDeLegajoTests.test_el_detalle_no_arma_links_a_la_ruta_inexistente`).

### FE-10 · Prestación mensual ilegible en celular
**Severidad:** MEDIA · **Estado:** CONFIRMADO en navegador (`th` de 25 a 50 px a 390 px) · **Origen:** A6-10 · **Ola:** 5, después de FE-01 (Ola 6 paso 3) · **Esfuerzo:** S
- **Propuesta:** en `programas/templates/programas/merenderos/prestacion_mensual.html:31-38`, contenedor `overflow-x-hidden` → `overflow-auto` y `<table>` con `min-w-[720px]` (clase arbitraria nueva: `npm run build:tailwind` y commitear el CSS; con la Ola 6, es «novedad»: pedir OK). **Precondición: FE-01** (con el swipe global, arrastrar la tabla abre el sidebar).
- **Verificación:** captura a 390 px sin encabezados partidos; CLASSDEF ve `min-w-[720px]` en el build.

### FE-11 · Los componentes canónicos solo los usa Becas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`page_header`, `_paginacion`, `_estado_vacio`, `_stat_card` y `_alerta` con 0 consumidores fuera de `programas/templates/programas/becas/**` y `templates/components/`) · **Origen:** A6-12 (= A7-02, diagnóstico del agente) · **Ola:** 5 (después de Ola 6 paso 4) · **Esfuerzo:** L
- **Propuesta (pantalla por pantalla, en este orden, clonando la golden de su arquetipo):** (1) Dispositivos `legajo/list`, `legajo/detail`, `admisiones/*` (solo si D-V1 = sí; si no, lo hereda la v2); (2) Merenderos `list`, `detail`, `solicitudes` (ídem); (3) `user_list`, `rol_list`, `rol_detail`; (4) `legajos/ciudadano_list`; (5) Configuración. Reemplazos: header ad hoc → `{% load nodo_ui %}{% page_header titulo=… bajada=… volver_url=… volver_label=… %}…{% endpage_header %}` (sacar `style="font-size:28px…"` de `user_list.html:10-13`, `.cl-h1` y el «← Volver» de texto); vacíos inline → `components/_estado_vacio.html` con `con_filtros=request.GET|hay_filtros`; stat cards propias → `_stat_card.html`.
- **Verificación:** `git grep -l "page_header"` ≥ 1 por pantalla migrada; `design_audit.py --ratchet` (Ola 6) con 0 nuevos; `check_design_agent.py --changed`; capturas antes/después.

### FE-12 · Tablas con estilos en línea por celda e iconografía mezclada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`style="` por archivo: 94 en `subsecretaria_list`, 79 en `secretaria_list`, 70 en `localidad_list`, 65 en `rol_list`, 46 en `user_list`, 296 en `ciudadano_detail`; SVG `stroke-width="1.5"`: 14 en `rol_list`, 9-10 en cada lista de Configuración y en `user_list`) · **Origen:** A6-13, A6-26 · **Ola:** 5 (después de Ola 6 paso 4) · **Esfuerzo:** M · **Decisión:** D3 del agente (íconos)
- **Propuesta (por archivo, según la ficha `componentes/tabla.md`):** `<table class="w-full border-collapse">`, `<tr class="nodo-thead-row">`, `<th class="nodo-th">` (acciones con `text-right` y `<span class="sr-only">Acciones</span>`), `<tr class="hover:bg-secondary">`, `<td class="nodo-td">`; acciones `<a class="nodo-icon-btn" aria-label="Editar {{ obj }}"><i class="fas fa-pen" aria-hidden="true"></i></a>` (borrar con `nodo-icon-btn--danger`); borrar `onmouseenter`/`onmouseleave` y SVG Heroicons del contenido (el shell puede seguir con Heroicons). Archivos: `users/templates/user/user_list.html`, `users/templates/rol/rol_list.html`, `configuracion/templates/configuracion/{provincia,municipio,localidad,secretaria,subsecretaria,programa}_list.html`, `legajos/templates/legajos/ciudadano_list.html`; y si D-V1 = sí, `dispositivos/legajo/list.html`, `dispositivos/config/tipo_list.html`, `merenderos/{list,solicitudes,detail}.html`.
- **Verificación:** conteo de `style="` y `stroke-width="1.5"` en 0 en las tablas; captura lado a lado con `personas_list`.

### FE-13 · `design_audit`: decodificador que trunca clases y sin regla «clase sin definición»
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO · **Origen:** A6-14, V5A-NEW-10; regla CLASSDEF construida sobre A6-06 y gate de build de V5A-NEW-01 · **Ola:** 6 (paso 2, herramientas; primer PR) · **Esfuerzo:** S
**Resolución:** ✅ Cerrada en #574 (Cambio 129), 05-oct-2026 — el decodificador de clases pasó a ser un parser de identificadores CSS (`clases_css()`, portado de `poc/herramientas/cssclasses.py`: el escape hexadecimal consume **un** espacio terminador, el literal no, y solo se leen los preludes de regla, no las declaraciones) y se agregó la regla **CLASSDEF** sobre el universo declarado, con la allowlist de hooks en `scripts/design_audit_hooks.txt`. Sobre `88a19c1e` da **70 P1 + 82 WARN**, y los P1 son exactamente la lista A del `anexo-front-clases-inexistentes.md` (`bg-gray-*`, `hover:bg-gray-*`, `bg-white/78`, `bg-white/90`, `bg-gray-900/80`, `border-fg-brand`, `divide-border`, `mt-px`, `w-40`, `text-opacity-90`). **Dos desvíos respecto de la ficha, los dos code-first:** (a) el punto (1) —la reordenación de la alternancia— ya lo había hecho el **Cambio 95**, así que los 2 TWBUILD falsos (`prestacion_mensual.html:31` y `ciudadano_detail.html:143`) **ya no existían** al empezar: el parser nuevo los cubre con un test de regresión y además arregla lo que la regex no podía (puntos dentro de declaraciones y de `url()`); (b) el universo suma el CSS de los **shells que el template extiende**, que la ficha no contemplaba: sin eso, `.animate-fadeInUp` —definida en el `<style>` de `portal/base.html`— daba 17 falsos positivos. La nota del Cambio 95 sobre el falso positivo queda corregida en la entrada del Cambio 129 (V5A-NEW-10). **Test permanente:** `scripts/test_design_audit.py::DecodificadorTests.test_twbuild_reconoce_valores_arbitrarios_con_coma` y `core.tests.test_design_audit_estructura.DecodificadorCssTests` + `ReglasP1Tests.test_classdef_*`.

**Ampliado por RS-R6-08 (04-oct-2026, duplicado):** los dos `TWBUILD` falsos (`h-[clamp(12rem,calc(100dvh-31rem),28rem)]` en `prestacion_mensual.html:31` y `xl:grid-cols-[minmax(0,1fr)_auto]` en `ciudadano_detail.html:143`) dan error bloqueante en el hook `PostToolUse` y enseñan a ignorar TWBUILD justo cuando el verdadero (V5A-NEW-01) aparece. Test pedido: `scripts/test_design_audit.py::test_twbuild_reconoce_valores_arbitrarios_con_coma` (CSS mínimo con `.h-\[clamp\(1rem\2c 2rem\)\]{}` y un template con `h-[clamp(1rem,2rem)]` → `clases_sin_build` vacío).

- **Evidencia:** `_clases_del_build()` trunca `h-[clamp(12rem,` porque la alternancia prueba `\\.` antes que el escape hexadecimal y el espacio que sigue a `\2c` corta el match; `clases_sin_build()` solo verifica clases con variante o valor arbitrario (no ve `bg-gray-600`, `mt-px`, `w-40`, `bg-white/90`, `border-fg-brand`, `divide-border`). El Cambio 95 registró el `xl:grid-cols-[minmax(0,1fr)_auto]` de `ciudadano_detail.html:143` como «preexistente que `build:tailwind` no resuelve»: es este falso positivo (V5A-NEW-10: corregir la nota al cerrar).
- **Propuesta (`scripts/design_audit.py`):** (1) decodificador: reemplazar el `re.findall` de la línea 216 por un parser de identificadores CSS (`\` + 1-6 hex consume **un** espacio opcional; `\` + otro carácter es literal), base `poc/herramientas/cssclasses.py` (~40 líneas); (2) regla **CLASSDEF** (detalle en `../anexo-agente-diseno.md` §5 y `../anexo-front-clases-inexistentes.md`): ERROR para tokens con forma de utilidad Tailwind ausentes del universo declarado, WARN para el resto, allowlist de hooks en `scripts/design_audit_hooks.txt`; (3) gate de build en CI (V5A-NEW-01); (4) documentar que `compile_templates.py` se corre con `.venv312` (V5A-NEW-08).
- **Verificación:** test unitario del parser con `.h-\[clamp\(12rem\2c calc\(…\)\2c 28rem\)\]`, `.xl\:top-6` y `.w-1\/2`; corrida completa: desaparecen los 2 TWBUILD falsos y aparecen `bg-gray-*` sin variante, `bg-white/90`, `border-fg-brand`, `divide-border`, `mt-px`, `w-40`.

### FE-17 · Paginaciones falsas, sin codificar o copiadas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`rol_list.html:379-389` pie estático «1 de 1» con botones `disabled`; `ciudadano_list.html` arma `&search={{ search_value }}` sin `urlencode`) · **Origen:** A6-17 · **Ola:** 5 · **Esfuerzo:** M
- **Propuesta:** `templates/components/_paginacion.html` con `param` (default `page`) y `extra_qs` (p. ej. `tab=beneficiarios`) —parámetro nuevo de componente canónico: actualizar su fila/ficha—; usarlo en `becas/cupo/segmento_detail.html:116,186,256` (golden de detalle: actualizar su ficha), `relevamientos/convocatoria_detail.html:222`, `relevamiento_detail.html:287`; `rol_list.html`: quitar el pie estático o paginar la vista; `user_list.html:110-128` y `legajos/ciudadano_list.html:154-172` al componente; `ConvocatoriaListView` y el detalle de convocatoria (PERF-17, pendiente del Cambio 92) con `paginate_by` + componente; listas de Merenderos y Dispositivos con `paginate_by = 25` (criterio v2 si D-V1 = no).
- **Verificación:** casos `param`/`extra_qs` en `core/tests/test_nodo_ui_piezas.py`; test de `rol_list` sin «1 de 1».

### FE-18 · Badges de estado: Merenderos sin badge, «Inactivo» en rojo, «Sin datos» en rojo
**Severidad:** MEDIA · **Estado:** CONFIRMADO · **Origen:** A6-18 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** `programas/templates/programas/merenderos/_estado_badge.html` y `_solicitud_estado_badge.html` con el contrato de `dispositivos/_estado_badge.html`, incluidos en `merenderos/list.html:10`, `detail.html:11`, `solicitudes.html:23`; «Inactivo» → `badge badge-gray badge-dot` en `user_list.html:66`, `rol_list.html:269`, `rol_detail.html:18`; en `dispositivos/legajo/detail.html:50-53`, rama `{% elif …semaforo == 'SIN_DATOS' %}text-body-subtle` antes del `else`. Registrar los parciales nuevos en el inventario.
- **Verificación:** test al estilo de `programas/tests/test_estado_badges.py`; `check_design_agent.py --changed`.

### FE-19 · Confirmaciones: «Activar» en rojo, «Rechazar/Cerrar» en color de marca y handler copiado 3 veces
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (los 3 handlers `data-confirm` no son idénticos: `merenderos/detail.html:77` usa `btn-tertiary … text-fg-danger`; `solicitudes.html` y `dispositivos/legajo/detail.html` el botón de marca; «Activar» sale con `btn-danger` en `user_list.html:171` y `rol_list.html:452`) · **Origen:** A6-19 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta (pantallas legacy existentes, coherente con el Cambio 48):** `programas/templates/programas/_swal_confirm_js.html` que lea `data-confirm-title`, `-text`, `-ok`, `data-confirm-danger` (→ `customClass.confirmButton: 'btn-nodo btn-danger btn-base'`; si no, `btn-brand btn-base`) y `data-requires-motivo`; incluirlo en `dispositivos/legajo/detail.html`, `merenderos/detail.html`, `merenderos/solicitudes.html` y borrar los tres `<script>` locales; «Rechazar»/«Cerrar» → `btn-nodo btn-danger btn-base` con `data-confirm-danger`; en `user_list.html:171` y `rol_list.html:452`, `confirmButton: activo ? 'btn-nodo btn-danger' : 'btn-nodo btn-brand'`. **Para pantallas nuevas** (v2 incluida) rige la decisión D2 del agente de diseño: confirmación sí/no con `data-confirm-url` → `ModernModal`; con motivo, arquetipo Modal con form POST. Ojo con la colisión de selectores: Becas escucha `[data-confirm-url]` y este handler `[data-confirm]`.
- **Verificación:** test estático del include; Playwright: el Swal de «Rechazar» tiene `.btn-danger` y el de «Activar» no.

### FE-20 · Formularios de Configuración sobre el wrapper legacy `includes/main.html`; páginas de error sin estilo
**Severidad:** MEDIA · **Estado:** CONFIRMADO en navegador (H1 en x=644, y=224 en `/configuracion/localidades/crear/` y en el paso 1 del wizard, contra x=320, y=104 en la lista; la 404 real con `DEBUG=False` sale como texto plano de 16 px en x=620) · **Origen:** A6-20, V5A-NEW-03 · **Ola:** 5 (después de Ola 6 paso 4) · **Esfuerzo:** M
- **Propuesta:** los 17 templates de Configuración (`*_form`, `*_confirm_delete`, `programa_wizard_paso1-4`) → `{% extends "includes/base.html" %}{% block main-content %}` con el esqueleto del arquetipo Formulario (`div.space-y-5` → `page_header` con `volver_url` → `form.bg-white.rounded-xl.border.border-base.shadow-sm.p-6` → `_form_errores` → `_field` → pie `btn-tertiary`/`btn-brand` `btn-base`). El wizard **no tiene golden** (D4 del agente: frenar): migrar solo el shell y el formulario de cada paso, sin inventar un stepper. `templates/{403,404,500}.html` → `extends includes/base.html` con `_estado_vacio.html` (`icono="fa-triangle-exclamation"`, `titulo`, `texto`, `accion_url` a `core:inicio`). Cuando no quede consumidor, borrar `templates/includes/main.html` (regla SHELLLEGACY del agente).
- **Verificación:** capturas a 1440 y 390 px (H1 en x=320); test con `DEBUG=False` que pide una URL inexistente → 404 con el título; `compile_templates`.

### FE-21 · Modales de Legajos sin Escape ni foco atrapado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (la única escucha de teclado en `ciudadano_detail.html` es la de flechas del tablist, `:1155`) · **Origen:** A6-21 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** en `ciudadano_detail.html`, `{% block customJS %}` con `becas-modal.js`; `window.becasModal.bind(document.getElementById('modalArchivos'), {onClose: () => cerrarModal('modalArchivos')})` (ídem `modalVinculo`, si LEG-03 lo conserva); botones de cierre con `data-becas-modal-cerrar`. El modal crítico de `alertas_websocket.js` va en FE-25.
- **Verificación:** Playwright: abrir, Tab no sale del panel, Escape cierra y el foco vuelve al disparador.

**Resolución:** ✅ Resuelto en el PR #598 (Cambio 150), 06-10-2026 — `ciudadano_detail.html` carga
`static/custom/js/becas-modal.js` en `{% block customJS %}` y ata el modal de archivos con
`window.becasModal.bind(overlay, {onClose: () => cerrarModal('modalArchivos')})`; los botones de cierre (la X y
«Cancelar») llevan `data-becas-modal-cerrar`. El helper observa la clase `hidden` del overlay, así que
`abrirModalArchivos()` y `cerrarModal()` siguen siendo los que mandan y no hubo que reescribir el markup al
arquetipo Modal (eso es FE-11/FE-12, PR 6 de la ola). `modalVinculo` **no se ató: se borró** con LEG-03.
**Test permanente:** `legajos.tests.test_ciudadano_detail_ola5.ModalesAccesiblesTests.test_el_detalle_carga_becas_modal`
(+ `test_los_botones_de_cierre_del_modal_declaran_el_marcador`); el comportamiento del helper ya lo cubre
`programas.tests.test_becas_modal`.

### V5A-NEW-01 · El CSS de Tailwind committeado está desactualizado y no hay gate
**Severidad:** MEDIA · **Estado:** CONFIRMADO (build fresco con `tailwindcss 3.4.19` del repo: faltan `mt-px` y `w-40`, que usa `becas/cupo/segmento_detail.html` desde `aac430c` del 30-sep; sobran 12 clases; último build `7b22954` del 22-sep; ningún workflow corre `build:tailwind`) · **Origen:** V5A-NEW-01 · **Ola:** 6 (paso 2) · **Esfuerzo:** S
**Resolución:** ✅ Cerrada en #574 (Cambio 129), 05-oct-2026 — `static/custom/css/tailwind.css` regenerado y committeado, y gate `Tailwind build is committed` en `design-agent-contract.yml` (`setup-node@v4` node 22 con cache npm → `npm ci` → `npm run build:tailwind` → `git diff --exit-code` con `::error::`). **La causa de fondo no era el build sino el `content` de `tailwind.config.js`,** que solo escaneaba `.html` y `.js`: los campos del backoffice traen buena parte de sus clases desde el widget del form (`programas/forms.py`, el wizard de `configuracion`, el input de archivo del legajo), y para el escáner eso no existía. Un rebuild con el `content` viejo **borraba `focus:ring-1` —los 5 campos del wizard de programas sin indicador de foco, WCAG 2.4.7— y `cursor-not-allowed`**. Con `content` arreglado (apps enumeradas en una constante `APPS`, más los `.py` de `{forms,models,templatetags}`) el build fresco **agrega 18** utilidades en uso (12 del input de archivo del legajo, `mt-px` y `w-40` de la golden de detalle, `text-opacity-90`, `bg-info-soft`, `ring`, `border-yellow-200`) y **saca 31** (no 12: el committeado venía de otro estado del árbol), verificadas una por una con `ast` sobre todos los `.py` de las apps: ninguna de las 31 se usa en ningún archivo del repo. **Segundo hallazgo del mismo renglón:** `./**/templates/**/*.html` alcanzaba los templates de Django admin de un virtualenv dentro del checkout y `node_modules/<pkg>/templates/`, así que el CSS salía distinto según la máquina y el gate obligatorio habría rechazado al que buildeara en la suya (medido: con `venv/` no-dot el CSS cambiaba; con `.venv` no, porque fast-glob no entra a directorios con punto). Enumerar las apps lo cierra por construcción. **Desvío de la ficha:** el gate quedó en `design-agent-contract.yml` y no en `pr-quality.yml` (RS-R6-07), porque el ruleset de `development` ya exige el check `Validate inventory and authority` y moverlo obligaría a reeditar el JSON del ruleset, que todavía no aplicó el dueño del repo. **Test permanente:** `core.tests.test_design_audit_estructura.CssCompiladoAlDiaTests` (toda clase usada en cualquier app está en el CSS compilado o en la deuda congelada) y `ContentDeTailwindTests` (ningún patrón positivo usa comodín de primer nivel; `APPS` cubre toda app con `templates/` o `forms`), más el propio job del CI y `core.tests.test_gates_ci`.

**Ampliado por RS-R6-07 (04-oct-2026, duplicado, frente Red de seguridad):** un rebuild limpio con `tailwindcss 3.4.19` da hoy **cuatro** utilidades faltantes en el CSS committeado (`w-40`, `mt-px`, `text-opacity-90`, `bg-info-soft`) y 13 sobrantes; `TWBUILD` de `design_audit.py` no puede verlo (solo mira clases con variante o valor arbitrario, `:173-176`). YAML del job, en `pr-quality.yml` y obligatorio en el ruleset (RED-20): `actions/setup-node@v4` (node 22, cache npm) → `npm ci` → `npm run build:tailwind` → `git diff --exit-code -- static/custom/css/tailwind.css` con `::error::` que diga «correr `npm run build:tailwind` y commitear»; sin filtro `paths` en el trigger (el filtro va dentro del job, RED-20) e incluyendo `tailwind.config.js` y `package*.json`. Sigue en la Ola 6; antes de encender el gate, commitear el CSS regenerado.

- **Propuesta:** regenerar y commitear (`npm run build:tailwind`); paso de CI (Backend CI o Design Agent Contract): `npm ci && npm run build:tailwind && git diff --exit-code static/custom/css/tailwind.css`. Es lo único que detecta utilidades válidas sin build (CLASSDEF no distingue «inválida» de «build viejo»).
- **Verificación:** el job falla con un template que agrega una utilidad nueva sin rebuild.

### V5A-NEW-07 · Deuda de accesibilidad y consistencia en las pantallas candidatas a referencia
**Severidad:** MEDIA · **Estado:** CONFIRMADO · **Origen:** V5A-NEW-07 · **Ola:** (a) 6, paso 3 · (b) 5, PR 7 · **Esfuerzo:** (a) incluido en el paso 3 · (b) S + S (4 h)
**Resolución:** 🟡 Parte **(a) cerrada** en #577 (Cambio 131), 05-oct-2026 — las cuatro goldens quedan en **0 hallazgos
P1 y marcadores de arquetipo completos**. Sobre lo que pedía la ficha se hizo, además de `programa_list` y
`personas_list`, el saneamiento que la tabla de goldens del anexo §3 manda para `cupo/segmento_detail` (quitar el
`<style>[x-cloak]` —la regla ya es global en `override.css`— y los 3 avatares con `style="background:var(--gradient-brand)"`
→ iniciales en `bg-brand-soft text-fg-brand`, **D5**). En `personas_list`: `<th class="nodo-th text-right"><span
class="sr-only">Acciones</span></th>` y el form de filtros **sin `class`**, con `aria-label` en el control en vez del
`<label>` suelto (`dynamic_list_filters.js:38-39` hace `form.innerHTML = ''` y `form.className = …`: el label y la clase
no sobreviven al montaje). En el modal de `programa_list`: labels `block text-sm font-medium text-heading mb-1` (los de
`_field.html`), help text de `text-fg-danger` → `text-body-subtle`, `data-error="__all__"`, nota → `_alerta.html
tono="info"` (sale además el SVG Heroicons del contenido, D3) y `style="backdrop-filter:blur(4px)"` → `backdrop-blur-sm`.
**Tres desvíos, los tres code-first:** (a) el `<p data-error="__all__">` **no** puede ir como hijo directo del cuerpo:
`space-y-5` compila a `>:not([hidden])~:not([hidden])` y mira el **atributo** `[hidden]`, no la clase `hidden`, así que
sumaba 20 px de hueco con el error oculto — va adentro del primer bloque de campo; (b) el `continue-on-error` del step
`Design audit goldens` se saca acá, pero antes hubo que darle a `--goldens` una fuente de goldens (`design_audit.GOLDENS`):
leía la tabla `## Arquetipos` del núcleo, que escribe el paso 4, y sin ella el gate salía verde sin verificar nada —desde
el **Cambio 132** esa tabla existe y manda, y que el núcleo no la declare es un error del gate—; (c) el
`<style>[x-cloak]` de `programa_list` que la ficha no nombraba también sale, porque `--goldens` audita el archivo entero.
**Parte (b) sigue abierta** (Ola 5, PR 7). **Test permanente:** `core.tests.test_design_audit_estructura.GoldensSaneadasTests`
(9 tests) + `MarcadoresDeArquetipoTests.test_las_goldens_limpias_cumplen_sus_marcadores` sobre los 4 arquetipos +
`GateDeCiTests.test_el_step_de_goldens_corre_y_bloquea`.
- **Evidencia:** `becas/config/programa_list.html:50` (help text del campo SIIS en `text-fg-danger`: parece un error); `becas/relevamientos/convocatoria_list.html:43,49,55,70,75,81` (6 `<label>` sin `for`, WCAG 1.3.1); `becas/revision/personas_list.html:39` (`<th>` de acciones vacío); `_dashboard_panel.html` (KPIs sin `_stat_card`, `modalRespuestas` sin `x-becas-modal`).
- **Propuesta:**
  - **(a) Goldens → Ola 6 paso 3:** `programa_list.html` (help text → `text-body-subtle`, labels, `data-error="__all__"`,
    nota → `_alerta`) y `personas_list.html` (`<span class="sr-only">Acciones</span>`), según la tabla de goldens del anexo
    del agente (§3), **antes** de nominarlas.
  - **(b) No goldens → Ola 5, PR 7:** (1) `becas/relevamientos/convocatoria_list.html:43,49,55,70,75,81`: agregar `for`
    (o `id` + `for`) a los 6 `<label>` (S); (2) `becas/config/_dashboard_panel.html`: KPIs a `_stat_card.html` (si hace
    falta el parámetro `kpi_id`/`nota` para los que llena `becas-dashboard.js`, es novedad del agente: pedir OK), `h3
    style="font-size:16px"` → `text-base`, `modalRespuestas` con `x-becas-modal` según el arquetipo Modal (S). El
    dashboard no es molde: solo se corrige esta deuda.
  - **Verificación (b):** V-UI; Playwright: cada label enfoca su control; `modalRespuestas` cierra con Escape y atrapa el
    foco.

## BAJA

### FE-14 · Estáticos huérfanos
**Severidad:** BAJA (A6: MEDIA; no afectan al usuario) · **Estado:** CONFIRMADO-AJUSTADO (29 JS, no 26; 2.809 líneas; más `static/custom/css/dashboard.css`; ningún consumidor por `git grep` de ruta) · **Origen:** A6-15 · **Ola:** 7 (antes de medir los WARN de CLASSDEF) · **Esfuerzo:** S
- **Archivos:** `alertas_conversaciones`, `alertas_conversaciones_simple`, `base`, `chaco-tailwind.config`, `ciudadanosalertas`, `ciudadanosarchivosform`, `ciudadanosarchivoslist`, `ciudadanosderivacionesform`, `ciudadanosdetail`, `ciudadanosdimensionesform`, `ciudadanosform`, `ciudadanosintervensiones`, `ciudadanosllamados`, `configuraciones`, `conversaciones_tiempo_real`, `custom`, `dashboard`, `fix_pagination`, `formutils`, `global_pagination`, `localidades_modal`, `login`, `navigator`, `passwordresetcomplete`, `perfilchangepassword`, `registros_erroneos`, `sidebar`, `simple_pagination`, `utils` (todos `static/custom/js/<nombre>.js`).
- **Propuesta:** `git rm` + `npm run build:tailwind` (diff sustractivo del CSS) + commit. Ojo: `alertas_conversaciones*.js` son los consumidores de `window.userGroups` que menciona SEC-08: confirmar que no se cargan antes de borrar.
- **Verificación:** `design_audit` baja 9 errores; `collectstatic` y recorrido sin 404 de estáticos; `git grep -E "custom/js/(base|utils|dashboard|custom)\.js"` vacío.

### FE-16 · «Gestión de Programas» de Legajos muestra KPIs sin valor
**Severidad:** BAJA (la pantalla no está en el sidebar) · **Origen:** A6-22 · **Ola:** 5 · **Esfuerzo:** S · **Decisión:** D-F16
- **Ubicación:** `legajos/views/programas.py:get_queryset` («DEPRECATED»; el template lee anotaciones que ya no existen).
- **Propuesta (default D-F16 = borrar con LEG-06):** si se usa, `_stat_card.html` con conteos anotados en `get_queryset`.

### FE-22 · Dashboards fuera de canon: hero, cards de colores, emojis y «Próximamente»
**Severidad:** BAJA · **Origen:** A6-23 · **Ola:** 5 · **Esfuerzo:** M · **Decisión:** D-F22 (hero de `inicio.html`)
- **Propuesta:** stat cards → `_stat_card.html`; quitar los «(Próximamente)» de `legajos/reportes.html`; emojis → Font Awesome con `aria-hidden`; `page_header`; ocultar «Estado WebSocket» si `websockets_enabled` es falso. El dashboard completo no tiene golden (agente: frenar): limitarse a estas piezas. D-F22: ¿el hero de `inicio.html` queda como excepción registrada? (el canon dice «no hero sections»). G2-04 corrige los números del mismo inicio.

### FE-23 · `_field.html` duplicado
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO (el de Becas lleva wrapper `mb-4`; el de Dispositivos ninguno) · **Origen:** A6-24 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** mover a `templates/components/_field.html` con `data-error="{{ field.name }}"` (lo usa `_ajax_js.html:96`), parámetro `wrapper_class` (default `mb-4`; Dispositivos pasa `""`), `aria-describedby` hacia ayuda y error y `aria-invalid="true"` con errores; apuntar los 10 consumidores y reemplazar los `{% for field in form %}` inline de `admisiones/*`, `dispositivos/legajo/{form,cama_form}` y `merenderos/*_form`. Golden de formulario: actualizar su ficha en el mismo PR.
- **Verificación:** `compile_templates`; `programas/tests/test_becas_feedback_js.py`.

### FE-24 · Solapas: ARIA desparejo y sin teclado
**Severidad:** BAJA · **Estado:** CONFIRMADO (0 ARIA en `programa_detail`, `convocatoria_detail`, `relevamiento_detail` y `rol_form`; `dispositivos/legajo/detail` con `role="tab"` sin `aria-controls` ni `tabpanel`; solo `ciudadano_detail.html:1155` implementa flechas) · **Origen:** A6-25 (= A7-12) · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** las solapas se clonan de la golden de detalle (`cupo/segmento_detail.html`) con su ARIA completo; `static/custom/js/nodo-tabs.js` con la navegación por flechas de `ciudadano_detail.html:1155-1164` (más Home/End y `tabindex` itinerante), cargado global en `base.html` (archivo JS nuevo: novedad del agente, con OK); migrar `programa_detail`, `convocatoria_detail`, `relevamiento_detail`, `dispositivos/legajo/detail` (si D-V1 = sí) y `rol_form`; la fila «Tabs backoffice» del inventario pasa a **exigir** ARIA y teclado. (El parcial `_tab.html` que proponían A6/A7 queda fuera: V5b lo recortó.)
- **Verificación:** `check_design_agent.py --changed`; Playwright: flecha derecha cambia la solapa y el foco.

### FE-25 · Avisos paralelos en `alertas_websocket.js`
**Severidad:** BAJA (solo con `WEBSOCKETS_ENABLED`) · **Estado:** CONFIRMADO (código, `alertas_websocket.js:96-146`) · **Origen:** A6-27 (parte websocket) · **Ola:** 5 (o con G1c-04, Ola 2) · **Esfuerzo:** S
- **Propuesta:** `showToast(alerta)` → `window.toast(alerta.prioridad === 'CRITICA' ? 'error' : 'warning', texto)`; `showCriticalModal` → `ModernModal.show({type:'warning', title, message, confirmText:'Ver'})` (hoy nunca se dispara: G1c-17); elimina además `bg-gray-200/hover:bg-gray-300` de `:146` y `hover:bg-gray-50` de `:245`.
- **Verificación:** test estático sin `alert-toast`.

### FE-26 · Doble envío posible en formularios clásicos fuera de Becas
**Severidad:** BAJA · **Estado:** PLAUSIBLE (no reproducido) · **Origen:** A6-29 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `programas/templates/programas/admisiones/{admitir,egreso,traslado,promover}.html`, `dispositivos/legajo/{form,parte_diario,camas_form}.html`, `merenderos/{solicitud_form,entrega_form,prestacion_mensual}.html`, formularios de Configuración y Legajos. Referencia: `programas/templates/programas/becas/_ajax_js.html`.
- **Propuesta:** script global chico en `base.html`: en `submit` de `form[method=post]:not([data-ajax])`, deshabilitar sus `[type=submit]` (incluidos los externos con `form=`), marcar `aria-busy` y restaurar en `pageshow` con `persisted`.
- **Verificación:** Playwright con doble clic en «Confirmar egreso» → un solo POST.

### V5A-NEW-04 · Edición del ciudadano: hero fuera de canon, tarjetas transparentes y texto técnico visible
**Severidad:** BAJA · **Estado:** CONFIRMADO en navegador · **Origen:** V5A-NEW-04 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `legajos/templates/legajos/ciudadano_edit_form.html` (hero con gradiente; tarjetas `bg-white/78` y `/90` computan transparente; la bajada visible dice «…desde una vista unificada con **componentes Flowbite**»).
- **Propuesta:** `page_header` con bajada funcional, sin hero; DNI, estado y perfil como `badge` en el header.

### V5A-NEW-08 · `compile_templates.py` compila templates de terceros en el checkout principal
**Severidad:** BAJA · **Estado:** CONFIRMADO (349 templates en el checkout contra 199 en un árbol limpio: el filtro de `scripts/compile_templates.py:41-42` compara prefijo de ruta y `.venv312` vive dentro del repo) · **Origen:** V5A-NEW-08 · **Ola:** 6 (paso 2) · **Esfuerzo:** S
**Resolución:** ✅ Cerrada en #574 (Cambio 129), 05-oct-2026 — el filtro de directorios descarta además cualquier ruta que contenga `site-packages`. Verificado: **199 compilados y 0 errores** tanto en el worktree como corriendo el script desde el checkout principal, donde viven `.venv` y `.venv312`. **Test permanente:** `scripts/test_design_audit.py::CompileTemplatesTests.test_compile_templates_excluye_site_packages`.
- **Propuesta:** excluir las rutas que contengan `site-packages`. Verificación: 199 en los dos lugares.
