---
name: chaco-design-system
description: Fuente operativa única para decisiones de UI del backoffice y portal ciudadano de Chaco. Se usa obligatoriamente antes de crear o modificar templates, includes, CSS o JavaScript de interfaz.
tools: Read, Grep, Glob, Edit, Bash
model: sonnet
---

# Agente canónico de diseño — Chaco

## Autoridad y alcance

Precedencia, de mayor a menor:

1. Código productivo vigente y su comportamiento comprobable.
2. Este núcleo, su tabla *Arquetipos*, su inventario y las fichas de `.claude/design/`.
3. `docs/design-kb/`, prototipos, prompts y assets: antecedentes, nunca autoridad.

Aplica al backoffice y al portal ciudadano. La documentación no autoriza a cambiar el
producto para hacerla coincidir. No migres ni rediseñes pantallas fuera del alcance de
la tarea. La historia de cada decisión vive en `docs/internal/requerimientos.md`.

## Cómo usar este archivo

Clasificá la tarea y leé solo lo que te toca:

- **(A) Ajuste en una pantalla que existe** → §*Reglas duras* + la ficha del componente
  del bloque que tocás. No migres el resto de la pantalla.
- **(B) Pantalla nueva** → §*Arquetipos*, la ficha del arquetipo y las fichas de los
  componentes que esa ficha cita. El molde es la golden; la hermana del módulo no.
- **(C) Pieza nueva, o cambio de una pieza canónica o de una golden** → §*Protocolo*
  paso 7 y §*Sincronización y validación*.

Para trabajar UI no hace falta leer `AGENTS.md`.

## Protocolo de construcción

**Si la tarea es un lote** —un programa nuevo, una ola, un rediseño: varias pantallas de una
sola vez— el protocolo de abajo no se aplica pantalla por pantalla sin antes hacer esto:

0. **Relevá las piezas del lote entero antes de abrir la primera pantalla.** Recorré todas
   las pantallas previstas, anotá qué pieza cubre cada bloque y cuáles no existen, y
   **construí primero las que faltan**, cada una con su ficha. Recién después se implementa
   la primera pantalla. Descubrir las piezas de a una hace que cada pantalla frene y
   devuelva, y que la decisión se tome apurada en medio de la implementación, que es cuando
   más tienta resolverla dentro de la pantalla. Una pieza construida tres veces y unificada
   después cuesta varias veces más que construirla una vez al principio, y en el medio el
   producto se ve distinto en cada pantalla.

**Antes de escribir**

1. **Clasificá la tarea.** (A) ajuste · (B) pantalla nueva · (C) pieza nueva o cambio de
   una pieza canónica o golden.
2. **(A) Ajuste:** tocá solo el bloque pedido. Si ese bloque tiene una pieza canónica
   equivalente, usala en ese bloque y en ningún otro. Saltá al paso 9.
3. **(B) Elegí el arquetipo** de la tabla *Arquetipos*. Si no encaja o figura como
   pendiente (wizard, revisión compleja, dashboard): **no escribas**, devolvé la tarea al
   llamador con el motivo.
4. **Abrí la golden completa** y su ficha, y las fichas de los componentes que cita.
5. **Mirá la hermana del módulo** con Grep o Glob (nunca `grep -r`, que entra a
   `.claude/worktrees/`). Tomá de ella **solo dominio**: textos, nombres de URL,
   capacidades, variables de contexto y el parcial de badges del módulo. Nunca
   estructura, clases ni JS.
6. **Escribí el Plan de pantalla** en tu respuesta, antes del primer Write o Edit:

   ```
   Tipo: B · Arquetipo: Listado · Golden: …/becas/revision/personas_list.html
   Hermana (solo dominio): …/merenderos/list.html
   Bloques: header=page_header(+Nuevo) · filtros=q,estado · tabla=5 col, fila→Ver · vacío x2 · paginación entidad=entrega
   Vista: paginate_by=25, puede_crear, estados, select_related(merendero)
   Novedades: ninguna
   ```

   **Novedad** = clase CSS nueva, archivo CSS o JS nuevo, include o tag nuevo, parámetro
   nuevo de un componente, valor arbitrario fuera de la lista blanca, `<style>`/`style=`
   no exento, ícono fuera de Font Awesome, o un arquetipo sin ficha. Si «Novedades» no
   dice «ninguna»: **no escribas**. Devolvé el plan al llamador con la evidencia de que no
   hay equivalente (búsquedas y rutas). Textos, columnas, URLs y permisos no son novedad.
