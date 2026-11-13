# Componente · Tarjeta de dispositivo para derivar (`components/_tarjeta_dispositivo_derivar.html`)

**Clasificación:** Canónico reutilizable. Una tarjeta por dispositivo candidato en un panel de derivación:
dónde queda, cuántas plazas tiene y si alcanza para lo que se pide.
**Evidencia:** `templates/components/_tarjeta_dispositivo_derivar.html`,
`core/tests/test_nodo_ui_emergencia.py` (`TarjetaDispositivoDerivarTest`).
**Consumidores previstos:** el panel «Derivar» de la ficha de un caso de Emergencia y la elección de
dispositivo en el asistente de entrega de kits. Solo usa clases y tokens que ya existen.

## Por qué no es `_tarjeta_edificio` ni `_lista_tarjetas`

`_tarjeta_edificio.html` (`tarjeta_edificio.md`) presenta un inmueble con su estado edilicio y lleva a su
ficha; `_lista_tarjetas.html` (`lista_tarjetas.md`) es la alternativa móvil de una tabla. Esta pieza responde
otra pregunta —«¿entra esta familia acá y qué tan lejos queda?»— con otro dato (plazas y distancia) y otra
acción (elegir el destino). Comparten el contrato de fondo: un dict armado por la vista, estado en texto
además del color y ninguna regla de dominio en el template.

## Invocación

```django
<div class="space-y-3">
  {% for dispositivo in dispositivos %}
  {% include "components/_tarjeta_dispositivo_derivar.html" with dispositivo=dispositivo only %}
  {% endfor %}
</div>
```

Claves de `dispositivo` (dict armado **en la vista o el selector**, nunca un modelo ni un queryset):

| Clave | Efecto |
|---|---|
| `pk` | Obligatoria. Arma los `id` de la tarjeta (`dispositivo-derivar-<pk>-titulo`, `-motivo`): única dentro de la lista |
| `nombre` | Obligatoria. Título (`h3`) y nombre accesible del `<article>` |
| `localidad` | Opcional; vacía = «Sin localidad cargada» |
| `libres`, `reservadas` | Plazas ya contadas. Sin ellas se muestra 0 |
| `distancia_km` | Número (km desde el caso), se muestra con un decimal («a 3,2 km»). `None` = «distancia desconocida»; un 0 es una distancia |
| `marca` | `ALCANZA`, `FALTAN` o `SIN_PLAZAS`, **ya resuelta**. Otro valor, o ninguno, no dibuja marca |
| `faltan` | Con `FALTAN`: cuántas faltan («Faltan 2 plazas», «Falta 1 plaza»; sin número, «Faltan plazas») |
| `accion_texto` | Opcional. Texto del botón, con el dispositivo («Derivar a CIS N.º 3»). Sin él no hay pie |
| `accion_url` | Destino del botón (`<a class="btn-nodo btn-brand btn-sm">`) |
| `accion_motivo` | Opcional. Deshabilita el botón y lo explica al lado. **Gana sobre `accion_url`**, que no llega al HTML |

## Qué dibuja

| Marca | Badge | Texto |
|---|---|---|
| `ALCANZA` | `badge badge-dot badge-success` | «Alcanza» |
| `FALTAN` | `badge badge-dot badge-warning` | «Faltan N plazas» |
| `SIN_PLAZAS` | `badge badge-dot badge-danger` | «Sin plazas» |

Surface `rounded-xl border border-base bg-white shadow-sm`; cuerpo `px-5 py-4` con el título, la línea
localidad · distancia (`text-xs text-body-subtle`), la marca y un `dl` de dos columnas (plazas libres y
reservadas). El pie (`border-t border-light bg-secondary`) solo existe si hay acción.

## Reglas

- **La marca, el orden de la lista y el bloqueo los decide la vista.** La tarjeta no compara plazas con
  integrantes ni deduce el bloqueo de la marca: una tarjeta `SIN_PLAZAS` sin `accion_motivo` deja la acción
  habilitada, porque hay consumidores donde no tener plazas libres no impide elegir el dispositivo.
- La marca va siempre en texto (badge con punto); el color solo la refuerza.
- La acción bloqueada es un `<button disabled>` con `aria-describedby` hacia el motivo, que queda visible
  al lado: se ve por qué no se puede. No se esconde el botón.
- La distancia es un número; el formato («a 3,2 km») lo pone la pieza con el separador del idioma.
- Autoescape siempre: ningún `|safe`.

## Prohibido

- Pasar un modelo o un queryset, o contar plazas desde la tarjeta (N+1).
- Calcular la distancia, la marca o lo que falta en el template.
- Armar la URL de la acción con `|add:` en el consumidor: llega resuelta en el dict.
- Una lista sin tope ni filtro: la vista acota y ordena (alcanza primero, después por distancia).
- Usarla como tarjeta genérica de dispositivo (legajo, infraestructura): esta responde a una derivación.
