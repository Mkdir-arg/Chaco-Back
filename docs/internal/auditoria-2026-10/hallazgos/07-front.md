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
| FE-06 | Clases que el build no genera: botones invisibles, backdrop transparente | ALTA | CONF. ajustado (navegador) | 5 | S | ✅ |
| FE-01 | `mobile-enhancements.js` global altera controles, modales y swipe | MEDIA (A6: ALTA) | CONF. ajustado | 5 | S | ✅ |
| FE-07 | Modales de Configuración en la esquina y con botones sin tamaño | MEDIA | CONF. navegador | 5 | M | ✅ |
| FE-08 | Errores no de campo invisibles | MEDIA | CONF. | 5 | S | ✅ |
| FE-09 | Links a `/legajos/<id>/`, ruta inexistente | MEDIA | CONF. ajustado | 5 | S | ✅ |
| FE-10 | Prestación mensual ilegible en celular | MEDIA | CONF. navegador | 5 | S | ✅ |
| FE-11 | Componentes canónicos solo en Becas | MEDIA | CONF. | 5 | L | 🟡 (Usuarios, Roles y Configuración ✅; `ciudadano_list` en el PR 6b) |
| FE-12 | Tablas con estilos en línea e iconografía mezclada | MEDIA | CONF. | 5 | M | 🟡 (8 de 9 archivos; falta `ciudadano_list`) |
| FE-13 | `design_audit`: decodificador roto y sin regla «clase sin definición» | MEDIA | CONF. ajustado | 6 | S | ✅ |
| FE-17 | Paginaciones falsas o copiadas | MEDIA | CONF. | 5 | M | 🟡 (`rol_list` pagina y `user_list` usa la pieza; `param`/`extra_qs` y los detalles de Becas en el PR 6b) |
| FE-18 | Badges de estado incoherentes | MEDIA | CONF. | 5 | S | ✅ |
| FE-19 | Confirmaciones con colores invertidos y handler copiado | MEDIA | CONF. ajustado | 5 | S | ✅ |
| FE-20 | Wrapper legacy `includes/main.html`: contenido desplazado; 403/404/500 sin estilo | MEDIA | CONF. navegador | 5 | M | ⬜ |
| FE-21 | Modales de Legajos sin Escape ni foco | MEDIA | CONF. | 5 | S | ✅ |
| V5A-NEW-01 | `tailwind.css` committeado desactualizado y sin gate | MEDIA | CONF. | 6 | S | ✅ |
| V5A-NEW-07 | Deuda de accesibilidad en las pantallas candidatas a referencia | MEDIA | CONF. | 6 (a) / 5 (b) | (a) en paso 3 · (b) 2 × S | 🟡 (a) ✅ · (b) parcial |
| FE-14 | 29 JS y 1 CSS huérfanos | BAJA (A6: MEDIA) | CONF. ajustado | 7 | S | ⬜ |
| FE-16 | «Gestión de Programas» de Legajos con KPIs sin valor | BAJA | CONF. | 5 | S | ✅ |
| FE-22 | Dashboards fuera de canon | BAJA | CONF. | 5 | M | 🟡 |
| FE-23 | `_field.html` duplicado | BAJA | CONF. ajustado | 5 | S | ⬜ |
| FE-24 | Solapas sin ARIA ni teclado | BAJA | CONF. | 5 | S | ⬜ |
| FE-25 | Avisos paralelos en `alertas_websocket.js` | BAJA | CONF. código | 5 | S | ✅ |
| FE-26 | Doble envío en formularios clásicos | BAJA | PLAUSIBLE | 5 | S | ✅ |
| V5A-NEW-04 | Edición del ciudadano: hero fuera de canon y texto técnico visible | BAJA | CONF. navegador | 5 | S | ✅ |
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

**Resolución:** ✅ Resuelto en el PR #603 (Cambio 155), 06-10-2026 — cada clase inexistente se reemplazó
por el token o la pieza canónica, **sin** agregar la escala `gray` al build. El `<html>` pierde su
`bg-gray-50`, el backdrop del sidebar pasa a `bg-black/50`, los diecisiete «Cancelar» de Configuración y el
de `rol_form` a `btn-nodo btn-tertiary btn-base` (y sus acciones principales crudas a `btn-brand`/`btn-danger`
`btn-base`), los «Volver» de las tres `*_contactos_simple` a `btn-nodo btn-secondary btn-sm` con
`fa-arrow-left`, los fondos de los formularios de Legajos a `bg-secondary`, los rieles de progreso a
`bg-tertiary`, `bg-white/78`/`/90` a `bg-white`, `border-fg-brand` a `border-brand`, `divide-border` a
`divide-light` y `badge-nodo` a `badge`. **Ningún template del backoffice nombra ya una clase que el build
no genere.** **Tres desvíos, los tres code-first:** (a) el indicador de WebSocket de `alertas_dashboard`
quedó en `bg-disabled` y no en `badge badge-gray` —es un punto de 12 px sin texto, y un `badge` le pondría
padding de píldora; es el mismo token que usa el indicador gemelo del navbar—; (b) el `bg-gray-500` de
`legajos/reportes.html` no era un «Volver» sino el punto de color del estado «otros», así que quedó en
`bg-gray`, token declarado en `tailwind.config.js`; (c) `divide-y divide-light` en vez de
`divide-y [&>*]:border-light`, que evita un valor arbitrario nuevo con el mismo resultado.

**Qué queda y por qué** (deuda de `CssCompiladoAlDiaTests`, que baja de 22 clases a 6, cada una con su
dueño): `bg-gray-50` y `bg-gray-600` en **Conversaciones** (`configurar_cola.html`, `lista.html`), que se
apaga entera con G1-01 fase 2; `bg-gray-200` y `bg-gray-900` en **`static/custom/js/portal-effects.js`**
(portal ciudadano); `hover:bg-gray-50` en el JS de alertas, que borra **FE-25** (`alertas_websocket.js`) y
**FE-14** (`alertas_conversaciones_simple.js`); y `bg-gray-100` en **`legajos/forms/ciudadanos.py`** y
**`legajos/models/base.py`**, que **no se tocaron a propósito**: el primero es el bloque `_FLOWBITE_*_CSS`
entero del formulario del ciudadano —su reemplazo es `nodo-field`, FE-11/FE-12— y el segundo es un mapa
estado→clase dentro del modelo, que por el inventario va en el parcial de badges del módulo (FE-12).
Cambiarles la clase sola los deja igual de fuera de canon.
**Test permanente:** `core.tests.test_front_ola5.ClasesQueElBuildNoGeneraTests.test_las_pantallas_de_la_ficha_no_usan_clases_fuera_del_build`
(+ `test_el_backdrop_del_sidebar_tiene_fondo_real`, `test_el_html_no_pinta_un_fondo_que_no_existe`,
`test_los_cancelar_de_configuracion_son_botones_del_sistema` y
`core.tests.test_design_audit_estructura.CssCompiladoAlDiaTests.test_la_deuda_no_tiene_entradas_resueltas`).
**Playwright (1440 y 390 px):** «Cancelar» con fondo `rgb(255,255,255)` y `padding-left: 16px`; «Volver» con
fondo; backdrop en `rgba(0, 0, 0, 0.5)`.

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

