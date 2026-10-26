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
- Solo el paso final **escribe** en la base, y limpia la sesión. La golden escribe con un
  `Model.objects.create()` suelto porque toca **una sola fila** y nada de lo que eligió en los pasos
  previos se lo puede llevar otro mientras tanto. **No copies eso sin pensarlo.**
- **El paso final escribe lo que la pantalla mostró, no lo que hay en la sesión.** El estado del
  wizard vive en la sesión, y **la sesión la comparten todas las pestañas** del mismo usuario: si en
  otra pestaña se avanza con otra persona u otra elección, el «Confirmar» de la primera escribiría lo
  de la segunda, que esa pantalla nunca mostró. Por eso **el formulario de cada paso que decide algo
  lleva en campos ocultos lo que mostró**, y la vista lo compara con la sesión: si no coinciden, no
  escribe y vuelve a mostrar el paso con un aviso. Una clave de sesión por intento **no alcanza**:
  una pestaña duplicada o el botón «atrás» comparten el mismo intento. El estado se guarda además
  **por objeto** —por dispositivo, por programa—, para que abrir el wizard de otro no borre el
  progreso del primero. Pasó en el ingreso a un dispositivo, donde alojaba a la persona equivocada.
- Elegir dentro de un paso —una plaza en el mapa— **no escribe la sesión**: solo marca la elección.
  Recién el botón que avanza, por POST, la guarda.
- **Revalidar en el paso final lo que pudo cambiar mientras el usuario completaba el wizard.** Entre el
  paso 1 y el paso 4 pasan minutos; lo que ahí se validó puede haber dejado de ser cierto. Si el
  wizard reserva algo que otro puede tomar —una plaza, un lugar del cupo, un código único—, el paso
  final **revalida y escribe dentro de `transaction.atomic()`, tomando la fila con
  `select_for_update()`**, y si ya no está disponible vuelve al paso que la eligió con el error, en vez
  de dejar que reviente. Cuando eso pasa de una fila, va en un servicio.
  El ingreso de Dispositivos es exactamente ese caso: la plaza elegida en el paso 2 puede ocuparse
  antes del paso 4, así que **no alcanza con clonar la golden** — hay que agregarle el bloqueo.
  La golden misma tiene la versión chica del problema: `Programa.codigo` es `unique=True` y se valida
  en el paso 1, así que dos altas simultáneas del mismo código terminan en `IntegrityError`.
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
  En el paso de plaza de Dispositivos, el include real `components/_mapa_plazas.html` reemplaza
  el marcador de campo del auditor Wizard; no hay campos visibles ni un include ficticio.
  El mapa queda a la izquierda (`lg:col-span-2`) y Persona a la derecha, en la grilla
  `grid grid-cols-1 lg:grid-cols-3 gap-5`: distribución de la golden de Revisión con
  la separación de 5 pedida en el encargo (la golden usa 4). Los datos usan los
  rótulos `text-xs font-semibold uppercase text-body-subtle` de P7, también en el resumen final;
  el DNI visible va con `|dni` (`nodo_ui`), como en P7.
- Avisos de situación dentro de un paso (bloqueos, advertencias): `components/_alerta.html`.
  En el paso de plaza, la ocupación crítica usa tono `warning` debajo del mapa y dice «El sistema no bloquea el ingreso.»; la vista arma porcentaje y texto con los umbrales del tipo, desde `services.ocupacion`.
- Alta mínima dentro de un paso (paso 1 de Dispositivos, cuando la persona no está en el legajo ni en el Registro de Personas): `components/_alerta.html` tono `warning` y, debajo, una segunda tarjeta-formulario con `_field.html`, su propio `csrf_token`, un oculto `accion` y un oculto `persona` con lo que la pantalla mostraba. No es una pieza nueva.
- Pie que no cabe en móvil: `flex flex-wrap justify-between gap-3`; si agrupa acciones,
  el grupo también usa `flex flex-wrap gap-3`. Conserva los tamaños canónicos de botón
  y la fila de escritorio. Evidencia: `programas/templates/programas/dispositivos/ingreso/paso_plaza.html`.

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
- [ ] Cada paso que decide algo lleva en ocultos lo que mostró, y la vista lo compara con la
  sesión antes de escribir. El estado de la sesión se guarda por objeto, no uno global.
- [ ] El paso final limpia la sesión, y **revalida lo que pudo cambiar entre pasos**: si reserva algo
  disputable, escribe en `atomic()` con la fila bloqueada y vuelve al paso que la eligió si se ocupó.
- [ ] Pie con «Anterior» (`btn-tertiary btn-base`) y la acción primaria (`btn-brand btn-base`).
