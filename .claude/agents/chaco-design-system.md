---
name: chaco-design-system
description: Fuente operativa única para decisiones de UI del backoffice y portal ciudadano de Chaco. Se usa obligatoriamente antes de crear o modificar templates, includes, CSS o JavaScript de interfaz.
tools: Read, Grep, Glob, Edit, Bash
model: sonnet
---

# Agente canónico de diseño — Chaco

## Autoridad y alcance

Este archivo es la única fuente de verdad **operativa** de diseño. No reemplaza al
producto: ante cualquier diferencia, el orden de precedencia es:

1. Código productivo vigente y su comportamiento comprobable.
2. Este agente y su inventario, actualizados con evidencia del código.
3. `docs/design-kb/`, prototipos, prompts y assets, únicamente como referencia.

Aplica al backoffice y al portal ciudadano. La documentación no autoriza a cambiar
el producto para hacerla coincidir; si discrepa, se corrige esta clasificación con
evidencia. No migres ni rediseñes pantallas fuera del alcance de la tarea.

## Procedimiento obligatorio antes de editar UI

1. Leé `AGENTS.md` y este archivo.
2. Ubicá la ruta, el template final, su `{% extends %}` y los includes compartidos.
3. Identificá CSS y JavaScript que el shell realmente carga, además de los usos de
   las clases o APIs involucradas.
4. Consultá el inventario. La UI nueva reutiliza exclusivamente piezas clasificadas
   como **Canónico reutilizable**.
5. Si no existe una pieza canónica, demostralo con rutas y búsqueda, creá el patrón
   reutilizable más pequeño necesario dentro del alcance y agregalo al inventario
   en el mismo PR.

### Reconciliación obligatoria

Si el inventario, otro agente o un material histórico contradice el código:

- detené el cambio visual;
- citá las rutas que prueban el comportamiento cargado o usado;
- actualizá aquí la clasificación, contrato y reemplazo recomendado;
- retomá solamente la tarea afectada.

Esa reconciliación no habilita migraciones laterales, limpieza masiva ni cambios de
pantallas ajenas.

## Clasificación

- **Canónico reutilizable:** tiene evidencia de carga y contrato reutilizable en el
  producto. La UI nueva puede usarlo.
- **Legacy solo mantenimiento:** sigue vivo por una pantalla o compatibilidad. Solo
  se conserva o corrige al mantener esa superficie; no se propaga.
- **Duplicado o conflictivo:** compite con otro contrato, tiene cascada global o es
  documentación/prototipo no verificado. No se reutiliza; se indica el reemplazo.

## Inventario operativo inicial

