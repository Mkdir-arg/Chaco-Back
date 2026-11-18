# Componente · Domicilio con mapa (`components/_ubicacion_domicilio.html`, `nodo-ubicacion.js`)

**Clasificación:** Canónico reutilizable. Pieza única (Cambio 489, fase 2).
**Evidencia:** `templates/components/_ubicacion_domicilio.html`, `static/custom/js/nodo-ubicacion.js`,
`static/custom/css/nodo-ubicacion.css`, `core/tests/test_nodo_ui_piezas.py` (`UbicacionDomicilioTest`).
**Consumidor de referencia:** alta y edición del legajo de Dispositivos
(`programas/templates/programas/dispositivos/legajo/form.html`). **A pedido:** alta manual, confirmación con
RENAPER y edición del ciudadano (`legajos/templates/legajos/ciudadano_manual_form.html`,
`ciudadano_confirmar_form.html`, `ciudadano_edit_form.html`) y la dirección del Formulario 1 de Emergencia, en
«Nuevo caso» de la mesa y en la puerta del dispositivo (`programas/templates/programas/emergencia/_formulario1_bloques.html`).
**Depende de:** el cargador de Google Maps (`.claude/design/componentes/mapa_google.md`).

## Invocación

```django
{% block page_css %}<link rel="stylesheet" href="{% static 'custom/css/nodo-ubicacion.css' %}">{% endblock %}
…
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
  {% include "components/_field.html" with field=form.localidad wrapper_class="" %}
  {% include "components/_ubicacion_domicilio.html" with domicilio=form.domicilio latitud=form.latitud longitud=form.longitud localidad_id=form.localidad.id_for_label %}
</div>
…
{% block customJS %}
  {% include "components/_google_maps.html" %}
  <script src="{% static 'custom/js/nodo-ubicacion.js' %}"></script>
{% endblock %}
```

| Parámetro | Efecto |
|---|---|
| `domicilio`, `latitud`, `longitud` | BoundField. Label, ayuda y error con el mismo marcado que `_field.html` |
| `localidad_id` | Opcional. El texto de la opción elegida se suma a la búsqueda |
| `provincia_id` | Opcional. Id del control de provincia; si tiene una elegida, reemplaza a `provincia` |
| `provincia` | Opcional, «Chaco» por defecto |
| `a_pedido` | Opcional. Con `True` la pantalla no le pide nada a Google al abrirse: el mapa carga con «Ubicar en el mapa» o, si ya hay coordenadas, con «Ver en el mapa». **Obligatorio en el domicilio de una persona** (SEC-33) |
| `wrapper_class` | Opcional, `sm:col-span-2` por defecto |

## Comportamiento

- **Ubicar en el mapa** (o Enter en el domicilio, salvo con una búsqueda en curso) busca «domicilio, localidad, provincia, Argentina» con el
  Geocoder de Google, restringido a Argentina. La búsqueda no se dispara sola mientras se escribe: cada
  consulta se cobra.
- Un resultado pone el marcador y centra el mapa. Varios (hasta 5, sin repetidos) se listan para elegir. Ninguno:
  alerta `warning` y el punto se marca tocando el mapa.
- El marcador (`AdvancedMarkerElement` con `PinElement` del color de marca) se arrastra; un clic en el mapa lo
  mueve. Latitud y longitud se escriben en los campos reales con 6 decimales y disparan `input`/`change`.
- Badge de estado: Sin ubicar · Con ubicación · Ubicado con Google · Ajustado a mano · Marcado a mano · Elegí una
  opción · El domicilio cambió: volvé a ubicarlo · No encontrado. Si cambia el domicilio, las coordenadas **no** se
  borran: el badge avisa.
- **Cargar coordenadas a mano** abre los dos campos; escribir en ellos mueve el marcador.
- Sin JS, sin `GOOGLE_MAPS_API_KEY`, con la key rechazada (`nodo-mapa:error`) o si falla la búsqueda: quedan
  domicilio, latitud y longitud a mano, con alerta `info` o `danger`. Con errores de validación en latitud o
  longitud los campos manuales quedan abiertos.

- **A pedido:** hasta que el operador lo pide, el bloque muestra el domicilio, el botón, las coordenadas y
  «Ver en el mapa» (solo con coordenadas guardadas); el recuadro del mapa no existe. Así abrir un legajo no le
  manda a Google la ubicación de la persona.

## Prohibido

- Geocodificar en `input`/`blur` (gasta cuota).
- Borrar coordenadas cuando cambia el domicilio.
- Usarla en el portal ciudadano: la inscripción pública no geocodifica (Cambio 489).
- Usarla sin `a_pedido=True` en el domicilio de una persona.
