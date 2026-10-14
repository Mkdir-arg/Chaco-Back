# Componente · Tarjeta de turno y entradas de bitácora (`components/_turno_tarjeta.html`, `components/_entradas_bitacora.html`)

**Clasificación:** Canónico reutilizable. Dos includes del registro diario de un dispositivo: la cabecera
de cada turno y la lista de anotaciones de un turno.
**Evidencia:** `templates/components/_turno_tarjeta.html`, `templates/components/_entradas_bitacora.html`,
`core/tests/test_nodo_ui_lote_c.py`.
**Consumidores de referencia:** `programas/templates/programas/dispositivos/bitacora/bitacora.html` (bitácora del turno, P10).
Se entra desde el botón «Bitácora del turno» del encabezado de P4
(`programas/templates/programas/dispositivos/legajo/detail.html`), como en el mockup.

## Invocación

```django
<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
  {% for turno in turnos %}{% include "components/_turno_tarjeta.html" with turno=turno %}{% endfor %}
</div>
{% include "components/_entradas_bitacora.html" with entradas=entradas_del_turno total=turno_abierto.entradas_total %}
```

La tarjeta va una por turno (la grilla es de la pantalla); las entradas van dentro de la card «Turno
Tarde · entradas», debajo de su encabezado.

| Parámetro | Efecto |
|---|---|
| `turno` | Dict armado por la vista: `nombre`, `estado`, y opcionales `horario`, `tono`, `detalle`, `activo`, `sin_abrir`, `acciones` (lista de `url`, `texto`, `variante`) |
| `entradas` | Lista de dicts (no queryset), de la más nueva a la más vieja: `hora`, `categoria`, y opcionales `tono`, `titulo`, `texto`, `autor`, `automatica`, `version` |
| `total` | Opcional: cantidad real de entradas si la vista mandó menos |

## Quién decide qué

- **El estado, la categoría y el tono los decide la vista.** El template solo traduce `tono` a la variante de
  badge: `success`, `info`, `warning`, `danger`, `brand`. Un tono desconocido, o ninguno, dibuja el badge neutro
  (`badge-gray`) y el ícono genérico; no se rompe. No hay reglas de dominio en el template.
- **El color no es el único portador.** El badge de la tarjeta lleva el texto del estado; el de cada entrada
  lleva el texto de la categoría y un ícono por tono (`fa-circle-check`, `fa-circle-info`,
  `fa-triangle-exclamation`, `fa-circle-exclamation`, `fa-flag`), todos `aria-hidden`.
- **El texto lo escribe un usuario:** se imprime con autoescape y `linebreaksbr` (respeta los saltos de línea,
  no deja pasar HTML). No hay `|safe` ni `{% autoescape off %}`.
- Las acciones de la tarjeta las arma la vista según capacidades; la pieza no decide quién puede qué.
  **Un enlace nunca muta estado.** Cada acción es de uno de dos tipos: `url` navega —a otra pantalla
  (`Ver`) o a la misma con el modal pedido por querystring (`+ Novedad`, `Corregir`), nunca por ancla—
  y se dibuja como `<a>`; `confirm_url` (con `confirm_title`, `confirm_text`,
  `confirm_ok` y `peligro`) es la que cambia estado (`Cerrar turno`) y se dibuja como
  `<button data-confirm-url>` que confirma con `ModernModal` y hace el POST con CSRF desde el handler de
  `programas/templates/programas/becas/_confirm_js.html`, que la pantalla tiene que cargar. Es el mismo contrato que el ítem
  del menú de fila. Una acción sin ninguno de los dos no se dibuja. Un cierre con pase de guardia que pide
  datos (pendientes, quién recibe) no es esta pieza: es el arquetipo Modal.

## Tope

Una bitácora crece sin techo: un turno largo tiene muchas entradas y un dispositivo tiene turnos todos los días.
**El recorte lo hace la vista**: manda las entradas más recientes del turno (por ejemplo las últimas 50) junto con
`total`, la cantidad real, y la lista completa pasa por paginación o por la pantalla del turno. Como red de
seguridad la pieza dibuja **hasta 100 entradas** y avisa «Mostrando N de M entradas». Un queryset sin acotar no
es contrato válido de esta pieza. Una lista vacía muestra el estado vacío canónico.

## Diferencias con el mockup

- La fila no usa la grilla `56px 110px 1fr` (valor arbitrario fuera de la lista blanca): son tres columnas en
  `flex flex-wrap` con `w-12`, `w-32` y el cuerpo `w-full sm:flex-1`. Desde `sm` van en una fila; a 390 px la hora
  y el badge quedan arriba y el texto abajo, a todo el ancho. `w-32` es lo que entra «Mantenimiento» sin montarse
  sobre el texto (`.badge` no corta línea).
- El turno activo marca el borde con `border-brand` y `aria-current`; no dibuja el anillo de 3 px, que no tiene
  utilidad en la lista blanca.
- El turno sin abrir no baja la opacidad (.65): usa fondo `bg-secondary`, para que el texto conserve el contraste.
- El badge de la entrada lleva un ícono por tono **en lugar** del punto del mockup (`badge-dot`): una sola marca,
  que además del color distingue la categoría.
- El 📎 de «adjunto» y el enlace «corregir» no son parte de la pieza (emoji fuera de Font Awesome; la corrección
  la define la pantalla). Las etiquetas extra como «Seguimiento abierto» tampoco.

## Para la pantalla que la use

- La vista trae `autor` y `categoria` ya resueltos (`select_related` o un mapa), para no hacer una consulta
  por entrada.
- La columna de categoría mide `w-32`: entran todas las categorías manuales («Mantenimiento» es la más larga).
  «Pase de guardia», cuando exista, hay que mirarla en la pantalla.
- `texto` puede faltar o ser `None`: no se dibuja nada, no «None».

## Prohibido

- Resolver estado, categoría o tono en el template, o mandar un queryset en `entradas`.
- `|safe` o autoescape apagado sobre el texto de una entrada.
- Una acción que muta estado como `url` (GET).
- Mandar toda la bitácora de un turno sin recorte ni `total`.
- Usar solo el color para distinguir la categoría.
