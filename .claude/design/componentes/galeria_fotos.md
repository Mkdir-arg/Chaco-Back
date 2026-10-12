# Componente · Galería fotográfica histórica (`components/_galeria_fotos.html`)

**Clasificación:** Canónico reutilizable. Pieza única, sin variantes.
**Evidencia:** `templates/components/_galeria_fotos.html`, `core/tests/test_nodo_ui_lote_b.py`
(`GaleriaFotosTest`).
**Consumidores de referencia:** ninguno todavía; lo usará la solapa Infraestructura del detalle de
Dispositivos (mockup P19).

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

- **No va dentro de un evento de la línea de tiempo** (`components/_linea_tiempo.html`): esa pieza no tiene
  slot de cuerpo. Por ahora es una pieza propia dentro de su card; cuando la línea de tiempo tenga cuerpo,
  se anida sin cambiar esta pieza.
- No hay manejo de imagen rota (sería JS): la vista no debería mandar una `url` cuyo archivo no existe.

## Prohibido

- Pasar URLs públicas o externas; dibujar las fotos sin `loading="lazy"`; un `alt` genérico («foto»).
- Armar la grilla de fotos a mano en una pantalla.
