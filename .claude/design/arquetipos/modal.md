# Arquetipo · Modal de alta/edición (y confirmación con motivo)

**Golden (la única que se clona):** el modal «Nuevo programa» de
`programas/templates/programas/becas/config/programa_list.html` (bloque `x-becas-modal`), con
`programas/templates/programas/becas/_modal_header.html`,
`programas/templates/programas/becas/_modal_footer.html`, `static/custom/js/becas-modal.js` y
`programas/templates/programas/becas/_ajax_js.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo modal <archivo>`.
**Componentes:** modal_partes · field · alerta · botones_badges.

Se descartó `config/convocatoria_list.html` como golden: tiene 6 labels sin `for` y el backdrop
con `style=`.

## Cuándo

- Alta o edición **corta** que no justifica perder el contexto de la lista.
- **Confirmación con motivo**: cuando la acción pide un texto (motivo, fecha, observación),
  `ModernModal` no alcanza. Se usa este arquetipo con `<form method="post">` y un textarea
  `nodo-field` requerido. Para un sí/no sin datos, el arquetipo es Confirmación.

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load static nodo_ui %}

{% block main-content %}
<div x-data="{ modalCrear: false }" @becas-saved.window="modalCrear=false">

  {# Los overlays fixed van FUERA del space-y-*: el margin-top los corre y el clic en esa franja no cierra #}
  <div class="space-y-5">
    {% page_header titulo="<Entidades>" bajada="<bajada>" %}
      {% if puede_crear %}
      <button type="button" @click="modalCrear=true" class="btn-nodo btn-brand btn-base">
        <i class="fas fa-plus" aria-hidden="true"></i> Nuevo <entidad>
      </button>
      {% endif %}
    {% endpage_header %}
    <div id="<entidad>s-table" class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">
      {% include "<app>/<modulo>/_<entidad>s_table.html" %}
    </div>
  </div>

  {# Modal: x-becas-modal da foco, Tab atrapado, Escape y bloqueo del scroll del fondo #}
  <div x-show="modalCrear" x-cloak x-becas-modal="modalCrear" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="modalCrear=false"></div>
    <div class="relative bg-white rounded-2xl shadow-xl w-full max-w-[560px] max-h-[90vh] flex flex-col overflow-hidden" @click.stop
         role="dialog" aria-modal="true" aria-labelledby="modal-crear-titulo">
      {% include "programas/becas/_modal_header.html" with titulo="Nuevo <entidad>" titulo_id="modal-crear-titulo" icono="fa-<x>" cerrar="modalCrear=false" %}
      <form method="post" action="{% url '<app>:<entidad>_crear' %}" data-ajax class="flex flex-col flex-1 min-h-0">
        {% csrf_token %}
        <div class="px-6 py-6 space-y-5 overflow-y-auto min-h-0">
          <div>
            {# El error general va ADENTRO del bloque: como hijo directo de space-y-5 suma un hueco de 20px aunque esté oculto #}
            <p class="mb-2 text-xs text-fg-danger hidden" data-error="__all__" role="alert"></p>
            <label for="{{ form.<campo>.id_for_label }}" class="block text-sm font-medium text-heading mb-1"><Etiqueta> <span class="text-fg-danger">*</span></label>
            {{ form.<campo> }}
            {% if form.<campo>.help_text %}<p class="mt-1 text-xs text-body-subtle">{{ form.<campo>.help_text }}</p>{% endif %}
            <p class="mt-1 text-xs text-fg-danger hidden" data-error="<campo>"></p>
          </div>
          {% include "components/_alerta.html" with tono="info" texto="<nota que explica de dónde salen los datos>" %}
        </div>
        {% include "programas/becas/_modal_footer.html" with cancelar="modalCrear=false" accion_texto="Guardar" %}
      </form>
    </div>
  </div>
</div>
{% endblock %}

{% block customJS %}{% include "programas/becas/_ajax_js.html" %}
<script src="{% static 'custom/js/becas-modal.js' %}"></script>{% endblock %}
```

## Confirmación con motivo

Mismo esqueleto, con:

- título y tono del encabezado según la acción (`tono="danger"` para lo destructivo);
- cuerpo con un solo control: `<textarea name="motivo" class="nodo-field" rows="3" required>`
  con su label canónico y su `<p data-error="motivo">`;
- `{% include "components/_alerta.html" with tono="warning" … %}` explicando la consecuencia;
- pie con `accion_tono="danger"` y el texto en «Sí, <verbo>».

Nada de `ModernModal` con input ni de un `Swal.fire` nuevo.

## Variantes permitidas

- Campos en dos columnas: `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">`.
- Panel más ancho cuando suma un bloque de identificadores: `max-w-2xl` en vez de `max-w-[560px]`.
- Form fuera del panel scrolleable: el `<form id="…">` en el cuerpo y el submit del pie
  apuntándole con `form_id` de `_modal_footer.html`.
- Título dinámico Nuevo/Editar: `titulo_x_text` (expresión Alpine) en `_modal_header.html`.
- Modal sin Alpine: `window.becasModal.bind(overlay, {onClose})` observa la clase `hidden` del
  overlay; Escape y cualquier `[data-becas-modal-cerrar]` llaman a `onClose`.
- Modal anidado sobre otro: el de arriba atrapa Tab y Escape; el de abajo no se cierra.

## Prohibido

- `<style>` local o `[x-cloak]` propio; `style="backdrop-filter:blur(4px)"` (la clase compilada
  es `backdrop-blur-sm`).
- Labels con valores arbitrarios (`text-[13px] font-semibold mb-1.5`) o sin `for`.
- Texto de ayuda en `text-fg-danger`: la ayuda va en `text-body-subtle` y el rojo queda para
  el error.
- Overlay dentro del `space-y-*` de la página.
- Un modal propio sin `role="dialog"`, `aria-modal="true"` y `aria-labelledby`.
- `Swal.fire` nuevo.

## Checklist (la usa el revisor)

- [ ] `--arquetipo modal` OK y `--ratchet` con 0 nuevos.
- [ ] `x-becas-modal` presente y `becas-modal.js` cargado en `customJS`.
- [ ] `role="dialog"`, `aria-modal="true"`, `aria-labelledby` apuntando al `id` del título.
- [ ] Cuerpo `overflow-y-auto min-h-0`; header y pie `flex-shrink-0`; el pie se ve en pantallas bajas.
- [ ] Cada campo tiene label con `for`, `data-error="<campo>"` y, si hay errores generales,
      `data-error="__all__"`.
- [ ] El POST va por `data-ajax` con el include de guardado, o es un POST clásico con CSRF.
- [ ] Clic afuera, Escape y la X cierran; el foco vuelve al disparador.
