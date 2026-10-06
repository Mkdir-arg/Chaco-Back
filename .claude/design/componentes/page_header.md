# Componente · Encabezado de página (`{% page_header %}`)

**Clasificación:** Canónico reutilizable (todas las superficies del backoffice).
**Evidencia:** `core/templatetags/nodo_ui.py`, `templates/components/_page_header.html`,
`core/tests/test_page_header_tag.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/revision/personas_list.html`
(listado), `programas/templates/programas/becas/config/segmento_form.html` (form con título
calculado), `programas/templates/programas/becas/cupo/segmento_detail.html` (detalle con migas).

## Invocación

```django
{% load nodo_ui %}
{% page_header titulo=<str> bajada=<str> volver_url=<url> volver_label=<str> migas=<lista> %}
  {% bajada %}<HTML de plantilla>{% endbajada %}   {# opcional; hijo directo, uno solo #}
  <badges y acciones>
{% endpage_header %}
```

**Nunca** `{% include "components/_page_header.html" %}` a mano.

## Parámetros (solo con nombre; todos opcionales salvo `titulo`)

| Parámetro | Tipo | Efecto |
|---|---|---|
| `titulo` | str (**obligatorio**) | `<h1 class="text-3xl font-extrabold text-heading tracking-tight">`, escapado |
| `bajada` | str | `<p class="text-sm text-body-subtle mt-1">`, escapada. Para HTML, el bloque `{% bajada %}`, que tiene precedencia sobre el argumento; con `bajada=texto|safe` lo marca la plantilla, nunca el tag |
| `volver_url` | url | Botón circular `btn-tertiary btn-back-circle` con `fa-arrow-left` (`aria-hidden`) |
| `volver_label` | str | `aria-label="Volver a {volver_label}"` (por defecto «la pantalla anterior»). Nombra la pantalla de **origen** |
| `migas` | lista de `{"label", "url"}` | Se muestran solo con **3 o más** elementos; la última sin enlace (`aria-current="page"`). En Becas la arma `{% becas_migas objeto [actual=…] as migas %}` (biblioteca `becas_extras`); en otros módulos se arma en la vista |

Errores de compilación (`TemplateSyntaxError`): un argumento posicional, uno desconocido, falta
`titulo`, o más de un `{% bajada %}`. Un `{% bajada %}` dentro de un `{% if %}` **no** se
reconoce como bajada: se renderiza entre las acciones.

## Render

Contenedor `space-y-3` → migas (`nav aria-label="Migas"` + `ol flex items-center gap-1.5
flex-wrap text-xs text-body-subtle`, enlaces `text-fg-brand hover:underline`, separador `/` con
`aria-hidden`) → fila `flex items-start justify-between gap-4 flex-wrap`: a la izquierda
`flex items-start gap-3 min-w-0` con volver + título + bajada, a la derecha el cuerpo en
`flex items-center gap-2 flex-wrap`.

## Acciones del cuerpo (regla observada en el código)

- **Listados y formularios:** primaria `btn-nodo btn-brand btn-base` (+ ícono `fa-plus` en las
  altas); secundaria `btn-nodo btn-tertiary btn-base`.
- **Detalles:** acciones `btn-nodo btn-secondary btn-sm`; los badges de estado
  (`badge … badge-dot`) van antes de las acciones.
- Lo que abre **otra pantalla** va acá, nunca como solapa.

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

- `<h1>` a mano (`text-2xl font-bold text-gray-900`, `style="font-size:28px"`), eyebrow en
  mayúsculas, «← Volver» como link de texto, header dentro de una card.
- Migas de 2 niveles: no se muestran (alcanza con el volver).
- Acciones del header con tamaño mezclado en la misma pantalla.