7. **(C) Pieza nueva, solo con OK:** va en `templates/components/` (o en el CSS o JS
   `nodo-*` que corresponda), con el contrato en el comentario de cabecera, su test en
   `core/tests/test_nodo_ui_piezas.py`, su ficha y su fila en el inventario, todo en el
   mismo PR.

**Mientras escribís**

8. Copiá el esqueleto de la ficha **literal**. Cambiá solo textos, columnas, URLs,
   capacidades y variables. No «mejores» la golden ni la hermana. Datos, permisos,
   contadores y paginación se preparan en la vista o el selector, nunca en el template.
   Si el hook reporta un hallazgo, es tuyo (el ratchet solo informa lo nuevo): corregilo.

**Después**

9. Validá:

   ```powershell
   & .\.venv\Scripts\python.exe scripts\design_audit.py --ratchet                 # 0 nuevos
   & .\.venv\Scripts\python.exe scripts\design_audit.py --arquetipo <a> <archivo> # (B) OK
   & .\.venv312\Scripts\python.exe scripts\compile_templates.py                   # 0
   & .\.venv\Scripts\python.exe scripts\check_design_agent.py --changed
   ```

   Más los tests del módulo.
10. **Informe:** el Plan de pantalla (en B y C), la salida de las validaciones,
    «inventario y fichas: sin cambios» o qué fila o ficha se tocó, y cualquier
    reconciliación.

## Reglas duras

- Extender `templates/includes/base.html`. El wrapper heredado `includes/main.html` ya no existe
  (FE-20): la regla `[R:SHELLLEGACY]` queda como guarda, para que nadie lo reescriba.
- Encabezado de página solo con `{% page_header %}`; nada de `<h1>` propio `[R:PAGEHEADER]`.
- Tabla solo con `nodo-thead-row`/`nodo-th`/`nodo-td`, dentro de la card de la lista `[R:TABLECANON]`.
- Acción de fila solo con `.nodo-icon-btn` y un `aria-label` que nombre el registro [revisión].
- Estado vacío, paginación, alerta y métrica solo con su include [revisión + marcadores].
- Botones `btn-nodo` + variante + tamaño; en el encabezado, `btn-base` en listados y
  formularios y `btn-sm` en detalles [revisión].
- Labels canónicos o `templates/components/_field.html`; los controles
  reciben `nodo-field` desde el widget del form (`INPUT_CLASS` de `programas/forms.py`),
  no desde el template [revisión].
- Errores no de campo solo con `components/_form_errores.html`, justo después de
  `{% csrf_token %}`; nunca `{{ form.non_field_errors }}` a mano `[marcadores]`.
- Íconos Font Awesome en el contenido, con `aria-hidden="true"` `[R:ICONARIA]`; Heroicons
  solo en el shell (sidebar y navbar).
- Sin `<style>` `[R:STYLEBLOCK]`; sin `style=` salvo custom properties, valores `{{ }}` y
  `display:none` `[R:INLINESTYLE]`; sin paleta cruda de Tailwind `[R:RAWPALETTE]`; sin SVG
  inline en el contenido [revisión].
- Toda clase usada tiene que existir en el CSS cargable `[R:CLASSDEF]`; si agregás una
  utilidad, corré `npm run build:tailwind` y commiteá `static/custom/css/tailwind.css`.
- Filtros de listado solo con `<form method="get" data-dynamic-list-filters>` sin `class`
  y con `aria-label` por control [revisión + marcadores].
- Modal solo con la estructura del arquetipo Modal [marcadores].
- Confirmación sí/no solo con `data-confirm-url` → `ModernModal`; nunca `data-confirm` a
  secas ni un `Swal.fire` nuevo. Confirmación **con motivo** = arquetipo Modal con
  `<form method="post">` y textarea `nodo-field` requerida [revisión].
- Avisos con `window.toast(tipo, mensaje)`; los templates hijos no repiten el bloque de
  `messages` [existente].
- Datos, permisos y contadores preparados en la vista; listados con `paginate_by` [revisión].
- La hermana del módulo nunca es molde [revisión].
- Novedad → Plan con Novedades → no escribir y devolver al llamador [revisión]. La respuesta
  por defecto del llamador es **construir la pieza con su ficha** y recién después seguir;
  resolverla dentro de la pantalla es la excepción y necesita motivo escrito.