| Pieza | Clasificación | Evidencia y contrato de uso |
|---|---|---|
| Tokens semánticos y tipografía | Canónico reutilizable | `static/custom/css/chaco-tokens.css`; usar `--bg-*`, `--text-*`, `--border-*` y `--font-*`, no valores visuales ad hoc. |
| Shell backoffice | Canónico reutilizable | `templates/includes/base.html`, `templates/includes/navbar.html`, `templates/includes/sidebar/base.html`; heredar/incluir, no recrear sidebar ni offsets. El sidebar es un único panel responsivo: overlay en móvil y fijo/colapsable en escritorio, con una sola inclusión de `includes/sidebar/opciones.html`. Su control de cierre móvil queda fuera del panel y debe usar `x-show="sidebarOpen"` con `display: none` inicial para no interceptar el botón Abrir cuando está fuera de pantalla. Tailwind se sirve desde `static/custom/css/tailwind.css`, generado por `npm run build:tailwind` con `tailwind.config.js`; no usar Play CDN. El WebSocket `conversaciones_lista_ws.js` se carga únicamente en `conversaciones:lista`; en esa ruta, `conversaciones_tiempo_real_global.js` usa HTTP solo como fallback mientras el socket no esté abierto y suspende/cancela el polling en pestañas ocultas. El cierre de sesión del menú de usuario es un `<form method="post">` con `{% csrf_token %}`, no un enlace: `LogoutView` no acepta GET desde Django 5.0. |
| Shell de autenticación pública | Canónico reutilizable | `users/templates/user/base_public_auth.html`; lo extienden `establecer_contrasena.html`, `recuperar_contrasena.html`, `recuperar_contrasena_enviada.html` y `cambiar_contrasena_obligatorio.html`. Contrato: clases `public-auth__title`, `__help`, `__field`, `__error`, `__button` y `__link`, con `button.public-auth__link` para la misma apariencia cuando la acción tiene que ir por formulario; la marca web usa `static/custom/chaco/login-logo.png` —330×120, el logo del Gobierno del Chaco— y el CSS compilado `tailwind.css`. `static/custom/icore/nodo-logo.svg` es la marca de ICore y no se usa en superficies del organismo. Es el shell de las pantallas de credenciales fuera de sesión; no reutiliza el shell del backoffice. |
| Shell portal ciudadano | Canónico reutilizable | `portal/templates/portal/base.html`, `portal/templates/portal/ciudadano/base_ciudadano.html`; superficie separada del backoffice y consumidora de `static/custom/css/tailwind.css` compilado. Contrato de marca (Cambio 42): título del navegador «DATAÑACH — Portal Ciudadano», header «DATAÑACH» + «Portal Ciudadano · Gobierno del Chaco», footer con la misma marca, copyright con año dinámico (`{% now "Y" %}`) y datos de contacto únicos **+54 362 430-0002** / **datanach@chaco.gob.ar** (se repiten en header, footer y en las pantallas de inscripción pública: cambiarlos en todos a la vez). No usa la sub-marca «Ñandé» ni «Portal Nande». La home (`portal/templates/portal/home.html`) toma su contexto de `portal.selectors.public.get_portal_home_context`, cacheado 5 min (`portal:home_ctx`). No lo extienden las pantallas de inscripción pública: usan el shell propio de abajo para no cargar `portal-effects.js`. |
| Shell de inscripción pública | Canónico reutilizable | `portal/templates/portal/inscripcion/base_inscripcion.html`; layout Opción B «Panel de marca» — grid `var(--di-panel-w) minmax(0,1fr)` desde 1024px (el ancho del panel se declara una sola vez en `.di-shell`: 520px) con panel `var(--gradient-brand)` a la izquierda y columna de contenido blanca a la derecha. **En escritorio el panel es fijo**: `.di-panel-head` va `position: fixed; top: 0; height: 100vh` y `.di-panel-foot` `position: fixed; bottom: 0`, las dos con `width: var(--di-panel-w)`; por largo que sea el formulario solo scrollea la columna de contenido, y la primera columna del grid queda vacía porque sus dos piezas salen del flujo (la mantiene el track explícito). La cabecera lleva `overflow-y: auto` y `padding-bottom: 136px` —alto del pie (112px) más aire— para que en ventanas muy bajas su contenido siga alcanzable en lugar de quedar tapado por el pie. En celular el panel vuelve al flujo como cabecera compacta y el pie con ayuda/copyright se recoloca debajo del contenido (mismo HTML, solo `grid-template-areas` por media query). El pie del panel en escritorio va sobre `var(--bg-navy)` sólido (no sobre el gradiente) para el contraste del texto blanco; el cuerpo del panel conserva el gradiente. Bloques: `title`, `panel_titulo` (etiqueta + `<h1>` + bajada, con fallback si no hay `convocatoria` en contexto), `stepper` (vacío por defecto — cada página lo completa con `{% include "portal/inscripcion/_stepper.html" with paso_activo=1 %}`, 1/2/3 según el paso; las pantallas de resultado lo dejan vacío), `content` y `extra_js`. El include `_stepper.html` no distingue el paso activo solo por color (WCAG 1.4.1): el `<li>` correspondiente lleva `aria-current="step"` (con `data-step` conservado solo para el CSS del círculo, vía `[aria-current="step"] .di-step__circle`) y un `<span class="sr-only">Paso actual: </span>` antes del nombre del paso; `sr-only` es de `static/custom/css/tailwind.css`. No carga `static/custom/js/portal-effects.js`, Alpine, Font Awesome, `nodo-toast` ni el modal de `portal/templates/portal/base.html`; sin `animate-fadeInUp` ni `@keyframes`. **Único JS propio del shell** (inline, sin dependencias): refresca el `csrfmiddlewaretoken` de los formularios contra `{% url "portal:csrf_token" %}` cuando la pestaña vuelve al frente (`visibilitychange`, `focus`, `pageshow` persistido), con throttle de 30 s y salida temprana si la página no tiene formulario; el backoffice y el portal comparten dominio y `login()` rota la cookie CSRF de todo el navegador. Si el pedido falla se manda el token original y el 403 cae en `portal/templates/portal/sesion_vencida.html` (pantalla recuperable del `CSRF_FAILURE_VIEW`, `config.views.csrf_failure`, que extiende este mismo shell con el `panel_titulo` propio y sin stepper). Tokens consumidos: `--gradient-brand`, `--bg-navy`, `--bg-white`, `--text-white`, `--bg-secondary`, `--bg-brand-soft`/`--bg-brand-softer`, `--bg-brand-tint`, `--border-brand-subtle`, `--bg-danger-soft`, `--border-danger-subtle`, `--text-fg-danger`, `--text-fg-brand`, `--text-heading`, `--text-body`, `--text-body-subtle`, `--border-base`, `--font-size-*`, `--font-weight-*`, `--radius-*`; light-only. Lo extienden `portal/templates/portal/inscripcion/paso1.html`, `paso2.html`, `confirmacion.html`, `ya_inscripto.html`, `no_disponible.html`, `demasiados_intentos.html` y `portal/templates/portal/sesion_vencida.html`. |
| Shell público de autenticación | Canónico reutilizable | `users/templates/user/base_public_auth.html`; superficie sin sesión, menú ni alertas internas para recuperación y establecimiento de contraseña. Consumido por `users/templates/user/recuperar_contrasena.html`, `users/templates/user/recuperar_contrasena_enviada.html` y `users/templates/user/establecer_contrasena.html`. |
| Botones NODO | Canónico reutilizable | `static/custom/css/nodo-buttons.css`; reutilizar `btn-nodo` con las variantes y tamaños existentes. |
| Badges NODO | Canónico reutilizable | `static/custom/css/nodo-badges.css`; reutilizar `badge` y sus variantes, siempre con texto además del color. |
| Campos NODO | Canónico reutilizable | `static/custom/css/nodo-forms.css`; usar `nodo-field` en controles que correspondan. |
| Canon visual backoffice derivado de Becas | Canónico reutilizable | Patrones productivos en `programas/templates/programas/becas/config/programa_detail.html`, `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`, `programas/templates/programas/becas/revision/formulario_detalle.html`, `programas/templates/programas/becas/reportes/reporte.html` y `programas/templates/programas/becas/config/_segmentos_table.html`. Es la referencia de estructura, densidad, color y componentes para nuevas pantallas de backoffice, abstraída del dominio Becas. Ver sección "Canon visual backoffice". |
| Header de página backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/programa_detail.html` y `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`: contenedor superior sin card, `flex items-start justify-between gap-4 flex-wrap`, botón volver `btn-tertiary btn-back-circle`, `h1 text-3xl font-extrabold text-heading tracking-tight`, bajada `text-sm text-body-subtle`, acciones y badges a la derecha. |
| Surface/card backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/programa_detail.html` y `programas/templates/programas/becas/revision/formulario_detalle.html`: secciones y paneles con `bg-white rounded-xl border border-base shadow-sm overflow-hidden`; padding interno usual `p-5`/`p-6`, headers internos `px-5 py-4 border-b border-light`, títulos internos `text-heading font-bold` ~16px. No usar cards anidadas salvo métricas o elementos repetidos dentro de un panel funcional. |
| Tabs backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/programa_detail.html`, `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`, `programas/templates/programas/becas/cupo/segmento_detail.html`: tabs dentro de una surface, barra `border-b border-base flex gap-1 px-2 flex-wrap`; item `px-4 py-3 text-sm border-b-2 -mb-px transition flex items-center gap-1.5`; activo `text-fg-brand border-brand font-bold`; inactivo `text-body-subtle border-transparent hover:text-body font-medium`; contadores como `badge`. |
| Tabla densa backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/_segmentos_table.html`, `programas/templates/programas/becas/revision/personas_list.html`, `programas/templates/programas/becas/reportes/reporte.html`: wrapper `overflow-x-auto`, tabla `w-full border-collapse`, header `bg-secondary border-b border-base`, th `px-4 py-[11px] text-left font-bold uppercase tracking-[.05em] text-body-subtle` con 11px, rows `hover:bg-secondary`/`hover:bg-tertiary`, td `px-4 py-[13px] text-sm border-t border-light`, links de entidad `text-fg-brand hover:underline font-medium`, acciones compactas con icono y `aria-label`. |
| Stat cards / métricas backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/relevamientos/convocatoria_detail.html` y `programas/templates/programas/becas/_resumen_ciudadano.html`: grid responsive `grid grid-cols-1 sm:grid-cols-2/lg:grid-cols-* gap-3/4`, card `bg-white rounded-xl border border-base shadow-sm p-4/5`, label `text-xs text-body-subtle font-medium`, valor `text-2xl` o `text-3xl font-bold/extrabold text-heading`, icono en caja `w-8 h-8` o `52px`, `rounded-lg`/`16px`, fondo `bg-brand-soft`, `bg-success-soft`, `bg-warning-soft` o `var(--gradient-brand)` según significado. |
| Estado vacío backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/_segmentos_table.html`, `programas/templates/programas/becas/config/_requisitos_programa_panel.html` y `programas/templates/programas/becas/reportes/reporte.html`: bloque centrado `py-12/14 px-6 text-center flex flex-col items-center gap-3`, icono en `text-fg-brand`, título `text-[17px] font-bold text-heading`, descripción `text-sm text-body max-w-xs`, acción primaria opcional con `btn-nodo btn-brand`. |
| Alertas inline backoffice | Canónico reutilizable | Evidencia en `programas/templates/programas/becas/config/programa_detail.html` y `programas/templates/programas/becas/revision/formulario_detalle.html`: `rounded-lg`/`rounded-xl`, fondo tonal `bg-warning-soft`/`bg-danger-soft`, borde `border-warning-subtle`/`border-danger-subtle`, texto con `text-heading` para título y `text-body`/`text-fg-*` para detalle, `role="alert"` cuando informa bloqueo o error. |
| Toasts NODO | Canónico reutilizable | `templates/includes/base.html`, `static/custom/css/nodo-toast.css`, `static/custom/js/nodo-toast.js`; preservar roles, live regions, persistencia de errores y cierre accesible. |
| Confirmación SweetAlert2 | Canónico reutilizable, condicionado | `static/custom/css/nodo-swal.css` y `static/custom/js/nodo-swal-theme.js`; antes de `Swal.fire`, verificar que la pantalla cargue SweetAlert2. |
| Drag & drop SortableJS | Canónico reutilizable, condicionado | `static/vendor/sortablejs/Sortable.min.js` (1.15.6, MIT, sin CDN por la CSP) + `static/custom/css/nodo-constructor.css` (manija `.grip`, estados `.sortable-ghost`/`.sortable-chosen`, `.is-saving`). Evidencia: catálogo agrupado de requisitos generales (`programas/templates/programas/becas/config/_preguntas_grupos.html` + `static/custom/js/nodo-catalogo-grupos.js`, Cambio 58 #337) y constructor de formularios de la convocatoria. Contrato: se arrastra **solo desde la manija** (`handle`), nunca desde toda la fila; la manija es `<span class="grip"><i class="fas fa-grip-vertical"></i></span>` con `aria-hidden` y se omite cuando el usuario no puede editar (`data-puede-ordenar="0"` ⇒ no se inicializa); cada soltada guarda **en vivo** contra un endpoint JSON que devuelve `{ok, target, html}` (el mismo contrato de `ajax_ok`) y el JS reemplaza el contenedor y se vuelve a enlazar; los huecos vacíos llevan una fila `.sortable-placeholder` (filtrada del arrastre) para que se pueda soltar adentro; sin `confirm()` ni recarga de página. Cargar el vendor en `{% block customJS %}` antes del JS propio. **Gotcha del CSRF**: la cookie se lee con `document.cookie.match('(^|;)\s*' + name + …)` con **doble barra** (o `new RegExp`); con una sola, `\s` es la letra «s» y el token solo se encuentra si `csrftoken` es la primera cookie: el POST del reordenamiento vuelve 403. Hay un test que fija el patrón (`JsCatalogoTests`). |
| Constructor de formularios (diseño + vista previa) | Canónico reutilizable | `programas/templates/programas/becas/formulario/convocatoria_formulario.html` + `_constructor_items.html`, `static/custom/js/nodo-constructor.js`, `static/custom/js/nodo-condiciones.js` (espejo del motor del servidor) y `static/custom/css/nodo-constructor.css` (Cambio 58, tasks 342-344). Patrón: header de página canónico con badge de versión y estado «Guardado en vivo» (`aria-live`); grid `grid-cols-1 xl:grid-cols-2` con dos surfaces —izquierda el diseño (toolbar `btn-secondary`/`btn-brand` en `btn-sm` + contenedor `#constructor-items` sobre `bg-tertiary`), derecha la vista previa `xl:sticky` con toggle de canal (`aria-pressed`)—. Ítems del diseño: `section.cons-grupo` con header `bg-secondary` (manija `.grupo-grip`, badges, acciones icon-button con `aria-label`) y `ul.cons-hijos` de `li.cons-item` (manija `.item-grip`, `.cons-icono` por tipo, badges de alcance/origen/canal/condición). La vista previa se renderiza en JS con clases `.pv-*` y controles `nodo-field`; imita la densidad del paso 2 del portal sin cargar su shell. Modales: el patrón mínimo de Becas (Alpine `x-show` + `data-ajax`), uno por tipo de ítem, y el editor de condiciones (filas fuente / operador / valor con `x-for`). Guardado en vivo: cada mutación responde `{ok, target, html, datos}`; en error el JS restaura el HTML anterior y avisa con `toast`. Las confirmaciones destructivas van por `ModernModal.show` (nunca `confirm()`). La vista previa no promete lo que el paso 2 no hace: DNI y sexo del titular van de solo lectura (vienen del paso 1), el sexo del apoderado se elige con nombre (Femenino/Masculino, valor F/M) y los selectores múltiples se apilan como los rinde Django. |
| Formulario público por diseño (paso 2) | Canónico reutilizable | `portal/templates/portal/inscripcion/paso2.html` + `static/custom/js/nodo-formulario.js` sobre `nodo-condiciones.js` (Cambio 58, task 345). El paso 2 ya no tiene bloques fijos en el template: recorre `form.grupos()` y por cada ítem rinde un `<section data-item="<clave>">` (grupo, con `h2` uppercase 12px y subtítulo `text-xs`), un `<p data-item>` para los párrafos, un par etiqueta+valor cuando el dato ya vino del paso 1, o `label` + control `nodo-field` para lo que se pide. Contrato del JS: cada ítem lleva `data-item` con su clave y los ítems planos viajan en `#formulario-items` (`json_script`); al ocultar, el JS pone `hidden` en el contenedor y `disabled` en sus controles para que no viajen en el POST. **Sin JS el formulario se muestra completo y se envía igual**: el servidor vuelve a evaluar las condiciones y es la autoridad. Mantiene el shell de inscripción, `nodo-buscador` para los selectores con píldoras y los tokens del portal (light-only). |
| Modal global `ModernModal` | Legacy solo mantenimiento | Implementaciones activas en `templates/includes/base.html` y `portal/templates/portal/base.html`; preservar su contrato en pantallas existentes. No hay reemplazo canónico probado: si una tarea exige un modal nuevo, crear el patrón mínimo y registrarlo. |
| Bootstrap/AdminLTE y estilos de pantalla heredados | Legacy solo mantenimiento | `static/custom/css/main.css`, `custom.css`, `override.css`; mantener solamente en la superficie que los consume. Reemplazo para UI nueva: piezas canónicas inventariadas. |
| Puente `paleta-unificada.css` | Legacy solo mantenimiento | Alias de compatibilidad cargados desde `templates/includes/base.html`; no usar sus utilidades en UI nueva. Reemplazo: tokens semánticos y componente canónico aplicable. |
| `nodo-brand.css` | Duplicado o conflictivo | Selectores globales de links, submits y focus en `static/custom/css/nodo-brand.css`; el base los neutraliza parcialmente. Reemplazo: tokens, botones, badges y campos canónicos. |
| CSS responsive/mobile global | Duplicado o conflictivo | `static/custom/css/responsive.css`, `mobile-forms.css`, `mobile-modals.css`, `mobile-tables.css`; sus reglas generales compiten con contratos específicos. En particular, `responsive.css` debe preservar `.modal-responsive.hidden` porque se carga después de Tailwind. Reemplazo: responsive del shell y del componente canónico afectado. |
| Kits, JSX, tokens y documentos previos | Duplicado o conflictivo como autoridad | `docs/design-kb/`; pueden aportar assets o antecedentes, nunca decidir contra el runtime. Reemplazo: este inventario contrastado con código. |

No hay todavía un componente/include único para estos patrones de página. La
canonicidad actual es de **contrato visual productivo**, no de helper técnico: si
una tarea necesita reutilizar mucho una pieza, extraé el include mínimo desde el
patrón de Becas y registralo acá en el mismo cambio. Para modales nuevos sigue sin
haber reemplazo canónico probado: si una tarea exige uno, creá el patrón mínimo y
registralo.

## Canon visual backoffice

Becas es la referencia visual productiva del backoffice. Cuando diseñes una página
nueva de backoffice, copiá su **lógica de composición**, no sus reglas de dominio.
La pantalla nueva tiene que sentirse parte del mismo sistema aunque el programa sea
Dispositivos, Merenderos, Usuarios, Legajos u otro módulo.

### Estructura de página

Usá este esqueleto salvo que la superficie existente tenga un contrato distinto:

1. Contenedor principal con separación vertical moderada: `space-y-5` o `space-y-6`.
2. Header sin card: botón volver circular si es detalle, título grande, bajada corta
   y acciones/badges a la derecha.
3. Alertas inline debajo del header si hay bloqueo, advertencia o estado crítico.
4. Contenido en una surface blanca con tabs si hay 2 o más áreas equivalentes; si no,
   secciones apiladas con cards/surfaces.
5. Dentro de cada tab/sección: introducción breve a la izquierda y acción principal
   a la derecha, luego tabla/formulario/métricas.
6. Cierre con paginación, acciones secundarias o estado vacío según corresponda.

La densidad es de herramienta operativa: mucha información escaneable, poco texto
explicativo, acciones cerca del dato, y jerarquía visual clara.

### Color y tono

- Fondo de superficies: blanco (`bg-white` o `var(--bg-primary)`).
- Bordes: `border-base` para contenedores, `border-light` para divisiones internas.
- Texto: `text-heading` para títulos y datos principales, `text-body` para contenido,
  `text-body-subtle` para ayudas, metadatos y valores secundarios.
- Marca: `text-fg-brand`, `border-brand`, `bg-brand-soft` y `var(--gradient-brand)`.
  Usá el gradiente con moderación: acción primaria, avatar/ícono destacado o un solo
  acento por bloque.
- Estados: success, warning y danger solo por significado funcional. No usar color
  como único indicador: siempre acompañar con texto o icono con label.
- Evitá paletas nuevas por módulo. El programa puede tener dominio distinto, pero el
  lenguaje visual debe seguir siendo Chaco/NODO.

### Componentes y patrones

- **Botones:** siempre `btn-nodo` + variante (`btn-brand`, `btn-secondary`,
  `btn-tertiary`, `btn-danger`) + tamaño (`btn-sm`, `btn-base`, etc.). El botón
  principal de un bloque suele ser `btn-brand`; exportes, filtros, volver o acciones
  auxiliares usan `btn-secondary`/`btn-tertiary`; destrucción o rechazo usa
  `btn-danger`.
- **Iconos:** usar icono + texto en acciones visibles; para acciones compactas en
  tablas usar icon button con `aria-label`, hover `hover:bg-secondary` y color de
  marca o peligro según acción.
- **Badges:** usar `badge` con variante semántica y texto. Para estados principales,
  preferir `badge-dot`.
- **Forms:** labels `text-sm font-medium text-heading mb-1`, requerido con
  `text-fg-danger`, campos `nodo-field` o clases equivalentes con `border-base`,
  `focus:border-brand`, `focus:ring-brand`; errores cerca del campo en
  `text-fg-danger`.
  Cuando el alta tiene `fieldset` condicionados por tipo (`x-show`/`:disabled` con
  Alpine), adentro va **solo** lo que aplica a ese tipo: un control común a todos los
  tipos se ubica fuera del `fieldset`, o queda deshabilitado y sin enviarse para el
  resto. Evidencia en el alta de relevamiento —`convocatoria_detail.html`,
  `relevamiento_list.html` y `relevamiento_form.html`—: el toggle de avisos por correo
  vale para territoriales y públicos y por eso quedó fuera del `fieldset` de tipo
  público, que conserva cupo y padrón.
- **Tables:** preferir tabla densa antes que cards repetidas cuando el usuario compara
  filas. Mantener encabezados uppercase de 11px, celdas de 13-14px y acciones en la
  última columna alineadas a la derecha.
- **Tabs:** usarlas para separar áreas del mismo objeto. Preservar estado vía Alpine
  o querystring si hay paginación/exportes dentro del tab.
- **Métricas:** usar stat cards solo para números o estados de alto valor operativo,
  no como decoración.
- **Empty states:** siempre explicar qué falta y, si corresponde, ofrecer la acción
  primaria para resolverlo.

### Reglas de abstracción

- Si el dominio no es Becas, mantené el layout, densidad, tokens y componentes, pero
  reemplazá la semántica por la del módulo.
- Dispositivos debe verse como Chaco/NODO, pero hablar de operación institucional:
  camas, ocupación, admisiones, egresos, traslados, partes y validaciones.
- Merenderos debe verse como Chaco/NODO, pero hablar de solicitudes, entregas,
  prestación mensual y documentación.
- No crear landing pages para backoffice operativo. La primera pantalla debe ser la
  herramienta usable: listado, detalle, formulario o tablero operacional.
- No introducir un framework visual paralelo, gradientes nuevos, cards decorativas,
  hero sections ni layouts de marketing.

## Estados transversales comprobados

- **Accesibilidad:** los toasts tienen roles/live regions y foco visible; el modal
  global del backoffice tiene `role=dialog`, focus trap, Escape y devolución de
  foco. Todo cambio debe conservar o mejorar ese soporte.
- **Responsividad:** el shell provee sidebar móvil/colapsable; las piezas con reglas
  responsive propias deben verificarse en el CSS que se carga para esa superficie.
- **Dark mode:** `chaco-tokens.css` define variables para `[data-theme="dark"]` y
  `.dark`, pero no hay evidencia actual de activación compartida en el shell. Usá
  tokens semánticos para no bloquearlo, sin declarar soporte funcional hasta que se
  compruebe la activación en código.
- **Portal:** no hay activación dark comprobada; tratarlo como light-only mientras
  no exista evidencia productiva distinta.

## Perfiles de producto por programa

Estos perfiles orientan decisiones de interfaz y revisión. No reemplazan el
inventario operativo ni autorizan a copiar pantallas entre programas sin verificar
el código cargado.

### Becas

Becas es el programa con mayor madurez productiva y sirve como **modelo de calidad**
para otros frentes: trazabilidad de estados, permisos finos, formularios largos,
revisión caso por caso, cupo/lista de espera, validaciones externas, exportes,
paginación y controles de performance.

Usalo como referencia para:

- disciplina de permisos y acciones visibles según rol;
- patrones de revisión y estados con badges textuales;
- paginación de listados grandes y exportes separados de la vista;
- cuidado de N+1, conteos repetidos y querysets sin límite;
- formularios extensos agrupados por bloques verificables;
- cierre técnico con pruebas focalizadas.

No lo uses como molde automático para otros programas: su lógica es de
postulación/relevamiento/cupo. No traslades por defecto conceptos como
convocatoria, segmento, formulario enviado, beneficiario, lista de espera o SIIS a
programas que no los tengan.

### Dispositivos

Dispositivos es una experiencia de **operación institucional continua**. El centro
no es una postulación sino el legajo del dispositivo, su estado operativo, camas,
admisiones, egresos, traslados, partes diarios y auditoría de movimientos.

La UI debe priorizar:

- lectura rápida de ocupación, disponibilidad y estado;
- acciones operativas claras: admitir, egresar, trasladar, parte diario, validar,
  observar, inactivar o cerrar;
- historial permanente, sin borrar registros;
- formularios configurables por tipo de dispositivo;
- tablas y métricas compactas para uso repetido;
- evitar lenguaje o estructura de Becas cuando hable de cupos, convocatorias o
  postulaciones.

### Merenderos

Merenderos es un programa propio, hermano de Dispositivos, enfocado en solicitud,
validación institucional, entregas de mercadería y prestación alimentaria periódica.

La UI debe priorizar:

- legajo institucional y documentación respaldatoria;
- solicitudes y estados de validación;
- registro de entregas;
- prestación mensual con grilla por día/servicio;
- acciones de suspensión/cierre que preserven historial.

### Transversal

Incluye shell, usuarios, roles, legajos, portal, documentación, infraestructura y
soporte. Para cambios transversales, verificá consumidores en todos los programas
afectados y no tomes Becas como único consumidor.

## Sincronización y validación

Cada PR que cree, altere o reclasifique una pieza reutilizable actualiza esta tabla
en el mismo PR, con ruta, contrato, estados y clasificación. En la descripción del
PR, informar el delta de inventario y cualquier reconciliación.

Si se modifican templates, CSS o JavaScript de UI, ejecutar:

```powershell
& .\.venv\Scripts\python.exe scripts\check_design_agent.py --changed
& .\.venv\Scripts\python.exe scripts\design_audit.py <rutas-tocadas>
& .\.venv\Scripts\python.exe scripts\compile_templates.py  # si hubo templates
```

`check_design_agent.py` valida rutas de evidencia, consumidores, autoridad residual y
que una pieza canónica modificada actualice este inventario. La auditoría mecánica es
un control parcial; ninguna de las dos sustituye la verificación de carga,
accesibilidad, responsividad y comportamiento de la superficie afectada.
