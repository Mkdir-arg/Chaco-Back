# Componente · Cargador de Google Maps (`components/_google_maps.html`, `nodo-mapa.js`)

**Clasificación:** Canónico reutilizable. Pieza única de infraestructura, sin markup visible.
**Evidencia:** `templates/components/_google_maps.html`, `static/custom/js/nodo-mapa.js`, tag
`google_maps_config` de `core/templatetags/nodo_ui.py`, `GOOGLE_MAPS_SOURCES` de
`config/middlewares/security_headers.py`, `core/tests/test_nodo_ui_piezas.py` (`GoogleMapsCargadorTest`).
**Consumidores:** `components/_ubicacion_domicilio.html` (domicilio → coordenadas) y
`components/_mapa_capas.html` (mapa de puntos con capas). Lo va a usar también el lugar de la toma de Becas.
Una pantalla no arma marcadores a mano sobre `NodoMapa`: usa una de esas dos piezas. Guía operativa: `docs/mapa.md`.

## Invocación

Una sola vez, en el bloque `customJS` de la pantalla que dibuja un mapa:

```django
{% block customJS %}
  {% include "components/_google_maps.html" %}
  <script>
    if (window.NodoMapa.configurado) {
      NodoMapa.crearMapa(document.getElementById('mapa-x'), { zoom: 15 }).then(function (mapa) { … });
    }
  </script>
{% endblock %}
```

| API (`window.NodoMapa`) | Efecto |
|---|---|
| `configurado` | `false` sin `GOOGLE_MAPS_API_KEY`: la pantalla no intenta cargar y muestra su estado vacío |
| `crearMapa(elemento, opciones)` | `Promise<google.maps.Map>` con el Map ID del ambiente, centro en Resistencia, zoom 13, sin controles de tipo de mapa, Street View ni pantalla completa, POI no clicables y `gestureHandling: 'cooperative'`. `opciones` pisa cualquiera |
| `importar('marker', 'geocoding', …)` | `Promise` con las librerías pedidas (`google.maps.importLibrary`) |
| `cargar()` | `Promise<google.maps>`; la usan las dos anteriores |
| evento `nodo-mapa:error` en `document` | La key no vale para el sitio (`gm_authFailure`); `detail.mensaje` en castellano |

## Reglas

- **Google se pide en la primera llamada, no al cargar la página.** Un mapa a pedido (SEC-33) sigue sin
  mandarle nada a Google hasta que alguien lo abre.
- **Marcadores con `AdvancedMarkerElement`** (`importar('marker')`), nunca `google.maps.Marker`
  (deprecado). Por eso el Map ID es obligatorio; `DEMO_MAP_ID` solo en `dev` y `core.W005` avisa en
  `qa`/`prd`.
- La CSP se abre a Google **solo con key configurada** (`GOOGLE_MAPS_SOURCES`), como GTM.
- Al cargar, la página pasa a `Referrer-Policy: strict-origin-when-cross-origin` (meta `referrer` +
  `script.referrerPolicy`): sin `Referer`, Google rechaza la key restringida por referente. Solo viaja el
  origen; antes de pedir el mapa la página sigue con el `same-origin` de Django.
- El script de Google se carga desde JS (`maps.googleapis.com/maps/api/js?…&loading=async&callback=`):
  ninguna plantilla escribe un `<script src="https://…">` (`SinRecursosDeTercerosTests`).

## Prohibido

- Pegar el script de Google o el *bootstrap loader* inline en una pantalla, o cargarlo dos veces.
- Escribir la key en el código o en una plantilla: sale de settings.
- Usar `google.maps.Marker`.
