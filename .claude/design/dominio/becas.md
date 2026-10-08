# Dominio · Becas

Contratos que **solo existen en Becas**. Se componen con las piezas canónicas del inventario y
**no son molde** para otros módulos: convocatoria, segmento, subsegmento, cupo, lista de espera,
beneficiario, relevamiento, padrón y SIIS no se trasladan a un módulo que no los tenga.

---

## Mapa de estados

Un color por estado en todas las pantallas. **El mapeo estado → badge vive solo en estos parciales
y las pantallas los incluyen; no repiten el `if`.** Tests: `programas/tests/test_estado_badges.py`.

| Objeto | Parcial | Reglas |
|---|---|---|
| Caso | `programas/templates/programas/becas/_formulario_estado_badge.html` | `estado`: Enviado `badge-warning`, Aprobado `badge-success`, Rechazado `badge-danger`, Baja `badge-gray` «Dado de baja». Con `en_espera_activa` **suma** un `badge badge-warning` «Lista de espera» sin dot: la lista de espera no es un estado. `color_enviado` y `dot` quedan por compatibilidad; el dot va siempre |
| Relevamiento | `programas/templates/programas/becas/relevamientos/_estado_badge.html` | `rel`: «Vencido» suma `badge-warning`, igual que la convocatoria vencida |
| Convocatoria | `programas/templates/programas/becas/_convocatoria_estado_badge.html` | `convocatoria`: precedencia `pausa_efectiva` «Pausada» warning > activa y `esta_vencida` «Vencida» warning > `activo` «Activa» success > «Cerrada» gray |
| Programa, segmento y subsegmento | `programas/templates/programas/becas/_pausable_estado_badge.html` | `objeto`: «Pausado» warning > `activo` False «Inactivo» gray > «Activo» success. Usa `pausa_efectiva`; `solo_manual=True` mira solo `pausado`, para las pantallas de programa que muestran el bloqueo del sistema externo como badge aparte |

Todos con `badge badge-<tono> badge-dot`. **Pausado nunca es danger** y apagado es gris, no rojo.

Un módulo nuevo arma **su propio** parcial de badges con el mismo patrón:
`programas/templates/programas/dispositivos/_estado_badge.html` es el de Dispositivos y
`programas/templates/programas/merenderos/_estado_badge.html` (+ `_solicitud_estado_badge.html`)
los de Merenderos. **Apagado es gris, no rojo**: «Inactivo», «Cerrado» y «Sin datos» nunca van en
`badge-danger` ni en `text-fg-danger`.

---

## Identificadores de integración (programa y segmento)

Evidencia: `programas/templates/programas/becas/config/_siis_programa_modal.html` (bloque del pop
up «Detalle SIIS», que `programa_detail.html` incluye con `identificadores_programa=programa`) y
`programas/templates/programas/becas/config/segmento_list.html` (modal «Editar segmento»), que
`programas/templates/programas/becas/config/_segmentos_table.html` alimenta.

Contrato: los identificadores que viajan a un sistema externo se editan como `input type="number"`
con `nodo-field`, agrupados en una grilla (`sm:grid-cols-3` en el programa, `sm:grid-cols-2` en el
segmento, que no repite los que son únicos por programa) y **siempre dentro del pop up del
registro al que pertenecen**, separados del resto con `pt-4 border-t border-light` y un título.

- El pop up que los suma ensancha su panel a `max-w-2xl` (sin el bloque sigue en `max-w-[560px]`)
  y **no repite arriba, como dato de solo lectura, ningún identificador que abajo sea editable**:
  el valor que informó la integración va bajo su propio campo, en la línea del nombre técnico.
- El `<form>` vive en el cuerpo scrolleable con `id`, y su submit en el pie fijo del modal
  apuntándole con el atributo `form=`, al lado de «Cerrar» (`btn-tertiary` + `btn-brand`).
- Cada campo lleva la etiqueta en lenguaje del usuario y debajo, en `text-xs text-body-subtle`, el
  nombre técnico que espera el servicio (`jurid · el catálogo informó #28`), porque quien los
  completa los copia de una comunicación del organismo. El `placeholder` dice de dónde sale el valor por defecto si se deja vacío.
