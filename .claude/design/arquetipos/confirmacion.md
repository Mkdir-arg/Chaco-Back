# Arquetipo · Confirmación sí/no (y guardado AJAX)

**Golden:** el include `programas/templates/programas/becas/_confirm_js.html` + un botón con
`data-confirm-url`, que abre el `ModernModal` del shell (`templates/includes/base.html`).
**Transversal:** se incluye desde esa ruta también fuera de Becas (solo depende de
`ModernModal`, que ya carga el shell del backoffice).
**Componentes:** modern_modal_toast · botones_badges.
Tests: `programas/tests/test_becas_feedback_js.py`, `core/tests/test_modern_modal_contrato.py`.

## Cuándo

Acción que muta y **no pide ningún dato**: desactivar, eliminar, reenviar, promover. Si hay que
pedir un motivo o una fecha, el arquetipo es Modal (ficha `arquetipos/modal.md`). Nunca
`confirm()` nativo ni un `Swal.fire` nuevo.

## Esqueleto

```django
{% load nodo_ui %}

<button type="button" class="nodo-icon-btn nodo-icon-btn--danger"
        aria-label="Desactivar <entidad> {{ obj.nombre }}"
        data-confirm-url="{% url '<app>:<entidad>_desactivar' obj.pk %}"
        data-confirm-title="¿Desactivar <entidad>?"
        data-confirm-text="{{ obj.nombre }} deja de estar disponible. Se puede volver a activar."
        data-confirm-ok="Sí, desactivar"
        data-confirm-danger="true">
  <i class="fas fa-ban" aria-hidden="true"></i>
</button>

{% block customJS %}{% include "programas/becas/_confirm_js.html" %}{% endblock %}
```

## Contrato del include (leído del código)

| Atributo | Efecto |
|---|---|
| `data-confirm-url` | **Obligatorio.** El click arma un `<form method="POST">` a esa URL con el token CSRF y lo envía. Un solo POST por confirmación (`data-confirm-enviado` lo marca y `pageshow` lo limpia al volver con «atrás») |
| `data-confirm-title` | Título; por defecto «¿Confirmás la acción?» |
| `data-confirm-text` | Mensaje; siempre se pinta con `textContent` |
| `data-confirm-ok` | Texto del botón, en forma «Sí, <verbo>»; por defecto «Sí, confirmar» |
| `data-confirm-danger` | `"true"`/`"false"`: decide el botón rojo de forma explícita y manda sobre el ícono |
| `data-confirm-icon` | `warning`, `danger`, `question` o `info`; viaja a `ModernModal` solo si está puesto. Sin `data-confirm-danger`, `warning` (el default) se trata como destructiva |

El token sale del `[name=csrfmiddlewaretoken]` de la página o de la cookie `csrftoken`.

## Guardado AJAX de los formularios de modal

`programas/templates/programas/becas/_ajax_js.html` (también transversal) maneja los
`<form data-ajax>`. Contrato JSON que la vista tiene que respetar:

- **2xx `{ok, target, html, message}`** → reemplaza el nodo `target`, re-inicializa Alpine,
  dispara el evento `becas-saved` y avisa `success`.
- **2xx `{ok, redirect, message}`** → navega; el mensaje lo muestra la página destino y el
  botón queda ocupado hasta cambiar de página.
- **400 `{ok:false, errors}`** → cada error va a su `<p data-error="campo">` (el general a
  `data-error="__all__"` si el form lo tiene) y se emite **un** aviso `error` «Revisá los datos
  del formulario.»; solo lo que no tiene lugar inline se suma al aviso.
- **409 `confirm_required`** → abre `ModernModal` `type:'confirm'`, `icon:'warning'`, título
  «¿Asignar igual?» y botón «Sí, asignar igual» (marca, no destructivo), y reenvía **una sola
  vez** con `confirmar_solapamiento=1` vía `requestSubmit()` (el campo se agrega para ese envío
  y se quita después).
- **403, error de servidor y red** → avisan `error`. CSRF por la cookie `csrftoken`.

Mientras el pedido está en curso el form lleva `aria-busy`, todos sus submit (también los de
afuera con `form="id"`) quedan deshabilitados y el que envió muestra «Guardando…» con spinner;
al terminar se restauran los nodos originales (no `innerHTML`, para no romper los bindings de
Alpine) y el `disabled` previo. Un segundo submit durante el envío se ignora.

## Piezas hermanas del mismo sistema

- `programas/templates/programas/becas/relevamientos/_cascada_localidad.html`: selects
  dependientes que se llenan por `fetch`; el error de red avisa con `window.toast('error', …)`,
  nunca en silencio.
- `programas/templates/programas/becas/relevamientos/_copiar_link_js.html`: copiar un link.
  El éxito avisa `success`. Sin permiso o sin API de portapapeles **nunca** aparece la ventana
  nativa: se selecciona el campo de solo lectura del mismo bloque si ya muestra el link, o se
  abre un popover (`role="dialog"`, cierre con botón, Escape o clic afuera) con el link en un
  `nodo-field` de solo lectura ya seleccionado, más un aviso `warning` «Copialo manualmente: el
  link quedó seleccionado.».

## Prohibido

- `confirm()` nativo.
- `data-confirm` a secas: es el contrato **legacy condicionado** de Dispositivos y Merenderos, que
  vive en `programas/templates/programas/_swal_confirm_js.html` y declara el tono con
  `data-confirm-danger`. Compite con este contrato y no se copia a UI nueva; tampoco se reimplementa
  el handler en la pantalla.
- `Swal.fire` nuevo. SweetAlert queda **legacy condicionado** en las pantallas de Dispositivos,
  Merenderos y Legajos que ya lo usan; esas pantallas no se migran sin decisión aparte, y antes
  de llamarlo hay que verificar que la pantalla cargue SweetAlert2.
- Colores invertidos: lo destructivo es rojo y arranca con el foco en «Cancelar»; una
  advertencia que no destruye va con `icon:'warning'` y botón de marca.
- Un toast de éxito además del inline cuando el indicador de la pantalla ya lo informa.

## Checklist (la usa el revisor)

- [ ] Toda acción que muta va por POST con CSRF (nunca un `<a href>` que borra).
- [ ] La confirmación usa `data-confirm-url`; el include está en `customJS`.
- [ ] `data-confirm-ok` dice el verbo; `data-confirm-danger` es explícito.
- [ ] Un solo POST por confirmación, también con doble clic.
- [ ] Los avisos salen por `window.toast`, sin bloque de `messages` propio en el template.
