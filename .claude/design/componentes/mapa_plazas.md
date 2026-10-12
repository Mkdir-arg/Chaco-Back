# Componente · Mapa de plazas y leyenda (`components/_mapa_plazas.html`, `components/_leyenda_plazas.html`)

**Clasificación:** Canónico reutilizable. Dos includes que se usan juntos: el mapa de un sector y la
leyenda de la pantalla.
**Evidencia:** `templates/components/_mapa_plazas.html`, `templates/components/_leyenda_plazas.html`,
`core/tests/test_nodo_ui_lote_b.py` (`MapaPlazasTest`).
**Consumidores de referencia:** ninguno todavía; lo usarán «Sectores y plazas» y el selector de plaza del
ingreso (mockup P5 y P6).

## Invocación

```django
{% include "components/_leyenda_plazas.html" with leyenda=leyenda_plazas %}
{% include "components/_mapa_plazas.html" with plazas=plazas_del_sector total=sector.plazas_total %}
```

La leyenda va una vez por pantalla, encima de las cards de sector; el mapa va dentro de la card de cada
sector (header con título y bajada, cuerpo con la grilla).

| Parámetro | Efecto |
|---|---|
| `plazas` | Lista de dicts (no queryset) armada por la vista: `codigo`, `estado`, `tono`, y opcionales `detalle`, `url`, `seleccionada` |
| `total` | Opcional: cantidad real si la vista mandó menos de las que hay |
| `leyenda` | Lista de dicts `estado` + `tono`, los mismos estados con que la vista da el tono a las plazas |

## Quién decide qué

- **El estado y el tono los decide la vista.** El template solo traduce `tono` a clases:
  `success` (disponible), `info` (ocupada), `warning` (reservada), `brand` (prestada), `danger` (fuera de
  servicio). Un tono desconocido dibuja la celda neutra. No hay reglas de dominio en el template.
- **El color no es el único portador.** Cada celda lleva el código, el texto del estado y un ícono por
  tono (`fa-circle-check`, `fa-user`, `fa-clock`, `fa-right-left`, `fa-ban`), todos `aria-hidden`; la leyenda
  repite muestra, ícono y texto. Una plaza elegida suma el texto «Elegida» y `aria-current`.

## Accesibilidad y teclado

- La grilla es una `ul` con `role="list"` y un `li` por plaza; el código se lee «Plaza A-01».
- Una plaza con `url` es un `<a>` real: se llega con Tab, se activa con Enter y muestra el foco nativo.
  Una plaza sin `url` es informativa y no entra en el orden de tabulación. La vista decide cuáles se
  pueden elegir (p. ej. en el ingreso, solo las disponibles); el componente no lo infiere del estado.
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
- Dibujar plazas con `<div>` clicables o con JS propio: lo accionable es un enlace.
- Mapa de plazas sin leyenda en la misma pantalla.