**Resolución:** ✅ Resuelto en el PR #603 (Cambio 155), 06-10-2026 — el `<script>` salió de
`templates/includes/base.html` y `static/custom/js/mobile-enhancements.js` **se borró**: no tenía un solo
consumidor de su API. El área táctil de 44 px la dan ahora `static/custom/css/nodo-buttons.css` y el
`<style>` de `templates/includes/sidebar/base.html`, los dos detrás de `@media (pointer: coarse)`, así que
con mouse cada control conserva el alto de su token. El `display:none !important` de `navbar.html` se fue
con sus dos clases hook (`lg:hidden` alcanza: el shell sirve Tailwind compilado, no el CDN). **D-F01 = No:**
no se reimplementó el swipe. **Desvío (code-first): un bug que la ficha no vio.** Su propio criterio de
verificación —`ModernModal.show({type:'success'})` deja `#modal-cancel` en `display:none`— **seguía
fallando con el script ya borrado**: `.btn-nodo { display: inline-flex }` tiene la misma especificidad que
`.hidden` (0,1,0) y `nodo-buttons.css` se carga **después** de `tailwind.css`, así que ganaba por orden y el
«Cancelar» se veía en cualquier modal de aviso. Se agregó `.btn-nodo.hidden, .nodo-icon-btn.hidden
{ display: none }`, el mismo recaudo que `responsive.css` ya toma con `.modal-responsive.hidden`.
**Test permanente:** `core.tests.test_front_ola5.MobileEnhancementsRetiradoTests.test_el_shell_del_backoffice_no_carga_el_script`
(+ `test_el_script_no_existe_en_el_repo`, `test_ningun_template_ni_js_lo_referencia`,
`test_el_area_tactil_de_44px_la_da_el_css_y_solo_en_tactil`, `test_el_sidebar_da_area_tactil_en_tactil`,
`test_el_navbar_no_esconde_el_boton_mobile_con_important` y
`test_un_boton_del_sistema_con_hidden_queda_oculto`).
**Playwright:** a 1440 px el ítem del sidebar mide 40 px y hay **0** controles con estilo en línea; a 390 px
con `has_touch`, `btn-nodo` mide 44 px; `ModernModal` `success` deja `#modal-cancel` en `display: none`.

### FE-07 · Modales de Configuración: se abren en la esquina y con botones sin tamaño
**Severidad:** MEDIA · **Estado:** CONFIRMADO en navegador (con `x-show` + `display:flex` en línea, al abrir Alpine borra el `display` y el overlay queda `block` con el panel en (16,16); los botones del pie con `btn-nodo btn-tertiary` sin tamaño: `padding-left: 0px`) · **Origen:** A6-07 · **Ola:** 5, después de la Ola 6 paso 3 (clona el modal golden saneado; arrastra a FE-01 y FE-10) · **Esfuerzo:** M
- **Propuesta (cada modal de alta y edición de `configuracion/templates/configuracion/{localidad,municipio,provincia,secretaria,subsecretaria}_list.html`):** overlay `<div x-show="modalCrear" x-cloak x-becas-modal="modalCrear" class="fixed inset-0 z-50 flex items-center justify-center p-4">` sin `style=`; fondo `<div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="modalCrear=false"></div>`; panel `relative bg-white rounded-2xl shadow-xl w-full max-w-[560px] max-h-[90vh] flex flex-col overflow-hidden` con `role="dialog" aria-modal="true" aria-labelledby`; encabezado `{% include "programas/becas/_modal_header.html" with titulo=… titulo_id=… icono="fa-plus" cerrar="modalCrear=false" %}`; pie `{% include "programas/becas/_modal_footer.html" with cancelar="modalCrear=false" accion_texto="Guardar" %}`; `becas-modal.js` en `{% block customJS %}`; en edición con `<template x-if>`, la directiva va igual sobre el overlay con una booleana derivada (`modalEditarPk === pk`). Sidebar (`templates/includes/sidebar/opciones.html:118,330,440,614,695`): `style="display:flex;flex-direction:column;gap:2px"` → `class="flex flex-col gap-0.5"`.
- **Verificación:** molde `programas/tests/test_becas_modal.py`; Playwright: panel centrado (`|x − (vw − w)/2| < 2`), Escape cierra, Tab no sale del panel.

**Resolución:** ✅ Resuelto en el PR #603 (Cambio 155), 06-10-2026 — los **diez** modales (alta y edición
de las cinco pantallas) clonan la golden del arquetipo Modal: overlay
`x-show + x-cloak + x-becas-modal class="fixed inset-0 z-50 flex items-center justify-center p-4"` sin
`style=`, backdrop `absolute inset-0 bg-black/50 backdrop-blur-sm`, panel
`max-w-[560px] max-h-[90vh] flex flex-col overflow-hidden` con `role="dialog"`, `aria-modal="true"` y
`aria-labelledby`, `_modal_header.html` / `_modal_footer.html` —que son los que traen el tamaño de los
botones— y `becas-modal.js` en `customJS`. En el modal de edición, que vive dentro de un `<template x-if>`
por fila, la directiva toma **`modalEditarPk`** y no la booleana derivada `modalEditarPk === pk`: la
directiva cierra con `evaluate(expresión + ' = false')`, así que la expresión tiene que ser asignable. El
`aria-labelledby` del diálogo pasa la **pk a texto antes** de concatenar
(`{% with pk_texto=obj.pk|stringformat:"s" %}` y recién después `|add:pk_texto`): `add` con un `int` del lado
derecho **devuelve cadena vacía**, y la primera versión del PR dejaba `aria-labelledby=""` con `<h3 id="">`
—un diálogo sin nombre accesible— sin que se notara en el texto del template. Lo encontró la ronda 2 de
revisión; de ahí que los tests de esta ficha afirmen sobre la **respuesta renderizada** y no sobre el markup.
Los cinco contenedores de subítems del sidebar y su `<nav>` dejan el `style=` por clases.
**Desvío (code-first): la confirmación de borrado deja SweetAlert2** y pasa a `data-confirm-url` →
`ModernModal` con `programas/becas/_confirm_js.html`. Fue necesario —el arquetipo Modal prohíbe un
`Swal.fire` nuevo en la pantalla y el inventario clasifica SweetAlert2 como legacy condicionado solo para
Dispositivos, Merenderos y Legajos— y de paso las cinco pantallas dejan de bajar la biblioteca y el `<form>`
oculto que la disparaba. Se arreglaron además «Filtrar» y «Limpiar» de la barra de filtros de Secretarías y
Subsecretarías, con el mismo defecto de botón sin tamaño que la ficha describe para el pie.
**Test permanente:** `configuracion.tests.test_configuracion_modales.ModalesDeConfiguracionTests.test_cumplen_el_arquetipo_modal`
(+ `test_el_overlay_se_centra_por_clase_y_no_por_style`, `test_los_modales_atrapan_el_foco_y_cierran_con_escape`,
`test_el_pie_del_modal_usa_la_pieza_canonica`, `test_ningun_boton_del_sistema_queda_sin_tamano`,
`test_la_confirmacion_de_borrado_es_la_canonica`, `test_el_titulo_del_dialogo_lo_nombra`,
`ModalesRenderizadosTests.test_cada_dialogo_tiene_un_nombre_accesible_que_existe` —sobre la respuesta
renderizada, que es donde se ve el `aria-labelledby` vacío— y
`SubitemsDelSidebarTests.test_los_contenedores_de_subitems_van_por_clase`).
**Playwright:** panel centrado con desvío de **0,00 px**, Tab atrapado dentro del panel y Escape cierra.

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

