# Componente · Ubicación sin mapa (`components/_ubicacion.html`)

**Clasificación:** Canónico reutilizable. Pieza única, sin variantes.
**Evidencia:** `templates/components/_ubicacion.html`, `core/tests/test_nodo_ui_piezas.py` (`UbicacionTest`).
**Consumidores de referencia:** ninguno todavía; lo usará la solapa Infraestructura del detalle de
Dispositivos.

## Por qué no hay mapa

La CSP de `SecurityHeadersMiddleware` bloquea los CDN y el repo no trae ninguna librería de mapas.
La ubicación se resuelve con coordenadas legibles, un enlace que abre el mapa **fuera** del sistema
y el plano como adjunto. El mapa embebido no se agrega.

## Invocación

```django
{% include "components/_ubicacion.html" with latitud=dispositivo.latitud longitud=dispositivo.longitud plano_url=plano.archivo.url plano_nombre=plano.nombre %}
```

| Parámetro | Efecto |
|---|---|
| `latitud`, `longitud` | Decimal o `None`. Se muestran con 6 decimales. Sin las dos: estado vacío y sin enlace |
| `plano_url` | Opcional. Enlace al plano del edificio, en pestaña nueva |
| `plano_nombre` | Texto del enlace del plano; por defecto «Plano del edificio» |

Render: `dl` de dos columnas (mismo patrón que las solapas de datos) + `btn-secondary btn-sm`
«Ver en el mapa» + `btn-tertiary btn-sm` para el plano. El vacío reusa `_estado_vacio.html`.

## Reglas

- Los enlaces externos llevan `target="_blank"` y `rel="noopener noreferrer"`, con aviso
  `sr-only` de que abren una pestaña nueva.
- Las coordenadas del enlace van con `unlocalize` (punto decimal), nunca con la coma local.
- Va dentro de una card; no es una card propia.
- El badge «Geolocalizado» lo decide la pantalla con las mismas coordenadas; esta pieza no lo dibuja.

## Prohibido

- Cargar librerías de mapas, iframes o imágenes de tiles; agregar orígenes a la CSP.
- Armar el enlace al mapa a mano en una pantalla.
