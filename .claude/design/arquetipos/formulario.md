# Arquetipo · Formulario de página

**Golden (la única que se clona):** `programas/templates/programas/becas/config/segmento_form.html`
(29 líneas) + el include de campo `programas/templates/programas/becas/_field.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo formulario <archivo>`.
**Componentes:** page_header · field · alerta · botones_badges.

No hay golden secundaria. La variante con `fieldset` por tipo es una regla de esta ficha.

## Cuándo

Alta o edición de un registro en su propia pantalla, con los campos de un Django Form o
ModelForm. Si el alta es corta y no vale perder el contexto de la lista, el arquetipo es
Modal. Si el usuario carga muchas filas de lo mismo, no es este arquetipo: frená.

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load nodo_ui %}
{% block title %}<Módulo> · {% if form.instance.pk %}Editar{% else %}Nuevo{% endif %} <entidad>{% endblock %}

{% block main-content %}
<div class="space-y-5">
  {% url '<app>:<lista>' as url_lista %}
  {% with titulo_pagina=form.instance.pk|yesno:"Editar <entidad>,Nuevo <entidad>" %}
  {% page_header titulo=titulo_pagina volver_url=url_lista volver_label="<entidades>" %}
    {% bajada %}{% if form.instance.pk %}<qué se puede cambiar>{% else %}<qué se carga ahora y qué después>{% endif %}{% endbajada %}
  {% endpage_header %}
  {% endwith %}
  <form method="post" class="bg-white rounded-xl border border-base shadow-sm p-6">
    {% csrf_token %}
    {% if form.non_field_errors %}
      <div class="mb-4 rounded-lg bg-danger-soft border border-danger-subtle p-4 text-sm" role="alert">
        <strong class="text-heading">Revisá el formulario</strong>
        <div class="text-body mt-1">{{ form.non_field_errors }}</div>
      </div>
    {% endif %}
    {% for field in form %}{% include "programas/becas/_field.html" %}{% endfor %}
    <div class="flex justify-end gap-3 mt-6 pt-4 border-t border-light">
      <a href="{% url '<app>:<lista>' %}" class="btn-nodo btn-tertiary btn-base">Cancelar</a>
      <button type="submit" class="btn-nodo btn-brand btn-base"><i class="fas fa-check" aria-hidden="true"></i> Guardar <entidad></button>
    </div>
  </form>
</div>
{% endblock %}
```

Vista: `CreateView`/`UpdateView` (o función) con un Django Form o ModelForm. **La validación
vive en el form y en los servicios**, nunca en el template. Los widgets ya traen `nodo-field`
desde `INPUT_CLASS` de `programas/forms.py`: el template no agrega clases a los controles.

## Variantes permitidas

- Campos agrupados: varios `{% for %}` sobre subconjuntos del form dentro de bloques con
  `h2 text-heading font-bold` + `border-t border-light pt-4`.
- Grilla de dos columnas: envolver los `{% include %}` de campo en
  `<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">`.
- Acción auxiliar al lado de un campo: `btn-nodo btn-tertiary btn-sm` justo después del
  `{% include %}` de ese campo, condicionada por capacidad (como «Crear coordinador» en la
  golden, que es **de dominio** y no se copia).
- `fieldset` condicionado por tipo (`x-show` / `:disabled` con Alpine): adentro va **solo** lo
  que aplica a ese tipo. Un control común a todos los tipos se ubica **fuera** del `fieldset`,
  o queda deshabilitado y sin enviarse para el resto. Evidencia en el alta de relevamiento
  (`relevamiento_form.html`, `relevamiento_list.html` y `convocatoria_detail.html` de
  `programas/templates/programas/becas/relevamientos/`): el toggle de avisos por correo vale para
  territoriales y públicos y por eso quedó fuera del `fieldset` de tipo público, que conserva
  cupo y padrón.
- Confirmación de borrado: misma estructura, con el texto del riesgo en
  `{% include "components/_alerta.html" with tono="danger" … %}` y la acción `btn-nodo btn-danger btn-base`.

## Prohibido

- `<h1>` propio, «← Volver» de texto, header dentro de la card.
- `class="nodo-field"` escrito en el template sobre un control del form (lo pone el widget).
- Labels con valores arbitrarios (`block text-[13px] …`): el label canónico es
  `block text-sm font-medium text-heading mb-1` y lo rinde el include de campo.
- `<style>`, `style=`, paleta cruda, SVG inline.
- Resolver reglas de negocio o permisos en el template.

## Deuda conocida de la golden

`{{ form.non_field_errors }}` está escrito a mano y el include de campo todavía no emite
`aria-describedby` / `aria-invalid`. Está previsto moverlo a una pieza
`components/_form_errores.html`; hasta que exista, **se copia tal cual** y no se inventa otra
forma. `user/_alta_rapida_modal.html` que la golden incluye es **de dominio**: no se copia.

## Checklist (la usa el revisor)

- [ ] `--arquetipo formulario` OK y `--ratchet` con 0 nuevos.
- [ ] `{% csrf_token %}` presente y método POST.
- [ ] Todos los campos salen del form (nada de `<input>` suelto sin `name` del form).
- [ ] Pie con Cancelar (`btn-tertiary btn-base`) y Guardar (`btn-brand btn-base`), en ese orden.
- [ ] Título calculado con `yesno` para alta/edición y `volver_url` a la lista.
- [ ] Los errores generales se muestran arriba con `role="alert"`.
- [ ] La validación está en el form o el servicio, no en la vista ni en el template.