**Resolución:** ✅ Resuelto en el PR #603 (Cambio 155), 06-10-2026 — el contenedor pasa de
`overflow-x-hidden overflow-y-auto` a `overflow-auto` y la tabla lleva `min-w-[720px]`, con
`npm run build:tailwind` corrido y `static/custom/css/tailwind.css` committeado. La novedad (clase
arbitraria) la autoriza esta misma ficha. Va **después de FE-01**, como pedía la precondición: con el swipe
global, arrastrar la tabla abría el sidebar.
**Test permanente:** `programas.tests.test_merenderos.PrestacionMensualEnCelularTests.test_el_contenedor_de_la_grilla_scrollea_en_horizontal`
(+ `test_la_tabla_tiene_ancho_minimo` y `test_el_ancho_minimo_existe_en_el_build`, que exige la clase en el
CSS committeado: sin ella la tabla se vuelve a comprimir sin que falle nada).
**Playwright (390 px):** la tabla mide 720 px, el contenedor scrollea en horizontal y el `<th>` de servicio
pasa de 50 a **101 px**, sin encabezados partidos.

### FE-11 · Los componentes canónicos solo los usa Becas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`page_header`, `_paginacion`, `_estado_vacio`, `_stat_card` y `_alerta` con 0 consumidores fuera de `programas/templates/programas/becas/**` y `templates/components/`) · **Origen:** A6-12 (= A7-02, diagnóstico del agente) · **Ola:** 5 (después de Ola 6 paso 4) · **Esfuerzo:** L
- **Propuesta (pantalla por pantalla, en este orden, clonando la golden de su arquetipo):** (1) Dispositivos `legajo/list`, `legajo/detail`, `admisiones/*` (solo si D-V1 = sí; si no, lo hereda la v2); (2) Merenderos `list`, `detail`, `solicitudes` (ídem); (3) `user_list`, `rol_list`, `rol_detail`; (4) `legajos/ciudadano_list`; (5) Configuración. Reemplazos: header ad hoc → `{% load nodo_ui %}{% page_header titulo=… bajada=… volver_url=… volver_label=… %}…{% endpage_header %}` (sacar `style="font-size:28px…"` de `user_list.html:10-13`, `.cl-h1` y el «← Volver» de texto); vacíos inline → `components/_estado_vacio.html` con `con_filtros=request.GET|hay_filtros`; stat cards propias → `_stat_card.html`.
- **Verificación:** `git grep -l "page_header"` ≥ 1 por pantalla migrada; `design_audit.py --ratchet` (Ola 6) con 0 nuevos; `check_design_agent.py --changed`; capturas antes/después.

**Resolución:** 🟡 **Parcial** en el PR 6 de la Ola 5 (Cambio 166), 07-10-2026 — migrados los puntos **(3)** y
**(5)** de la propuesta: `user_list`, `rol_list`, `rol_detail` y las **seis** listas de Configuración
(`provincia`, `municipio`, `localidad`, `secretaria`, `subsecretaria`, `programa`). Las ocho listas clonan la
golden `becas/revision/personas_list.html` (`--arquetipo listado` OK en las ocho): encabezado con
`{% page_header %}` —se fue el `<h1 style="font-size:28px">` de las ocho y el «← Volver» circular a mano de
`rol_detail`—, estado vacío con `components/_estado_vacio.html` en sus **dos** variantes (con filtros, con
«Limpiar filtros» decidido por `request.GET|hay_filtros`; sin datos, con la acción de alta) y paginación con
`components/_paginacion.html`. `rol_detail` entra como **ajuste (tipo A)**, no como arquetipo: no tiene solapas
ni métricas, así que solo se le cambió el encabezado y la paleta cruda (`text-gray-900`, `bg-blue-600`,
`border-gray-200`, `text-green-500` → tokens). **Los puntos (1) y (2) no se hacen:** D-V1 = No, así que las
pantallas de Dispositivos y Merenderos las hereda la v2. **Queda para el PR 6b** el punto (4),
`legajos/ciudadano_list.html` (492 líneas, con su propio JS), y los formularios de Configuración, que son FE-20.
**Test permanente:** `core.tests.test_listados_canonicos_ola5_pr6.EncabezadoCanonicoTests.test_todas_usan_el_tag_canonico`
(+ `test_ninguna_escribe_su_propio_h1`, `test_ninguna_dibuja_su_estado_vacio_a_mano` y
`MarcadoresDelArquetipoTests.test_las_nueve_clonan_el_esqueleto_de_la_golden`).
**Playwright (1440 y 390 px, 0 errores de consola):** `<h1>` en **x = 320** a 1440 px y **x = 16** a 390 px, 30 px
y peso 800, en las ocho pantallas.

### FE-12 · Tablas con estilos en línea por celda e iconografía mezclada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (`style="` por archivo: 94 en `subsecretaria_list`, 79 en `secretaria_list`, 70 en `localidad_list`, 65 en `rol_list`, 46 en `user_list`, 296 en `ciudadano_detail`; SVG `stroke-width="1.5"`: 14 en `rol_list`, 9-10 en cada lista de Configuración y en `user_list`) · **Origen:** A6-13, A6-26 · **Ola:** 5 (después de Ola 6 paso 4) · **Esfuerzo:** M · **Decisión:** D3 del agente (íconos)
- **Propuesta (por archivo, según la ficha `componentes/tabla.md`):** `<table class="w-full border-collapse">`, `<tr class="nodo-thead-row">`, `<th class="nodo-th">` (acciones con `text-right` y `<span class="sr-only">Acciones</span>`), `<tr class="hover:bg-secondary">`, `<td class="nodo-td">`; acciones `<a class="nodo-icon-btn" aria-label="Editar {{ obj }}"><i class="fas fa-pen" aria-hidden="true"></i></a>` (borrar con `nodo-icon-btn--danger`); borrar `onmouseenter`/`onmouseleave` y SVG Heroicons del contenido (el shell puede seguir con Heroicons). Archivos: `users/templates/user/user_list.html`, `users/templates/rol/rol_list.html`, `configuracion/templates/configuracion/{provincia,municipio,localidad,secretaria,subsecretaria,programa}_list.html`, `legajos/templates/legajos/ciudadano_list.html`; y si D-V1 = sí, `dispositivos/legajo/list.html`, `dispositivos/config/tipo_list.html`, `merenderos/{list,solicitudes,detail}.html`.
- **Verificación:** conteo de `style="` y `stroke-width="1.5"` en 0 en las tablas; captura lado a lado con `personas_list`.

