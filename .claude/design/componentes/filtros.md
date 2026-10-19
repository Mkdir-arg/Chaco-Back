# Componente · Filtros de listado (`data-dynamic-list-filters`)

**Clasificación:** Canónico reutilizable. Es la pieza transversal más usada del backoffice
(listados de 7 módulos) y la que más dialectos de markup acumuló.
**Evidencia:** `static/custom/js/dynamic_list_filters.js`,
`templates/components/list_filters.html` (el shell lo inyecta como `<template>` desde
`templates/includes/base.html`), `static/custom/css/nodo-forms.css`.
**Consumidor de referencia:** `programas/templates/programas/becas/revision/personas_list.html`.

## Contrato

```django
<form method="get" data-dynamic-list-filters>
  <input type="search" name="q" value="{{ request.GET.q }}" class="nodo-field max-w-xs" aria-label="Buscar">
  <select name="estado" class="nodo-field max-w-xs" aria-label="Estado">
    <option value="">Todos</option>
    {% for value, label in estados %}<option value="{{ value }}" {% if value == estado_actual %}selected{% endif %}>{{ label }}</option>{% endfor %}
  </select>
</form>
```

- El `<form>` va **sin `class`** y sin `style`.
- Cada control lleva `name` y **`aria-label`**.
- Nada de `<label>` suelto, wrapper de card, grilla ni botones «Filtrar»/«Limpiar» propios.

## Por qué (leído del JS)

Al montar, `dynamic_list_filters.js` hace `form.innerHTML = ''`, le pone
`form.className = 'dynamic-list-filters'` y le saca el `style`. Después clona el contenido del
`<template id="nodo-list-filters-template">` que inyecta el shell y reconstruye la barra:
«Agregar filtro», una fila por filtro elegido, el selector de lógica, «Limpiar filtros» y
«Aplicar». Todo lo que el template haya escrito alrededor de los controles **desaparece**: el
label suelto no sobrevive y la clase del form tampoco.

El nombre de cada filtro lo resuelve `labelFor(control)`, en este orden:

1. `aria-label` del control;
2. `label[for=<id>]` dentro del mismo form (sin el `*`);
3. `placeholder`;
4. para un `<select>`, el texto de la primera opción (sin el guion inicial);
5. el `name` con guiones bajos pasados a espacio y la inicial en mayúscula.

Solo mira `input[name]` y `select[name]`, descartando `hidden`, `submit` y `button`; los
`input[type=hidden]` se preservan y se vuelven a agregar al form.

Por eso el `aria-label` tiene que leerse bien **como chip**: «Estado», no «Estado:» ni
«Filtrar por estado».

## Variantes permitidas

- Filtro de texto, select, fecha (`type="date"`) y checkbox, todos dentro del mismo `<form>`.
  La golden los combina: `type="search"` (nombre, apellido, DNI), `type="date"` (fecha de nacimiento) y el `<select>` de estado, cada uno con su `aria-label`.
- `max-w-xs` en el control para que no ocupe todo el ancho antes de que monte el JS.
- Filtros avanzados: `{% include "components/list_filters.html" with advanced=True allow_or=True reset_url=reset_url %}`
  renderiza la barra sin pasar por el `<template>` del shell. Único consumidor:
  `users/templates/user/user_list.html`, que arma el form desde `filters_config` (`json_script`) y por eso
  **sí** lleva `id`, `action` y `class="dynamic-list-filters"`: es la excepción, no el contrato.
  Su columna de acciones, además, es **condicional por fila** (`user.gestionable`,
  `user.credenciales_editables` y `user.tiene_token_app`, anotadas en lote por la vista): el lápiz
  y el interruptor no se dibujan sobre una cuenta que el servidor va a rechazar, y en su lugar va
  «Fuera de tu alcance» en `text-xs text-body-subtle` (R0b-10) —en las **dos** ramas sin acción
  posible: la cuenta fuera de alcance y la gestionable con credenciales ajenas—. La tercera acción
  es «Cerrar sesión de la app» (`nodo-icon-btn` con `fa-mobile-screen`), que solo aparece sobre
  quien tiene un token de la app de campo y confirma con el modal estándar de SweetAlert2 avisando
  que lo no sincronizado queda trabado en el teléfono (SEC-26). Es alcance, no estilo: no se copia
  como patrón de listado salvo que la pantalla tenga la misma asimetría.
- Sin filtros: se omite el `<form>` entero (las tres listas de geografía).
- Consumidores del contrato simple fuera de Becas: `users/templates/rol/rol_list.html`,
  `configuracion/templates/configuracion/secretaria_list.html`,
  `configuracion/templates/configuracion/subsecretaria_list.html`,
  `configuracion/templates/configuracion/programa_list.html` y
  `legajos/templates/legajos/ciudadano_list.html` (un `input[type=search]` con `aria-label`).
  En `rol_list.html` y `configuracion/templates/configuracion/programa_list.html` las acciones de cada fila siguen el
  alcance **de esa fila** (`item.puede_editar`, `programa.puede_editar`) y la columna de acciones se
  dibuja si hay alguna fila editable (`puede_editar_alguno`): un admin de programa ve su propio rol o
  los programas ajenos sin el lápiz que el servidor le va a rechazar (G1b-02, SEC-07, Cambio 193).
  También monta la barra, con clase propia y sin migrar:
  `conversaciones/templates/conversaciones/lista.html` (pantalla **sin ruta**: no es
  referencia de nada).