- Cuando un valor editado difiere del que trajo la integración, la pantalla lo dice en la alerta
  inline tonal de arriba del formulario —`rounded-lg bg-warning-soft border border-warning-subtle`,
  `role="alert"`, un `<li>` por identificador contrastando «se manda #X» contra «el catálogo
  informó #Y»— y el formulario se sigue pudiendo guardar: es una advertencia, no un bloqueo.

---

## Panel de integración con el sistema externo en el caso

Evidencia: `programas/templates/programas/becas/revision/formulario_detalle.html` (secciones
«Resultado SIIS» y «Envío a SIIS») y `programas/templates/programas/becas/config/_siis_programa_modal.html`.

Patrón para informar el estado de un intento contra un sistema externo: surface estándar con
header `px-5 py-4 border-b border-light` e ícono `text-fg-brand`; dentro, el último intento como
`badge` con texto (`badge-success` enviado, `badge-warning` incompleto o error técnico,
`badge-danger` rechazado) más fecha y usuario a la derecha en `text-xs text-body-subtle`, y el
identificador externo en un `dl`.

El detalle por campo va en la alerta inline tonal (`role="status"`) como lista `campo — mensaje`:
**la plantilla nunca decide la forma del dato**, la vista normaliza a `[(campo, mensaje)]` porque
el sistema externo devuelve listas y las validaciones locales frases sueltas.

Las acciones (`btn-secondary` para corregir, `btn-brand` para enviar o reenviar) se ocultan cuando
el caso tiene un **intento vigente** —uno que ocupa el caso, no simplemente el último— o falta la
capacidad: la pantalla no ofrece lo que el servicio no haría. Dos estados más del intento (Cambio 127):
`badge-info` «En proceso» mientras la llamada está en vuelo y `badge-warning` «Resultado incierto»
cuando no se sabe si el otro lado la procesó; en los dos, en lugar del botón va una alerta inline
tonal warning (`role="status"`) que dice por qué no se puede reintentar. Todo form que dispara una
acción irreversible lleva `data-un-solo-envio` y el guard de JS de la pantalla, que lo manda una
sola vez y deshabilita el botón. El historial de intentos repite el plegado del historial de
validaciones (`btn-tertiary btn-sm` con `aria-expanded`/`aria-controls` y `classList.toggle('hidden')`).

El pop up de corrección (`modal-datos-siis-overlay`, overlay
`fixed inset-0 z-[1001] hidden … bg-black/50`) y los otros dos modales propios del caso
—«Rechazar caso» (`modal-rechazo-overlay`, tono danger, pie que envía el form oculto
`#form-rechazar` con `form=`) y «Validar identidad manualmente» (`modal-forzar-overlay`, tono
warning)— siguen
el patrón de modal canónico: panel `bg-white rounded-2xl shadow-xl max-h-[90vh] flex flex-col` con
`role="dialog" aria-modal="true" aria-labelledby`, las partes de header y pie, y cuerpo
`overflow-y-auto min-h-0` con los campos en `grid-cols-1 sm:grid-cols-2`. El foco, el Tab
atrapado, Escape y el bloqueo del scroll de fondo los pone
`window.becasModal.bind(overlay, {onClose})`; el clic en el fondo lo cierra la propia pantalla.

Los selects dependientes se llenan por `fetch` contra un endpoint JSON propio y avisan los fallos
con `window.toast('error', mensaje)`, nunca en silencio: el valor ya guardado viaja en
`data-actual` del `<select>`, el listado se repuebla en cada `change` del campo del que depende y
la primera opción es siempre «Sin cambios».

**Estado del caso:** el badge del encabezado sale del parcial único, nunca de un mapeo a mano; la
lista de espera no es un estado sino un badge adicional «Lista de espera · posición N», y mientras
dura el caso no ofrece «Aprobar»: lo explica una alerta inline `role="status"` con link a Cupo.

**Cómo llegó el caso (G1-04 / G1-05).** Lo que el servidor tuvo que decidir solo al recibir una
carga de la app de campo se cuenta con las dos piezas que ya están en la pantalla, sin markup
propio: un **badge adicional** del encabezado —`badge badge-warning` con ícono, al lado de
«Duplicado por resolver»— para «Sincronizado tarde» (la captura se hizo en fecha y el teléfono la
subió después del cierre), y la **alerta inline** `components/_alerta.html` con `tono="warning"`
para las observaciones de la carga (una obligatoria sin responder, una opción fuera del
formulario, el GPS que faltaba). Las dos son advertencias, no bloqueos: «Aprobar» sigue
habilitado, que es la regla de la ficha de la alerta. La vista entrega el texto **ya armado** en
una sola cadena; la plantilla no recorre ni formatea la lista, igual que con el detalle por campo
del panel de integración.