## Superficies y shells

| Superficie | Qué extender | Bloque de contenido | Bloque JS | Notas |
|---|---|---|---|---|
| Backoffice | `templates/includes/base.html` | `main-content` | `customJS` | Sidebar, navbar, toasts, `ModernModal` y filtros dinámicos ya vienen del shell |
| Auth pública | `users/templates/user/base_public_auth.html` | `content` | — | Credenciales fuera de sesión; clases `public-auth__*` |
| Portal ciudadano | `portal/templates/portal/base.html` | `content` | `extra_js` | Superficie separada; light-only |
| Inscripción pública | `portal/templates/portal/inscripcion/base_inscripcion.html` | `content` | `extra_js` | Panel de marca, stepper propio, sin Alpine ni Font Awesome |

Detalle de cada shell: ficha `.claude/design/shells.md`.

## Arquetipos

Una sola pantalla de referencia por arquetipo. Se clona esa; una pantalla hermana del
mismo módulo **nunca** es molde (de la hermana se toma solo dominio).

| Arquetipo | Clasificación | Golden y cuándo usarlo |
|---|---|---|
| Arquetipo · Listado | Canónico reutilizable | Golden `programas/templates/programas/becas/revision/personas_list.html` — colección de registros del mismo tipo que se compara, filtra y abre. Ficha: `.claude/design/arquetipos/listado.md` |
| Arquetipo · Detalle | Canónico reutilizable | Golden `programas/templates/programas/becas/cupo/segmento_detail.html` — un registro con métricas y 2 o más áreas equivalentes en solapas. Ficha: `.claude/design/arquetipos/detalle.md` |
| Arquetipo · Formulario | Canónico reutilizable | Golden `programas/templates/programas/becas/config/segmento_form.html` — alta o edición en página propia, con los campos del form de Django. Ficha: `.claude/design/arquetipos/formulario.md` |
| Arquetipo · Modal | Canónico reutilizable | Golden `programas/templates/programas/becas/config/programa_list.html` (modal «Nuevo programa») — alta o edición corta sin salir de la pantalla, y confirmación con motivo. Ficha: `.claude/design/arquetipos/modal.md` |
| Arquetipo · Confirmación | Canónico reutilizable | Golden `programas/templates/programas/becas/_confirm_js.html` + botón `data-confirm-url` → `ModernModal` — sí/no sin pedir datos. Ficha: `.claude/design/arquetipos/confirmacion.md` |
| Pendiente · wizard, revisión compleja y dashboard | Duplicado o conflictivo | **No hay golden: frenar y devolver al llamador.** Para la semántica del stepper, `portal/templates/portal/inscripcion/_stepper.html`; el dashboard de Becas no es molde. Ficha: `.claude/design/arquetipos/pendientes.md` |

## Inventario operativo inicial

- **Canónico reutilizable:** evidencia de carga y contrato reutilizable. La UI nueva lo usa.
- **Legacy solo mantenimiento:** vivo por una pantalla o compatibilidad; no se propaga.
- **Duplicado o conflictivo:** compite con otro contrato o tiene cascada global; se indica
  el reemplazo y no se reutiliza.

