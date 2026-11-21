# Componente · Ubicación sin mapa (`components/_ubicacion.html`)

**Clasificación:** Canónico reutilizable. Pieza única, sin variantes.
**Evidencia:** `templates/components/_ubicacion.html`, `core/tests/test_nodo_ui_piezas.py` (`UbicacionTest`).
**Consumidor de referencia:** `programas/templates/programas/dispositivos/legajo/detail.html`:
Datos recibe coordenadas del legajo; Infraestructura recibe las de cada edificio. En el MVP no
se pasa plano. La lectura de coordenadas comparte el queryset del inmueble, sin N+1.

## Por qué no hay mapa

Es la ubicación **de lectura** de una ficha: coordenadas legibles, un enlace que abre Google Maps **fuera** del
sistema (Cambio 493, fase 4) y el plano como adjunto. No carga nada en la página ni pide key. Si una pantalla
necesita el mapa adentro, usa la pieza Mapa con capas (`mapa_capas.md`), no esta.

## Invocación

```django
{% include "components/_ubicacion.html" with latitud=dispositivo.latitud longitud=dispositivo.longitud plano_url=plano.archivo.url plano_nombre=plano.nombre %}
```

| Parámetro | Efecto |
|---|---|
| `latitud`, `longitud` | Decimal o `None`. Se muestran con 6 decimales. Sin las dos: estado vacío y sin enlace |
| `plano_url` | Opcional. Enlace al plano del edificio, en pestaña nueva |
| `plano_nombre` | Texto del enlace del plano; por defecto «Plano del edificio» |
| `compacto` | Opcional. Sin coordenadas, el vacío es una línea con ícono («Sin ubicación cargada…», `text-sm text-body-subtle`) en vez de `_estado_vacio.html`. Con coordenadas no cambia nada |

Render: `dl` de dos columnas (mismo patrón que las solapas de datos) + `btn-secondary btn-sm`
«Ver en el mapa» + `btn-tertiary btn-sm` para el plano. El vacío reusa `_estado_vacio.html`.

## Reglas

- Los enlaces externos llevan `target="_blank"` y `rel="noopener noreferrer"`, con aviso
  `sr-only` de que abren una pestaña nueva.
- Las coordenadas del enlace van con `unlocalize` (punto decimal), nunca con la coma local.
- Va dentro de una card; no es una card propia.
- El badge «Geolocalizado» lo decide la pantalla con las mismas coordenadas; esta pieza no lo dibuja.

## Prohibido

- Cargar librerías de mapas, iframes o imágenes de tiles, o agregar orígenes a la CSP **desde esta pieza**.
- Armar el enlace al mapa a mano: sale de `core.coordenadas.url_en_google_maps` (tag `url_google_maps`).

## Lo que hay que saber antes de usarla

- **El plano no depende de las coordenadas.** Son dos datos independientes: un plano cargado se
  muestra aunque todavía nadie haya tomado las coordenadas del edificio, y el estado vacío cubre
  solo la parte de la ubicación. Al revés también: coordenadas sin plano se ven completas.
- **Un `0` cuenta como coordenada cargada.** El chequeo es contra `None` y contra la cadena vacía,
  así que `0` pasa. Si el modelo que la alimenta usa `0` por defecto en vez de `null`, el bloque va a
  mostrar «0,000000 / 0,000000» y enlazar a Null Island, frente a la costa de África. Hay que pasar
  `None`, no `0`.
- **`plano_url` tiene que venir de un archivo adjunto** (`FileField.url`), no de una URL libre. El
  autoescape protege del marcado, pero no de un esquema `javascript:`.
- **Los valores van como `Decimal`, `float` o `None`.** Un texto no numérico no rompe ni permite
  inyección —sale escapado—, pero produce un enlace con basura.
- **El proveedor del mapa está en un solo lugar:** `core.coordenadas.url_en_google_maps`, que usan esta pieza
  y el lugar de la toma de Becas. Si se cambia, hay que actualizar también la lista de permitidos de
  `SinRecursosDeTercerosTests` (`portal/tests/test_seguridad_publica.py`), que hoy admite
  `https://www.google.com/maps/search/`. No es un recurso de terceros —es un `<a>` que navega fuera— pero el
  barrido de ese test no distingue el atributo.