**Resolución:** 🟡 **Parcial** en el PR 6 de la Ola 5 (Cambio 166), 07-10-2026 — **8 de los 9 archivos** que
nombra la ficha (`ciudadano_list.html` queda para el PR 6b; Dispositivos y Merenderos no entran porque
D-V1 = No). Las ocho tablas pasan a `nodo-thead-row`/`nodo-th`/`nodo-td` dentro de `overflow-x-auto` +
`table.w-full.border-collapse`, con la columna de acciones nombrada (`<span class="sr-only">Acciones</span>`,
que ninguna tenía) y cada acción de fila en `.nodo-icon-btn` con `aria-label` que **nombra el registro**; la
destructiva, en `.nodo-icon-btn--danger`. **Conteos a 0 en los ocho archivos:** `style="` fuera del contrato
(eran 94 en `subsecretaria_list`, 79 en `secretaria_list`, 70 en `localidad_list`, 65 en `rol_list` y 46 en
`user_list`), `<svg` en el contenido —los 14 de `rol_list` y los 9-10 de cada lista pasan a Font Awesome con
`aria-hidden`, D3— y los cuatro handlers de hover inline (`onmouseenter`/`onmouseleave`/`onmouseover`/`onmouseout`),
que ahora son `hover:bg-secondary`. **Dos desvíos, los dos code-first:** (a) el **kebab** de `rol_list` —menú
Alpine con `x-teleport`, posicionado a mano y sostenido por un `<style>` de 140 líneas— se reemplaza por las
cuatro `.nodo-icon-btn` en la celda, que es la variante que el arquetipo permite; con eso se va el `<style>`
entero, incluido su `[x-cloak]` local (ya lo define `override.css`) y el `@media` con `min-width:720px`
(`responsive.css` le da a la tabla `width: max-content; min-width: 100%`, que es lo mismo sin arbitrario). (b)
El `badge-danger` de «Inactiva» en `secretaria_list` y `subsecretaria_list` **no se tocó**: es el defecto de
FE-18, que nombró `user_list`, `rol_list` y `rol_detail`, y cambiarlo acá sería una decisión de producto fuera
de ficha. Queda anotado en el propio template.
**Test permanente:** `core.tests.test_listados_canonicos_ola5_pr6.TablaCanonicaTests.test_ninguna_celda_lleva_sus_utilidades_en_linea`
(+ `test_las_celdas_usan_las_clases_del_sistema`, `test_el_hover_de_fila_no_es_un_handler_inline`,
`test_los_iconos_del_contenido_son_font_awesome`, `test_la_accion_de_fila_nombra_el_registro`,
`test_la_columna_de_acciones_tiene_nombre` y `SinEstilosDePantallaTests.test_ninguna_pantalla_trae_su_propio_bloque_de_estilos`).
**Playwright (1440 y 390 px):** `th` en 11 px, mayúsculas y fondo `rgb(249,250,251)`; `td` en 14 px con
`13px 16px` de padding; `.nodo-icon-btn` de 26 × 26 px en `rgb(107,114,128)` con su `aria-label`
(«Editar Localidad 00», «Ver rol Rol de prueba 00»). A 390 px la tabla scrollea **adentro de su card**
(`scrollWidth` 709 contra `clientWidth` 356 en Usuarios) y el documento no se desplaza.

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

**Resolución:** 🟡 **Parcial** en el PR 6 de la Ola 5 (Cambio 166), 07-10-2026 — cierra la parte que no toca la
pieza canónica. (1) **`rol_list` pagina la vista**, que es la opción de fondo de las dos que ofrecía la ficha:
`RolListView.por_pagina = 25` sobre la lista ya filtrada, y el pie estático «1 de 1» con los dos botones
`disabled` se reemplaza por `components/_paginacion.html`. Con 30 roles visibles la pantalla decía «1 de 1» y
los 30 colgaban abajo; ahora dice «Página 1 de 2» y la 2 es alcanzable. El contador `total_roles` se fue con
el pie que lo imprimía: la pieza cuenta lo que se está viendo. (2) **`user_list` pasa al componente**: se fue
el pie de 20 líneas copiado a mano (`page_obj.has_previous`/`has_next` con sus SVG), y el querystring de los
filtros viaja por `filtros_qs`. (3) **Las ocho incluyen la pieza**, pero **solo cinco paginan**: las tres
listas de geografía ya lo hacían desde FE-04, más `user_list` y `rol_list`. `secretaria`, `subsecretaria` y
`programa` la incluyen y **todavía no paginan**: sus `form_invalid` renderizan el listado a mano, así que
ponerles `paginate_by` sin el tratamiento de `_contexto_lista` (FE-04) reestrena el bug de la fila 21 en
Configuración. El include no dibuja nada sin `page_obj`, así que el PR 6b solo toca la vista. Va ahí, junto
con el `param`/`extra_qs` de la pieza, los tres detalles de Becas (`segmento_detail` —que es golden—,
`convocatoria_detail`, `relevamiento_detail`) y `ConvocatoriaListView`.
**Test permanente:** `users.tests.test_listados_paginados_ola5_pr6.RolesPaginaDeVerdadTests.test_el_pie_ya_no_afirma_una_sola_pagina`
(+ `test_la_primera_pagina_corta_en_el_tope`, `test_la_segunda_pagina_trae_el_resto_y_es_alcanzable`,
`test_el_filtro_viaja_a_la_pagina_siguiente`, `test_el_contador_lo_pone_la_pieza_y_cuenta_lo_filtrado`,
`UsuariosUsaLaPiezaDePaginacionTests.test_la_pagina_1_ofrece_la_2_con_el_texto_de_la_pieza`,
`test_la_ultima_fila_es_alcanzable`,
`core.tests.test_listados_canonicos_ola5_pr6.PaginacionCanonicaTests.test_ningun_pie_esta_escrito_a_mano` y
`test_las_ocho_incluyen_la_pieza`).
**Playwright (1440 y 390 px):** «Página 1 de 2» en las **cinco** que paginan (Usuarios, Roles y las tres de
geografía).

