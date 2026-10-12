# Arquetipo · Wizard (alta o edición en pasos)

**Golden (la única que se clona):** `configuracion/templates/configuracion/programa_wizard_paso4.html`
(paso final: resumen + confirmación). Un paso intermedio con lista de campos es
`configuracion/templates/configuracion/programa_wizard_paso3.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo wizard <archivo>` (están pensados para el
paso final; un paso intermedio no lleva resumen `<dl>`).
**Componentes:** stepper · page_header · field · form_errores · alerta · botones_badges.

## Cuándo

Un alta o edición que **no entra en una sola pantalla**: pasos que dependen unos de otros, con
validación por paso y un resumen antes de confirmar. Si cabe en una página, es Formulario; si es
corta y no vale perder el contexto, es Modal. Pasos que el usuario puede completar en cualquier
orden son solapas de un Detalle, no un wizard.

## Contrato de la vista (Django)

- **Una URL por paso.** Cada paso es una vista con su Django Form; el estado entre pasos va en
  sesión y se guarda **solo cuando el form del paso es válido** (esa es la validación por paso).
- Un paso al que se llega sin haber completado el anterior **redirige** a ese anterior.
- Solo el paso final **escribe** en la base, con un servicio, en una transacción, y limpia la sesión.
- La vista arma el contexto del indicador (`pasos`, `paso_actual`, `total_pasos`): en
  Configuración, `_contexto_pasos(paso, programa=None)`. El template no calcula nada de dominio.
- La bajada del encabezado dice «Paso N de M · qué se carga».

## Esqueleto del paso final (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load nodo_ui %}
{% block title %}<Módulo> · {% if es_edicion %}Editar{% else %}Nuevo{% endif %} <entidad> — Paso {{ paso_actual }}{% endblock %}

{% block main-content %}
<div class="space-y-5">
  {% url '<app>:<lista>' as url_lista %}
  {% with titulo_pagina=es_edicion|yesno:"Editar <entidad>,Nuevo <entidad>" %}
  {% page_header titulo=titulo_pagina volver_url=url_lista volver_label="<entidades>" %}
    {% bajada %}Paso {{ paso_actual }} de {{ total_pasos }} · <qué se carga y confirma>.{% endbajada %}
  {% endpage_header %}
  {% endwith %}

  {% include "components/_stepper.html" with pasos=pasos paso_actual=paso_actual %}

  <div class="bg-white rounded-xl border border-base shadow-sm p-6">
    <h2 class="text-heading font-bold">Resumen de <entidad></h2>
    <dl class="mt-3 space-y-1 text-sm text-body">
      <div class="flex gap-2"><dt class="font-medium text-heading w-32"><Dato>:</dt><dd>{{ resumen.<dato> }}</dd></div>
    </dl>
    <p class="mt-3 text-xs text-body-subtle"><qué pasa al confirmar></p>
  </div>

  <form method="post" class="bg-white rounded-xl border border-base shadow-sm p-6">
    {% csrf_token %}
    {% include "components/_form_errores.html" %}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {% for field in form %}{% include "components/_field.html" %}{% endfor %}
    </div>
    <div class="flex justify-between gap-3 mt-6 pt-4 border-t border-light">
      <a href="<url del paso anterior>" class="btn-nodo btn-tertiary btn-base"><i class="fas fa-arrow-left" aria-hidden="true"></i> Anterior</a>
      <button type="submit" class="btn-nodo btn-brand btn-base"><i class="fas fa-check" aria-hidden="true"></i> Confirmar <entidad></button>
    </div>
  </form>
</div>
{% endblock %}
```

## Variantes permitidas

- **Paso intermedio:** igual, sin la surface de resumen y con «Siguiente» (`fa-arrow-right`) en
  lugar de «Confirmar». Primer paso: el pie lleva «Cancelar» (`btn-tertiary`) a la izquierda de
  «Siguiente», sin «Anterior» (ver `programa_wizard_paso1.html`).
- **Último paso que solo confirma:** el `<form>` lleva solo el `csrf_token`, `_form_errores` y el pie.
- **Control que no cabe en `_field.html`** (grupo de radios con descripción por opción): conserva
  shell, indicador, surface, `_form_errores` y pie; no pasa los marcadores del arquetipo Formulario
  (evidencia: `programa_wizard_paso2.html`).
- Avisos de situación dentro de un paso (bloqueos, advertencias): `components/_alerta.html`.

## Prohibido

- Barra de progreso a mano o un stepper propio: el indicador es `components/_stepper.html`.
- Pasos pendientes clicables, o un paso que escribe en la base antes del final.
- Validar en el template o confiar en que el paso anterior ya validó: cada vista revalida.
- `<h1>` propio, `<style>`, `style=`, paleta cruda, SVG inline, `{{ form.non_field_errors }}`.
- Un `confirm()` o `Swal.fire` en el paso final: la confirmación es el submit del paso.

## Checklist (la usa el revisor)

- [ ] `--arquetipo wizard` OK en el paso final y `--ratchet` con 0 nuevos.
- [ ] El indicador marca el paso actual (`aria-current`) y los hechos son links.
- [ ] Cada paso valida con su form y redirige si falta el anterior.
- [ ] El resumen sale de lo guardado en sesión, no de campos recalculados en el template.
- [ ] El paso final escribe con un servicio, en transacción, y limpia la sesión.
- [ ] Pie con «Anterior» (`btn-tertiary btn-base`) y la acción primaria (`btn-brand btn-base`).
