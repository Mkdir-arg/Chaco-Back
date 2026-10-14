# Componente · Galería fotográfica histórica (`components/_galeria_fotos.html`)

**Clasificación:** Canónico reutilizable. Pieza única, sin variantes.
**Evidencia:** `templates/components/_galeria_fotos.html`, `core/tests/test_nodo_ui_lote_b.py`
(`GaleriaFotosTest`).
**Consumidores de referencia:** `templates/components/_linea_tiempo.html`, que la anida dentro de cada
evento que trae `fotos` (ficha `ficha_timeline.md`); a través de ella, la solapa Infraestructura del
detalle de Dispositivos (`programas/templates/programas/dispositivos/legajo/detail.html`, mockup P19),
una tanda por relevamiento.

En P19, `fecha` es `InspeccionEdificio.realizada_en`, la misma del evento. Una foto de un
relevamiento en curso omite fecha: no se rotula con la fecha de subida dentro de otra tanda.
`_evento_de_relevamiento` adapta los dicts de `fotos_para_galeria` solo para P19; el informe
del relevamiento conserva su fecha de carga.

En esa solapa, cada tanda pertenece al edificio del relevamiento. El encabezado del inmueble
ofrece editar y desvincular con `dispositivo.editar` sobre la institución; desvincular conserva
las tandas y solo retira su acceso desde ese legajo. El vacío sin edificio enlaza a «Cargar
edificio» para quien puede editar. Alta, edición y vínculo usan las partes del modal canónico,
sin cambiar el contrato de la galería.

## Invocación

```django
{% include "components/_galeria_fotos.html" with fotos=fotos_de_la_tanda total=tanda.cantidad_fotos %}
```

| Parámetro | Efecto |
|---|---|
| `fotos` | Lista de dicts (no queryset) armada por la vista: `url`, `alt`, `rotulo` y `fecha` |
| `total` | Opcional: cantidad real si la vista mandó menos de las que hay |

Render: `ul` en grilla (`grid-cols-2` a `lg:grid-cols-6`, `gap-3`) con un `figure` por foto: imagen
`h-24 w-full object-cover` y `figcaption` con el rótulo y la fecha en un `<time>`. Va dentro de una card;
no es una card propia.

## Reglas

- **Las imágenes viven en `media/`, que se sirve detrás de login.** `url` tiene que ser la URL de un
  archivo adjunto servido por la vista autenticada: nunca una URL pública, un CDN ni un enlace libre.
- Cada imagen lleva `loading="lazy"`, `decoding="async"` y un `alt` real (si falta, el rótulo). La foto
  abre en pestaña nueva (`rel="noopener noreferrer"`, con aviso `sr-only`).
- Una foto sin `url` se dibuja como la celda gris con cámara del mockup, con su texto para lectores de pantalla.

## Tope

Una galería sin tope carga decenas de imágenes de golpe. **El recorte es de la vista**: una tanda por
vez, con paginación o «ver más»; la pieza dibuja **hasta 24 fotos** como red de seguridad y avisa
«Mostrando 24 de N fotos». Lista vacía: estado vacío canónico.

## Límites actuales

- **Dentro de una línea de tiempo no se incluye a mano:** se pasa como `fotos` + `total_fotos` del evento
  y `components/_linea_tiempo.html` la dibuja adentro del `<li>`. Suelta, va dentro de su card.
- Un formato que el navegador no dibuja (HEIC/HEIF) va con `url` vacía desde la vista: queda la celda gris
  con cámara en vez de una imagen rota. Es un manejo **de legado**: desde que
  `core.validators.FOTO_EXTENSIONES` rechaza HEIC/HEIF no entra ninguna nueva, y la app de campo convierte
  a JPEG antes de enviar.
- No hay manejo de imagen rota (sería JS): la vista no debería mandar una `url` cuyo archivo no existe.

## Prohibido

- Pasar URLs públicas o externas; dibujar las fotos sin `loading="lazy"`; un `alt` genérico («foto»).
- Armar la grilla de fotos a mano en una pantalla.