**Ronda 2 de la revisión (07-10-2026).** `{% url 'configuracion:programa_list' as url_sin_filtros %}`
nombraba una ruta que **no existe** —se llama `configuracion:programas`—, y la forma `as` **se traga el
`NoReverseMatch`**: la variable queda vacía, `components/_estado_vacio.html` recibe `accion_url=""` y no
dibuja el ancla. Medido: `/configuracion/programas/?q=zzzz` daba 0 anchors, así que el botón «Limpiar
filtros» de esa pantalla no existió nunca, sin error ni log. Además del nombre corregido quedan dos redes:
una **conductual** —las ocho listas, llevadas a su estado vacío, tienen que dibujar el botón con un `href`
no vacío que `resolve()`— y una **de repositorio**: un barrido de todos los `{% url '<nombre>' %}` literales
de `templates/` y los ocho `*/templates/` que exige que cada nombre resuelva, con ratchet en las dos
direcciones. El barrido midió **33** nombres rotos preexistentes: 32 en `portal/templates/portal/ciudadano/`
(pantallas sin ruta, que el inventario ya declara «no son referencia» y borra la Ola 7) y
`legajos:metricas_contactos_api` en `templates/components/widget_contactos.html`, parcial del shell legacy
que retira LEG-06. **Ninguno fuera de eso.**

### FE-18 · Badges de estado: Merenderos sin badge, «Inactivo» en rojo, «Sin datos» en rojo
**Severidad:** MEDIA · **Estado:** CONFIRMADO · **Origen:** A6-18 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta:** `programas/templates/programas/merenderos/_estado_badge.html` y `_solicitud_estado_badge.html` con el contrato de `dispositivos/_estado_badge.html`, incluidos en `merenderos/list.html:10`, `detail.html:11`, `solicitudes.html:23`; «Inactivo» → `badge badge-gray badge-dot` en `user_list.html:66`, `rol_list.html:269`, `rol_detail.html:18`; en `dispositivos/legajo/detail.html:50-53`, rama `{% elif …semaforo == 'SIN_DATOS' %}text-body-subtle` antes del `else`. Registrar los parciales nuevos en el inventario.
- **Verificación:** test al estilo de `programas/tests/test_estado_badges.py`; `check_design_agent.py --changed`.

**Resolución:** ✅ Resuelto en el PR #605 (Cambio 157), 07-10-2026 — Merenderos estrena sus dos parciales,
`merenderos/_estado_badge.html` (ACTIVO success · SUSPENDIDO warning · CERRADO gray) y
`merenderos/_solicitud_estado_badge.html` (BORRADOR white · EN_REVISION info · OBSERVADA warning · APROBADA
success · RECHAZADA danger), los dos con el contrato de `dispositivos/_estado_badge.html`, y los incluyen el
listado, el detalle —al lado del nombre, como el detalle del dispositivo— y la tabla de solicitudes. **Ninguna
de las tres pantallas vuelca ya `get_estado_display` como texto suelto**, que es lo que había. «Inactivo» pasa
a `badge badge-gray badge-dot` en `user_list.html`, `rol_list.html` y `rol_detail.html`.
**Desvío (code-first):** la rama `SIN_DATOS` se agregó a **dos** de los cuatro indicadores del detalle del
dispositivo, no a los cuatro que nombra la ficha: `programas/services/indicadores.py` solo devuelve
`semaforo == "SIN_DATOS"` en `actualizacion` y `completitud`; ocupación y disponibilidad siempre salen VERDE,
AMARILLO o ROJO (`services/camas.py` y `_semaforo_disponibilidad`), así que ponerles la rama sería código
muerto. Los dos parciales nuevos se registran en el inventario del agente (fila «Mapa de estados por módulo»).
**Test permanente:** `programas.tests.test_estado_badges_merenderos.MerenderoEstadoBadgeTests.test_mapa_estado_a_tono`
(+ `SolicitudMerenderoEstadoBadgeTests.test_mapa_estado_a_tono`,
`PantallasDeMerenderosUsanElParcialTests.test_ninguna_pantalla_vuelca_el_estado_como_texto_suelto`,
`SemaforoSinDatosTests.test_la_rama_sin_datos_va_antes_del_else_que_pinta_de_rojo` y
`users.tests.test_badges_confirmaciones_ola5.InactivoEnGrisTests.test_el_badge_de_inactivo_es_gris`).
**Playwright (1440 y 390 px):** Activo `rgb(236,253,245)`, Suspendido `rgb(255,248,241)`, Cerrado
`rgb(229,231,235)`; «Inactivo» del listado de usuarios en `rgb(229,231,235)`.

### FE-19 · Confirmaciones: «Activar» en rojo, «Rechazar/Cerrar» en color de marca y handler copiado 3 veces
**Severidad:** MEDIA · **Estado:** CONFIRMADO-AJUSTADO (los 3 handlers `data-confirm` no son idénticos: `merenderos/detail.html:77` usa `btn-tertiary … text-fg-danger`; `solicitudes.html` y `dispositivos/legajo/detail.html` el botón de marca; «Activar» sale con `btn-danger` en `user_list.html:171` y `rol_list.html:452`) · **Origen:** A6-19 · **Ola:** 5 · **Esfuerzo:** S
- **Propuesta (pantallas legacy existentes, coherente con el Cambio 48):** `programas/templates/programas/_swal_confirm_js.html` que lea `data-confirm-title`, `-text`, `-ok`, `data-confirm-danger` (→ `customClass.confirmButton: 'btn-nodo btn-danger btn-base'`; si no, `btn-brand btn-base`) y `data-requires-motivo`; incluirlo en `dispositivos/legajo/detail.html`, `merenderos/detail.html`, `merenderos/solicitudes.html` y borrar los tres `<script>` locales; «Rechazar»/«Cerrar» → `btn-nodo btn-danger btn-base` con `data-confirm-danger`; en `user_list.html:171` y `rol_list.html:452`, `confirmButton: activo ? 'btn-nodo btn-danger' : 'btn-nodo btn-brand'`. **Para pantallas nuevas** (v2 incluida) rige la decisión D2 del agente de diseño: confirmación sí/no con `data-confirm-url` → `ModernModal`; con motivo, arquetipo Modal con form POST. Ojo con la colisión de selectores: Becas escucha `[data-confirm-url]` y este handler `[data-confirm]`.
- **Verificación:** test estático del include; Playwright: el Swal de «Rechazar» tiene `.btn-danger` y el de «Activar» no.

