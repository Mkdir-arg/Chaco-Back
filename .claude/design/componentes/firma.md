# Componente · Campo «Firma» (`FirmaWidget`, `nodo-firma.js`, `_firma_respondida.html`)

**Clasificación:** Canónico reutilizable. Pieza única (Cambio 480).
**Evidencia:** `programas/forms_dinamicos.py` (`FirmaField`, `FirmaWidget`, `imagen_desde_trazo`),
`programas/templates/programas/widgets/firma.html`, `static/custom/js/nodo-firma.js`,
`static/custom/css/nodo-forms.css` (`.nodo-firma__lienzo`, `.nodo-firma__canvas`),
`templates/components/_firma_respondida.html`, `programas/services/firma.py`.
**Consumidores de referencia:** formulario del tipo de dispositivo (`programas/templates/programas/dispositivos/legajo/_formulario_tipo.html`,
vía `components/_field.html`) y paso 2 de la inscripción pública (`portal/templates/portal/inscripcion/paso2.html`, `{{ item.bound }}`).

## Para firmar

Un campo `TipoCampo.FIRMA` del constructor se dibuja con `FirmaWidget` (un `MultiWidget`), dentro del
mismo `_field.html` que cualquier campo: recuadro `<canvas>` de 600x200 con fondo blanco, botón
«Limpiar» (`btn-tertiary btn-sm btn-fit`, `fa-eraser`) y dos `nodo-field`: «Nombre y apellido de quien
firma» y «DNI». El trazo se dibuja con eventos de puntero (dedo, lápiz o mouse) y, al terminar cada
trazo, `nodo-firma.js` escribe el PNG (`data:image/png;base64,…`) en el campo oculto `data-firma-trazo`
y dispara `change`: eso leen las condiciones (`nodo-formulario.js`, `nodo-formulario-tipo.js`) y el panel
de faltantes. No intercepta el envío, así que anda en los formularios que llegan por AJAX; el script va
por delegación y se puede cargar más de una vez (el widget lo incluye; las pantallas de Dispositivos lo
cargan junto a `nodo-formulario-tipo.js`).

- `touch-action: none` en el canvas: el dedo dibuja, no desplaza la página.
- Una firma ya guardada se muestra arriba («Ya firmó: Ana Gómez · DNI … · fecha») y no se precarga en el
  recuadro: firmar de nuevo la reemplaza.
- Un formulario que vuelve con errores redibuja el trazo desde el campo oculto.
- Firmar a medias (trazo sin nombre o DNI, o al revés) es error del campo; el DNI usa la regla única de
  `core.dni`.

## Para ver una firma

`{% include "components/_firma_respondida.html" with adjunto=… firmante=… etiqueta=… only %}`: la
imagen (`h-16 w-40`, `object-contain`, enlace a la imagen) y «Firmó: …» en `text-xs text-body-subtle` con
`fa-signature`. Sin imagen todavía (la app la sube después de los datos), `badge-warning` «Falta la
imagen de la firma». La usan la revisión de Becas (`_respuesta_valor.html`), el formulario respondido de
Dispositivos y el informe del relevamiento edilicio; las tres reciben `es_firma` y `firmante` del
servicio, nunca arman el texto en el template.

## No

- No es una firma digital con certificado: no se le pone «firmado digitalmente» ni un sello.
- No se usa una librería de firma: el canvas y los eventos de puntero alcanzan, y no cambia la CSP.