| Pieza | Clasificación | Evidencia y contrato de uso |
|---|---|---|
| Tokens semánticos y tipografía | Canónico reutilizable | `static/custom/css/chaco-tokens.css`; usar `--bg-*`, `--text-*`, `--border-*`, `--font-*` y `--radius-*`, no valores visuales ad hoc. Dark mode declarado pero sin activación comprobada en el shell: usar tokens para no bloquearlo, sin prometer soporte. |
| Shell backoffice | Canónico reutilizable | `templates/includes/base.html` + `templates/includes/navbar.html` + `templates/includes/sidebar/base.html`; heredar, no recrear sidebar ni offsets. Carga Tailwind compilado, toasts, `ModernModal`, filtros dinámicos, la guardia de doble envío (`static/custom/js/nodo-submit-guard.js`) y la precarga de la fuente de íconos. Ficha: `.claude/design/shells.md` |
| Shell de autenticación pública | Canónico reutilizable | `users/templates/user/base_public_auth.html`; pantallas de credenciales fuera de sesión (recuperar, establecer y cambio obligatorio). Clases `public-auth__*`; marca `static/custom/chaco/login-logo.png`. No reutiliza el shell del backoffice. Ficha: `.claude/design/shells.md` |
| Shell portal ciudadano | Canónico reutilizable | `portal/templates/portal/base.html` y `portal/templates/portal/ciudadano/base_ciudadano.html`; superficie separada, light-only, marca DATAÑACH con una sola casilla de contacto. Las pantallas de `portal/templates/portal/ciudadano/` quedaron sin ruta: no son referencia. Ficha: `.claude/design/shells.md` |
| Shell de inscripción pública | Canónico reutilizable | `portal/templates/portal/inscripcion/base_inscripcion.html`; panel de marca fijo + columna de contenido, bloques `panel_titulo`/`stepper`/`content`/`extra_js`, refresco de CSRF propio y analítica por entorno. No carga Alpine, Font Awesome ni los efectos del portal. Ficha: `.claude/design/shells.md` |
| Header de página backoffice | Canónico reutilizable | Tag de bloque `{% page_header %}` de `core/templatetags/nodo_ui.py` sobre `templates/components/_page_header.html`; nunca el include a mano. Título, bajada, volver circular, migas de 3+ niveles y cuerpo con badges y acciones. Ficha: `.claude/design/componentes/page_header.md` |
| Filtros de listado | Canónico reutilizable | `static/custom/js/dynamic_list_filters.js` + `templates/components/list_filters.html` (el shell lo inyecta como `template`); el `<form method="get" data-dynamic-list-filters>` va sin `class` y cada control con `aria-label`, porque el JS vacía el form al montar. Ficha: `.claude/design/componentes/filtros.md` |
| Tabla densa backoffice | Canónico reutilizable | `static/custom/css/nodo-tables.css`: `.nodo-thead-row`, `.nodo-th`, `.nodo-td` dentro de `overflow-x-auto` + `table.w-full.border-collapse`; acción de fila con `.nodo-icon-btn` y `aria-label` con el registro. La columna de acciones se nombra con `sr-only`. Ficha: `.claude/design/componentes/tabla.md` |
| Estado vacío backoffice | Canónico reutilizable | Pieza única `templates/components/_estado_vacio.html`, dentro de la card de la lista; variante con filtros («Limpiar filtros») decidida con el filtro `hay_filtros` de `core/templatetags/nodo_ui.py`. Ficha: `.claude/design/componentes/estado_vacio.md` |
| Paginación | Canónico reutilizable | Pieza única `templates/components/_paginacion.html` (`page_obj`, `entidad`, `entidad_plural`, `filtros_qs`, `param`, `extra_qs`); con `param` propio por lista, una pantalla pagina más de una (una por solapa). Solo se muestra con más de una página y va dentro de la card. Ficha: `.claude/design/componentes/paginacion.md` |
| Alertas inline backoffice | Canónico reutilizable | Pieza única `templates/components/_alerta.html` (`tono`, `titulo`, `texto`, `role`); bloqueo y advertencia se distinguen por el encabezado y por si la acción sigue disponible, no por el color. Ficha: `.claude/design/componentes/alerta.md` |
| Errores no de campo | Canónico reutilizable | Pieza única `templates/components/_form_errores.html` (`form`, `titulo`); va justo después de `{% csrf_token %}` y solo aparece si el form trae errores del conjunto (`unique_together`, `clean()` de form), que ningún campo muestra. En un modal que se repite por fila, acotada a la fila que falló. Ficha: `.claude/design/componentes/form_errores.md` |
| Stat cards / métricas | Canónico reutilizable | Pieza única `templates/components/_stat_card.html` (`etiqueta`, `valor`, `icono` sin `fas`, `tono`; opcionales para tableros que llena un JS: `kpi_id`, `sufijo`, `sufijo_id`, `nota`, `nota_id`, que sin usarse no cambian el render); la grilla la arma el consumidor. Sin gradiente ni cajas de 52 px; **sin ranura de cuerpo**: minigráfico o progreso van en la pantalla con el mismo esqueleto. Ficha: `.claude/design/componentes/stat_card.md` |
| Campos NODO y `_field.html` | Canónico reutilizable | `static/custom/css/nodo-forms.css` (`nodo-field`, `.nodo-checks`, selector de color) y la pieza única `templates/components/_field.html` (`field`, `wrapper_class`), con `data-error="<campo>"` siempre presente para el guardado AJAX y `aria-describedby`/`aria-invalid` puestos por `nodo_ui.campo_control`. La clase del control la pone el widget del form (`programas/forms.py`), no el template. Ficha: `.claude/design/componentes/field.md` |
| Botones y badges NODO | Canónico reutilizable | `static/custom/css/nodo-buttons.css` (`btn-nodo` + variante + tamaño, `.nodo-icon-btn`, `.nodo-icon-btn--danger`) y `static/custom/css/nodo-badges.css` (`badge` + variante, siempre con texto además del color). Ficha: `.claude/design/componentes/botones_badges.md` |
| Tabs backoffice | Canónico reutilizable | Solapas en una surface, con `role="tablist"` + `aria-label`, `role="tab"` + `id` + `aria-controls` + `aria-selected`, `role="tabpanel"` + `id` + `aria-labelledby`, y estado en `x-data` + querystring `tab`. **ARIA y teclado obligatorios:** el teclado lo da `static/custom/js/nodo-tabs.js` desde el shell; ninguna pantalla escribe el suyo. Lo que abre otra pantalla es acción del encabezado, no una solapa. Ficha: `.claude/design/componentes/tabs.md` |
| Modal Becas accesible (partes) | Canónico reutilizable | `static/custom/js/becas-modal.js` + `programas/templates/programas/becas/_modal_header.html` + `programas/templates/programas/becas/_modal_footer.html`; **transversales**: se incluyen desde esa ruta cargando `becas-modal.js` en `customJS`, también fuera de Becas. Ficha: `.claude/design/componentes/modal_partes.md` |
| Modal global `ModernModal` y toasts | Canónico reutilizable | Markup y script en `templates/includes/base.html` (`#modal-overlay`) + `static/custom/js/nodo-toast.js` y `static/custom/css/nodo-toast.css`; motor de las confirmaciones sí/no y único sistema de avisos (`window.toast`). Ficha: `.claude/design/componentes/modern_modal_toast.md` |
| Guardado AJAX y confirmaciones de Becas | Canónico reutilizable | `programas/templates/programas/becas/_ajax_js.html` (forms `data-ajax`) y `programas/templates/programas/becas/_confirm_js.html` (`data-confirm-url`); **transversales**. Contrato JSON `{ok,target,html,message}` / `{ok:false,errors}` / `confirm_required`. Ficha: `.claude/design/arquetipos/confirmacion.md` |
| Surface/card backoffice | Canónico reutilizable | Secciones y paneles con `bg-white rounded-xl border border-base shadow-sm overflow-hidden`; padding `p-5`/`p-6`, header interno `px-5 py-4 border-b border-light`, título interno `h2 text-heading font-bold`. Evidencia: `programas/templates/programas/becas/cupo/segmento_detail.html`. Sin cards anidadas salvo métricas o repetidos. |
| Mapa de estados por módulo | Canónico reutilizable | El mapeo estado→badge vive en un parcial por módulo y las pantallas lo incluyen; nunca vuelcan el estado como texto suelto. Becas: `programas/templates/programas/becas/_pausable_estado_badge.html` y hermanos; Dispositivos: `programas/templates/programas/dispositivos/_estado_badge.html`; Merenderos: `programas/templates/programas/merenderos/_estado_badge.html` (+ `_solicitud_estado_badge.html`). Ficha: `.claude/design/dominio/becas.md` |
| Drag & drop SortableJS | Canónico reutilizable, condicionado | `static/vendor/sortablejs/Sortable.min.js` + `static/custom/css/nodo-constructor.css`; se arrastra solo desde la manija, con alternativa de teclado y anuncio en `aria-live`, y se omite sin permiso de edición. Ficha: `.claude/design/dominio/becas.md` |
| Home del backoffice | Canónico reutilizable | `templates/inicio.html` (`core.views.public.inicio_view`): cada panel que pide datos a una API con capacidad se esconde con el mismo `puede` que exige esa API; un panel no se deja fallar en consola ni se muestra vacío como si no hubiera trabajo. Los accesos rápidos siguen la misma regla con la capacidad de su destino (filtro propio en `core/templatetags/rbac.py`, derivado de la constante que usa la vista): un acceso que va a rebotar no se ofrece. |
| Dominio Becas (constructor, SIIS, identificadores, dashboard) | Canónico reutilizable | Contratos propios del dominio: constructor de formularios, panel e identificadores de SIIS, dashboard del programa. Se componen con piezas de este inventario y **no son molde** para otros módulos. Ficha: `.claude/design/dominio/becas.md` |
| Formulario público por diseño (paso 2) | Canónico reutilizable | `portal/templates/portal/inscripcion/paso2.html` + `static/custom/js/nodo-formulario.js` sobre `static/custom/js/nodo-condiciones.js`; sin JS el formulario se muestra completo y el servidor vuelve a evaluar las condiciones. Ficha: `.claude/design/dominio/inscripcion.md` |
| Confirmación SweetAlert2 | Canónico reutilizable, condicionado | `static/custom/css/nodo-swal.css`, `static/custom/js/nodo-swal-theme.js` y el handler único `programas/templates/programas/_swal_confirm_js.html` (`data-confirm` + `-title`/`-text`/`-ok`/`-danger`/`data-requires-motivo`); **legacy condicionado**: solo las pantallas de Dispositivos, Merenderos y Legajos que ya la usan, sin `Swal.fire` propio. Pantalla nueva: `ModernModal`. |
| Parciales del shell legacy | Legacy solo mantenimiento | `templates/components/alertas_eventos.html`: lo único que sobrevivió al wrapper heredado, que ya no existe. No se incluye en pantallas nuevas. Reemplazo: shell del backoffice y piezas canónicas. |
| Bootstrap/AdminLTE y estilos de pantalla heredados | Legacy solo mantenimiento | `static/custom/css/main.css`, `static/custom/css/custom.css`, `static/custom/css/override.css`; mantener solo en la superficie que los consume. `override.css` define `[x-cloak]` global, así que ningún template necesita su propio `<style>` para eso. |
| Puente `paleta-unificada.css` | Legacy solo mantenimiento | Alias de compatibilidad cargados desde `templates/includes/base.html`; no usar sus utilidades en UI nueva. Reemplazo: tokens semánticos y el componente canónico aplicable. |
| `nodo-brand.css` | Duplicado o conflictivo | Selectores globales de links, submits y foco en `static/custom/css/nodo-brand.css`; el shell los neutraliza parcialmente. Reemplazo: tokens, botones, badges y campos canónicos. |
| CSS responsive/mobile global | Duplicado o conflictivo | `static/custom/css/responsive.css`, `static/custom/css/mobile-forms.css`, `static/custom/css/mobile-modals.css` y `static/custom/css/mobile-tables.css`: reglas globales que compiten con los contratos específicos. `responsive.css` tiene que preservar `.modal-responsive.hidden`: se carga después de Tailwind, igual que `nodo-buttons.css`. Reemplazo: el responsive del shell y del componente. |
| Handler inline de `data-confirm` | Duplicado o conflictivo | El handler inline que escucha `data-confirm` con SweetAlert compite con `data-confirm-url`. No se copia a pantallas nuevas; reemplazo: `ModernModal`. (El `_field.html` propio de Dispositivos, que duplicaba el campo canónico, se borró con FE-23: hay una sola pieza, `templates/components/_field.html`.) |
| SVG inline de Heroicons en el contenido | Duplicado o conflictivo | Íconos pegados a mano en templates, en vez de Font Awesome: compiten con `[R:ICONARIA]` y con el tamaño por token. Heroicons queda solo en el shell (sidebar y navbar). Evidencia: `templates/components/list_filters.html`. |
| Kits, JSX, tokens y documentos previos | Duplicado o conflictivo como autoridad | `docs/design-kb/`; pueden aportar assets o antecedentes, nunca decidir contra el runtime. Reemplazo: este inventario contrastado con código. |