**Resolución:** ✅ Resuelto en el PR #605 (Cambio 157), 07-10-2026 — `programas/templates/programas/_swal_confirm_js.html`
es el handler único: carga SweetAlert2 y lee `data-confirm-title`, `-text`, `-ok`, `data-confirm-danger` (→
`confirmButton: 'btn-nodo btn-danger btn-base'`; si no, `btn-brand btn-base`) y `data-requires-motivo`. Lo
incluyen `dispositivos/legajo/detail.html`, `merenderos/detail.html` y `merenderos/solicitudes.html`, y los
tres `<script>` locales —con sus tres variantes— **se borraron**. «Rechazar» y «Cerrar» llevan
`data-confirm-danger`; «Enviar a validación», «Validar», «Observar», «Aprobar», «Suspender» e «Inactivar» no.
En `user_list.html` y `rol_list.html` el `confirmButton` pasa a `activo ? 'btn-nodo btn-danger btn-base' :
'btn-nodo btn-brand btn-base'`. El selector `[data-confirm]` no colisiona con el `[data-confirm-url]` de Becas
y hay un test que lo fija.
**Tres desvíos, los tres code-first:** (a) los botones del diálogo llevan **`btn-base`**, que la propuesta no
nombraba: `customClass` reemplaza entero el del mixin de `nodo-swal-theme.js`, así que sin la clase de tamaño
el botón quedaba con `padding-left: 0` —el mismo defecto de FE-06/FE-07—; (b) se descartó el
`customClass.actions: 'flex gap-2'` que tenía una sola de las tres copias, porque `nodo-swal.css` ya arma el
pie del popup y la clase no hacía nada; (c) el envío confirmado va por **`form.requestSubmit()`** y no por
`form.submit()`, que **no** dispara el evento `submit` y se saltearía la guardia de doble envío de FE-26.
**Lo que no se hizo:** las tres acciones del listado de solicitudes siguen siendo texto subrayado dentro de la
celda, no `btn-nodo`. Recibieron el `data-confirm-danger` —que es lo que arregla el color del diálogo—; pasar
tres acciones de una celda a botones completos es rediseñar la tabla, y eso es FE-12.
**Test permanente:** `programas.tests.test_confirmaciones_legacy.HandlerUnicoTests.test_una_accion_destructiva_confirma_en_rojo`
(+ `test_una_accion_no_destructiva_confirma_en_color_de_marca`, `test_el_motivo_obligatorio_viaja_en_el_post`,
`test_el_envio_dispara_el_evento_submit`, `test_no_intercepta_el_confirm_canonico_de_becas`,
`PantallasSinHandlerPropioTests.test_ninguna_pantalla_conserva_su_copia_del_handler` y
`users.tests.test_badges_confirmaciones_ola5.ConfirmacionSegunLaAccionTests.test_activar_usuario_no_confirma_en_rojo`).
**Playwright (1440 y 390 px):** el Swal de «Cerrar merendero» sale con
`swal2-confirm btn-nodo btn-danger btn-base`, fondo `rgb(199,0,54)` y `padding-left: 16px`; el de «Suspender»,
con `btn-nodo btn-brand btn-base` y sin rojo.

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
**Parte (b): cerrada salvo los 6 KPIs** en el PR #609 (Cambio 161), 07-10-2026 — ver abajo. **Test permanente:** `core.tests.test_design_audit_estructura.GoldensSaneadasTests`
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

**Resolución de la parte (b):** 🟡 Resuelta **menos los KPIs**, en el PR #609 (Cambio 161), 07-10-2026.
**(b.1) `relevamientos/convocatoria_list.html` — cerrada.** Los seis `<label>` del modal «Nueva convocatoria»
llevan `for="{{ form_convocatoria.<campo>.id_for_label }}"` (nombre, segmento, subsegmento, fecha_inicio,
fecha_fin, descripción). **Se saneó además lo otro que la ficha del arquetipo Modal le reprochaba** —es lo que
la descartó como golden—: el `[x-cloak]` propio en un `<style>` local, que `override.css` ya declara global
(misma limpieza que el Cambio 131 en `programa_list`), y el backdrop con el fondo y el blur en un `style=`, que
pasan a `bg-black/50 backdrop-blur-sm`. `design_audit.py --arquetipo modal` sobre ese archivo da **OK**.
**(b.2) `config/_dashboard_panel.html` — parcial.** Los tres títulos de bloque con el tamaño fijado en un
`style=` pasan a `text-base`, y el modal «Exportar respuestas por persona» pasa al arquetipo Modal:
`x-becas-modal="modalRespuestas"` (foco al abrir, Tab atrapado, Escape, scroll del fondo bloqueado y foco
devuelto al disparador), backdrop como hijo propio, panel `max-w-[560px] max-h-[90vh] flex flex-col`, cuerpo
`overflow-y-auto min-h-0`, `_modal_header.html` —que se lleva el SVG de la X pegado a mano— y
`_modal_footer.html`; la nota informativa, que era el markup de `_alerta.html tono="info"` copiado, pasa al
include. `becas-modal.js` ya lo carga el consumidor (`config/programa_detail.html`).
**Los 6 KPIs NO se migraron: frenado por el protocolo del agente.** La ficha lo anticipaba («es novedad del
agente: pedir OK»). `templates/components/_stat_card.html` acepta `etiqueta`, `valor`, `icono` y `tono`; las
tarjetas necesitan además `data-kpi` en el valor, nota al pie, valor compuesto `N / M`, sufijo « %», variación,
un minigráfico SVG de 12 semanas y una barra de progreso. Darle esos parámetros al componente canónico es
rediseñarlo para un arquetipo que no tiene golden: la propuesta concreta va en el cuerpo del PR, para OK del PM.
Es el mismo bloqueo que deja 🟡 a FE-22 con las 4 stat cards del inicio. Quedan también fuera, por no estar en la
ficha, la regla local de impresión del panel y el gradiente del ícono de «Formularios recibidos».
**Test permanente:** `core.tests.test_front_ola5_pr7.ConvocatoriaListLabelsTests.test_cada_label_apunta_a_su_control`
(+ `test_no_quedan_labels_sueltos`, `test_el_modal_no_arrastra_estilo_local`) y
`DashboardPanelDeBecasTests.test_el_modal_de_respuestas_usa_la_pieza_del_arquetipo`
(+ `test_los_titulos_de_bloque_no_fijan_el_tamano_en_linea`, `test_el_modal_de_respuestas_usa_el_header_y_el_pie_canonicos`,
`test_el_modal_no_dibuja_su_propia_x_con_svg`).

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

**Resolución:** ✅ Resuelto en el PR #609 (Cambio 161), 07-10-2026 — salen las tres métricas por tarjeta
(`total_instituciones`, `total_derivaciones_pendientes`, `total_casos_activos`), que imprimían anotaciones que
`get_queryset` dejó de calcular al retirarse `models_institucional`, y el «DEPRECATED» de la vista pasa a decir
qué calcula hoy. **Desvío respecto del default D-F16:** no se borra la pantalla. El default es «borrar **con
LEG-06**», que es de la Ola 7 y es donde vive la decisión sobre derivaciones (D-L06); además `programa_detalle`
sigue siendo el destino de redirect de `dar_de_baja_inscripcion` y de las derivaciones. Acá se saca la deuda
visible; el borrado completo sigue siendo de LEG-06. **Test permanente:**
`core.tests.test_front_ola5_pr7.ProgramasDeLegajosSinKpisVaciosTests.test_las_tres_anotaciones_muertas_no_estan`
(+ `test_el_queryset_ya_no_se_declara_deprecado_con_anotaciones`).

