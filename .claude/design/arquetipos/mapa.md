# Arquetipo · Mapa

**Golden (la única que se clona):** `mapa/templates/mapa/mapa.html` (`/mapa/`, Cambio 493), con la pieza
Mapa con capas (`componentes/mapa_capas.md`) y, si se edita, `static/custom/js/mapa-general.js`.
**Marcadores:** `scripts/design_audit.py --arquetipo mapa <archivo>`.
**Componentes:** mapa_capas · mapa_google · item_lista · page_header · modal_partes (alta) · field.

## Cuándo

- Una pantalla **cuyo protagonista es el mapa**: cosas ubicadas, con capas para prender y apagar, una lista que
  se sincroniza y, opcionalmente, alta y movimiento de puntos.
- No es para un mapa dentro de un formulario (eso es `ubicacion_domicilio.md`) ni para un mapa chico en una
  solapa de otra pantalla: ahí se usa la pieza sola (`alto` por defecto), sin este esqueleto.

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load static nodo_ui %}

{% block page_css %}
<link rel="stylesheet" href="{% static 'custom/css/nodo-mapa-capas.css' %}">
<link rel="stylesheet" href="{% static 'custom/css/nodo-item-lista.css' %}">
{% endblock %}

{% block main-content %}
<div class="space-y-5">
  {% page_header titulo="<Título>" eyebrow="<Contexto>" %}
    {% bajada %}<qué se ve en el mapa>{% endbajada %}
  {% endpage_header %}

  <div class="nodo-mapa-escena">
    {% include "components/_mapa_capas.html" with nombre="<nombre>" puntos=puntos etiqueta="<nombre accesible>" alto="pagina" only %}
    <aside class="nodo-mapa-panel" data-mapa="<nombre>" aria-label="Capas y lista">
      <button type="button" class="nodo-mapa-panel__asa" aria-expanded="false" aria-controls="<id>">…</button>
      <div class="nodo-mapa-panel__cuerpo" id="<id>">
        <div class="nodo-mapa-panel__cabeza">
          <input type="search" class="nodo-field" data-mapa-buscar aria-label="Buscar en el mapa">
          <p class="nodo-mapa-panel__titulo">Capas</p>
          {# una por capa: .nodo-mapa-capa .nodo-mapa-tono-<tono> data-mapa-capa aria-pressed + punto, texto, nota, __n, __sw #}
        </div>
        <div class="nodo-mapa-panel__lista" role="group" aria-label="En el mapa">
          {% for p in puntos %}{% include "components/_item_lista.html" with nombre=p.titulo meta=p.subtitulo clave=p.id only %}{% endfor %}
        </div>
        <p data-mapa-vacio hidden>…</p>
      </div>
    </aside>
  </div>
</div>
{% endblock %}

{% block customJS %}
{% include "components/_google_maps.html" %}
<script src="{% static 'custom/js/nodo-mapa-capas.js' %}"></script>
{% endblock %}
```

## Reglas

- **La vista arma los puntos y las capas** (`mapa.services.capas_del_mapa` es el molde): cada capa con la regla
  de lectura de su módulo, y lo que no se dibuja (sin ubicación, ubicación reservada, el edificio de un refugio) se
  cuenta en la nota de la capa, nunca se dibuja. Estados y tonos de otro módulo salen de su tabla única (p. ej.
  `estado_visible_de_caso`), nunca de una copia.
- **Leyenda = las capas del panel**: botón `.nodo-mapa-capa` con interruptor, ícono y color de la capa, total y
  nota. Un subfiltro va en `.nodo-mapa-chips` > `.nodo-mapa-chip[data-mapa-grupo]` debajo de su capa.
- **Alta de puntos**: botón en el `page_header` con `aria-pressed`, `.nodo-mapa-barra` («Tocá el mapa…» +
  Cancelar) y el arquetipo Modal para los datos (`data-ajax` + `_ajax_js.html`); la posición viaja en campos
  ocultos. La pantalla escucha `becas-saved` (`detail` = respuesta) para sumar el punto y el ítem que devuelve el
  servidor ya renderizado. Mover = soltar el marcador
  (`PATCH`); si el servidor lo rechaza, vuelve a su lugar. Eliminar = acción del detalle → `ModernModal` con
  `danger: true` → `DELETE`.
- La API responde JSON también en 401/403 y exige CSRF (`X-CSRFToken`).

## Prohibido

- `<style>` local, `google.maps.Marker`, Leaflet u otra librería, el script de Google pegado.
- Un panel propio que no use los atributos `data-mapa-*` (se desincroniza del mapa).
- Dibujar algo que la persona no podría ver por su módulo: la regla vive en el servicio.
