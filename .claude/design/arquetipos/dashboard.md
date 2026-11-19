# Arquetipo · Dashboard de programa (tablero)

**Golden (la única que se clona):** `programas/templates/programas/dispositivos/tablero/tablero_referencia.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo dashboard <archivo>`.
**Componentes:** hero_inicio · filtros (píldora) · stat_card (`variante="tablero"`) · tabs · alerta · tabla ·
botones_badges · estado_vacio.
**Molde visual:** el mockup del tablero de Dispositivos
(`docs/superpowers/specs/2026-11-08-tablero-dispositivos/mockup-tablero.dc.html`) y su spec
(`docs/superpowers/specs/2026-11-08-tablero-dispositivos-design.md`, §2-§3).

La golden es una **referencia sin vista**, como la de Revisión: no tiene URL. Es el esqueleto del tablero de
Dispositivos con los datos de ejemplo del mockup; el test `TableroReferenciaTest`
(`core/tests/test_nodo_ui_piezas.py`) la renderiza. Cuando el tablero de Dispositivos exista, la pantalla real
**clona** este archivo y le pone su vista; la referencia no se edita para parecerse a ella. Los tableros que
se declaran de este arquetipo: Dispositivos (`dispositivos:tablero`) y la Situación de Emergencia (E8).

## Cuándo

La **primera pantalla de un programa**: responde en un vistazo cuánto, dónde y qué hay que atender, sobre
todo el alcance de quien mira, con filtros que acotan **todos** los bloques. No es para un registro (eso es
Detalle) ni para una colección que se abre fila por fila (Listado). Con un único bloque de números y sin
solapas es Detalle apilado con hero (`{# arquetipo: detalle + apilado #}`, el tablero E1 de Emergencia).

No es molde: el dashboard de Becas (`programas/templates/programas/becas/config/_dashboard_panel.html`, una
solapa del detalle del programa, con `<style>`, `style=` y gráficos de Chart.js) ni E1.

## Estructura (en este orden)

1. **Hero** `{% hero_inicio %}` en lugar del `page_header`: `titulo`, `eyebrow` («Programa X · …»), la bajada
   con los números **armada en la vista** y una sola acción (la pantalla de trabajo del programa). La ruta del
   template se suma a `HERO_PANTALLAS` en el mismo PR (`componentes/hero_inicio.md`).
2. **Una sola barra de filtros arriba de las solapas**: `components/_filtro_pildora.html` con «Filtrar»
   visible, «Limpiar» (solo con filtros) y «Actualizado a las HH:MM» a la derecha. Los filtros acotan todos
   los paneles. Ver *Filtros y solapas*.
3. **Franja de métricas**: `_stat_card.html` con `variante="tablero"`, **una sola franja grande** (regla de
   `componentes/stat_card.md`). Grilla `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`; con cinco
   tarjetas hace falta `lg:grid-cols-5`, que **no está compilada** hoy: sumarla con `npm run build:tailwind` en
   el PR que la use. Valor ya formateado, `sufijo` y `nota` desde la vista; sin plazas o sin dato, «—».
4. **Barra de solapas en su propia surface** (`bg-white rounded-xl border border-base shadow-sm
   overflow-hidden`), con el ARIA de `componentes/tabs.md` y deep link `?tab=`. Resumen primero; Mapa (y lo
   que el programa sume) después.
5. **Cada panel es una pila de surfaces** (`space-y-5`), fuera de la surface de la barra: un tablero tiene
   varios bloques con título propio y no se anidan cards. Cada bloque es `<section aria-labelledby>` con
   cabecera `px-5 py-4 border-b border-light`, `h2 text-heading font-bold` y bajada
   `mt-1 text-xs text-body-subtle`. Dos bloques angostos pueden ir lado a lado en
   `grid grid-cols-1 lg:grid-cols-2 gap-4`.
6. **«Necesita atención»** primero en Resumen: `_alerta` por aviso (`tono`, `icono`, `titulo`, `texto`,
   acción con URL) con `role="status"` (son muchos y llegan con la página: `alert` los anunciaría todos).
   Sin avisos, `_estado_vacio` «Nada pendiente».
7. **Tablas** de la tabla densa (`componentes/tabla.md`): `<caption class="sr-only">`, `scope="col"`,
   `nodo-col-acciones` con su `sr-only`, badges con **ícono + texto** (`badge badge-{tono}`), enlace de
   entidad `text-fg-brand hover:underline` y «Ver listado completo» (`btn-nodo btn-secondary btn-sm`) en la
   cabecera del bloque. Vacía por los filtros: `_estado_vacio` con `con_filtros=True` y la URL de «Limpiar».
8. **Mapa**: panel propio que se carga **a pedido** (no en el render del Resumen). La golden trae el estado
   cerrado como `_estado_vacio`; la pieza del mapa es `components/_mapa.html` con su ficha, y entra con el PR
   que la construya.

## Filtros y solapas

