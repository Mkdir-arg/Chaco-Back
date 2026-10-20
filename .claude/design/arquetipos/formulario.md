# Arquetipo · Formulario de página

**Golden (la única que se clona):** `programas/templates/programas/becas/config/segmento_form.html`
(29 líneas) + el include de campo `templates/components/_field.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo formulario <archivo>`.
**Componentes:** page_header · field · form_errores · alerta · botones_badges.

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
    {% include "components/_form_errores.html" %}
    {% for field in form %}{% include "components/_field.html" %}{% endfor %}
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
Lo mismo vale para los forms chicos que viven en un modal, como `FormularioTipoNuevoForm`
(P17, «Nuevo formulario» del detalle del tipo): el select llega con `INPUT_CLASS` y el modal
solo pone etiqueta y error.

## Variantes permitidas

- Formulario con asistencia lateral (P3): grilla exterior
  `grid grid-cols-1 lg:grid-cols-3 gap-5`; contenedor del form
  `lg:col-span-2 min-w-0`; `aside space-y-5 min-w-0` con surfaces canónicas,
  encabezado `px-5 py-4 border-b border-light` y cuerpo `p-5`. Se apila en móvil.
  Conserva el esqueleto de la golden, sus campos y errores. Los paneles muestran
  información del dominio (duplicados y requisitos existentes), nunca reglas nuevas.
  Estado mediante el parcial del módulo y pie `flex flex-wrap justify-end gap-3`.
  Puede sumar «Enviar a validación» si existe la transición, con su capacidad y alcance,
  guardando y enviando en una transacción del POST actual. En edición dice «Guardar cambios».
  Cuando está disponible el envío, Guardar es `btn-secondary` y Enviar es `btn-brand`;
  con JS, Enviar queda `disabled` mientras el resumen indique campos faltantes y se
  habilita al completarlos. Sin JS queda habilitado: siempre valida el servidor.
  En alta, el header de duplicados incluye `badge badge-warning` con la cantidad
  de coincidencias visibles, actualizada por la búsqueda existente (sin revelar ajenas).
  Un código duplicado bloquea el envío y lleva su aviso a la vista y al foco;
  el contenedor es enfocable con `tabindex="-1"` y conserva la alerta canónica.
  sin envío, Guardar conserva `btn-brand`. Campos en `sm:grid-cols-2`, nombre y textarea
  de ancho completo mediante `wrapper_class="sm:col-span-2"` del campo canónico.
  Evidencia: `programas/templates/programas/dispositivos/legajo/form.html` (P3).
  Los asteriscos marcan requisitos para validar (`marca_requerido`, sin cambiar `required`); la bajada lo explica y el borrador admite incompletos.
  La coincidencia de nombre/localidad confirma con `ModernModal` canónico (`warning`, botón de marca); un error de búsqueda avisa con `window.toast`.
  La localidad es un `Select` común del campo canónico (el buscador `nodo-buscador.js` solo
  está cargado en el portal); un valor heredado fuera del catálogo se ofrece primero como
  «<valor> (cargado antes)». Días y horarios: las franjas guardadas van en la tabla canónica
  (`table w-full border-collapse` con `nodo-thead-row`/`nodo-th`, dentro de `overflow-x-auto`) con los campos ocultos del formset, y «Quitar»
  es `btn-tertiary btn-sm btn-fit`; la fila de carga usa el campo canónico en
  `sm:grid-cols-3` y «Agregar» es `btn-secondary btn-sm`, visible solo con JS. Sin JS,
  «Quitar» es el checkbox `DELETE` del formset. Un error que cruza filas va en la celda de su fila.

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
- **Confirmación de borrado** (ya listada arriba): **no** pasa `--arquetipo formulario`, y está bien.
  No tiene campos (así que no hay `_field.html` ni `_form_errores`) y su acción primaria es
  `btn-nodo btn-danger btn-base`, no `btn-brand`. El modo de marcadores no modela esa variante:
  se valida por revisión. Evidencia: los cinco `*_confirm_delete.html` de Configuración, por ejemplo
  `configuracion/templates/configuracion/provincia_confirm_delete.html`.
- **Paso de un wizard:** es del arquetipo Wizard (ficha `wizard.md`). Un paso que es una lista de
  campos sigue este esqueleto y pasa los marcadores; uno cuyo control es un grupo de radios con
  descripción por opción **no** (no cabe en `_field.html`). Evidencia:
  `configuracion/templates/configuracion/programa_wizard_paso3.html` contra
  `configuracion/templates/configuracion/programa_wizard_paso2.html`.

## Prohibido

- `<h1>` propio, «← Volver» de texto, header dentro de la card.
- `class="nodo-field"` escrito en el template sobre un control del form (lo pone el widget).
- Labels con valores arbitrarios (`block text-[13px] …`): el label canónico es
  `block text-sm font-medium text-heading mb-1` y lo rinde el include de campo.
- `<style>`, `style=`, paleta cruda, SVG inline.
- Resolver reglas de negocio o permisos en el template.
- `{{ form.non_field_errors }}` escrito a mano: la pieza es `components/_form_errores.html`.

## Alcance de la golden

El include de campo emite `aria-describedby` / `aria-invalid` mediante `campo_control`; el handler AJAX mantiene ese contrato al recibir un 400.
`user/_alta_rapida_modal.html` que la golden incluye es **de dominio**: no se copia.

## Checklist (la usa el revisor)

- [ ] `--arquetipo formulario` OK y `--ratchet` con 0 nuevos.
- [ ] `{% csrf_token %}` presente y método POST.
- [ ] Todos los campos salen del form (nada de `<input>` suelto sin `name` del form).
- [ ] Pie con Cancelar (`btn-tertiary btn-base`) y Guardar (`btn-brand btn-base`), en ese orden.
- [ ] Título calculado con `yesno` para alta/edición y `volver_url` a la lista.
- [ ] Los errores generales se muestran arriba con `role="alert"`.
- [ ] La validación está en el form o el servicio, no en la vista ni en el template.