**Panel «Aviso al ciudadano»** (G1-14, Cambio 176): misma surface estándar que las secciones
hermanas —`bg-white rounded-xl border border-base shadow-sm overflow-hidden`, header
`px-5 py-4 border-b border-light` con `<h2 class="text-heading font-bold text-base">` e ícono
`text-fg-brand` con `aria-hidden="true"`, cuerpo `p-6`—. El encabezado usa la utilidad `text-base`
y **no** el `style="font-size:16px"` que arrastran las secciones vecinas: la medida es la misma y
la deuda no se propaga a lo nuevo. Aparece solo con el caso ya resuelto; cuando no hay a quién
avisar (toggle apagado o sin correo de contacto) el cuerpo es una sola línea
`text-sm text-body-subtle` que dice por qué, sin botón. El reenvío es un `<form method="post">` con
un `btn-nodo btn-secondary btn-base`: es una acción de apoyo sobre algo ya resuelto, no la acción
principal de la pantalla.

---

## Mapa del lugar de la toma, en el detalle del caso

Evidencia: `programas/templates/programas/becas/revision/formulario_detalle.html`.

El `iframe` del mapa **no se carga al abrir la pantalla**: su URL viaja en `data-src` y la pone un
botón «Ver el mapa», que se esconde al usarse. Lleva `referrerpolicy="no-referrer"`. La razón no es de
performance: las coordenadas del domicilio de una persona son un dato del caso, y cargar el mapa solo
se las manda a un tercero —con la IP del backoffice y el `Referer` de la pantalla— cuando alguien
decide mirarlo. Las coordenadas como texto y el enlace «Abrir mapa» siguen visibles.

---

## Modal de requisito (alta / edición)

Evidencia: `programas/templates/programas/becas/config/requisitos_segmento.html`,
`programas/templates/programas/becas/config/segmento_detail.html`,
`programas/templates/programas/becas/config/subsegmento_detail.html` y
`programas/templates/programas/becas/config/programa_detail.html`, alimentados por
`programas/templates/programas/becas/config/_requisitos_page_table.html`,
`programas/templates/programas/becas/config/_requisitos_panel.html`,
`programas/templates/programas/becas/config/_requisitos_programa_panel.html` y
`programas/templates/programas/becas/config/_requisitos_propios_panel.html` vía `openEdit` /
`openReqEdit` (y `openEditar` en el modal de segmento).

Contrato: todo control con `nodo-field`; **cada campo del modelo que el formulario acepte tiene su
control en todos los modales**, porque el POST reemplaza el registro completo y un campo ausente
se guarda vacío (el selector «Este dato alimenta a SIIS como», `destino_siis`, se sumó a los cinco
a la vez, con `badge badge-info` «SIIS: …» en las filas). Las mismas etiquetas y ayudas que el
modal de preguntas generales.
`requisitos_segmento.html` y `subsegmento_detail.html` ya usan el helper de modales y las partes
de header y pie; `segmento_detail.html` y `programa_detail.html` siguen con marcado propio hasta
su propia migración.

---

## Cupo: qué número manda, y qué campo se congela

**El cupo del subsegmento es una referencia de distribución, no un tope.** Quien decide aprobar o
mandar a lista de espera es el cupo del **segmento** (`services/cupo.get_cupo_stats`); el del
subsegmento solo valida que lo distribuido no se pase del segmento (RN-40). La pantalla lo dice,
no lo deja deducir: la bajada de `programas/templates/programas/becas/config/subsegmento_detail.html`
rotula **«Cupo asignado»** —no «máximo»— con la aclaración entre paréntesis, y la tarjeta
«Distribución del cupo» de `config/segmento_detail.html` lo repite debajo de los lugares
disponibles. Un rótulo que promete un tope que el sistema no aplica es la clase de número que la
Ola 5 PR 7 ya tuvo que corregir en otras cinco pantallas.

