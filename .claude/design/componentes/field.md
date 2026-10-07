# Componente · Campo de formulario (`_field.html`, `nodo-field`, `.nodo-checks`)

**Clasificación:** Canónico reutilizable.
**Evidencia:** `programas/templates/programas/becas/_field.html`,
`static/custom/css/nodo-forms.css`, `programas/forms.py` (`INPUT_CLASS`).
**Consumidores de referencia:** `programas/templates/programas/becas/config/segmento_form.html`,
`programas/templates/programas/becas/revision/formulario_detalle.html` (modal de corrección).

El include vive en Becas pero es **transversal**: se incluye desde esa ruta desde cualquier
módulo. (Está previsto moverlo a `templates/components/`; hasta entonces, se usa donde está y
**no se copia** un `_field.html` propio por módulo.)

## Invocación

```django
{% for field in form %}{% include "programas/becas/_field.html" %}{% endfor %}
```

Render de cada campo:

```html
<div class="mb-4">
  <label class="block text-sm font-medium text-heading mb-1" for="…">Etiqueta <span class="text-fg-danger">*</span></label>
  {{ field }}
  <p class="mt-1 text-xs text-body-subtle">ayuda</p>
  <p class="mt-1 text-xs text-fg-danger">error</p>
</div>
```

- El asterisco sale de `field.field.required`, no se escribe a mano.
- La ayuda va en `text-body-subtle`; el rojo queda **solo** para el error.

## La clase del control la pone el widget

`nodo-field` llega desde `INPUT_CLASS` en los widgets del form (`programas/forms.py`), **no desde
el template**. Un control escrito a mano en el template (un filtro, un campo de un modal que no
sale del form) sí lo lleva en el markup:
`<select name="estado" class="nodo-field" aria-label="Estado">`.

No hay «clases equivalentes»: es `nodo-field` o nada.

## Selector múltiple apilado

El contenedor del campo lleva `.nodo-checks`: el widget de Django queda como grilla de filas
clickeables, caja de 18 px con `accent-color` de marca y `:focus-visible` con anillo. Lo consumen
el paso 2 del portal (`portal/templates/portal/inscripcion/paso2.html`), la vista previa del
constructor —que lo espeja con sus propias clases— y el bloque «Quitar corrección» del modal
«Completar datos para SIIS» (`revision/formulario_detalle.html`, `DatosSiisForm.quitar`).

Cuando el campo de checks convive con una grilla de campos normales va **fuera** de la grilla,
separado con `border-t border-light mt-2 pt-5`: metido adentro de `sm:grid-cols-2` queda en media
columna y las filas se cortan. El label de un `CheckboxSelectMultiple` no apunta a un control
único, así que ahí va un `<p class="block text-sm font-medium text-heading mb-1">` y no un
`<label for>` sin destino.

## Campos dentro de un modal

En un modal con guardado AJAX el campo se escribe a mano para poder enganchar el error inline:

```django
<label for="{{ form.campo.id_for_label }}" class="block text-sm font-medium text-heading mb-1">Etiqueta <span class="text-fg-danger">*</span></label>
{{ form.campo }}
{% if form.campo.help_text %}<p class="mt-1 text-xs text-body-subtle">{{ form.campo.help_text }}</p>{% endif %}
<p class="mt-1 text-xs text-fg-danger hidden" data-error="campo"></p>
```

## Prohibido

- Labels con valores arbitrarios: `block text-[13px] font-semibold mb-1.5` es el dialecto de
  `programas/templates/programas/dispositivos/config/_field.html`, que **duplica** esta pieza. No
  se copia; esa pantalla se migra cuando se la toque.
- `class="nodo-field"` escrito en el template sobre un control que sale del form.
- Label sin `for`.
- Validar en el template: la validación vive en el Django Form y en los servicios.

## Deuda conocida

El include todavía no emite `aria-describedby` ni `aria-invalid` para enlazar el error con el
control. Está previsto; hasta entonces se usa tal cual y no se inventa otra forma.
