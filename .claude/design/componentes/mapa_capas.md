# Componente · Mapa con capas (`components/_mapa_capas.html`, `nodo-mapa-capas.js/.css`)

**Clasificación:** Canónico reutilizable.
**Evidencia:** `templates/components/_mapa_capas.html`, `static/custom/js/nodo-mapa-capas.js`,
`static/custom/css/nodo-mapa-capas.css`, `core/tests/test_nodo_ui_piezas.py` (`MapaCapasTest`). Se apoya en el
cargador de Google Maps (`mapa_google.md`).
**Consumidores previstos:** `/mapa/` (Cambio 493, fase 3) y la solapa «Mapa» del tablero «Situación» de
Emergencia (E8: C1 #1173, E-6 #1185). Una pantalla con mapa de puntos usa esta pieza: no arma sus marcadores a
mano sobre `NodoMapa`.

## Invocación

```django
{% block page_css %}<link rel="stylesheet" href="{% static 'custom/css/nodo-mapa-capas.css' %}">{% endblock %}

<div class="nodo-mapa-escena">
  {% include "components/_mapa_capas.html" with nombre="mapa" puntos=puntos capas=capas etiqueta="Mapa" alto="pagina" only %}
  <aside class="nodo-mapa-panel" data-mapa="mapa" aria-label="Capas y lista">
    <button type="button" class="nodo-mapa-panel__asa">Capas y lista</button>
    <div class="nodo-mapa-panel__cuerpo">
      <input type="search" class="nodo-field" data-mapa-buscar aria-label="Buscar en el mapa">
      {% for capa in capas %}<button type="button" data-mapa-capa="{{ capa.id }}" aria-pressed="true">{{ capa.nombre }} <span data-mapa-capa-n></span></button>{% endfor %}
      <div class="nodo-mapa-panel__lista" role="group" aria-label="En el mapa">
        {% for p in puntos %}{% include "components/_item_lista.html" with nombre=p.titulo meta=p.subtitulo clave=p.id only %}{% endfor %}
      </div>
      <p data-mapa-vacio hidden>Nada coincide con la búsqueda.</p>
    </div>
  </aside>
</div>

{% block customJS %}
  {% include "components/_google_maps.html" %}
  <script src="{% static 'custom/js/nodo-mapa-capas.js' %}"></script>
{% endblock %}
```

| Parámetro | |
|---|---|
| `nombre` | Obligatorio, `[a-z0-9-]`. Identifica el mapa; los controles de afuera lo nombran con `data-mapa` |
| `puntos` | Lista de dicts de la vista. Obligatorios `id`, `capa`, `lat`, `lng`, `etiqueta`, `icono`, `tono`, `titulo`; opcionales `subtitulo`, `estado {texto, tono}`, `datos [[etiqueta, valor]]`, `url` + `url_texto`, `acciones [{accion, texto, icono, tono}]`, `grupo`, `movible` |
| `capas` | `[{id, nombre, icono, tono}]` para la leyenda de la pantalla |
| `etiqueta` | Nombre accesible del mapa |
| `alto` | `"pagina"`: mapa protagonista (`max(560px, 100dvh − 230px)`). Por defecto, 420 px |
| `a_pedido` | `True`: «Ver mapa» y nada a Google hasta tocarlo (SEC-33) |

`tono`: `brand`, `success`, `warning`, `danger`, `info`, `gray`, `navy` (la variante fuerte de cada token, para
leerse sobre el mapa). Cualquier otro valor se dibuja `gray`; un ícono que no es `fa-…` cae a `fa-location-dot`.

| Atributo en la pantalla | La pieza |
|---|---|
| `[data-mapa-capa="<id>"]` | Alterna la capa y su `aria-pressed`; escribe la cantidad en su `[data-mapa-capa-n]` |
| `[data-mapa-grupo="<valor>"]` | Alterna el subfiltro por `grupo` |
| `[data-mapa-buscar]` | Filtra por título, subtítulo y etiqueta, sin tildes |
| `[data-item="<id>"]` | Centra el punto y abre su detalle; `aria-pressed` en el elegido; se oculta (o su `<li>`) si un filtro lo deja afuera |
| `[data-mapa-total]` / `[data-mapa-vacio]` | Cantidad visible / se muestra si no queda ninguno |

| Evento en el contenedor (`[data-mapa-capas]`) | `detail` |
|---|---|
| `nodo-mapa-capas:listo` | — |
| `nodo-mapa-capas:seleccion` | `{id}` (`null` al cerrar) |
| `nodo-mapa-capas:accion` | `{id, accion}` |
| `nodo-mapa-capas:movido` | `{id, lat, lng}`: la pantalla guarda |
| `nodo-mapa-capas:clic` | `{lat, lng}`, solo con `modoClic(true)` |

API: `contenedor.nodoMapaCapas.{seleccionar(id), cerrar(), encuadrar(), agregar(punto), quitar(id), modoClic(si)}`.

## Reglas

- **La vista arma cada punto.** Capa, color, textos y enlace salen del servidor; el JS no decide qué se muestra a
  quién. Lo que una persona no puede ver no viaja en `puntos` (en E8, nunca la coordenada de un caso).
- **Textos como texto.** El JS arma el detalle con `textContent`; `url` solo se dibuja si es una ruta del sitio
  (`/…`, no `//`).
- **Panel de la pantalla, sincronizado por la pieza.** `nodo-mapa-escena` + `nodo-mapa-panel` dan el panel
  flotante (al costado en escritorio, hoja inferior en celular con `.is-abierto`); el encuadre deja ese margen
  libre. Un panel fuera del mapa también vale.
- **Solo se arrastra lo `movible`**, y la pieza no guarda: emite `movido` y la pantalla hace el `PATCH`.
- Google se pide cuando el mapa entra en pantalla; con `a_pedido`, recién con «Ver mapa». Sin key, estado vacío
  (`_estado_vacio.html`); con la key rechazada, `_alerta.html` en `danger`. La lista y los filtros andan igual.

## Prohibido

- `google.maps.Marker`, Leaflet u otra librería de mapas.
- Colores fuera de los tonos de la tabla, o un `<style>` por pantalla para pintar marcadores.
- Armar HTML del detalle con datos de la vista (`innerHTML`).