## Filtro rápido en píldora (`components/_filtro_pildora.html`)

Variante **compacta** del filtro: «Campo: valor ⌄» en una píldora de 36 px, para los pocos filtros
que se tocan todo el tiempo (área, estado, sector). Va en una fila propia **fuera** del
`<form data-dynamic-list-filters>` (ese JS vacía su form al montar).

```django
{% include "components/_filtro_pildora.html" with pildoras=pildoras ocultos=ocultos %}
```

- `pildoras`: lista de dicts armada **en la vista**: `nombre` (parámetro GET), `etiqueta` (texto
  antes de los dos puntos y `aria-label`), `opciones` (lista de `(valor, texto)`), `valor` (el
  elegido; vacío = «Todos») y opcional `todos` (texto de la opción vacía).
- `ocultos`: opcional, `(nombre, valor)` que se conservan al filtrar (la búsqueda). La página no
  se conserva: al filtrar se vuelve a la primera.
- Es un `<form method="get">` propio, con botón «Filtrar» **visible**. No filtra al cambiar el
  valor: con teclado la flecha sobre un `<select>` cerrado dispara `change` y recargaría la
  página en la primera opción, sin llegar a la segunda (WCAG 3.2.2). Se aparta del mockup, que
  filtra al elegir; el botón es la forma de avisar y confirmar el cambio.
- CSS: `.nodo-pildora` y `.nodo-pildora__control` en `static/custom/css/nodo-forms.css`.
- Sin chevron propio: se ve la flecha nativa del `<select>`.

**Con solapas, las píldoras van dentro de cada panel y el oculto `tab` es el del panel.** La solapa
visible la cambia Alpine **en el navegador** y este form lo arma el **servidor**: un solo bloque de
píldoras arriba con `ocultos=(("tab", solapa_actual),)` manda siempre la solapa que resolvió el
servidor, así que filtrar parado en otra te devuelve a la primera. Cada panel dibuja su propio
include con `ocultos=(("tab", <su clave>),)`, y la vista le arma a cada uno las píldoras que ahí
**filtran algo**: una que no cambia nada en ese panel confunde más de lo que ayuda. Evidencia:
`programas/templates/programas/dispositivos/relevamientos/list.html` (P21) y la solapa Estadías de
`programas/templates/programas/dispositivos/legajo/detail.html` (P4).

En P21, «Revisados» filtra completados con fecha de revisión; su contador y «Asignado a»
conservan el mismo alcance que las demás solapas. Las opciones de «Asignado a» se limitan a relevamientos cuya asignación puede ver
quien mira: coordina ese edificio o es el agente asignado. Leer el edificio por
`dispositivo.ver` no habilita su nombre ni en la píldora ni en la fila (que muestra «—»).

**Prohibido combinarlo con la tarjeta de filtros.** Son dos `<form method="get">` separados y
`dynamic_list_filters.js` vacía y reconstruye el suyo sin arrastrar parámetros ajenos: cada form
pisaría los filtros del otro, y `ocultos` solo protege a la píldora. Una pantalla usa **o** las
píldoras **o** la tarjeta. Si necesita ambos conjuntos, todos los filtros van en la tarjeta (con
`aria-label` por control); o se amplía `dynamic_list_filters.js` para preservar los parámetros
externos, y eso es una pieza nueva con su propio OK. El mockup muestra píldoras **dentro** de la
`.fcard` (P1, P4, P10…): esa composición no está cubierta.

## Prohibido

- Clases en el `<form>`, card alrededor, grilla de filtros, `style=`.
- Botones propios de «Filtrar» o «Limpiar» (el JS los tira y deja el listado sin forma de
  limpiar).
- `<label>` suelto como único nombre accesible.
- Controles sin `name`.

## Estado vacío con filtros

Cuando el listado queda vacío **por los filtros**, el estado vacío cambia: lo decide
`request.GET|hay_filtros` (filtro de `core/templatetags/nodo_ui.py`) y la acción es «Limpiar
filtros» hacia la URL sin parámetros, nunca la de alta. Ver la ficha `estado_vacio.md`.

## Deuda conocida

`templates/components/list_filters.html` dibuja sus íconos con SVG inline (Heroicons) y tiene un
`style="width:120px"` en el selector de lógica. Es la pieza, no el consumidor: una pantalla nueva
**no copia** ese markup, solo pone el `<form>` con sus controles.