`componentes/filtros.md` pide, con solapas, una barra por panel. El tablero se aparta a propósito (decisión
del spec de Dispositivos, §8.1, y del análisis 009, §3.3): los filtros acotan todos los paneles y una sola
barra arriba es lo que se entiende. Para que filtrar no devuelva a la solapa que resolvió el servidor, la
vista pasa `ocultos=(("tab", solapa_actual),)` y el envoltorio de la barra copia la solapa visible al
enviar:

```django
<div class="flex flex-wrap items-center justify-between gap-3"
     @submit.capture="$event.target.elements.tab && ($event.target.elements.tab.value = tab)">
  {% include "components/_filtro_pildora.html" with pildoras=pildoras ocultos=ocultos %}
  …
</div>
```

«Limpiar» conserva la solapa con `:href`. No se filtra al cambiar un `<select>` (WCAG 3.2.2) y no se combina
con la tarjeta de `data-dynamic-list-filters`. El estado vacío decide con `request.GET|hay_filtros:"page,tab"`:
la solapa no es un filtro.

## Contrato de contexto (la vista lo prepara)

| Variable | Qué es |
|---|---|
| `titulo`, `eyebrow`, `resumen` | hero: título, línea de contexto y bajada **ya armada** («538 de 554 plazas ocupadas…»; con filtro vacío, «Ningún dispositivo coincide con el filtro.») |
| `url_accion`, `accion_texto`, `accion_icono` | la única acción del hero |
| `pildoras`, `ocultos` | contrato de `_filtro_pildora.html`; `ocultos` incluye `("tab", solapa_actual)` |
| `url_limpiar`, `actualizado` | URL sin filtros y hora `HH:MM` del cálculo |
| `tarjetas` | lista de dicts `etiqueta`, `valor`, `sufijo`, `nota`, `icono`, `tono` |
| `atencion`, `atencion_resumen` | avisos (`tono`, `icono`, `titulo`, `texto`, `url`, `accion`) ya ordenados y recortados; texto del contador |
| `filas`, `red_resumen`, `url_listado` | filas de la tabla con `nombre`, `url`, `tipo`, `localidad`, `ocupacion` y `relevamiento` (`texto`, `tono`, `icono`), `libres` |

## Límites y rendimiento (la vista, no el template)

- Todo sale de **un** servicio de agregación sobre el alcance del usuario (`dispositivos_visibles(user)` en
  Dispositivos), con un número fijo de consultas que no crece con la red; va con su test `--tag performance` y
  su presupuesto en `scripts/perf_budgets.json`.
- Agrupar por día **en Python**, nunca con `Trunc*` (ECOM no tiene tablas de timezone).
- Las listas («Necesita atención», la tabla) llegan **recortadas**, con su total contado aparte y el enlace al
  listado completo; el template no pagina ni corta.
- Lo que solo se ve en otra solapa (mapa, abastecimiento) se calcula cuando esa solapa está activa o se pide
  aparte (`componentes/tabs.md`, *Prohibido*).
- Los números se dicen «de tu alcance» cuando el usuario no ve la red completa.

## Impresión

El tablero se imprime para una reunión: hoja apaisada sin sidebar, filtros, botones, barra de solapas ni mapa;
el hero, los filtros aplicados como subtítulo, la franja y **todo el panel Resumen** aunque se esté mirando
otra solapa, con un pie «Documento de trabajo · impreso el …». **No hay pieza de impresión canónica** (el
`dash-no-print` de Becas es local y `.no-print` vive en `responsive.css`, clasificado como conflictivo), así
que la golden no la trae: la construye, con su ficha, el primer tablero que imprima (E8), y los demás la
reusan. No se escribe un `<style>` de impresión en la pantalla.

## Qué no cubre la golden

Las piezas nuevas del spec de Dispositivos (§3.2) entran con su ficha en el PR que las construya y se suman a
este esqueleto como bloques del panel: barra con marcas de umbral, gráfico de barras pareadas, mapa
(`_mapa.html`), lista de selección `item-lista`, píldora con campo de texto, fila de persona y fila de plaza
libre. Mientras no tengan ficha, son **novedad**: se frena y se devuelve.

## Prohibido

- `<h1>` a mano, `{% page_header %}` debajo del hero, `<style>`, `style=`.
- Más de una franja de stat cards grandes; tarjetas armadas a mano.
- Filtrar al cambiar el valor; la tarjeta de filtros junto a las píldoras; una barra de filtros por panel.
- Anidar las surfaces de un panel dentro de la surface de la barra de solapas.
- Gráficos con `<canvas>` o librerías sin ficha; color como único portador de un estado.
- Contar, decidir tonos o armar la bajada en el template.

## Checklist (la usa el revisor)

- [ ] `--arquetipo dashboard` OK, `--ratchet` con 0 nuevos y la ruta en `HERO_PANTALLAS`.
- [ ] Molde declarado = golden; del mockup y de la hermana solo salió dominio.
- [ ] Una sola barra de filtros, que conserva la solapa visible al filtrar y al limpiar.
- [ ] Una sola franja grande; «—» donde no hay dato.
- [ ] Ningún número, tono ni texto de estado calculado en el template.
- [ ] Consultas fijas con presupuesto de performance; listas recortadas con su total.
- [ ] Badges con ícono y texto; tablas con `caption`, `scope` y acciones con nombre.
