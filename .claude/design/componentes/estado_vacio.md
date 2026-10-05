# Componente · Estado vacío (`components/_estado_vacio.html`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `templates/components/_estado_vacio.html`, `core/templatetags/nodo_ui.py` (filtro
`hay_filtros`), `core/tests/test_nodo_ui_piezas.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/reportes/reporte.html`,
`programas/templates/programas/becas/revision/personas_list.html`.

## Invocación

```django
{# sin datos todavía #}
{% include "components/_estado_vacio.html" with icono="fa-users" titulo="Todavía no hay entregas" texto="Registrá la primera entrega del mes." accion_url=url_crear accion_texto="Nueva entrega" accion_icono="fa-plus" %}

{# vacío por los filtros #}
{% url '<app>:<lista>' as url_sin_filtros %}
{% include "components/_estado_vacio.html" with con_filtros=True titulo="Ninguna entrega coincide con los filtros" texto="Probá con otros filtros." accion_url=url_sin_filtros %}
```

| Parámetro | Efecto |
|---|---|
| `titulo` | **Obligatorio.** `p text-[17px] font-bold text-heading` |
| `texto` | Descripción opcional, `p text-sm text-body max-w-xs` |
| `icono` | Font Awesome sin `fas`. Por defecto `fa-inbox`; con `con_filtros`, `fa-magnifying-glass` |
| `accion_url` | Sin ella no hay botón |
| `accion_texto` | Texto del botón; con `con_filtros`, por defecto «Limpiar filtros» |
| `accion_icono` | Ícono opcional del botón |
| `con_filtros` | Variante «los filtros no traen nada»: la acción pasa a `btn-tertiary` (limpiar), no a la primaria de alta |

Render: `py-14 px-6 text-center flex flex-col items-center gap-3`, ícono `text-5xl` en
`text-fg-brand` con `aria-hidden`, y la acción `btn-nodo btn-{brand|tertiary} btn-base mt-2`.

## Dónde va

**Dentro de la card de la lista**, como hermano de la tabla:

```django
<div class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">
  {% if objetos %}
    …tabla…
    {% include "components/_paginacion.html" with page_obj=page_obj entidad="entrega" %}
  {% elif request.GET|hay_filtros %}
    …variante con filtros…
  {% else %}
    …variante sin datos…
  {% endif %}
</div>
```

Dentro de una tabla con solapas, va en el `{% empty %}` del `{% for %}`:
`<tr><td colspan="<n>" class="p-0">{% include … %}</td></tr>`.

`request.GET|hay_filtros` (filtro de `core/templatetags/nodo_ui.py`) devuelve `True` si algún
parámetro no excluido trae valor; por defecto excluye `page`, y acepta una lista propia:
`request.GET|hay_filtros:"page,tab"`.

## Prohibido

- El bloque a mano (`py-14 px-6 text-center` escrito en la pantalla).
- Un solo estado vacío cuando la lista tiene filtros: siempre son dos, y el de filtros ofrece
  limpiar, nunca crear.
- Texto genérico («No hay datos»): decí qué falta y qué hacer.
