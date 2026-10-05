# Arquetipo · Listado con filtros

**Golden (la única que se clona):** `programas/templates/programas/becas/revision/personas_list.html`
(97 líneas). Una pantalla hermana del módulo **nunca** es molde: de ella se toma solo dominio.
**Marcadores:** `scripts/design_audit.py --arquetipo listado <archivo>`.
**Componentes:** page_header · filtros · tabla · estado_vacio · paginacion · botones_badges.

**Secundarias, solo para lo indicado:** `programas/templates/programas/becas/reportes/reporte.html`
(varios filtros a la vez) y `programas/templates/programas/becas/revision/formulario_list.html`
(acción primaria en el encabezado).

## Cuándo

Colección de registros del mismo tipo que el usuario compara, filtra y abre. No es un
listado si el usuario carga datos en la grilla (eso es formulario) ni si son menos de 5
filas fijas (eso es una sección del detalle).

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load nodo_ui %}
{% block title %}<Módulo> · <Entidades>{% endblock %}

{% block main-content %}
<div class="space-y-6">

  {% page_header titulo="<Entidades>" bajada="<qué muestra la lista, una línea>" %}
    {% if puede_crear %}
      <a href="{% url '<app>:<entidad>_crear' %}" class="btn-nodo btn-brand btn-base">
        <i class="fas fa-plus" aria-hidden="true"></i> Nuevo <entidad>
      </a>
    {% endif %}
  {% endpage_header %}

  <form method="get" data-dynamic-list-filters>
    <input type="search" name="q" value="{{ request.GET.q }}" class="nodo-field max-w-xs" aria-label="Buscar">
    <select name="estado" class="nodo-field max-w-xs" aria-label="Estado">
      <option value="">Todos</option>
      {% for value, label in estados %}<option value="{{ value }}" {% if value == estado_actual %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select>
  </form>

  <div class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">
    {% if <objetos> %}
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="nodo-thead-row">
            <th class="nodo-th"><Columna principal></th>
            <th class="nodo-th"><Columna></th>
            <th class="nodo-th">Estado</th>
            <th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>
          </tr>
        </thead>
        <tbody>
          {% for obj in <objetos> %}
          <tr class="hover:bg-secondary">
            <td class="nodo-td text-heading font-medium">{{ obj.<nombre> }}
              <span class="block text-xs text-body-subtle"><metadato></span></td>
            <td class="nodo-td text-body">{{ obj.<campo> }}</td>
            <td class="nodo-td">{% include "programas/<modulo>/_estado_badge.html" with estado=obj.estado %}</td>
            <td class="nodo-td text-right">
              <a href="{% url '<app>:<entidad>_detalle' obj.pk %}?next={{ request.get_full_path|urlencode }}"
                 class="nodo-icon-btn" aria-label="Ver <entidad> {{ obj.<nombre> }}">
                <i class="fas fa-eye" aria-hidden="true"></i>
              </a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% include "components/_paginacion.html" with page_obj=page_obj entidad="<entidad>" %}
    {% elif request.GET|hay_filtros %}
      {% url '<app>:<lista>' as url_sin_filtros %}
      {% include "components/_estado_vacio.html" with con_filtros=True titulo="Ningún <entidad> coincide con los filtros" texto="Probá con otros filtros." accion_url=url_sin_filtros %}
    {% else %}
      {% include "components/_estado_vacio.html" with icono="<fa-…>" titulo="Todavía no hay <entidades>" texto="<qué hacer>" accion_url=url_crear accion_texto="Nuevo <entidad>" accion_icono="fa-plus" %}
    {% endif %}
  </div>
</div>
{% endblock %}
```

Vista: `ListView` (o función) con `paginate_by` (25 es el valor de Becas); en el contexto,
los objetos de `page_obj.object_list`, `estados` (choices), `estado_actual`, `puede_crear`
(capacidad resuelta con `puede()`), la URL de alta y las relaciones con `select_related`.

## Variantes permitidas

- Sin filtros: se omite el `<form>` entero (y el estado vacío con filtros).
- Sin acción de alta: el `page_header` sin cuerpo. Acción secundaria: `btn-nodo btn-tertiary btn-base`.
- Varias acciones por fila: varias `.nodo-icon-btn` en la misma celda; la destructiva con
  `.nodo-icon-btn--danger` + `data-confirm-url` (arquetipo Confirmación).
- Columna con enlace a otra entidad: `<a class="text-fg-brand hover:underline">`.
- Columna centrada: `text-center` en el `th` **y** en el `td`; ancho fijo con `w-28` en el `th`.
- Filtro de fecha o checkbox: `<input type="date">` o `type="checkbox"` con `name` y
  `aria-label`, dentro del mismo form.
- Listado dentro de una solapa: el bloque `overflow-x-auto` → paginación → vacío, sin
  `page_header` y dentro del `tabpanel` (ver el arquetipo Detalle).
- Badge extra en una celda (por ejemplo «Duplicado por resolver»): `badge badge-warning mt-1`
  junto al badge de estado, nunca reemplazándolo.

## Prohibido (lo que hoy se copia de las hermanas)

- Clases, wrapper de card, grilla o `style` en el form de filtros; botones «Filtrar» o
  «Limpiar» propios (el JS reescribe el form y los tira).
- `thead style=`, `th` con utilidades sueltas, `divide-y`, `hover:bg-tertiary`, cards por fila.
- «Ver detalle» como botón con texto en la fila; `aria-label` genérico («Ver»).
- Mapeo de estado a color dentro de la pantalla: va en el parcial de badges del módulo.
- Paginación a mano (`page_obj.has_next`); estado vacío a mano (`py-14 px-6 text-center`).
- `<h1>`, `<style>`, `[x-cloak]` local, `style=`, paleta cruda, SVG inline, flecha «←» de texto.

## Checklist (la usa el revisor)

- [ ] `--arquetipo listado` OK y `--ratchet` con 0 nuevos.
- [ ] Molde declarado = golden; la hermana solo aportó textos, URLs y permisos.
- [ ] Acción primaria condicionada por una capacidad resuelta en la vista.
- [ ] Cada control de filtro tiene `name` + `aria-label` que se lee bien como chip
      («Estado», no «Estado:»).
- [ ] Una sola card envuelve tabla, paginación y estado vacío.
- [ ] Toda `.nodo-icon-btn` tiene `aria-label` con el registro; los íconos, `aria-hidden`.
- [ ] Hay dos estados vacíos: con filtros (limpiar) y sin datos (crear).
- [ ] La vista pagina y resuelve relaciones sin N+1.
