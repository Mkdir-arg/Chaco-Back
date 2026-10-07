# Componente · Campo de formulario (`components/_field.html`, `nodo-field`, `.nodo-checks`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `templates/components/_field.html`, `static/custom/css/nodo-forms.css`,
`core/templatetags/nodo_ui.py` (`campo_control`, `campo_wrapper_class`),
`programas/forms.py` (`INPUT_CLASS`).
**Consumidores de referencia:** `programas/templates/programas/becas/config/segmento_form.html`
(golden del arquetipo Formulario), `configuracion/templates/configuracion/secretaria_form.html`.

Es **una sola pieza para todo el repo**. Hasta FE-23 había dos —una en Becas y otra en
Dispositivos, con otro dialecto de label—: las dos se borraron.

## Invocación

```django
{% for field in form %}{% include "components/_field.html" %}{% endfor %}
{% with field=form.nombre %}{% include "components/_field.html" %}{% endwith %}
```

| Parámetro | Efecto |
|---|---|
| `field` | `BoundField` (obligatorio) |
| `wrapper_class` | clases del contenedor; por defecto `mb-4`. Un formulario cuya grilla ya separa con `gap`/`space-y` pasa `wrapper_class=""` |

Render de cada campo:

```html
<div class="mb-4">
  <label class="block text-sm font-medium text-heading mb-1" for="…">Etiqueta <span class="text-fg-danger">*</span></label>
  <input class="nodo-field" aria-describedby="id_campo-ayuda" …>
  <p id="id_campo-ayuda" class="mt-1 text-xs text-body-subtle">ayuda</p>
  <p id="id_campo-error" class="mt-1 text-xs text-fg-danger hidden" data-error="campo"></p>
</div>
```

- El asterisco sale de `field.field.required`, no se escribe a mano.
- La ayuda va en `text-body-subtle`; el rojo queda **solo** para el error.
- **El `<p>` del error está siempre**, con `data-error="<campo>"` y oculto mientras no haya
  texto: es donde el guardado AJAX (`programas/templates/programas/becas/_ajax_js.html`) lo
  escribe sin recargar.
- **ARIA:** `aria-describedby` apunta a la ayuda, y suma el error **solo cuando hay error**
  (si no, cada campo se leería con una descripción vacía); con errores el control lleva
  además `aria-invalid="true"`. Lo pone `{% campo_control field %}`, porque una plantilla no
  puede llamar a `BoundField.as_widget(attrs=…)`.

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

El bloque de checks **no** lleva recorrido de `.errors` cuando su form no se re-renderiza inválido: el modal
«Completar datos para SIIS» no es AJAX y su vista arma un solo aviso con todos los errores y redirige (ALR-8),
así que ese markup sería muerto y simularía una validación inline que no existe. Donde el form sí vuelve
renderizado —un formulario de pantalla completa—, el error va como en el resto de `_field.html`.

## Campos dentro de un modal

En un modal con guardado AJAX el campo se escribe a mano para poder enganchar el error inline:

```django
<label for="{{ form.campo.id_for_label }}" class="block text-sm font-medium text-heading mb-1">Etiqueta <span class="text-fg-danger">*</span></label>
{{ form.campo }}
{% if form.campo.help_text %}<p class="mt-1 text-xs text-body-subtle">{{ form.campo.help_text }}</p>{% endif %}
<p class="mt-1 text-xs text-fg-danger hidden" data-error="campo"></p>
```

## Prohibido

- Un `_field.html` propio por módulo. Hay **uno solo**, y labels con valores arbitrarios
  (`block text-[13px] font-semibold mb-1.5`, el dialecto que tenía Dispositivos) no vuelven.
- `class="nodo-field"` escrito en el template sobre un control que sale del form.
- Label sin `for`.
- Validar en el template: la validación vive en el Django Form y en los servicios.
