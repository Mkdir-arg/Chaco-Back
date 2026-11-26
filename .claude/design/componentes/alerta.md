# Componente · Alerta inline (`components/_alerta.html`)

**Clasificación:** Canónico reutilizable. Pieza única, variante única.
**Evidencia:** `templates/components/_alerta.html`, `core/tests/test_nodo_ui_piezas.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/config/programa_list.html`
(nota informativa del modal), `programas/templates/programas/becas/config/programa_detail.html`,
`programas/templates/programas/becas/revision/formulario_detalle.html` (la alerta queda en el archivo
raíz, junto al encabezado del caso; las secciones del detalle viven en `revision/_detalle/`; las de SIIS solo con `siis_aplica`).

## Invocación

```django
{% include "components/_alerta.html" with tono="warning" titulo="Sin padrón el link queda abierto" texto="Cualquier persona que lo reciba puede inscribirse y ocupar cupo." %}
```

| Parámetro | Efecto |
|---|---|
| `tono` | `warning` (por defecto), `danger`, `success`, `info` |
| `titulo` | Opcional, `strong text-heading` |
| `texto` | Opcional, `p text-body mt-1` |
| `contenido_template` | Opcional: template propio incluido después del texto y fuera de su párrafo. En `info` y en la rama con ícono/acción, es hijo del cuerpo `div.flex-1.min-w-0`, junto al texto; la acción es hermana del cuerpo. El consumidor controla el markup y sus selectores `data-*`; no inspecciona los internos de la alerta |
| `role` | Por defecto `alert` en danger y warning, `status` en info y success. `role=""` no es válido: pasá el que corresponda |
| `icono` | Opcional. Nombre Font Awesome sin prefijo (`triangle-exclamation`). Se dibuja a la izquierda a 18 px (`text-lg`), con `aria-hidden="true"` y el color del tono. En `info` reemplaza al `circle-info` |
| `accion_url` + `accion_texto` | Opcionales y **van juntos**: link subrayado a la derecha dentro del bloque («Resolver», «Ver legajo»). Con solo uno de los dos no se dibuja el link y el render es el de siempre |

Render: `rounded-lg bg-{tono}-soft border border-{tono}-subtle p-4 text-sm`.

Con `icono` o con acción completa el bloque pasa a `flex items-start gap-3` (ícono · cuerpo `flex-1` · link
`shrink-0`). `info` siempre agrupa texto y contenido en `div.flex-1.min-w-0`:
el contenido adicional queda debajo del texto, en la misma columna. El tono, el `role`
y el escapado no cambian.

P3 (`programas/templates/programas/dispositivos/legajo/form.html`) usa contenido propio en su panel lateral de duplicados:
`_duplicados.html` contiene mensaje y contenedor de lista hermanos. La lista dinámica se inserta
en un `div`, nunca dentro de un `p`; la alerta conserva tono y rol. El contenido recibe el
contexto del include y conserva el autoescape.

## Cuándo cada tono

- **danger:** la acción está bloqueada o algo falló.
- **warning:** advertencia que **no** impide seguir. Encabezado «Atención» y el botón de la
  acción **habilitado**: bloqueo y advertencia se distinguen por el encabezado y por si la acción
  está disponible, no por el color.
- **success:** confirmación persistente de un resultado (un envío que salió bien).
- **info:** nota explicativa dentro de un modal o de una card.

## Dónde va

- Debajo del encabezado de la página cuando condiciona toda la pantalla.
- Dentro de la card o del modal cuando explica ese bloque.
- El resultado de un proceso (por ejemplo, una carga de padrón) se muestra **fijo** con esta
  pieza dentro de su card, no solo como toast.

## Lista de avisos con severidad

Una lista de avisos (los de un detalle, los de un tablero) **no es otra pieza**: es esta alerta en bucle,
dentro de una `section` con `space-y-3` y `aria-label`, con el `tono` de cada aviso según su severidad. La
vista entrega la lista ya ordenada y acotada, cada aviso con `tono`, `icono`, `titulo`, `texto` y, si
corresponde, el par de la acción; el template no decide la severidad ni cuenta.

