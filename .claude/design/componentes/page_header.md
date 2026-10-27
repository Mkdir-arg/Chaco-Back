# Componente · Encabezado de página (`{% page_header %}`)

**Clasificación:** Canónico reutilizable (todas las superficies del backoffice).
**Evidencia:** `core/templatetags/nodo_ui.py`, `templates/components/_page_header.html`,
`core/tests/test_page_header_tag.py`.
**Contrato del estado opcional:** `core/tests/test_nodo_ui_piezas.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/revision/personas_list.html`
(listado), `programas/templates/programas/becas/config/segmento_form.html` (form con título
calculado), `programas/templates/programas/becas/cupo/segmento_detail.html` (detalle con migas).

## Invocación

```django
{% load nodo_ui %}
{% page_header titulo=<str> eyebrow=<str> bajada=<str> volver_url=<url> volver_label=<str> migas=<lista> %}
  {% bajada %}<HTML de plantilla>{% endbajada %}   {# opcional; hijo directo, uno solo #}
  <badges y acciones>
{% endpage_header %}
```

**Nunca** `{% include "components/_page_header.html" %}` a mano.

## Parámetros (solo con nombre; todos opcionales salvo `titulo`)

| Parámetro | Tipo | Efecto |
|---|---|---|
| `titulo` | str (**obligatorio**) | `<h1 class="text-3xl font-extrabold text-heading tracking-tight">`, escapado |
| `eyebrow` | str | Línea chica sobre el título: `<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">`, escapada, dentro del mismo bloque que el `h1`. Dice **dónde está parado** el usuario (programa, institución, rol), no repite el título. Sin valor no se dibuja |
| `bajada` | str | `<p class="text-sm text-body-subtle mt-1">`, escapada. Para HTML, el bloque `{% bajada %}`, que tiene precedencia sobre el argumento; con `bajada=texto|safe` lo marca la plantilla, nunca el tag |
| `volver_url` | url | Botón circular `btn-tertiary btn-back-circle` con `fa-arrow-left` (`aria-hidden`) |
| `volver_label` | str | `aria-label="Volver a {volver_label}"` (por defecto «la pantalla anterior»). Nombra la pantalla de **origen** |
| `migas` | lista de `{"label", "url"}` | Se muestran solo con **3 o más** elementos; la última sin enlace (`aria-current="page"`). En Becas la arma `{% becas_migas objeto [actual=…] as migas %}` (biblioteca `becas_extras`); en otros módulos se arma en la vista |
| `estado_texto` | str | Estado escapado junto al H1, fuera de las acciones. Sin texto no se dibuja ni se agrega wrapper: el HTML previo se conserva carácter por carácter |
| `estado_variante` | str | `gray`, `white`, `brand`, `success`, `danger`, `warning` o `info`; ausente/desconocida cae en `gray`. Dibuja `badge badge-dot badge-<variante>`; el consumidor obtiene el tono del módulo |

Errores de compilación (`TemplateSyntaxError`): un argumento posicional, uno desconocido, falta
`titulo`, o más de un `{% bajada %}`. Un `{% bajada %}` dentro de un `{% if %}` **no** se
reconoce como bajada: se renderiza entre las acciones.

## Render

Contenedor `space-y-3` → migas (`nav aria-label="Migas"` + `ol flex items-center gap-1.5
flex-wrap text-xs text-body-subtle`, enlaces `text-fg-brand hover:underline`, separador `/` con
`aria-hidden`) → fila `flex items-start justify-between gap-4 flex-wrap`: a la izquierda
`flex items-start gap-3 min-w-0` con volver + (eyebrow + título + bajada), a la derecha el cuerpo en
`flex items-center gap-2 flex-wrap`.

Con `estado_texto`, solo el título se envuelve en `flex items-center gap-3 flex-wrap`:
H1 y badge quedan alineados verticalmente y el badge baja de línea si falta ancho (390 px).
Sin el parámetro, tampoco se hereda un estado del contexto de la pantalla.
P4 (incluida Infraestructura/P19), P7 y el detalle de tipo P14 usan este slot.
P14 identifica el contexto con `eyebrow="Tipo de dispositivo"` sobre el título del tipo.

## Acciones del cuerpo (regla observada en el código)

- **Listados y formularios:** primaria `btn-nodo btn-brand btn-base` (+ ícono `fa-plus` en las
  altas); secundaria `btn-nodo btn-tertiary btn-base`.
- **Detalles:** acciones `btn-nodo btn-secondary btn-sm`; los badges de estado
  (`badge … badge-dot`) pueden usar `estado_texto` junto al H1; los consumidores que
  ya los dibujan en el cuerpo conservan su contrato hasta que se migre ese bloque.
- Lo que abre **otra pantalla** va acá, nunca como solapa.
- Más de una acción secundaria: van al menú con `texto="Más acciones"` (regla de la «Variante de encabezado» de `tabla.md`).

## Patrones

- Título calculado:
  `{% with titulo_pagina=form.instance.pk|yesno:"Editar X,Nuevo X" %}{% page_header titulo=titulo_pagina … %}…{% endwith %}`.
- Volver al origen: la pantalla a la que se llega desde varios lugares recibe el origen en
  `?next=` y **la vista lo valida** —`url_has_allowed_host_and_scheme` **más** el prefijo de la
  sección, por ejemplo `/becas/`— antes de pasarlo como `volver_url`; sin origen válido cae en
  su destino de siempre. El `next` viaja en los `action` y en los redirect de los POST para no
  perderlo al guardar. Evidencia: `programas/views/revision.py` (`_next_valido`, `_origen_del_caso`) y
  `programas/templates/programas/becas/revision/formulario_detalle.html`.

## No usar / errores comunes

- `<h1>` a mano (`text-2xl font-bold text-gray-900`, `style="font-size:28px"`), un eyebrow
  armado a mano en vez de `eyebrow=`, «← Volver» como link de texto, header dentro de una card.
- Migas de 2 niveles: no se muestran (alcanza con el volver).
- Acciones del header con tamaño mezclado en la misma pantalla.