**«Cupo disponible» son tres números distintos, y cada pantalla lee el suyo** (RED-49). El dato que
alimenta la tarjeta «Cupo disponible» y el cuadro «Distribución del cupo» de
`config/segmento_detail.html`, más la bajada de `config/subsegmento_form.html`, es
**`cupo_sin_distribuir`** (`cupo_maximo` menos lo repartido entre subsegmentos). El de la tarjeta
homónima de `cupo/segmento_detail.html` es `stats.cupo_disponible` (`get_cupo_stats`: lugares libres
de verdad, `cupo_maximo` menos los aprobados). Y el de la app de campo es
`Relevamiento.cupos_libres_del_relevamiento`, que viaja por la API con el nombre viejo
(`cupo_disponible`) porque es contrato publicado. Los dos rótulos coinciden a propósito —son los
textos que el cliente usa— pero **las variables no se pueden intercambiar**: pasar una por la otra
cambia el número de la pantalla de configuración y la validación del alta de subsegmentos.

**El segmento y el subsegmento de una convocatoria con relevamientos se muestran deshabilitados,
no escondidos.** `ConvocatoriaForm` les pone `disabled=True` y un `help_text` que dice por qué
(«No se puede cambiar: la convocatoria ya tiene relevamientos»). El control sigue en el
formulario con su valor: sacarlo dejaría la pantalla sin decir a qué segmento pertenece la
convocatoria que se está editando, y un `disabled` de Django además ignora lo que venga en el POST.

---

## Drag & drop (SortableJS)

`static/vendor/sortablejs/Sortable.min.js` (1.15.6, MIT, sin CDN por la CSP) +
`static/custom/css/nodo-constructor.css` (manija `.grip`, estados `.sortable-ghost` /
`.sortable-chosen`, `.is-saving`). Evidencia: el catálogo agrupado de requisitos generales
(`programas/templates/programas/becas/config/_preguntas_grupos.html` +
`static/custom/js/nodo-catalogo-grupos.js`) y el constructor de formularios.

- Se arrastra **solo desde la manija** (`handle`), nunca desde toda la fila.
- La manija es
  `<span class="grip" role="button" tabindex="0" aria-label="Reordenar X: flechas arriba y abajo"><i class="fas fa-grip-vertical" aria-hidden="true"></i></span>`:
  focusable y con **alternativa de teclado** (las flechas arriba y abajo mueven el grupo o la
  pregunta, y una pregunta cruza al grupo vecino en los bordes). Cada movimiento se anuncia en una
  región `aria-live` que crea el JS, el guardado va con demora de 700 ms para no disparar un POST
  por pulsación, el foco vuelve a la manija tras el re-render y `.grip:focus-visible` marca el foco
  con anillo por token.
- Se omite cuando el usuario no puede editar (`data-puede-ordenar="0"` ⇒ no se inicializa).
- Cada soltada guarda **en vivo** contra un endpoint JSON que devuelve `{ok, target, html}` (el
  mismo contrato de `ajax_ok`) y el JS reemplaza el contenedor y se vuelve a enlazar.
- Los huecos vacíos llevan una fila `.sortable-placeholder` (filtrada del arrastre) para que se
  pueda soltar adentro. Sin `confirm()` ni recarga de página.
- El vendor se carga en `{% block customJS %}` **antes** del JS propio.
- **Gotcha del CSRF:** la cookie se lee con `document.cookie.match('(^|;)\\s*' + name + …)` con
  **doble barra** (o con `new RegExp`); con una sola, `\s` es la letra «s» y el token solo se
  encuentra si `csrftoken` es la primera cookie: el POST del reordenamiento vuelve 403. Hay un test
  que fija el patrón (`JsCatalogoTests`).

---

## Constructor de formularios (diseño + vista previa)

`programas/templates/programas/becas/formulario/convocatoria_formulario.html` +
`programas/templates/programas/becas/formulario/_constructor_items.html`,
`static/custom/js/nodo-constructor.js`, `static/custom/js/nodo-condiciones.js` (espejo del motor
del servidor) y `static/custom/css/nodo-constructor.css`.

Patrón: encabezado por `{% page_header %}` con las migas de Becas, badge de versión y estado
«Guardando… / Guardado en vivo» (`aria-live`) como acciones; grid `grid-cols-1 xl:grid-cols-2` con
dos surfaces —izquierda el diseño (toolbar `btn-secondary` / `btn-brand` en `btn-sm` + contenedor
de ítems sobre `bg-tertiary`), derecha la vista previa `xl:sticky` con toggle de canal
(`aria-pressed`)—.

