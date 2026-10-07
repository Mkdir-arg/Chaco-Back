# Componente · Paginación (`components/_paginacion.html`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `templates/components/_paginacion.html`, `core/tests/test_nodo_ui_piezas.py`,
`programas/tests/test_renaper_pendientes_paginacion.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/revision/renaper_pendientes.html`,
`programas/templates/programas/becas/revision/personas_list.html`,
`programas/templates/programas/becas/cupo/segmento_detail.html`.

## Invocación

```django
{% include "components/_paginacion.html" with page_obj=page_obj entidad="caso" %}
```

| Parámetro | Efecto |
|---|---|
| `page_obj` | **Obligatorio.** `Page` de Django |
| `entidad` | Sustantivo en **singular** del contador («caso»); por defecto «registro» |
| `entidad_plural` | Plural cuando no alcanza con agregar «s» («localidades») |
| `filtros_qs` | Querystring ya codificado, sin `page` ni `?`. Si falta, se conservan todos los parámetros de `request.GET` salvo `param` y las claves que ya trae `extra_qs` |
| `param` | Nombre del parámetro de página (por defecto `page`). Con un nombre propio por lista, una pantalla pagina más de una |
| `extra_qs` | Querystring ya codificado, sin `?`, que el enlace conserva siempre (p. ej. `tab=beneficiarios`, para volver a la solapa que se estaba mirando) |

## Reglas

- **Solo se muestra con más de una página.** Nada de «1 de 1» con los botones deshabilitados.
- Va **dentro de la card de la tabla**, después del wrapper `overflow-x-auto`.
- Pie `flex items-center justify-between gap-3 flex-wrap px-4 py-3 border-t border-light bg-secondary`.
- Contador «Página X de Y · N entidad» en `text-xs text-body-subtle`.
- Anterior/Siguiente `btn-nodo btn-tertiary btn-sm` con `fa-chevron-left` / `fa-chevron-right`
  (`aria-hidden`) y `aria-label` «Página anterior» / «Página siguiente», solo cuando existen.
- Los enlaces son `?page=N` seguidos de los demás parámetros, codificados y con `&amp;`.
- La vista pagina con `paginate_by` (25 en Becas) o con un `Paginator` explícito; el template
  nunca recorta la lista.

## Más de una lista paginada por pantalla

El include acepta `param` y `extra_qs`, así que **sí** sirve para varias listas en la misma pantalla:
cada una declara su propio parámetro de página y el `tab` al que vuelve. Lo sostiene el filtro
`sin_parametros` de `core/templatetags/nodo_ui.py`, que saca del querystring las claves que se le
pasan (y se encadena consigo mismo). Sin él, el enlace salía con el parámetro de página **repetido**
y el pie no movía de página.

```django
{% include "components/_paginacion.html" with page_obj=beneficiarios entidad="beneficiario" param="beneficiarios_page" extra_qs="tab=beneficiarios" filtros_qs=beneficiarios_querystring %}
```

El `filtros_qs` lo arma la vista (`_querystring_without(request, "beneficiarios_page", "tab")`).
Evidencia: las tres solapas de `programas/templates/programas/becas/cupo/segmento_detail.html`.

## Prohibido

- Paginación a mano con `page_obj.has_next` / `has_previous`.
- Mostrar el pie con una sola página.
- Paginación fuera de la card, o con botones de otro tamaño.
