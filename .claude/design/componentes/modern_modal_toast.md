# Componente · `ModernModal` y toasts NODO

**Clasificación:** Canónico reutilizable. Los dos los carga el shell del backoffice: están
disponibles en cualquier pantalla sin incluir nada.
**Evidencia:** `templates/includes/base.html` (`#modal-overlay` y su script),
`static/custom/js/nodo-toast.js`, `static/custom/css/nodo-toast.css`,
`core/tests/test_modern_modal_contrato.py`.

## `ModernModal`

Motor de las confirmaciones del backoffice. Lo consumen el include
`programas/templates/programas/becas/_confirm_js.html` (`data-confirm-url`), el constructor de
formularios y las confirmaciones de cupo, caso y procesos masivos.

`ModernModal.show(options)`:

| Opción | Efecto |
|---|---|
| `type` | `confirm` muestra «Cancelar»; `success`, `error`, `warning` e `info` son avisos de un botón |
| `title` | Título |
| `message` | Mensaje; siempre se pinta con `textContent` |
| `confirmText`, `cancelText` | Textos de los botones |
| `onConfirm`, `onCancel` | Callbacks |
| `danger: true` (o `confirmVariant: 'danger'`) | Acción destructiva: botón `btn-danger`, ícono en tono danger y **foco inicial en Cancelar** (Enter-Enter no confirma) |
| `icon` | `warning`, `danger`, `question` o `info`, solo con `type:'confirm'`: fija el tono del ícono y manda sobre el default (sin `icon`: `danger` si es destructiva, «?» gris si no) |

- Pie con botones del sistema: «Cancelar» `btn-tertiary btn-base`, confirmar `btn-brand` o
  `btn-danger` en `btn-base`; en celular (≤ 640 px) queda **centrado, de alto automático y con el mismo
  margen a los dos lados** que los modales Alpine de las pantallas (`rounded-2xl`, tope `100dvh - 2rem`), con
  los botones a ancho completo. Lo fija `static/custom/css/mobile-modals.css` solo sobre `#modal-overlay > div`
  y `#modal-content`; las reglas `.modal`/`.modal-dialog` de esa hoja son de otras pantallas y no se tocan.
- Tras el primer confirmar/cancelar/cerrar ignora clics repetidos durante la animación de cierre
  (300 ms): `onConfirm` corre una sola vez. Si un `onConfirm` abre otro `ModernModal` (por
  ejemplo un aviso de error), el cierre diferido del primero no oculta al segundo.
- Escape, la X y el clic afuera cierran **sin** llamar a `onCancel`.
- **Para pedir un dato (motivo, fecha) no alcanza:** eso es el arquetipo Modal con form POST.
- Convive con la confirmación SweetAlert2, **legacy condicionada**, que siguen usando Dispositivos y
  Legajos; esas pantallas no se migran sin una decisión aparte. La copia del shell
  del portal es aparte y no sigue este contrato.

## Toasts

**Único sistema de avisos del producto:** `window.toast(tipo, mensaje)` —tipo primero—. No hay
toast local por módulo (nada de `becasToast`), y los templates hijos **no** repiten el bloque de
`{% for message in messages %}`: el shell convierte los mensajes de Django en toasts.

- Abajo a la derecha. `success`, `info` y `warning` duran 7 s con barra de progreso y pausa al
  pasar el mouse o con el foco.
- **Errores:** persisten (sin barra) hasta cerrarlos con el botón o con Escape (no si hay un modal
  abierto), salvo que se pase una duración explícita.
- **Aviso con lista (errores de un form):** `window.toast('error', '', { title, items: [{texto, href}] })`.
  La lista va en `ul.toast__lista` (scrollea pasados 40 vh) y cada ítem es `li.toast__message`; con `href`
  `#id` el ítem es un `a.toast__enlace` que baja al control y le da el foco, sin `href` es texto. Un aviso con
  `items` nunca se cierra solo (como un error persistente, salvo `duration` explícita), puede llevar mensaje
  vacío y todo el texto se pinta con `textContent`. No se arma a mano: lo abre el include
  `templates/components/_aviso_errores.html` (ver abajo).
- Máximo 3 visibles en escritorio y 1 en ≤ 640 px sin modal. Con un modal abierto en ≤ 640 px la
  pila se apoya bajo el encabezado y sobre el pie del modal **solo si** hay ≥ 120 px entre ambos;
  si no se pueden detectar o no hay espacio, los errores se comportan como un toast común mientras
  el modal esté abierto (7 s con barra, máx. 1, el más reciente) y al cerrarse vuelve la regla
  persistente.
- Mientras haya un error persistente visible y ningún modal abierto, el JS reserva en el
  `padding-bottom` del `<body>` el alto de la pila más el offset del breakpoint, para que el error
  no tape el pie de la página; al desaparecer se restaura el valor previo.
- Roles y live regions ya están resueltos: no se tocan.

## Aviso flotante con la lista de errores de un form

**Pieza:** `templates/components/_aviso_errores.html` + el tag `resumen_errores` de
`core/templatetags/nodo_ui.py` + `opts.items` de `nodo-toast.js` (y `.toast__lista`/`.toast__enlace` en
`nodo-toast.css`). **Test:** `core/tests/test_nodo_ui_piezas.py` (`AvisoErroresTest`).

```django
{% include "components/_form_errores.html" %}
{% include "components/_aviso_errores.html" %}
{% include "components/_aviso_errores.html" with form=form_domicilio %}
```

- Va después de `_form_errores.html`. **Suma** al error debajo de cada campo y al bloque de arriba; no los
  reemplaza. Sin JS, la pantalla queda como antes.
- `form` por contexto. Sin errores (sin bindear, válido o ausente) no dibuja nada. Un ítem por mensaje:
  «Etiqueta: mensaje» enlazado a `#<id del control>`; el error del conjunto va solo con el mensaje y sin enlace.
  Título «No se guardó: hay N cosas para corregir» («1 cosa»).
- La lista viaja en `<script type="application/json" id="aviso-errores">` (`json_script`, escapado). Un solo
  aviso por página: el JS del shell lo abre al cargar, baja al primer control con error y le da el foco.
  Tocar un ítem hace lo mismo con su control. Queda hasta cerrarlo (botón o Escape).
- Se usa en «Nuevo caso» de la mesa y en el Formulario 1 de la puerta (Emergencia). Otro formulario lo suma con
  el include, sin JS propio. E7 · Configuración (formset del catálogo, con el nombre del ítem en cada error)
  queda pendiente: necesita su propia lista armada desde los formsets.

## Prohibido

- `confirm()` o `alert()` nativos.
- Un sistema de avisos nuevo, un toast propio del módulo o un `Swal.fire` de aviso.
- Repetir el bloque de `messages` en un template hijo.
- Pasar HTML al `message` esperando que se renderice (va con `textContent`).