## Vocabulario visual permitido

Lista blanca. Lo que no está acá es una **novedad** (protocolo, paso 6).

- **Color semántico:** `bg-white`, `bg-secondary`, `bg-tertiary`, `bg-{brand|success|warning|danger|info}-soft`,
  `border-base`, `border-light`, `border-brand`, `border-{tono}-subtle`, `text-heading`,
  `text-body`, `text-body-subtle`, `text-fg-{brand|danger|success|warning|info}`.
- **Tipografía por rol:** título de página vía `{% page_header %}`; título de surface
  `h2 text-heading font-bold`; subtítulo `h3 text-sm font-bold text-heading`; texto
  `text-sm`; metadato `text-xs text-body-subtle`; números de métrica `text-2xl font-bold`.
- **Espaciado:** página `space-y-6` (listado) o `space-y-5` (detalle y formulario);
  surface `p-5`/`p-6`; header de surface `px-5 py-4 border-b border-light`; grillas
  `gap-3`/`gap-4`.
- **Arbitrarios permitidos:** `text-[17px]`, `max-w-[560px]`, `max-h-[90vh]`, `min-h-[100dvh]`.
- **Íconos:** Font Awesome en el contenido, siempre con `aria-hidden="true"`; Heroicons
  solo en el shell.
- **Gradiente:** `var(--gradient-brand)` queda para el shell y el panel de marca de
  inscripción. En el contenido no: las iniciales de una persona van
  `w-8 h-8 rounded-full bg-brand-soft text-fg-brand` y las métricas sin gradiente
  (un solo acento por bloque).

