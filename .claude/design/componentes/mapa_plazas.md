# Componente · Mapa de plazas y leyenda (`components/_mapa_plazas.html`, `components/_leyenda_plazas.html`)

**Clasificación:** Canónico reutilizable. Dos includes que se usan juntos: el mapa de un sector y la
leyenda de la pantalla.
**Evidencia:** `templates/components/_mapa_plazas.html`, `templates/components/_leyenda_plazas.html`,
`core/tests/test_nodo_ui_lote_b.py` (`MapaPlazasTest`).
**Consumidores de referencia:** «Sectores y plazas» (P5, `programas/templates/programas/dispositivos/sectores/`),
con sus acciones por plaza, y el selector de plaza del ingreso (P6).

## Invocación

```django
{% include "components/_leyenda_plazas.html" with leyenda=leyenda_plazas %}
{% include "components/_mapa_plazas.html" with plazas=plazas_del_sector total=sector.plazas_total %}
```

La leyenda va una vez por pantalla, encima de las cards de sector; el mapa va dentro de la card de cada
sector (header con título y bajada, cuerpo con la grilla).

En P5, el encabezado usa `eyebrow=dispositivo.nombre` y su bajada muestra las cifras.
Los resúmenes de página y sector separan «reservada(s)» y «prestada(s)», con `pluralize`,
desde `Conteo.reservadas_sin_prestamo` y `Conteo.prestadas`. Conservan los ceros, como el
resto de la línea. `Conteo.reservadas` sigue siendo el agregado usado en P4; el desglose
sale de la misma consulta de reservas y no aumenta el presupuesto del censo.

| Parámetro | Efecto |
|---|---|
| `plazas` | Lista de dicts (no queryset) armada por la vista: `codigo`, `estado`, `tono`, y opcionales `detalle`, `detalle_completo`, `url`, `click`, `seleccionada` |
| `total` | Opcional: cantidad real si la vista mandó menos de las que hay |
| `leyenda` | Lista de dicts `estado` + `tono`, los mismos estados con que la vista da el tono a las plazas |

## Quién decide qué

- **El estado y el tono los decide la vista.** El template solo traduce `tono` a clases:
  `success` (disponible), `info` (ocupada), `warning` (reservada), `brand` (prestada), `danger` (fuera de
  servicio). Un tono desconocido dibuja la celda neutra. No hay reglas de dominio en el template.
- **El color no es el único portador.** Cada celda lleva el código, el texto del estado y un ícono por
  tono (`fa-circle-check`, `fa-user`, `fa-clock`, `fa-right-left`, `fa-ban`), todos `aria-hidden`; la leyenda
  es una fila de pastillas `badge badge-{tono}` con el mismo ícono por tono y el texto adentro (`<i> Texto`, sin margen propio: el badge ya trae `gap`) (tono
  desconocido: `badge-gray` con `fa-circle`; sin rótulo propio). Una plaza elegida suma el texto «Elegida» y `aria-current`.

## Accesibilidad y teclado

- La grilla es una `ul` con `role="list"` y un `li` por plaza; el código se lee «Plaza A-01».
- Una plaza con `url` es un `<a>` real: se llega con Tab, se activa con Enter y muestra el foco nativo.
  Usa `cursor-pointer`. Con `click` (expresión Alpine, p. ej. `abrirPlaza(12)`) es en cambio un
  `<button type="button" @click aria-haspopup="dialog">` y **gana sobre `url`**: abre el modal de la
  pantalla sin recargar. La pantalla que lo usa declara esa función en su `x-data`; `url` puede seguir
  viniendo como enlace directo (`?plaza=<id>`) para quien llegue por la barra de direcciones. Es
  opcional y la pieza no lo infiere: lo decide la vista (en P5, toda plaza accionable: la disponible
  abre un modal ya cargado en la página con `abrirPlaza(<id>)`, y la ocupada que se reubica pide su
  cuerpo al servidor con `abrirReubicar(<id>)`, porque depende de la estadía; si ese pedido falla, la
  pantalla navega al `url`). Como el modal es único, la pantalla lo limpia (`reset` de los forms,
  errores y `aria-invalid`) al abrir otra plaza y al volver al menú de opciones. Una plaza sin `url` usa `cursor-not-allowed` y `aria-disabled="true"`,
  es informativa y no entra en el orden de tabulación. La vista decide cuáles se
  pueden elegir (p. ej. en el ingreso, solo las disponibles); el componente no lo infiere del estado.
  El `detalle` trae apellido e inicial solo con `ciudadano.ver`; sin esa capacidad la plaza
  ocupada no agrega detalle debajo de su estado. Reservas y préstamos agregan solo el
  vencimiento sin esa capacidad (`hasta DD/MM HH:MM`, fecha y hora local, sin año),
  o «sin vencimiento» en una reserva sin fecha; fuera de servicio conserva su motivo.
  El `title` usa `detalle_completo`, con vencimiento `DD/MM/AAAA HH:MM` en hora local,
  para distinguir reservas de otro año; sin ese opcional usa `detalle`. Ambos textos
  respetan `ciudadano.ver`: sin capacidad nunca incluyen nombre. El servicio de ocupación
  prepara ambos; P5 y P6 los pasan sin reformatear. Sin vencimiento conserva ese texto.
- En P5, quien puede configurar ve «Editar plaza» dentro del modal de su acción. Si no puede
  liberar una reserva, la celda enlaza directamente a la edición de código y tipo; esa edición
  no cambia la ocupación. El sector vacío ofrece «Agregar plazas» desde la pantalla consumidora.
- La celda con enlace lleva siempre una clase `bg-*`: sin ella la regla global de enlaces de
  `nodo-brand.css` (`a:not([class*="bg-"])`, con `!important`) le pisaría el color del tono.

## Tope

Una grilla sin tope se vuelve inmanejable (y pesada) en un dispositivo grande. La pantalla arma **una
surface por sector** y la vista acota cada sector; como red de seguridad la pieza dibuja **hasta 200
plazas** y avisa «Mostrando 200 de N plazas». Si un sector pasa de ese número, el sector se parte o se
pagina en la vista. Una lista vacía muestra el estado vacío canónico.

## Diferencias con el mockup

- La grilla es responsive por columnas (`grid-cols-2` a `lg:grid-cols-6`) en vez de `auto-fill minmax(84px)`,
  que es un valor arbitrario fuera de la lista blanca.
- Ocupada (violeta) usa `border-info-subtle`, el borde del tono `info`. El token faltaba cuando se
  escribio la pieza —sus cuatro hermanos existian y el solo no—, asi que se agrego a `chaco-tokens.css`
  (claro y oscuro) y a `tailwind.config.js`, siguiendo el mismo paso de rampa que los demas.
- La celda lleva ícono además del texto, que el mockup no dibuja.
- El panel lateral que el mockup describe al hacer clic en una plaza **no es parte de esta pieza**: la
  plaza enlaza a la `url` que decida la pantalla.

## Prohibido

- Resolver el estado o el tono en el template, o mandar un queryset en `plazas`.
- Dibujar plazas con `<div>` clicables o con JS propio: lo accionable es un enlace o, con `click`, un botón.
- Mapa de plazas sin leyenda en la misma pantalla.