**Queda afuera, medido en la ronda 2:** `ProgramaDetailView` (`legajos/views/programas.py`) inyecta el mismo
tipo de ceros literales —`total_instituciones`, `total_derivaciones_pendientes`, `total_casos_activos`,
`total_casos_totales`, `tasa_aceptacion`, `total_derivaciones`, `promedio_casos_institucion`,
`total_acompanamientos_activos`— y `programas/programa_detail.html` los imprime en **19 lugares** repartidos
por los cinco tabs: la grilla de métricas del encabezado (`:37,45,53,61`), los badges de los tabs (`:77,83`),
las cuatro tarjetas del tab «Dashboard» (`:108,119,130,141`), las tres barras de progreso y la tasa
(`:159,168,177,184`) y tres tarjetas del tab «Indicadores» (`:494,503,512`). Sacarlos deja los tabs «Dashboard»
e «Indicadores» **vacíos**: es rediseñar la pantalla, y D-F16 la borra entera con **LEG-06** (Ola 7). El único
número real de esa vista es `total_acompanamientos_totales` (`:586`), que sí cuenta `InscripcionPrograma`.

### FE-22 · Dashboards fuera de canon: hero, cards de colores, emojis y «Próximamente»
**Severidad:** BAJA · **Origen:** A6-23 · **Ola:** 5 · **Esfuerzo:** M · **Decisión:** D-F22 (hero de `inicio.html`)
- **Propuesta:** stat cards → `_stat_card.html`; quitar los «(Próximamente)» de `legajos/reportes.html`; emojis → Font Awesome con `aria-hidden`; `page_header`; ocultar «Estado WebSocket» si `websockets_enabled` es falso. El dashboard completo no tiene golden (agente: frenar): limitarse a estas piezas. D-F22: ¿el hero de `inicio.html` queda como excepción registrada? (el canon dice «no hero sections»). G2-04 corrige los números del mismo inicio.

**Resolución:** 🟡 Resuelto en el PR #609 (Cambio 161), 07-10-2026 — **salvo las stat cards del inicio**.
**D-F22 aplicado con el default** («aplicar el canon salvo que el PM registre la excepción»): el hero de
`inicio.html` sale y el encabezado pasa al tag canónico, con el mismo saludo de título, la misma bajada en el
bloque `bajada` (trae `<strong>`) y «Ver ciudadanos» como acción. Con él se fueron sus cinco reglas CSS y el
eyebrow que calculaba el saludo por hora en el cliente, su único consumidor. `legajos/reportes.html` queda
migrada: encabezado canónico con «Exportar CSV», cuatro `components/_stat_card.html`, cuatro surfaces con los
cortes que sí se calculan, y **afuera** los dos botones «(Próximamente)» y las cinco «métricas de calidad» que
la vista devolvía en cero literal (también salen de `reportes_view`). El semáforo «Estado WebSocket» de
`alertas_dashboard.html` vive detrás de `{% if websockets_enabled %}`. Los cinco emojis de
`dashboard_contactos_simple.html` pasan a Font Awesome con `aria-hidden`, igual que los seis íconos que ya
estaban sin él.
**Lo que queda abierto (por eso 🟡):** las **4 stat cards de `inicio.html` siguen armadas a mano**. Las cuatro
tienen pie de tarjeta y una además un delta, y `_stat_card.html` solo acepta `etiqueta`, `valor`, `icono` y
`tono`: darle `nota`/`delta` es **novedad del agente** y el protocolo manda frenar y pedir OK. Es el mismo
bloqueo que V5A-NEW-07 (b) con los 6 KPIs de `_dashboard_panel`, y la propuesta concreta va en el cuerpo del PR.
**Fuera de alcance, code-first:** `dashboard/templates/dashboard.html` tiene el mismo defecto que FE-16 —tres de
sus cuatro cards leen claves que `DashboardView` no pone en el contexto— pero la vista está **tapada** por el
orden de `config/urls.py` (RED-78) y su borrado es de la Ola 7 con OPS-14. Y `dashboard_simple.html`,
`historial_contactos_simple.html` y `red_contactos_simple.html` también tienen emojis: son código muerto de
LEG-06 y dos de ellos ni siquiera tienen ruta. **Test permanente:**
`core.tests.test_front_ola5_pr7.ReportesDeLegajosTests` (6 tests) + `EstadoWebsocketTests.test_el_semaforo_vive_detras_de_websockets_enabled`
+ `EmojisComoIconosTests` (2) + `InicioSinHeroTests` (3).

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

**Resolución:** ✅ Resuelto en el PR #605 (Cambio 157), 07-10-2026 — `showToast` pasa a
`window.toast(alerta.prioridad === 'CRITICA' ? 'error' : 'warning', …)` y `showCriticalModal` a
`ModernModal.show({type:'warning', title, message, confirmText:'Ver'})`. Se fueron con ellos la pila de avisos
propia, el overlay armado a mano, `getAlertIcon` —sus cuatro SVG con `text-red-600`/`orange`/`yellow`/`blue`
solo los usaba el toast viejo— y las clases `bg-gray-200`/`hover:bg-gray-300` del pie del modal; el
`hover:bg-gray-50` y el `border-gray-100` de la vista previa de la campana pasaron a `hover:bg-secondary` y
`border-light`. Las dos piezas del shell escriben con `textContent`, así que el nombre del ciudadano ya no
necesita escaparse a mano en ese camino (`escaparHtmlAlerta` sigue, porque la vista previa todavía usa
`innerHTML`: eso es FE-11/FE-12).
**Desvío (code-first): el «Ver» no podía quedar como estaba.** La ficha pedía `confirmText:'Ver'` pero el
único destino del modal viejo era `/legajos/<id>/`, que **no existe** (FE-09). El payload de la alerta trae
`ciudadano_id` (`legajos/services/alertas.py`), así que «Ver» lleva al detalle del ciudadano, con la plantilla
de URL publicada por el shell en `window.alertasConfig` con `{% url %}` —mismo patrón que
`window.conversacionesConfig`, para no escribir rutas literales en el JS (RED-42)—. Sin plantilla o sin
ciudadano, el modal se muestra **sin** acción en vez de ofrecer un enlace roto.
**Lo que queda:** `showCriticalModal` sigue sin dispararse, pero por G1c-17 (el servicio emite
`nueva_alerta_critica` y el consumer declara `alerta_critica`), que no es de esta ficha. Y `hover:bg-gray-50`
sigue en la deuda de `CssCompiladoAlDiaTests` con un solo dueño, `alertas_conversaciones_simple.js` (FE-14).
**Test permanente:** `legajos.tests.test_alertas_avisos_ola5.AvisosPorElSistemaDelShellTests.test_el_toast_lo_dibuja_window_toast`
(+ `test_el_modal_critico_es_el_del_shell`, `test_ver_lleva_al_detalle_del_ciudadano`,
`test_sin_ciudadano_el_modal_no_ofrece_ver`, `SinPiezasParalelasTests.test_no_queda_la_ruta_de_legajo_que_no_existe`,
`test_no_quedan_clases_que_el_build_no_genera` y
`PlantillaDeUrlEnElShellTests.test_la_plantilla_llega_renderizada_y_resuelve`). El test de escape del Cambio 95
(`legajos.tests.test_alertas_websocket_escape`) se actualizó: ahora exige que el script **no escriba ningún
`innerHTML`** en esos dos caminos.