- Ítems del diseño: `section.cons-grupo` con header `bg-secondary` (manija `.grupo-grip`, badges,
  acciones de ícono con `aria-label`) y `ul.cons-hijos` de `li.cons-item` (manija `.item-grip`,
  `.cons-icono` por tipo, badges de alcance, origen, canal y condición), todos dentro de
  `#constructor-items`.
- La vista previa se renderiza en JS con clases `.pv-*` y controles `nodo-field`; imita la densidad
  del paso 2 del portal sin cargar su shell. Los selectores múltiples se apilan con el mismo estilo
  del paso 2 (`.pv-checks` espeja a `.nodo-checks`) y el toggle de canal `.pv-canal-btn` marca el
  foco con anillo por token.
- **Modales:** los cinco (grupo, texto, campo propio, etiqueta y condición) usan el helper de
  modales con sus partes de header y pie. Como el estado Alpine es un único `modal` de tipo string
  (no un booleano por modal), `constructorPagina()` expone un par `get`/`set` por modal (`mGrupo`,
  `mTexto`, `mPropio`, `mEtiqueta`, `mCondicion`) que lee `modal === '…'` y, al ponerse en `false`,
  llama a `cerrar()`; el título dinámico Nuevo/Editar usa `titulo_x_text`.
  El modal de condición no usa el pie canónico: tiene un tercer botón condicional («Quitar
  condición») en `justify-between`, y repite manualmente las clases del pie.
- **Guardado en vivo:** cada mutación responde `{ok, target, html, datos}`; en error el JS restaura
  el HTML anterior y avisa con `toast('error', …)` — **sin toast de éxito**: el indicador
  `aria-live` del encabezado ya informa el guardado.
- Las confirmaciones destructivas (eliminar, restablecer) van por `ModernModal.show`; si
  `ModernModal` no está cargado, la función de confirmación **falla cerrado** (avisa por toast y no
  ejecuta la acción, nunca `onConfirm()` a ciegas).
- La vista previa no promete lo que el paso 2 no hace: DNI y sexo del titular van de solo lectura
  (vienen del paso 1), el sexo del apoderado se elige con nombre (Femenino/Masculino, valor F/M) y
  los selectores múltiples se apilan con el mismo estilo del paso 2.
- Las manijas tienen la misma alternativa de teclado que el catálogo, y el movimiento viaja una
  sola vez con la posición final cuando la ráfaga termina (700 ms); el foco vuelve a la manija tras
  cada re-render.

---

## Dashboard del programa — **no es molde**

`programas/templates/programas/becas/config/_dashboard_panel.html`,
`programas/templates/programas/becas/config/_dashboard_card.html` y
`static/custom/js/becas-dashboard.js`. Se compone con piezas del inventario, pero **tiene deuda
propia**: los seis KPIs siguen armados en línea porque `_stat_card.html` no expresa el valor
compuesto, la nota, el minigráfico ni el medidor, y darle parámetros nuevos es una novedad que
necesita OK. No se clona para una pantalla nueva. Lo que vale como contrato:

- Tarjeta de gráfico: `data-dash-card`, header con título y subtítulo (`data-dash-sub`) que
  completa el JS, alternador gráfico/tabla (`data-dash-toggle`, `aria-pressed`), descarga CSV
  (`data-dash-exportar` + `data-bloque`) y cuerpo con `data-dash-grafico` (canvas),
  `data-dash-tabla` y `data-dash-vacio`.
- **Gráficos:** Chart.js vendorizado con carga diferida. **El JS no trae colores:** los lee de los
  tokens en runtime (`getComputedStyle(...).getPropertyValue('--color-brand-500')`) con nombres CSS
  como fallback. Un color por serie de magnitud; colores semánticos solo para estados; sin doble
  eje; leyenda o etiqueta siempre y **tabla equivalente**.
- Las tablas se arman con `textContent`, nunca con `innerHTML` de datos.
- **Estado de carga visible:** mientras se calcula, la leyenda de fecha dice «Calculando…» y las
  tarjetas bajan a `opacity-60`; la petición se cancela a los 60 s y toda falla (HTTP no OK,
  respuesta que no es el tablero, red, excepción al pintar) se muestra en una alerta inline danger
  con el detalle y un `console.error`. Nunca se deja el tablero vacío en silencio.
- Si falla solo un bloque, el servidor devuelve el resto con `avisos` y la pantalla lo muestra en
  una caja `role="status"` warning (`data-dash="aviso"`), distinta de la de error.