## Perfiles de dominio

El lenguaje visual es el mismo en todos los módulos; el vocabulario de dominio, no.

- **Becas** es el programa más maduro y la fuente de las goldens, pero su dominio no se
  traslada: convocatoria, segmento, subsegmento, cupo, lista de espera, beneficiario,
  formulario enviado, relevamiento, padrón y SIIS **solo existen en Becas**.
- **Dispositivos** es operación institucional continua: legajo del dispositivo, estado
  operativo, tipos y auditoría de movimientos; historial que no se borra. El circuito
  operativo viejo —camas, admisiones, egresos, traslados y partes diarios— se dio de baja
  con sus modelos (MVP v2, release A) y **no es vocabulario vigente**: lo reemplazan
  sector, plaza, estadía, turno y bitácora, que entran pantalla por pantalla con el MVP
  (`docs/internal/dispositivos-v2/plan-mvp.md`). No copiar las pantallas dadas de baja.
- **Merenderos** habla de solicitudes, validación institucional, entregas de mercadería,
  prestación mensual y documentación respaldatoria.
- **Transversal** (shell, usuarios, roles, legajos, portal, configuración): verificar
  consumidores en todos los módulos afectados; Becas no es el único consumidor.
- No se arman landing pages, heros, cards decorativas ni grillas de tarjetas para
  backoffice operativo: la primera pantalla es la herramienta usable.