```django
{% if avisos %}
<section class="space-y-3" aria-label="Avisos de la mesa">
  {% for aviso in avisos %}
  {% include "components/_alerta.html" with tono=aviso.tono icono=aviso.icono titulo=aviso.titulo texto=aviso.texto accion_url=aviso.enlace accion_texto=aviso.accion role="status" %}
  {% endfor %}
</section>
{% endif %}
```

- Cada include pasa **todos** los parámetros que usa la lista (o va con `only`): así no se cuela el `icono` o
  la acción del aviso anterior.
- `role="status"` en todos: una pila de `alert` se anuncia entera y a la vez al cargar la página.
- La severidad va en el título y el ícono de cada aviso, además del color. Sin avisos no se dibuja el bloque:
  no se rellena con una alerta `success`.

Consumidores: las alertas del dispositivo en
`programas/templates/programas/dispositivos/legajo/detail.html` (referencia) y los avisos del tablero de
Emergencia (`programas/templates/programas/emergencia/tablero.html`, armados por `programas/services/avisos_emergencia.py`). La composición no se extrae a un include propio. El aviso
«sin plazas» de E1 cuenta solo camas con la misma función que el panel «Derivar» (`camas_libres_del_conteo`, `programas/selectors/emergencia.py`).
«Necesita atención» de E8 (`programas/templates/programas/emergencia/situacion/situacion.html`) usa la misma
composición del arquetipo Dashboard: un include por alerta con `role="status"`, armadas por
`programas/services/alertas_situacion_emergencia.py` con los tonos e íconos de `programas/services/avisos_emergencia.py`.
En la ficha de la institución, antes de las alertas del dispositivo, un aviso de Llegadas (`aviso_llegadas`, armado por
`aviso_de_pendientes` de `programas/selectors/emergencia_llegadas.py`): las derivaciones de Emergencia por recibir, con el vencimiento
más próximo y «Ir a Llegadas» como acción. Tono `warning`, y `danger` si vence en menos de `POR_VENCER_MIN` o ya venció; solo lo
ven `dispositivo.admitir` con alcance, el admin del programa y el superusuario. Un include de `_alerta.html` con `role="status"`.
Justo debajo, el aviso de kits (`aviso_kits`, `aviso_de_kits_por_recibir` de `programas/services/kits.py` en su rama «para esta institución»): las entregas por recibir de toda la institución, con el número de la más vieja y «Recibir kits» hacia `/emergencia/dispositivos/<id>/kits/`. Tono `warning`, ícono `boxes-stacked`; lo ven `emergencia.recibir_kit` con alcance sobre **toda** la institución (no con alcance solo Edificios), el admin del programa y el superusuario. Si hay derivaciones y kits, son dos includes de `_alerta.html` uno debajo del otro (derivaciones primero), cada uno con su enlace; no hay pieza nueva.
La página operativa del edificio (`edificios/operativo.html`) repite ese aviso acotado a **ese** edificio (`pendientes_por_recibir(..., edificio)` y `aviso_de_pendientes(..., en_este_edificio=True)`) y suma el de kits por recibir (`warning`, ícono `boxes-stacked`, acción «Recibir kit» o «Ver entregas»), armado por `aviso_de_kits_por_recibir` de `programas/services/kits.py` (función pura que usa también la ficha de la institución) y juntado por `_avisos` de `programas/services/edificio_operativo.py` y dibujados en un `{% for aviso in avisos %}` con `role="status"`; cada uno solo con su capacidad (`dispositivo.admitir`, `emergencia.recibir_kit`) con alcance sobre ese edificio.
Con stock (RN-010-07), `programas/services/kits.py` no envía kits a una institución que lleva stock sin edificio activo y, al recibir una entrega sin edificio, pide elegirlo (`requiere_edificio_al_recibir`); esos textos llegan como error del formulario (`components/_form_errores.html`, o en el desplegable «Edificio en el que se recibe» cuando la recepción lo dibuja), no como `_alerta.html`. `edificio_de_la_institucion` de `programas/services/edificio_operativo.py` resuelve el edificio con la capacidad que pide cada pantalla (stock usa `stock.ver`).
El listado de entregas de kits (`programas/templates/programas/emergencia/kits/list.html`) suma un `_alerta.html` `warning` con las entregas que llevan más de 48 h en camino sin recibirse, con acción hacia la solapa «Demoradas»; el aviso equivalente de la mesa es la regla `emergencia.entrega_demorada` de `programas/services/avisos_emergencia.py` (Cambio 586). La solapa Abastecimiento muestra lo demorado en su propia columna, no como «en camino».
En la búsqueda de Llegadas (`emergencia/dispositivo/llegadas.html`), cuando la familia ya tiene un caso abierto (Cambio 579), un `_alerta.html` en tono `info` con el número, la familia y el estado del caso reemplaza al de «sin derivación»; con el caso en manos de otra institución y nada que hacer desde ese dispositivo, suma uno `warning`. Las salidas viven en el modal «Esta familia ya tiene un caso abierto» (`programas/selectors/emergencia_llegadas.py`: `que_pasa_si_se_ingresa` arma las líneas de «Si la ingresás acá»).Las filas de «Derivaciones por recibir» de Llegadas (`filas_de_llegadas`) suman `url_aceptar` para aceptar desde la fila con `data-confirm-url`.
Las alertas estratégicas nombran el dato y no enlazan a casos; la única con acción es la que lleva a otra parte de la
misma pantalla (`ACCIONES_DE_ALERTA` en `pantalla_situacion_emergencia.py`: AE-6 → «Ver el abastecimiento», con los
filtros), con `accion_url` y `accion_texto` del contrato. La solapa Abastecimiento
(`programas/templates/programas/emergencia/situacion/_abastecimiento.html`) repite la composición para AE-8 a AE-10,
sin acción; el estado «sin regla de consumo» enlaza a «Insumos» y el de «sin inicio del evento» a «Plazos de atención».
Si alguna institución lleva stock (`abastecimiento.con_stock`), la tabla suma la columna «Stock registrado» y la
explicación, la línea que aclara que ese número lo carga la institución y no entra en el faltante (RN-010-20).
Los avisos de la mesa arriba de la ficha del caso (`programas/templates/programas/emergencia/casos/detail.html`,
armados por `avisos_de_la_mesa` de `programas/selectors/emergencia_mesa.py`) van uno por include con `only`. La
condición de cada aviso es una sola y la comparten el tablero, la fila de la bandeja y la ficha
(`CasoEmergencia.esperando_en_la_puerta`, `selectors.emergencia.rechazo_sin_nueva_accion`, y «Derivación vencida sin marcar»,
que sale de la subconsulta `derivacion_vencida_sin_marcar` de `con_avisos_de_la_mesa`; «Aceptado sin movimiento hace N h»,
de `selectors.emergencia.horas_sin_movimiento` con las horas de E7; «Identidad a revisar», de
`CasoEmergencia.identidad_pendiente`, sin consultas): el template no decide cuándo se muestra.
La columna «Qué falta» de la bandeja (`que_falta`, `programas/selectors/emergencia_mesa.py`) no usa esta pieza: reutiliza las mismas
condiciones y dibuja la nota como `badge badge-warning` cuando es urgente (la subconsulta `derivada_a` de `con_avisos_de_la_mesa` trae la institución).
En el modal de confirmar «Derivar» de la misma ficha, las camas ya pedidas a esa institución (`ya_pedidas`, Cambio 535)
van como un `_alerta` `info` más, debajo del aviso de plazas: dato, no advertencia.

## Deuda conocida

El tono `info` no tiene par de tokens `bg`/`border` compilado: reusa la nota informativa canónica
con estilos en línea sobre `--bg-info-soft`, `--color-brand-200` y `--text-fg-info`, con ícono
`fa-circle-info`. Es deuda declarada en la pieza; **no se crean tokens nuevos** ni se copia ese
markup a mano: se usa el include.

## Prohibido

- Cajas de aviso escritas a mano con utilidades sueltas.
- Usar el color como único indicador (sin título ni texto).
- Un aviso efímero donde hace falta uno persistente: para avisos efímeros está `window.toast`.