- Un color por serie de magnitud (barras horizontales, `barThickness` 18, `borderRadius` 4 solo en
  el extremo, valor al final de la barra). La tarjeta «Estado de los formularios» no usa canvas:
  barra apilada de `div` con `background: var(--color-*)` y separadores de 2 px en
  `var(--bg-primary)`, una fila por estado (punto de color, nombre, cantidad `tabular-nums`, %) y
  el corte por canal con medidores. El alcance vigente se muestra como chips `badge badge-white`.
  El indicador de formularios lleva un minigráfico SVG de doce semanas con `stroke="currentColor"`
  sobre `text-body-subtle` y el último punto en `text-fg-brand`. Las tarjetas de barras fijan su
  alto según la cantidad de filas y la grilla usa `items-start` para que no se estiren.
- **Pop up «Exportar respuestas por persona»:** es el **arquetipo Modal**, sin excepciones —
  `x-becas-modal="modalRespuestas"`, backdrop propio `bg-black/50 backdrop-blur-sm`, panel
  `max-w-[560px] max-h-[90vh] flex flex-col`, cuerpo `overflow-y-auto min-h-0`,
  `_modal_header.html` y `_modal_footer.html`, y la nota con
  `components/_alerta.html tono="info"`. Se abre desde el botón `btn-nodo btn-secondary btn-sm`
  de la tarjeta de respuestas y desde el menú Exportar. El `<form id="dash-form-respuestas">`
  envuelve cuerpo y pie y lleva un `nodo-field` de convocatoria obligatorio con su
  `data-dash="respuestas-error"` y un segundo `nodo-field` de formato (XLSX / CSV) con su nota
  `text-xs text-body-subtle`. El JS escucha `dash-respuestas-abierto` para heredar la
  convocatoria del filtro y, al enviar, navega a la URL de descarga (`data-url-respuestas`, con
  `/0/` como marcador del id y `/FORMATO/` como marcador del formato). El pie dice «Descargar»,
  no «Descargar Excel»: el formato lo elige el campo.
- Medidores de progreso: pista `h-2 rounded-full bg-brand-soft overflow-hidden` y relleno con
  `background: var(--text-fg-brand)` (`--text-fg-warning-subtle` o `--text-fg-danger` por
  severidad). Ocultar en impresión con la clase `dash-no-print` (regla `@media print` local del
  panel).

---

## Home del backoffice

`templates/inicio.html` (ruta `/inicio/`, `core.views.public.inicio_view`). Encabezado
**canónico** (`{% page_header %}` con el saludo como título, la bajada en el bloque
`{% bajada %}` y «Ver ciudadanos» como acción): **no hay hero**, el canon no los usa en
backoffice operativo. Alpine `dashboardInicio()`: buscador de ciudadanos con typeahead
(`AbortController` + número de secuencia para descartar respuestas tardías), stat cards, «Mi
trabajo de hoy» con dos feeds, accesos rápidos y la grilla «Cobertura por programa» (barras de
progreso + tarjeta de tendencias con Chart.js vendorizado y carga diferida por
`IntersectionObserver`).

**Cada pieza que pide datos a una API con capacidad se esconde con el mismo `puede` que exige esa
API:** tarjeta de búsqueda rápida y feed de derivaciones con `ciudadano.ver` (la tarjeta sobrevive
con solo `ciudadano.crear`, pero sin el input), feed de conversaciones sin asignar con
`conversacion.operar`, tarjeta de tendencias con `dashboard.ver` —si falta el canvas, el JS no
llama a `dashboard:api_tendencias`—. El typeahead pega a `dashboard:api_buscar_ciudadanos`. Un panel no se deja pedir y fallar en consola, ni se muestra vacío como si no
hubiera trabajo pendiente: la bajada del encabezado solo dice «Todo al día» a quien tiene alguna
de las dos capacidades de los contadores; sin ellas, saludo neutro. Sus cuatro stat cards son
conteos globales, sin gate de capacidad, y cada una cuenta lo que dice su rótulo: «Legajos
activos» agrega `LegajoAtencion` con la regla de `legajos.selectors.legajos`, la misma que usa
`/legajos/reportes/`. Siguen armadas a mano —`_stat_card.html` no tiene pie de tarjeta—, y
migrarlas necesita OK: es la misma novedad que frena los KPIs del dashboard de Becas.