### FE-26 · Doble envío posible en formularios clásicos fuera de Becas
**Severidad:** BAJA · **Estado:** PLAUSIBLE (no reproducido) · **Origen:** A6-29 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `programas/templates/programas/admisiones/{admitir,egreso,traslado,promover}.html`, `dispositivos/legajo/{form,parte_diario,camas_form}.html`, `merenderos/{solicitud_form,entrega_form,prestacion_mensual}.html`, formularios de Configuración y Legajos. Referencia: `programas/templates/programas/becas/_ajax_js.html`.
- **Propuesta:** script global chico en `base.html`: en `submit` de `form[method=post]:not([data-ajax])`, deshabilitar sus `[type=submit]` (incluidos los externos con `form=`), marcar `aria-busy` y restaurar en `pageshow` con `persisted`.
- **Verificación:** Playwright con doble clic en «Confirmar egreso» → un solo POST.

**Resolución:** ✅ Resuelto en el PR #605 (Cambio 157), 07-10-2026 — `static/custom/js/nodo-submit-guard.js`,
cargado una sola vez desde `templates/includes/base.html`, cubre todo el backoffice sin tocar una sola
pantalla. En el `submit` de un `form[method=post]` que no sea `data-ajax`: si ya está `aria-busy`, **cancela**
el envío; si no, lo marca `aria-busy="true"` y deshabilita sus botones de envío, incluidos los externos con
`form="<id>"`. `pageshow` con `persisted` devuelve todo a su estado.
**Dos desvíos, los dos code-first:** (a) el `disabled` se aplica en el **turno siguiente**
(`setTimeout(…, 0)`), no durante el despacho del evento: el navegador arma la lista de entradas del POST
después de despachar `submit` y un control deshabilitado queda fuera, así que hacerlo en el acto le borraría
el `name`/`value` al botón que disparó el envío. La protección real es síncrona y es otra —el segundo
`submit` se cancela—, así que no se pierde nada; (b) el listener respeta `event.defaultPrevented` **y lo mira
dos veces**: si una validación o una confirmación canceló el envío, no bloquea nada. El selector de los
botones externos compara el atributo `form` en vez de armar un selector con el id, que con un id raro se
rompería.
**Ronda 2 de revisión (07-10-2026):** la primera versión leía `defaultPrevented` **solo al entrar**, con el
argumento de que el listener va en `document`, en burbuja, detrás de los del propio formulario. No alcanza: la
guardia se registra al cargar el shell y los scripts de `{% block customJS %}` se registran dentro de
`DOMContentLoaded`, o sea **después**, así que un listener delegado en `document` que cancele el envío corre
**detrás** de la guardia. Reproducido en Chromium: el envío quedaba cancelado y el formulario con
`aria-busy="true"` y los botones `disabled` para siempre. Hoy ninguna pantalla delega así, pero el script es
global. Ahora `defaultPrevented` se reevalúa en el mismo turno diferido del `disabled` y, si quedó cancelado,
se suelta la marca.
**Test permanente:** `core.tests.test_submit_guard.DobleEnvioBloqueadoTests.test_el_primer_envio_pasa_y_el_segundo_se_cancela`
(+ `test_el_boton_no_se_deshabilita_durante_el_despacho`, `test_alcanza_a_los_botones_externos_con_atributo_form`,
`LoQueElGuardNoToca.test_un_formulario_data_ajax_queda_libre`,
`test_un_envio_ya_cancelado_no_bloquea_el_formulario`,
`LoQueElGuardNoToca.test_un_listener_delegado_tardio_que_cancela_libera_el_formulario` (el de la ronda 2),
`VolverConAtrasTests.test_el_bfcache_devuelve_el_formulario_a_su_estado` y
`ElShellCargaLaGuardiaTests.test_el_shell_lo_carga_una_sola_vez`).
**Playwright (1440 y 390 px):** el script está una sola vez en la página; el primer `submit` pasa, el segundo
queda cancelado y el formulario con `aria-busy="true"`.

### V5A-NEW-04 · Edición del ciudadano: hero fuera de canon, tarjetas transparentes y texto técnico visible
**Severidad:** BAJA · **Estado:** CONFIRMADO en navegador · **Origen:** V5A-NEW-04 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `legajos/templates/legajos/ciudadano_edit_form.html` (hero con gradiente; tarjetas `bg-white/78` y `/90` computan transparente; la bajada visible dice «…desde una vista unificada con **componentes Flowbite**»).
- **Propuesta:** `page_header` con bajada funcional, sin hero; DNI, estado y perfil como `badge` en el header.

**Resolución:** ✅ Resuelto en el PR #609 (Cambio 161), 07-10-2026 — encabezado canónico con volver circular al
detalle, título con el nombre del ciudadano y bajada funcional («Datos personales, ubicación y perfil social del
ciudadano»); los tres datos de cabecera pasan a badges y **salen del registro**: `DNI {{ object.dni }}`,
`badge-success`/`badge-gray` según `object.activo` —«Activo» estaba escrito a mano y era igual para un ciudadano
dado de baja— y «Con usuario del portal» solo si `object.usuario` existe («Perfil: Backoffice» no correspondía a
ningún campo). Se fueron el hero con gradiente, su tarjeta sobre fondo y la bajada que le nombraba al usuario la
librería de maquetado.
**Dos desvíos code-first:** (a) las tarjetas `bg-white/78` y `bg-white/90` que citaba la ficha **ya no estaban**:
las arregló FE-06 (Cambio 155) al barrer las clases que el build no genera; (b) el avatar de la tarjeta
«Resumen» también llevaba gradiente y la ficha solo nombraba el del hero — se corrigió con el mismo criterio
**D5** del Cambio 131 (iniciales en `bg-brand-soft text-fg-brand`). **Test permanente:**
`core.tests.test_front_ola5_pr7.EdicionDelCiudadanoTests.test_la_bajada_no_nombra_la_libreria_de_maquetado`
(+ `test_el_encabezado_es_el_canonico`, `test_no_queda_el_hero_con_gradiente`,
`test_el_estado_sale_del_dato_y_no_de_un_literal`).

### V5A-NEW-08 · `compile_templates.py` compila templates de terceros en el checkout principal
**Severidad:** BAJA · **Estado:** CONFIRMADO (349 templates en el checkout contra 199 en un árbol limpio: el filtro de `scripts/compile_templates.py:41-42` compara prefijo de ruta y `.venv312` vive dentro del repo) · **Origen:** V5A-NEW-08 · **Ola:** 6 (paso 2) · **Esfuerzo:** S
**Resolución:** ✅ Cerrada en #574 (Cambio 129), 05-oct-2026 — el filtro de directorios descarta además cualquier ruta que contenga `site-packages`. Verificado: **199 compilados y 0 errores** tanto en el worktree como corriendo el script desde el checkout principal, donde viven `.venv` y `.venv312`. **Test permanente:** `scripts/test_design_audit.py::CompileTemplatesTests.test_compile_templates_excluye_site_packages`.
- **Propuesta:** excluir las rutas que contengan `site-packages`. Verificación: 199 en los dos lugares.