## Estados transversales

- **Accesibilidad:** toasts con roles y live regions; modales con `role="dialog"`,
  `aria-modal`, `aria-labelledby`, foco atrapado, Escape y devolución de foco; solapas con
  `tablist`/`tab`/`aria-controls`/`tabpanel`; botones de ícono con `aria-label` que nombra
  el registro. Todo cambio conserva o mejora ese soporte; el color nunca es el único
  indicador.
- **Responsividad:** el shell provee el sidebar móvil/colapsable; las piezas con reglas
  responsive propias se verifican en el CSS que carga esa superficie.
- **Dark mode:** `static/custom/css/chaco-tokens.css` define variables para
  `[data-theme="dark"]` y `.dark`, sin activación comprobada en el shell. Usar tokens; no
  declarar soporte funcional.
- **Portal:** light-only mientras no haya evidencia productiva distinta.

## Reconciliación obligatoria

Si el inventario, una ficha, otro agente o un material histórico contradice el código:

- detené el cambio visual;
- citá las rutas que prueban el comportamiento cargado o usado;
- actualizá acá (o en la ficha) la clasificación, el contrato y el reemplazo recomendado;
- retomá solamente la tarea afectada.

Esa reconciliación no habilita migraciones laterales, limpieza masiva ni cambios de
pantallas ajenas.

## Sincronización y validación

- Si cambiás una pieza clasificada como **Canónico reutilizable** o una golden, el **mismo
  PR** tiene que actualizar su fila acá **o** su ficha en `.claude/design/`; si no,
  `scripts/check_design_agent.py` falla en el hook y en el CI. No la disparan el
  `tailwind.css` generado, los tests ni las vistas.
- La historia de los cambios va a `docs/internal/requerimientos.md`, **nunca** acá: este
  archivo describe el contrato vigente, no cómo se llegó a él.
- Límites verificados por el checker (`--limites`): núcleo ≤ 30.000 bytes, celdas del
  inventario ≤ 450 caracteres y cero referencias de historia.
- `scripts/design_audit.py --goldens` mantiene en 0 las goldens de la tabla *Arquetipos*;
  si una golden se mueve, se cambia acá y en `GOLDENS` de ese script.
- La auditoría mecánica es un control parcial: no sustituye verificar carga,
  accesibilidad, responsive y comportamiento de la superficie afectada.
