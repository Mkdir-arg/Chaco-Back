# Componente · Barra con marcas de umbral (`components/_barra_umbral.html`)

**Clasificación:** Canónico reutilizable. Barra horizontal de ocupación con las marcas de los umbrales de
tensión (Exigida / Crítica), la cifra y el badge del nivel; sin umbrales es la barra simple proporcional.
**Evidencia:** `templates/components/_barra_umbral.html`, `static/custom/css/nodo-barra-umbral.css` (cargado
por el shell: solo marcas, muestra de la leyenda y alto contraste), el relleno `.nodo-ficha-medidor` de
`static/custom/css/nodo-ficha.css` (como `_contador_avance`), el tag `porcentaje_barra` y el filtro
`entero_o_none` de `core/templatetags/nodo_ui.py` y
`core/tests/test_nodo_ui_emergencia.py` (`BarraUmbralTest`).
**Consumidores:** previstos «Capacidad de la red», «Más tensionados» y el embudo de la Situación de Emergencia
(E8), y «Ocupación por tipo» y «Plazas libres por localidad» del tablero de Dispositivos.

## Por qué no es `_contador_avance` ni `_ficha_avance`

`_contador_avance` cuenta **unidades** («3 de 7») y su barra no tiene nivel. `_ficha_avance` es el medidor de
una sección de ficha. Acá el dato es un **porcentaje con nivel de tensión**: la barra tiene que mostrar dónde
empieza cada nivel, y el nivel lo decide el dominio (`programas/services/ocupacion.py`, que con `tipos=(Plaza.Tipo.CAMA,)` cuenta solo
camas), no la pantalla.

## Invocación

```django
{# Con marcas: la tensión y los umbrales del tipo (o 60/80 sin tipo) los arma la vista #}
{% include "components/_barra_umbral.html" with valor=t.ocupadas maximo=t.operativas porcentaje=t.porcentaje tono=t.tono etiqueta=t.etiqueta umbral_exigida=tipo.umbral_ocupacion_amarillo umbral_critica=tipo.umbral_ocupacion_rojo nombre="Ocupación de Hogar San José" only %}

{# Sin marcas: embudo, localidades #}
{% include "components/_barra_umbral.html" with valor=paso.casos maximo=embudo.relevados texto="204 casos" nombre="Tomados" only %}
```

| Parámetro | Efecto |
|---|---|
| `valor` | Entero **ya contado** (ocupadas, casos) |
| `maximo` | Entero ya contado sobre el que se mide. Sin máximo positivo o sin valor no hay cifra: «—» y barra vacía, nunca «0 %» |
| `porcentaje` | Opcional, el de `Tension.porcentaje`. Gana sobre `valor`/`maximo`: la barra dice el mismo número que la tabla. Sin él, se redondea igual que `tension_de_ocupacion` |
| `tono` | Opcional, `Tension.tono` (`success`, `warning`, `danger`, `gray`). Pinta el relleno y el badge. Sin él, relleno `bg-brand` |
| `etiqueta` | Opcional, `Tension.etiqueta` («Normal», «Exigida», «Crítica», «Sin plazas»). Badge con ícono + texto; sin ella no hay badge |
| `umbral_exigida` | Opcional, % del umbral amarillo (0 es válido y se dibuja) (`TipoDispositivo.umbral_ocupacion_amarillo`, o `UMBRAL_EXIGIDA` = 60 sin tipo) |
| `umbral_critica` | Opcional, % del umbral rojo (`umbral_ocupacion_rojo`, o `UMBRAL_CRITICA` = 80) |
| `texto` | Opcional, reemplaza la cifra visible «N %» («204 casos», «120 / 120») |
| `nombre` | Opcional, qué se mide, para el lector de pantalla. Por defecto «Ocupación» |

Sin `umbral_exigida` ni `umbral_critica` es la **variante sin marcas**: ni marcas ni leyenda.

Render: un `div[data-barra-umbral="{tono}"]` con

- una frase `sr-only` con el valor y el nivel en palabras: «Capacidad de la red: 88 por ciento, nivel Crítica.»
  (con `texto`: «Tomados: 96 por ciento (204 casos).»; sin cifra: «Ocupación: sin cifra, nivel Sin plazas.»);
- la fila gráfica `flex items-center gap-3` con `aria-hidden="true"`: pista `nodo-barra-umbral-pista block h-2
  rounded-full overflow-hidden bg-tertiary` (la clase gancho solo la usa el alto contraste) con el relleno `nodo-ficha-medidor block h-full max-w-full rounded-full bg-{tono}`
  (`style="--avance:88%"`, tope visual 100 %), las marcas de 2×16 px (`bg-warning` la exigida, `bg-danger` la
  crítica, `style="--umbral:60%"`, `title` «Exigida desde 60 %»), la cifra `text-sm font-semibold text-heading
  tabular-nums` y el badge `badge badge-{tono}` con ícono;
- con umbrales, la leyenda `text-xs text-body-subtle`: muestra de color + «Exigida desde 60 % · Crítica desde
  80 %», en texto, legible por el lector.

| Nivel | Relleno | Badge | Ícono |
|---|---|---|---|
| Normal | `bg-success` | `badge-success` | `fa-circle-check` |
| Exigida | `bg-warning` | `badge-warning` | `fa-triangle-exclamation` |
| Crítica | `bg-danger` | `badge-danger` | `fa-circle-exclamation` |
| Sin plazas | sin relleno (sin cifra) | `badge-gray` | `fa-circle-minus` |

En alto contraste (`forced-colors`) la pista (`.nodo-barra-umbral-pista`, nunca un selector por posición)
lleva borde, el relleno pasa a `Highlight` y las marcas a
`CanvasText`; la leyenda en texto dice cuál es cuál.

## Reglas

- **El nivel no se calcula en el template.** `tono` y `etiqueta` llegan de `tension_de_ocupacion(conteo,
  tipo=...)`; los umbrales que se dibujan son **los mismos** que usó esa llamada (los del tipo, o 60/80 sin tipo).
- Los números llegan contados; nada de `|length` ni `.count()` en el template.
- Cada umbral se convierte una vez con `|entero_o_none` y se condiciona por `is not None`: un umbral 0 dibuja
  marca y leyenda; uno que no es número no dibuja ni marca ni leyenda.
- El nombre del ámbito (dispositivo, tipo, paso) y «ocupadas / plazas» van en la pantalla, arriba de la barra;
  la pieza no los dibuja. `nombre` es solo para el lector.
- El color nunca va solo: badge con ícono y texto, y leyenda de umbrales en texto.

## Prohibido

- Reescribir pista o relleno en CSS propio: son utilidades + `.nodo-ficha-medidor`.
- Barras escritas a mano con `style="width:…"` o colores de serie en hex (el mockup usa `--serie-*`, que no
  existen en `chaco-tokens.css`).
- Pasar umbrales distintos de los que decidieron el nivel.
- Usarla para una cuenta «N de N» (eso es `_contador_avance`).
