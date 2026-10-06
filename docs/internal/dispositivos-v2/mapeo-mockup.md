# Mapeo del mockup v2 de Dispositivos y Merenderos al sistema de diseño y al backend

**Fuente analizada:** [`docs/client/mockups/dispositivos-v2.html`](../../client/mockups/dispositivos-v2.html)
(302 848 B, 1517 líneas; publicado como `mockups/dispositivos-v2.html` en GitHub Pages).
Última modificación del archivo: commit `c75a6b61`, 20/09/2026.

**Para qué sirve este documento.** Para que otro agente implemente la v2 **idéntica al
mockup** sin volver a leerlo entero: por cada pantalla queda el inventario visual literal,
qué pieza del sistema de diseño la cubre tal cual, qué pieza difiere y en qué, qué pieza
hay que crear, qué dato del backend la alimenta y qué falta en el modelo.

**Dónde «tal cual el mockup» choca** con el sistema de diseño productivo, con §7 de la
auditoría o con una decisión registrada, el conflicto queda listado en §7 con sus opciones y
su costo. **Los quince los decidió el PM el 06/10/2026** y cada uno lleva su línea
`Decisión tomada` debajo de las opciones; el registro formal es el **Cambio 134** de
[`requerimientos.md`](../requerimientos.md).

**Método.** Todo lo que se afirma del mockup está citado por selector CSS o por número de
línea del HTML. Todo lo que se afirma del backend está citado con `archivo:línea` del
código vigente en `origin/development`. Las capturas de
[`capturas/`](capturas/) se generaron con Chromium headless sobre el HTML local a 1760 px
(`pNN.jpg` = pantalla, `fNN.jpg` = flujo); no hay ninguna imagen inventada.

**Nombres propios.** Los nombres de personas e instituciones que aparecen acá («CIS N.º 3»,
«Gómez, Laura», «Marta Benítez») son los datos de ejemplo del mockup, no datos reales.

---

## 0. Hallazgo central: el mockup *es* el sistema de diseño

La primera conclusión cambia la forma de leer todo lo demás: **el mockup no propone un
lenguaje visual nuevo**. Fue construido copiando valor por valor el CSS productivo de
DATAÑACH. La comparación es literal:

| Mockup (`:root`, L23-L32) | Código productivo | ¿Coincide? |
|---|---|---|
| `--brand:#5059bc` | `--color-brand-700` ([`chaco-tokens.css:19`](../../../static/custom/css/chaco-tokens.css)) | idéntico |
| `--brand-050:#f5f3ff` · `--brand-200:#ddd6fe` · `--brand-900:#3730a3` | `--color-brand-050/200/900` (L12, L14, L21) | idéntico |
| `--brand-soft:#fee9ff` | `--color-pink-100` → `--bg-brand-soft` (L26, L153) | idéntico |
| `--brand-tint:#dee1ff` | `--bg-brand-tint` (L181) | idéntico |
| `--pink:#f98dff` | `--color-pink-600` (L31) | idéntico |
| `--g050…--g900` | `--color-gray-050…950` (L38-L49) | idéntico |
| `--navy:#252f40` / `--heading` | `--color-navy-700` → `--text-heading` (L53, L219) | idéntico |
| `--succ:#007a55` · `--succ-050` · `--succ-200` · `--succ-800` | `--color-emerald-700/050/200/800` (L66-L74) | idéntico |
| `--dang:#c70036` · `-050` · `-200` · `-900` | `--color-rose-700/050/200/900` (L79-L88) | idéntico |
| `--warn:#b43403` · `-050` · `-200` · `-600` · `-900` | `--color-orange-700/050/200/600/900` (L92-L101) | idéntico |
| `--gradient:linear-gradient(45deg,#5059bc 0%,#f98dff 100%)` | `--gradient-brand` (L185) | idéntico |
| `--font:Manrope,…` | `--font-family-base:'Manrope'` (L246) | idéntico |

Lo mismo pasa a nivel de componente. `.badge.bg-brand{background:#FFEAF6;border-color:#FFB9DC;color:#A11F60}`
(mockup L122) es carácter por carácter
[`nodo-badges.css:35`](../../../static/custom/css/nodo-badges.css). `.nf` (mockup L167) es
`.nodo-field`: 42 px de alto, radio 8, padding `0 14px`, textarea `min-height:80px`
([`nodo-forms.css:31-43`](../../../static/custom/css/nodo-forms.css)). `.fcard .row`
(mockup L164) declara `grid-template-columns:minmax(180px,1.15fr) minmax(150px,.9fr) minmax(200px,1.35fr) 42px`,
que es exactamente
[`dynamic-list-filters.css:36`](../../../static/custom/css/dynamic-list-filters.css).

**Consecuencia práctica:** «tal cual el mockup» es, en la mayoría de las pantallas,
**reutilizar lo que ya existe**, no construir un front paralelo. El esfuerzo real está en
(a) las 16 piezas que el mockup inventa y el sistema no tiene, (b) los datos que el
backend no modela todavía, y (c) **15 choques** con el sistema de diseño o con decisiones ya
registradas, que §7 lista con sus opciones.

---

## 1. Chrome compartido por las 22 pantallas

Las 22 pantallas se dibujan dentro de `.app` (mockup L67), que el script del final
(L1486-L1512) completa con un sidebar y una barra superior generados por JS. No se repite
en cada ficha; se describe una sola vez acá.

### 1.1 Sidebar

Mockup: `.sb` (L68-L90), armado por `sidebar(active,user,hide)` desde el array `NAV`
(L1469-L1481). Ancho 288 px, fondo blanco, borde derecho `--border`.

- **Marca:** caja de 44 px con el SVG del escudo, `DATAÑACH` en 15 px/800 y
  «Gobierno del Chaco» en 11,5 px subtle (L1489).
- **Usuario:** avatar circular 36 px con `--gradient`, nombre 13 px/700, rol 11 px subtle.
- **Ítems:** píldora (`border-radius:9999px`), 10×14 px de padding, ícono 20 px, activo
  `background:var(--brand);color:#fff;font-weight:700`. Contador a la derecha en píldora
  `--g100`; en el activo pasa a `rgba(255,255,255,.25)`.
- **Subítems:** indentados 20 px, 8×12 px, ícono 16 px.
- **Pie:** «Minimizar» en píldora sobre `--g050`.
- **Árbol literal** (L1470-L1480): Inicio · Dashboard · Ciudadanos · Reportes ·
  Configuración · Programas · **Dispositivos** (Tablero · Instituciones `128` · Estadías ·
  Lista de espera `14` · **Relevamientos** `9` · Bitácora · Configuración) ·
  **Merenderos** (Tablero · Merenderos `212` · Solicitudes `7` · Entregas · Prestaciones) ·
  Administración (Usuarios · Roles).

**Mapeo al código.** El shell real es
[`templates/includes/base.html`](../../../templates/includes/base.html) +
[`templates/includes/sidebar/opciones.html`](../../../templates/includes/sidebar/opciones.html).
El aspecto coincide (píldora, activo en `--bg-brand` + `#fff` + 700, subítems a 20 px,
13 px de fuente: `opciones.html:616-645`). **El árbol no coincide:**

| Grupo del mockup | Hoy en `opciones.html` | Delta |
|---|---|---|
| Inicio · Dashboard · Ciudadanos · Reportes · Configuración · Programas · Administración | existen (L82, L107, L205, L296, L321, L431, L686) | — |
| *(el mockup no lo muestra)* | **Conversaciones** (L259) | el mockup omite un ítem vivo |
| Dispositivos → 7 subítems | Dispositivos → **2**: «Legajos» (L616) y «Configuración» (L629) | **5 subítems nuevos** |
| Merenderos → 5 subítems | **no existe el grupo**; a `/merenderos/` se llega tipeando la URL | **grupo nuevo entero** |

El propio mockup lo dice en F1: *«Entrada propia en el sidebar; hoy solo se llega tipeando
la URL»* (L405).

### 1.2 Barra superior

Mockup: `.topbar` (L92-L99) + `topbar(user)` (L1502-L1505). Alto 64 px, fondo blanco,
`box-shadow:var(--shadow-sm)`; buscador de 320×40 px con radio completo sobre `--g050` y
el texto «Buscar ciudadanos...»; a la derecha campana de 22 px, un punto de 6 px y el
bloque de usuario con avatar de 36 px con gradiente.

**Mapeo:** es la navbar real.
[`templates/includes/navbar.html:69-72`](../../../templates/includes/navbar.html) declara
`placeholder="Buscar ciudadanos..."`, `height:40px`, `border-radius:var(--rounded-full)`,
`background:var(--bg-secondary)`, `font-size:13.5px`; L95 la campana `fa-bell` de 22 px;
L151 el avatar de 36 px con `var(--gradient-brand)`. **Coincide tal cual.** El «punto»
gris del mockup es el indicador de WebSocket (`#websocket-status`, L141).

### 1.3 Responsive

El mockup trae un único breakpoint (L299): bajo 1100 px el sidebar `.sb` **se oculta**
(`display:none`) y `.split`, `.split3`, `.form`, `.roles`, `.dl` y `.svc` pasan a una
columna. No muestra ninguna pantalla en celular ni el sidebar móvil.

**Mapeo:** el shell real sí tiene sidebar móvil en overlay (contrato de la fila «Shell
backoffice» de [`chaco-design-system.md`](../../../.claude/agents/chaco-design-system.md)).
El mockup no contradice eso, simplemente no lo cubre: **el responsive de cada pantalla
nueva no está diseñado** (ver pregunta abierta Q7).

---

## 2. Diccionario de clases: mockup → pieza real

Tabla maestra. Las fichas por pantalla referencian esta tabla en vez de repetirla.
«IGUAL» = se puede usar la pieza real sin tocar nada y el resultado es el del mockup.

| Clase del mockup (línea) | Pieza real | Veredicto |
|---|---|---|
| `:root` tokens (L23-L32) | [`chaco-tokens.css`](../../../static/custom/css/chaco-tokens.css) | **IGUAL** en valores; distinto en nombres (ver §7 C-1) |
| `.app` `.sb` `.topbar` (L67-L99) | `includes/base.html` + `sidebar/` + `navbar.html` | **IGUAL** (árbol del menú aparte, §1.1) |
| `.page` (L100) | contenedor `space-y-5` del arquetipo detalle | IGUAL (20 px de gap = `space-y-5`) |
| `.ph` `.ph h1` `.eyebrow` (L101-L107) | `{% page_header %}` ([`core/templatetags/nodo_ui.py`](../../../core/templatetags/nodo_ui.py)) | **IGUAL**; el `eyebrow` no es parámetro del tag → **ampliar la pieza** |
| `.back` (L103) | `.btn-tertiary.btn-back-circle` ([`nodo-buttons.css:182`](../../../static/custom/css/nodo-buttons.css)) | **IGUAL** (40 px, pill, borde de marca) |
| `.btn.b/.s/.t/.d` (L111-L114) | `btn-nodo` + `btn-brand/btn-secondary/btn-tertiary/btn-danger` | IGUAL de color; **difiere el ancho**: el real tiene `min-width` 128/143/151 px ([`nodo-buttons.css:37-56`](../../../static/custom/css/nodo-buttons.css)), el mockup no → C-15 |
| `.btn.sm` / `.btn.xs` / `.btn.dis` (L115-L117) | `btn-sm` (36 px) / `btn-xs` (32 px) / `:disabled` | **IGUAL** |
| `.badge` + `.bg-gray/-w/-brand/-succ/-dang/-warn/-info` + `.dotb` (L118-L126) | [`nodo-badges.css`](../../../static/custom/css/nodo-badges.css) `badge-gray/-white/-brand/-success/-danger/-warning/-info` + `badge-dot` | **IGUAL exacto**, hex por hex |
| `.surface` + `.hd` + `.bd` (L127-L131) | «Surface/card backoffice» (`bg-white rounded-xl border border-base shadow-sm overflow-hidden`, header `px-5 py-4 border-b border-light`) | **IGUAL** |
| `.tabs` (L154-L159) | «Tabs backoffice» | IGUAL en geometría; **difiere el contador**: `.cnt` propio vs contrato `badge badge-info`/`badge-gray` |
| `table.dense` (L174-L182) | [`nodo-tables.css`](../../../static/custom/css/nodo-tables.css) `.nodo-thead-row/.nodo-th/.nodo-td` | **IGUAL exacto** (11 px upper .05em / 11×16; 14 px / 13×16) |
| `.pager` (L184-L185) | [`components/_paginacion.html`](../../../templates/components/_paginacion.html) | **IGUAL** |
| `.empty` (L253-L255) | [`components/_estado_vacio.html`](../../../templates/components/_estado_vacio.html) | **IGUAL exacto** (`py-14 px-6`, ícono 48 px brand, título 17 px) |
| `.fcard` + `.row` + `.foot` + `.rm` (L160-L166) | [`components/list_filters.html`](../../../templates/components/list_filters.html) + [`dynamic-list-filters.css`](../../../static/custom/css/dynamic-list-filters.css) + [`dynamic_list_filters.js`](../../../static/custom/js/dynamic_list_filters.js) | **IGUAL exacto**, incluida la grilla de la fila y el pie «Todos / Limpiar filtros / Aplicar» |
| `.nf` + `.err` + `.ro` + `.ta` (L167-L172) | `.nodo-field` + estados | **IGUAL exacto** |
| `.nf.pill` (L173) | — | **NUEVA** (filtro rápido en píldora de 36 px) |
| `.f label` / `.help` / `.e` (L188-L191) | canon de formulario (`block text-sm font-medium text-heading mb-1`, ayuda `text-body-subtle`, error `text-fg-danger`) | **IGUAL** |
| `.form` / `.full` (L186-L187) | grilla de 2 columnas de `becas/_field.html` | IGUAL |
| `.modal` + `.mh` + `.mb` + `.mf` (L240-L249) | «Modal Becas accesible» (`_modal_header.html` + `_modal_footer.html` + `becas-modal.js`) | **IGUAL exacto** (560 px, radio 16, caja de ícono 40 px `bg-brand-soft`, pie `bg-secondary`) |
| `.alert` + `.w/.d/.i` + `.a` (L147-L153) | [`components/_alerta.html`](../../../templates/components/_alerta.html) | **DIFIERE**: radio 12 vs 8 (`rounded-lg`), padding `12px 16px` vs `p-4`, el mockup **lleva ícono** y un **link de acción a la derecha** que la pieza no tiene |
| `.bar` + `.bar i` (L227-L229) | medidor del dashboard de Becas (`h-2 rounded-full bg-brand-soft` + relleno `--text-fg-brand`) | **IGUAL** |
| `.stat` + `.ico` (L132-L141) | `.stat-card` de [`templates/inicio.html:84-137`](../../../templates/inicio.html) | **IGUAL a Inicio**, pero Inicio **no es la pieza canónica** → conflicto C-2 |
| `.hero` (L142-L146) | `.ini-hero` de [`inicio.html:11-65`](../../../templates/inicio.html) | **IGUAL a Inicio** (radio 16, 28×32, gradiente, `shadow-brand`, h1 30/800, botón 44 px) → conflicto C-3 |
| `.acceso` (L273-L276) | `.acceso-btn` de [`inicio.html:139-176`](../../../templates/inicio.html) | **IGUAL a Inicio** (18 px, radio 12, caja 44 px radio 10, label 14/700) |
| `.kv` (L202-L204) | patrón `dl` de los detalles de Becas | IGUAL de hecho; **sin pieza única** |
| `.dl` (L205-L207) | patrón `dl` de `legajo/detail.html:86-94` | IGUAL de hecho; **sin pieza única** |
| `.chips` + `.chip` + `.chip.on` (L250-L252) | — (lo más cercano son las píldoras de `nodo-buscador`) | **NUEVA** |
| `.toggle` (L266-L269) | — (no hay switch en `nodo-forms.css`) | **NUEVA** |
| `.stepper` (L192-L199) | semántica de [`portal/inscripcion/_stepper.html`](../../../portal/templates/portal/inscripcion/_stepper.html) | **NUEVA en backoffice** |
| `.plazas` + `.plz` + `.oc/.ok/.rs/.fs/.pr` (L208-L216) | — | **NUEVA** |
| `.tl` + `.ev` (L217-L223) | — (lo más cercano es la `<ol>` del historial de `legajo/detail.html:131`) | **NUEVA** |
| `.sec` + `.sh` + `.sb2` + `.locked` (L224-L232) | — | **NUEVA** |
| `.turno` + `.on/.off` (L233-L236) | — | **NUEVA** |
| `.entry` (L237-L239) | — | **NUEVA** |
| `.grilla` (L256-L261) | tabla de [`merenderos/prestacion_mensual.html:34-60`](../../../programas/templates/programas/merenderos/prestacion_mensual.html) | **DIFIERE** (ver P13) |
| `.roles` + `.role` (L262-L264) | — | **NUEVA** |
| `.legendmini` + `.sq` (L270-L272) | — | **NUEVA** |
| `.svc` (L292-L298) | — | **NUEVA** |
| `.mapa` (L290-L291) | — (no hay librería de mapas en el repo) | **NUEVA** |
| `.fotos` + `.foto` (L287-L289) | — | **NUEVA** |
| `.kebab` (L183) | — (hoy las acciones de fila son `.nodo-icon-btn` sueltos) | **NUEVA** |
| `.split` / `.split3` (L200-L201) | utilidades de grilla | IGUAL (se resuelve con Tailwind) |
| Íconos (`[data-ico]`, L1440-L1466) | **Heroicons outline inline** | **MIXTO**: la regla `ICONARIA` de `design_audit` asume Font Awesome, pero `list_filters.html` y el sidebar **ya usan Heroicons inline** → §7 C-4 |

---

## 3. Los flujos (F1-F10): qué reglas imponen a las pantallas

Los diez flujos son SVG estáticos (no son pantallas) y no requieren implementación, pero
fijan reglas que las pantallas tienen que respetar. Resumen operativo, con la captura de
cada uno en [`capturas/`](capturas/):

| Flujo | Qué fija | Regla que condiciona la UI |
|---|---|---|
| **F1** Mapa de módulos (L358) · [`f01.jpg`](capturas/f01.jpg) | M1-M17; M14/M16/M17 son base común, M15 vive en el menú de Dispositivos | Merenderos **fuera** del alcance de M14 y M15 en esta etapa (L409) |
| **F2** Legajo institucional: estados (L412) · [`f02.jpg`](capturas/f02.jpg) | Borrador → Pendiente → Activo, con Observado, Rechazado, Inauguración pendiente, Suspendido, Cerrado | «quien cargó no valida»; «código duplicado bloquea y explica aunque esté fuera del alcance»; «nada se borra» (L435) |
| **F3** Estadía punta a punta (L440) · [`f03.jpg`](capturas/f03.jpg) | Persona → Estadía → Plaza en tres carriles | «el sistema alerta y **no bloquea**»; ingreso excepcional sobre capacidad con autorización registrada; ficha se completa en 15 días |
| **F4** Traslado en tránsito (L489) · [`f04.jpg`](capturas/f04.jpg) | Alojada → En tránsito → Trasladada, con vuelta a Alojada | «Nunca dos estadías alojadas para la misma persona»; mientras hay tránsito, origen **no** puede egresar ni volver a trasladar |
| **F5** Plazas (L516) · [`f05.jpg`](capturas/f05.jpg) | Disponible/Reservada/Ocupada/Prestada/Fuera de servicio | **Todo lo numérico es derivado**: `disponibles = operativas − ocupadas − reservadas`; fuera de servicio solo tras reubicar |
| **F6** Turno y bitácora (L550) · [`f06.jpg`](capturas/f06.jpg) | Abrir → novedades → censo → cerrar con pase de guardia | «las entradas se agregan, nunca se pisan»; corregir = nueva versión; ventana de regularización 7 días |
| **F7** Merenderos (L569) · [`f07.jpg`](capturas/f07.jpg) | Solicitud → validación → activo → entregas → prestación | **Bloqueo duro** por documentación vencida (único bloqueo del sistema); cobertura = raciones servidas vs equivalente entregado vs capacidad |
| **F8** Infraestructura (L593) · [`f08.jpg`](capturas/f08.jpg) | Al día → Por vencer (aviso 30 d) → Vencido → alerta | Periodicidad 6 meses (1 mes en obra); «Relevar ya» solo del Administrador superior; **un edificio puede alojar varias instituciones** |
| **F9** Relevamiento edilicio (L633) · [`f09.jpg`](capturas/f09.jpg) | Coordinador asigna → territorial carga → tercero valida | **Nunca se asigna al personal de la institución relevada**; el territorial no ve el menú |
| **F10** Consumos y contratos (L662) · [`f10.jpg`](capturas/f10.jpg) | Ítem → vencimiento → alerta 7 d → pago con comprobante o escalamiento | Sin comprobante el ítem no vuelve a «al día»; nada se bloquea; un ítem no se borra, se da de baja |

> **Inconsistencia del propio mockup.** La bajada del sidebar y la intro dicen «Extendido
> con los requerimientos del 16/09/2026 (**F8 a F11**)» (L305, L347) y P22 dice «Implementa
> **F11**» (L1387), pero **no existe un tablero `#f11`**: los flujos terminan en F10.
> Coincide con el pendiente del Cambio 85: *«Abate menciona «F11» dos veces como referencia
> conocida y no está identificado en la documentación»*. Ver Q1.

---

## 4. Las 22 pantallas

> El pedido hablaba de 20 pantallas. El mockup publicado tiene **22** (`#p1`…`#p22`) más
> 10 flujos (`#f1`…`#f10`): 32 tableros `.board` en total. Se mapean las 22.

---

### P1 · Tablero de la red (`#p1`, L693-L730) · [`p01.jpg`](capturas/p01.jpg)

**Qué es y en qué flujo cae.** Primera pantalla del programa Dispositivos (ítem de menú
`disp-tablero`). Implementa **M8** de F1. Usuario del ejemplo: «Andrea Alarcón ·
Supervisora de área · Abordaje Psicosocial». La bajada del mockup lo declara explícito:
*«con el mismo patrón que el Inicio»*.

**Inventario visual.**

- Layout vertical `.page` (gap 20 px), sin `.ph`: arranca directo con la franja `.hero`.
- **Hero** con `--gradient`: eyebrow «PROGRAMA DISPOSITIVOS · ABORDAJE PSICOSOCIAL», h1
  «Red de dispositivos», bajada *«18 instituciones en tu alcance. Ocupación exigida en 3,
  dos tránsitos vencidos y un turno sin cerrar. Este es el estado de la red ahora.»* y
  botón blanco `.hb` «Ver instituciones» con ícono `building`.
- **4 stat cards** (`.stats`, `auto-fit minmax(190px,1fr)`), cada una con etiqueta,
  caja de ícono de 52 px, valor de 32 px y nota:
  «Plazas operativas» 1.284 / *de 1.340 totales · 56 fuera de servicio* (ícono `brand`);
  «Ocupación de la red» 78 % / *exigida · 3 dispositivos críticos* (`wa`, nota `.m.warn`);
  «Disponibles ahora» 231 / *51 reservadas · 12 prestadas* (`ok`, `.m.ok`);
  «Alertas activas» 17 / *4 tránsitos vencidos · 2 permanencias > 48 h* (`da`, `.m.bad`).
- **Tarjeta de filtros** `.fcard` en modo compacto: título «Filtros» con ícono `sliders` y
  cuatro `.nf.pill` — «Área: Abordaje Psicosocial», «Tipo: Todos», «Localidad: Resistencia»,
  «Período: 30 días» — más `.btn.t.sm` «+ Agregar filtro».
- **`.split` (1.6fr / 1fr):**
  - Izquierda, surface «Ocupación por dispositivo» / *«Sobre plazas operativas, con los
    umbrales de cada tipo»* + `.btn.s.sm` «Exportar». `table.dense` con columnas
    Dispositivo · Tipo · Ocup. · Disp. · Estado; 6 filas; nombre como link con `.sub`
    (`CIS-003 · Resistencia`); porcentajes en `td.num`; badges `bg-dang` «Crítica»,
    `bg-warn` «Exigida», `bg-succ` «Normal», `bg-gray` «No aplica». La fila «Mírame / Vedia»
    hace `colspan="2"` con el texto «64 en seguimiento».
  - Derecha, surface «Alertas operativas» / *«Ordenadas por severidad»* con `badge bg-dang`
    «17» y 5 `.alert` con ícono y link de acción: `d` «Permanencia > 48 h» → «Ver»;
    `d` «Tránsito vencido» → «Resolver»; `w` «Turno sin cerrar» → «Abrir»;
    `w` «Documentación vencida» → «Ver legajo»; `i` «Fichas incompletas» → «Listar».
- **`.split3`** con tres `.acceso`: «Lista de espera de la red · 14» (ícono warn),
  «Merenderos con cobertura en rojo · 5» (brand), «Calidad del dato · 117 verificadas,
  11 migradas» (succ).
- **Vocabulario fijado en las notas (L729):** *«normal, exigida, crítica en vez del nombre
  del color»*.
- Estados vacío / error / cargando: **no los muestra**.

**Mapeo al sistema de diseño.**

| Componente | Pieza | Veredicto |
|---|---|---|
| `.hero` | `.ini-hero` de `inicio.html` | productivo, **no canónico** → C-3 |
| `.stats`/`.stat` | `.stat-card` de `inicio.html` | productivo, **no canónico** → C-2 |
| `.fcard` con `.nf.pill` | `list_filters.html` | la tarjeta es IGUAL; **las píldoras son NUEVAS** |
| surface + `table.dense` + badges | canónicas | IGUAL |
| `.alert` con ícono + link | `_alerta.html` | **DIFIERE** → C-5 |
| `.acceso` | `.acceso-btn` de `inicio.html` | productivo, no canónico |

**Arquetipo.** Ninguno. El núcleo lo clasifica «Duplicado o conflictivo»: *«Pendiente ·
wizard, revisión compleja y dashboard … **No hay golden: frenar y devolver al llamador**»*
([`chaco-design-system.md:149`](../../../.claude/agents/chaco-design-system.md), ficha
[`arquetipos/pendientes.md`](../../../.claude/design/arquetipos/pendientes.md)). P1 es un
dashboard completo. → C-7.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Plazas totales / operativas / ocupadas / disponibles | `resumen_ocupacion()` ([`services/camas.py:9`](../../../programas/services/camas.py)) — es **por dispositivo** | agregación **de red** sobre el alcance |
| Ocupación % y semáforo | `indicadores_dispositivo()` ([`services/indicadores.py:44`](../../../programas/services/indicadores.py)) con `TipoDispositivo.umbral_ocupacion_amarillo/rojo` ([`models/__init__.py:451-460`](../../../programas/models/__init__.py)) | los umbrales existen; falta el rollup |
| Alcance del usuario | `dispositivos_visibles(user)` ([`services/dispositivos.py:94`](../../../programas/services/dispositivos.py)) | — |
| Reservadas / prestadas | `Cama.Estado` tiene `RESERVADA` (`models:663`) | **`PRESTADA` no existe** como estado de cama |
| Alertas operativas | — | **modelo de alerta operativa del programa inexistente**; `legajos` tiene `AlertaCiudadano` ([`legajos/models/base.py:400`](../../../legajos/models/base.py)) pero es del ciudadano |
| «Tránsito vencido» | — | **no hay estado de tránsito** (ver P8) |
| «Turno sin cerrar» | `RegistroDiario` (`models:807`) es un snapshot por turno, **sin apertura/cierre** | apertura, cierre y pase de guardia |
| «Fichas incompletas» | `indicadores.completitud` existe por dispositivo | rollup de red |
| Exportar | `dispositivos:exportar` (`padron`/`ocupacion`/`movimientos` × csv/xlsx) ([`dispositivos_urls.py:11`](../../../programas/dispositivos_urls.py)) | — |
| Capacidad RBAC | `dispositivo.ver` ([`core/rbac.py:63`](../../../core/rbac.py)) | capacidad propia para el tablero de red si se quiere separar |

**Reemplaza a.** Nada: hoy `/dispositivos/` abre directo el listado
([`dispositivos_urls.py:10`](../../../programas/dispositivos_urls.py)). Es pantalla nueva y
**ítem de menú nuevo**.

**Conflictos.** C-2 (stat cards), C-3 (hero), C-5 (alertas), C-7 (sin golden de dashboard).

**Esfuerzo.** **L** (agregación de red + modelo de alertas + 3 piezas nuevas).

---

### P2 · Instituciones: listado (`#p2`, L733-L756) · [`p02.jpg`](capturas/p02.jpg)

**Qué es y en qué flujo cae.** Listado del legajo institucional de dispositivos (M1 de F1,
estados de F2). Es la pantalla que el link del pedido abre (`#p2`). Menú `disp-inst`.

**Inventario visual.**

- `.ph` con eyebrow «Programa Dispositivos», h1 «Instituciones», bajada *«Legajo
  institucional de cada dispositivo: identidad, encuadre, plazas y estado de validación.
  Los merenderos tienen su propio listado.»* y tres acciones a la derecha:
  `.btn.s` «Exportar ⌄» (ícono `chart` + chevron), `.btn.t` «Importar padrón» (`doc`),
  `.btn.b` «+ Nueva institución».
- **`.fcard` completa:** título «Filtros» + `badge bg-gray` «2 activos»; `.btn.t`
  «+ Agregar filtro»; dos `.row` de cuatro celdas (campo · operador «es» · valor · `.rm` ✕):
  «Estado / es / Activo» y «Localidad / es / Resistencia»; `.foot` con `.nf` «Todos» de
  120 px, `.btn.t` «Limpiar filtros» y `.btn.b` «Aplicar» con ícono `search`.
- **Surface con `table.dense`**, 7 columnas: Institución · Tipo · área · Categoría ·
  Plazas · Estado · **Dato** · Acciones (derecha). 7 filas de ejemplo.
  - Institución: link + `.sub` `CÓDIGO · Localidad`.
  - Tipo · área: tipo + `.sub` con la dirección del Ministerio.
  - Categoría: «Público / Estatal», «Religioso» con `.sub` «gestión del Ministerio», «ONG».
  - Plazas: `td.num` «37 / 42» + badge de porcentaje tonal (`bg-dang` 88 %, `bg-warn` 74 %,
    `bg-succ` 42 %); variantes de texto subtle «sin plazas» y «64 en seguimiento».
  - Estado: `badge dotb` `bg-succ` «Activo», `bg-brand` «Inauguración pendiente»,
    `bg-info` «Pendiente de validación».
  - Dato: `badge bg-succ` «Verificado» / `bg-warn` «Migrado» (las notas lo definen como
    *«nivel de confianza del legajo»*).
  - Acciones: `.btn.s.sm` «Ver detalle».
- **`.pager`:** «Página 1 de 6 · 128 instituciones» + «‹ Anterior» (`.dis`) y «Siguiente ›».
- **Estados vacíos declarados en las notas (L755):** con filtro → *«Ningún dispositivo
  coincide con los filtros · Limpiar filtros»*; por alcance → *«No hay dispositivos en tu
  alcance»*.

**Mapeo al sistema de diseño.** Todo canónico: `page_header`, `list_filters`, surface,
`nodo-tables`, `nodo-badges`, `_paginacion`, `_estado_vacio` con `con_filtros`. El eyebrow
del `.ph` **no es parámetro** de `{% page_header %}` hoy → ampliar la pieza (N-1).

**Arquetipo.** **Listado** — golden
[`programas/templates/programas/becas/revision/personas_list.html`](../../../programas/templates/programas/becas/revision/personas_list.html),
ficha [`arquetipos/listado.md`](../../../.claude/design/arquetipos/listado.md). Es la pantalla
del mockup que **mejor encaja** con el sistema tal como está.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Nombre, código, localidad, tipo, estado | `Dispositivo` (`models:477-516`) | — |
| Filtros tipo/estado/localidad | `DispositivoListView` ([`views/dispositivos_legajo.py`](../../../programas/views/dispositivos_legajo.py)) y el form de `legajo/list.html:25-32` | solo el texto del operador: [`dynamic_list_filters.js:97`](../../../static/custom/js/dynamic_list_filters.js) ya pinta uno decorativo de una sola opción («Igual a» / «Contiene»), el mockup dice «es» |
| Estados «Inauguración pendiente» | `Dispositivo.Estado` tiene BORRADOR, PENDIENTE_VALIDACION, ACTIVO, OBSERVADO, RECHAZADO, INACTIVO, CERRADO (`models:480-487`) | **`INAUGURACION_PENDIENTE` y `SUSPENDIDO`** (F2 los pide; «Suspendido» existe en `Merendero.Estado` (`models:896`), `Programa` (`models:116`) e `InscripcionPrograma` (`models:219`), pero no en `Dispositivo.Estado`) |
| **Área del Ministerio** | — | **campo nuevo**; `configuracion` tiene secretarías/subsecretarías, falta la FK |
| **Categoría** (Público/Religioso/ONG) | — | **campo nuevo** |
| Plazas «37 / 42» | `camas_totales` (`models:509`) + `resumen_ocupacion()` | el denominador del mockup es **operativas**, no totales |
| **Dato / nivel de confianza** | `fuente_padron`, `fecha_padron`, `responsable_padron` (`models:506-508`) | **el badge Verificado/Migrado**: hay procedencia, no hay nivel |
| Paginación | — | **`paginate_by = 25` + `_paginacion`** (PERF-17 de §7 de la auditoría) |
| Importar padrón | — | **vista nueva** |
| RBAC | `dispositivo.ver`, `dispositivo.crear` | — |

**Reemplaza a.** [`programas/templates/programas/dispositivos/legajo/list.html`](../../../programas/templates/programas/dispositivos/legajo/list.html)
(`dispositivos:lista`), que hoy titula «Legajos de dispositivos», tiene **6 botones de
exportación sueltos** en el header (L15-L20) y una tabla con utilidades en línea
(`<thead style="background:…">`, L36) en vez de `.nodo-th`/`.nodo-td`. El mockup unifica los
6 botones en **un** control «Exportar ⌄».

**Conflictos.** Ninguno de diseño. El único roce es de vocabulario: el listado real se llama
«Legajos de dispositivos» y el mockup «Instituciones» (ver Q3).

**Esfuerzo.** **M** (pantalla fácil; el peso está en los campos nuevos del modelo).

---

### P3 · Alta de institución con anti-duplicado (`#p3`, L759-L791) · [`p03.jpg`](capturas/p03.jpg)

**Qué es y en qué flujo cae.** Alta del legajo institucional, estado Borrador de F2.
Usuario: «Claudia Ríos · Equipo territorial».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «Legajo institucional», h1 «Nueva institución», bajada
  *«Se guarda como borrador. Para enviar a validación hacen falta los campos marcados con
  \*»* (el asterisco en `--dang`).
- **`.split`.** Izquierda, surface «Identidad y encuadre» con `badge dotb bg-w` «Borrador»
  y un `.form` de 2 columnas:

  | Campo | Obligatorio | Control | Texto auxiliar |
  |---|---|---|---|
  | Código institucional | sí | `.nf.err` con «CIS-003» | `.e` *«El código ya está en uso por una institución fuera de tu alcance. Pedí el traspaso al administrador central o usá otro código.»* |
  | Tipo de dispositivo | sí | select | `.help` *«Define la ficha, los tipos de plaza y las reglas de ingreso.»* |
  | Nombre (`.full`) | sí | texto | — |
  | Categoría | sí | select «Público / Estatal» | — |
  | Área del Ministerio | sí | select «Dirección de Abordaje Psicosocial» | — |
  | Titularidad del inmueble | no | select «Iglesia Católica» | — |
  | Dependencia de la gestión | no | select «Ministerio» | — |
  | Domicilio (`.full`) | sí | texto + `badge bg-succ` «Geolocalizado» | — |
  | Responsable institucional | sí | `.nf.ph` «Buscar persona por DNI…» | — |
  | Teléfono de contacto | sí | texto | — |
  | Servicios que brinda (`.full`) | no | `.chips` 8 chips, 6 en `on`: Alojamiento, Desayuno, Almuerzo, *Merienda*, Cena, Atención social, Salud / Enfermería, *Actividades* | — |

  Pie de la card (`.pager` con fondo blanco): `.btn.t` «Cancelar», `.btn.s` «Guardar
  borrador», `.btn.b.dis` «Enviar a validación» **deshabilitado**.
- **Derecha, tres surfaces:**
  - «Posibles duplicados» + `badge bg-warn` «2»: `.alert.w` *«**Nombre y localidad
    coinciden** con CIS N.º 3 (CIS-003), Activo, misma área. Si es la misma institución,
    pedí el traspaso.»* y `.alert.i` *«**Domicilio a 120 m** de Anexo CIS 3 (CIS-003B),
    Suspendido.»*
  - «Qué falta para validar»: `<ul>` con «Código institucional disponible» y «Responsable
    institucional» + *«Lo demás está completo. Valida otra persona, no quien carga.»*
  - «Procedencia del dato»: `.kv` Fuente «Relevamiento territorial» · Fecha «08/09/2026» ·
    Confianza `badge bg-succ` «Verificado en campo».

**Mapeo al sistema de diseño.** `page_header`, surface, `nodo-field` (+ `.err`), labels y
ayudas canónicas, badges, `.alert` (difiere, C-5). **NUEVOS:** `.chips` como selector
múltiple en píldoras, y el pie de acciones dentro de la card con fondo blanco (la pieza
`_modal_footer` es para modales; en página el canon pone las acciones en el header).

**Arquetipo.** **Formulario** — golden
[`becas/config/segmento_form.html`](../../../programas/templates/programas/becas/config/segmento_form.html)
+ `becas/_field.html`. Pero el mockup lo arma en `.split` con una columna lateral de
feedback; eso **no está en la golden** (29 líneas, una sola columna). → variante nueva.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Código, nombre, domicilio, localidad, teléfono, responsable | `Dispositivo` (`models:495-504`) | — |
| Latitud/longitud («Geolocalizado») | `Dispositivo.latitud/longitud` (`models:499-500`) | **la captura del punto**: hoy son campos sueltos sin mapa |
| Anti-duplicado | **ya existe**: `buscar_posibles_duplicados(codigo, nombre, localidad)` ([`services/dispositivos.py:152`](../../../programas/services/dispositivos.py)) y la vista `DispositivoDuplicateSearchView` (`dispositivos_urls.py:13`) | **el criterio por distancia** («a 120 m»); y que busque **fuera del alcance** |
| «Qué falta para validar» | `_exigir_campos_para_validacion()` ([`services/dispositivos.py:178`](../../../programas/services/dispositivos.py)) | hoy corre **al enviar**, no en vivo mientras se carga |
| Separación de funciones | `enviar_a_validacion` / `validar_dispositivo` (`services/dispositivos.py:201,214`) | **el motor no comprueba hoy que quien validó no sea quien cargó** |
| Categoría · Área · Titularidad · Dependencia de la gestión | — | **4 campos nuevos** |
| Servicios que brinda | — | **campo nuevo** (M2M o JSON) |
| Responsable por DNI | `responsable_nombre`/`responsable_documento` son texto (`models:501-502`) | **FK a `Ciudadano`** si se quiere buscador real |
| Procedencia / confianza | `fuente_padron`, `fecha_padron`, `responsable_padron` | **nivel de confianza** |
| RBAC | `dispositivo.crear`, `dispositivo.validar` | — |

**Reemplaza a.** [`legajo/form.html`](../../../programas/templates/programas/dispositivos/legajo/form.html)
(85 líneas, `dispositivos:crear` / `:editar`).

**Conflictos.** C-5 (alertas). Y un conflicto funcional citable: el mensaje de error del
código duplicado **nombra una institución fuera del alcance del usuario** («CIS N.º 3
(CIS-003), Activo, misma área»), lo que filtra existencia y estado de un registro que el
usuario no puede ver → C-8.

**Textos que cambian por decisión del PM (06/10/2026, C-8 → B).** El HTML del mockup no se
edita; se implementa con estos textos:

| Dónde | Dice el mockup | Se implementa |
|---|---|---|
| `.e` bajo «Código institucional» | *«El código ya está en uso por una institución **fuera de tu alcance**. Pedí el traspaso al administrador central o usá otro código.»* | **«El código ya está en uso. Pedí el traspaso al administrador central.»** |
| `.alert.w` del panel «Posibles duplicados» | *«**Nombre y localidad coinciden** con CIS N.º 3 (CIS-003), Activo, misma área…»* | Si la institución coincidente está **fuera del alcance**, no se la nombra: ni nombre, ni código, ni estado, ni área. Solo se avisa que hay una coincidencia y se ofrece el traspaso. Si está **dentro** del alcance, el texto del mockup se mantiene tal cual. |

El badge «2» de posibles duplicados cuenta solo las coincidencias **visibles** para el
usuario; las de fuera del alcance bloquean sin sumar al contador.

**Esfuerzo.** **M**.

---

### P4 · Detalle del dispositivo (`#p4`, L794-L822) · [`p04.jpg`](capturas/p04.jpg)

**Qué es y en qué flujo cae.** La pantalla central del programa. Reúne M1-M6 + M14 + M16.
Usuario: «Marcela Fernández · Responsable institucional · CIS 3». Está mostrada con la
solapa **Estadías** activa.

**Inventario visual.**

- `.ph` con `.back`, h1 «CIS N.º 3» + `badge dotb bg-succ` «Activo», bajada en una línea:
  *«CIS-003 · Abordaje Psicosocial · Dirección de Abordaje Psicosocial · Av. Sarmiento
  1250, Resistencia · responsable M. Fernández»*. Acciones: `.btn.s` «Bitácora del turno»
  (ícono `clock`), `.btn.s` «Editar», `.btn.t` «Cerrar», `.btn.b` «+ Ingresar persona».
- **Dos `.alert` inline debajo del header:**
  - `d`: *«**Tránsito vencido:** L. Gómez lleva 9 h en tránsito hacia Albergue Calcuta. La
    plaza C-04 sigue reservada.»* → «Resolver».
  - `w`: *«**Relevamiento de infraestructura vencido:** última carga el 02/02/2026, el plazo
    de 6 meses venció el 02/08. No bloquea la operación del dispositivo.»* → «Ver
    Infraestructura».
- **Surface «Indicadores operativos»** / *«Derivados de plazas, estadías y bitácora; no
  admiten carga manual.»* con 4 stat cards fijas a `repeat(4,1fr)`:
  Ocupación 88 % (valor en `--dang`) / *crítica · 37 de 42 operativas*;
  Disponibles 3 / *2 reservadas · 1 prestada*;
  Bitácora «Al día» (valor a 24 px) / *turno Tarde abierto · última entrada 16:42*;
  Fichas completas 71 % / *6 estadías con secciones pendientes*.
- **Surface con 9 solapas** (L809): Datos · Sectores y plazas `42` · **Estadías `37`
  (activa)** · Lista de espera `5` · Bitácora · Documentación `4` · Infraestructura
  + `badge bg-warn` «vencido» · Consumos y contratos `4` · Historial.
- Fila de filtros rápidos en `.nf.pill`: «Estado: Alojadas», «Sector: Todos»,
  «Ficha: Todas» + `.btn.t.sm` «Ver egresadas» alineado a la derecha.
- **`table.dense`** Persona · Ingreso · Sector · plaza · Estado · Ficha · Alertas · Acciones.
  5 filas; la columna Ficha usa `.bar` + porcentaje (90 %, 45 % con `.bar.w`, 100 %, 80 %,
  30 % con `.bar.w`); los estados son badges `bg-warn` «En tránsito → Calcuta», `bg-info`
  «Alojado»/«Alojada»/«Permiso de salida», con badges extra `bg-brand` «Reingreso» y
  `bg-brand` «prestada a R. Díaz»; alertas `bg-dang` «Tránsito 9 h», `bg-warn` «Ficha 15 d»,
  `bg-warn` «Regresa 22:00». Acciones: `.btn.s.sm` «Ver» + `.kebab` ⋮.
- `.pager` «Página 1 de 4 · 37 alojadas».
- **Notas (L821):** el menú ⋮ ofrece *«cambiar plaza · permiso de salida · trasladar ·
  egresar, deshabilitados con motivo cuando hay tránsito pendiente»*; las solapas guardan
  estado en `?tab=` con *«ARIA completa»*.

**Mapeo al sistema de diseño.**

| Componente | Pieza | Veredicto |
|---|---|---|
| header + badge + acciones | `page_header` | IGUAL |
| alertas inline | `_alerta.html` | DIFIERE (C-5) |
| franja de métricas | `_stat_card.html` canónico vs `.stat-card` de Inicio | C-2 |
| solapas | Tabs backoffice, `?tab=` | IGUAL (el `.cnt` → `badge badge-info`/`badge-gray`) |
| tabla + badges + `.bar` + pager | canónicas | IGUAL |
| `.nf.pill` | — | NUEVA |
| `.kebab` | — | NUEVA |

**Arquetipo.** **Detalle con solapas** — golden
[`becas/cupo/segmento_detail.html`](../../../programas/templates/programas/becas/cupo/segmento_detail.html).
Encaja bien; la única salvedad es la cantidad de solapas (9, con una que lleva badge).

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Cabecera y estado | `Dispositivo` | el área del Ministerio (campo nuevo, ver P2) |
| Indicadores | `indicadores_dispositivo()` devuelve ocupación, disponibilidad, actualización y completitud con semáforo (`services/indicadores.py:44`) | «Bitácora: Al día» y el detalle «turno Tarde abierto» (no hay turnos abiertos) |
| Solapa Estadías | `Admision` (`models:695`) con `select_related` en `DispositivoDetailView` | — |
| Estado «En tránsito» | `Admision.Estado` tiene `TRASLADADO` pero **no `EN_TRANSITO`** (`models:698-706`) | **estado nuevo + reserva de plaza + vencimiento** |
| «Permiso de salida» | — | **estado/movimiento nuevo** |
| «Préstamo de plaza» 12/24 h | — | **nuevo** |
| Reingreso | `Admision.es_reingreso` (`models:745`) y `_es_reingreso()` ([`services/admisiones.py:45`](../../../programas/services/admisiones.py)) — **hoy mira solo el mismo dispositivo** | F3 lo pide *«en toda la red»* |
| Sector | **no existe**: `Cama` solo tiene `dispositivo` y `codigo` (`models:667-673`) | **modelo `Sector`** |
| % de ficha | `indicadores._tiene_valor()` sobre `respuestas_f00` | el corte **por sección** y el plazo de 15 días |
| Alertas de fila | — | nuevas |
| Paginación de estadías | — | PERF-17 |
| Solapas Documentación / Infraestructura / Consumos / Lista de espera / Bitácora | — | ver P19, P20, P11, P10 |

**Reemplaza a.** [`legajo/detail.html`](../../../programas/templates/programas/dispositivos/legajo/detail.html)
(173 líneas), que hoy tiene **4 solapas** (Datos · Camas · Admisiones · Historial), un
`<style>[x-cloak]` local (L9), `<h1>` a mano (L17) y confirmaciones por SweetAlert2
(L138-L172).

**Conflictos.** C-2, C-5, C-6 (SweetAlert vs modal con motivo), C-9 (el menú ⋮ no existe
como pieza y el canon pide `.nodo-icon-btn` con `aria-label`).

**Esfuerzo.** **L**.

---

### P5 · Sectores y plazas (`#p5`, L825-L844) · [`p05.jpg`](capturas/p05.jpg)

**Qué es y en qué flujo cae.** Mapa de plazas de M2; aplica los estados de F5. Es una
pantalla propia, no la solapa (aunque el detalle tiene la solapa «Sectores y plazas 42»).

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3», h1 «Sectores y plazas», bajada
  *«42 operativas de 44 · 37 ocupadas · 2 reservadas · 1 prestada · 2 fuera de servicio»*;
  acciones `.btn.t` «Nuevo sector» y `.btn.b` «+ Agregar plazas».
- **`.legendmini`** con 5 cuadraditos `.sq`: Disponible (succ-050/200), Ocupada
  (brand-050/200), Reservada (warn), Prestada (`#FFEAF6`/`#FFB9DC`), Fuera de servicio (dang).
- **Tres surfaces, una por sector.** Header: h4 «Pabellón A · varones · 16 camas» y
  bajada «14 ocupadas · 1 prestada · 1 fuera de servicio · 88 %», más `.btn.s.sm`
  «Editar sector». Cuerpo: `.plazas` (`auto-fill minmax(84px,1fr)`, gap 10) con celdas
  `.plz`: código en `<b>` 13 px, estado, y `<small>` con la persona (truncado con
  ellipsis). Variantes `oc` (ocupada, violeta), `ok` (disponible, verde), `rs` (reservada,
  naranja), `fs` (fuera de servicio, rojo, con motivo: «colchón», «reparación»), `pr`
  (prestada, rosa: «Díaz, R. (Pérez)»).
  - Pabellón B · mujeres · 12 camas — «10 ocupadas · 2 disponibles · 83 %».
  - Pabellón C · tránsito y observación · 16 camas — «13 ocupadas · 2 reservadas · 1 fuera
    de servicio»; C-03 «espera #1», C-04 «tránsito Gómez».
- **Notas (L843):** clic en una plaza abre *«panel lateral con estado, historial y acciones
  (reservar, prestar 12/24 h, fuera de servicio con motivo, reubicar)»*; en tipos sin cama,
  el sector *«muestra cupos o turnos con la misma mecánica»*.

**Mapeo al sistema de diseño.** `page_header` y surface son canónicos. **NUEVAS:**
`.legendmini`/`.sq` (leyenda de color), `.plazas`/`.plz` (mapa de plazas con 5 estados), y
el **panel lateral** que las notas describen y el mockup no dibuja.

**Arquetipo.** Detalle, degradado: no hay tabla ni solapas. El mapa de plazas es una pieza
sin precedente en el sistema.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Plaza, código, estado | `Cama` + `Cama.Estado` DISPONIBLE/RESERVADA/OCUPADA/FUERA_SERVICIO (`models:658-689`) | **estado `PRESTADA`** |
| Persona en la plaza | `Admision.cama` (`models:728`) | — |
| **Sector** («Pabellón A · varones · 16 camas») | **no existe** | **modelo `Sector`** (dispositivo, nombre, perfil, capacidad) + FK en `Cama` |
| Motivo del fuera de servicio | **no existe** | **campo obligatorio** (F5: *«motivo obligatorio»*) |
| Préstamo 12/24 h | — | **nuevo**: a quién, por cuánto, vencimiento |
| Reserva con vencimiento | `RESERVADA` es solo un estado | **vencimiento de la reserva** (F5: «reserva vencida» vuelve a Disponible) |
| «operativas = totales − fuera de servicio» | `resumen_ocupacion()` ([`services/camas.py:9`](../../../programas/services/camas.py)) devuelve totales/ocupadas/libres/fuera_servicio | la aritmética de F5 con reservadas y prestadas (criterio DIS-07 de §7: *«`libres = DISPONIBLE`; reservadas y prestadas no cuentan»*) |
| Sacar de servicio con alguien alojado | `actualizar_cama()` ([`services/camas.py:54`](../../../programas/services/camas.py)) | **asistente de reubicación** (F5: *«solo tras reubicar»*) |
| Alta de camas | `crear_camas()` (`services/camas.py:81`) + `dispositivos:camas_agregar` | alta **por sector** |

**Reemplaza a.** La solapa «Camas» de `legajo/detail.html:98-117` (tabla plana código +
estado) y [`legajo/camas_form.html`](../../../programas/templates/programas/dispositivos/legajo/camas_form.html).

**Conflictos.** Ninguno de diseño; el `.plz` usa los mismos tonos que los badges.

**Esfuerzo.** **M** (pantalla simple, pero depende del modelo `Sector` y de `PRESTADA`).

---

### P6 · Ingreso de una persona (`#p6`, L847-L872) · [`p06.jpg`](capturas/p06.jpg)

**Qué es y en qué flujo cae.** Asistente de ingreso de M3; implementa el carril «Persona»
y el salto a «Plaza» de F3. Usuario: «Lucía Méndez · Operadora de turno · CIS 3».
El mockup muestra el **paso 2 de 4**.

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3 · turno Tarde · 08/09/2026 16:48», h1 «Ingresar
  persona», bajada «Paso 2 de 4 · Plaza».
- **`.stepper`** de 4 pasos con conectores de 56 px: ① Persona (`done`, círculo violeta
  con ✓) — ② **Plaza** (`on`) — ③ Ficha mínima — ④ Confirmar.
- **`.split`.** Izquierda, columna con:
  - `.alert.w`: *«**Ramírez, Jorge tiene una estadía residencial activa** en Parador
    Nocturno (ingreso 05/09). No puede quedar alojado en dos lugares: egresalo allí o
    iniciá un traslado hacia acá.»* → «Iniciar traslado».
  - `.alert.i`: *«**Reingreso:** estadía anterior en CIS N.º 3 egresada el 14/03/2026 (alta
    con derivación). También está **en seguimiento ambulatorio** en Mírame/Vedia, compatible
    con alojarlo.»*
  - Surface «Elegí la plaza» / *«3 disponibles · sectores compatibles con el perfil»* +
    `.btn.t.sm` «Ver mapa». Cuerpo: `.plazas` a `minmax(120px,1fr)` con B-03 disponible
    **seleccionada** (`outline:2px solid var(--brand)`), B-08 disponible, C-03 reservada
    («espera #1 · liberar») y dos celdas **punteadas**: «Sin plaza / lista de espera» y
    «Excepcional / sobre capacidad» (borde y texto rosa `#FFB9DC`/`#A11F60`).
    Debajo, `.alert.w`: *«**Ocupación crítica (88 %).** El sistema no bloquea el ingreso. Si
    elegís "Excepcional", se pedirá quién autoriza y el motivo, y quedará en la traza.»*
  - Derecha, surface «Persona» + `badge bg-succ` «Legajo Ciudadano» con `.kv`:
    Nombre «Jorge Daniel Ramírez» · DNI / CUIL «28.556.001 · 20-28556001-3» ·
    Nacimiento «14/02/1981 · 45 años» · Género «Masculino» · Obra social «Sin cobertura» ·
    Domicilio «Sin domicilio fijo» · Legajo «Ver legajo completo →». Nota:
    *«Estos datos vienen del Legajo Ciudadano y no se vuelven a preguntar. Si están mal, se
    corrigen allí.»* Pie: `.btn.t` «‹ Persona» y `.btn.b` «Continuar ›».
- **Notas (L871):** paso 1 = DNI, sexo opcional para RENAPER, alta mínima si no existe;
  paso 3 = solo las secciones mínimas del tipo; paso 4 = resumen, turno, hora y
  confirmación, **y genera la entrada en la bitácora**.

**Mapeo al sistema de diseño.** `page_header`, surface, `.kv`, `.alert` (C-5), botones.
**NUEVAS:** `.stepper` en backoffice (la semántica accesible sale de
[`portal/inscripcion/_stepper.html`](../../../portal/templates/portal/inscripcion/_stepper.html):
`aria-current="step"` + `sr-only "Paso actual:"`), y el selector de plaza con celdas
punteadas.

**Arquetipo.** **Wizard → sin golden: «frenar y devolver al llamador»**
([`arquetipos/pendientes.md`](../../../.claude/design/arquetipos/pendientes.md)). → C-7.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Persona | `Ciudadano` ([`legajos/models/base.py:15`](../../../legajos/models/base.py)): dni, nombre, apellido, fecha_nacimiento, genero, domicilio, `obra_social` (L123) | **CUIL no existe** como campo |
| Estadía activa en otro dispositivo | `UniqueConstraint(["ciudadano","dispositivo"], condition=ALOJADO)` (`models:781-785`) — **es por dispositivo, no por red** | criterio **DIS-02** de §7: `clave_alojamiento` nullable con UNIQUE real (no `condition`) |
| Reingreso | `_es_reingreso()` (`services/admisiones.py:45`) mira el mismo dispositivo | detección **en toda la red** |
| Estadía ambulatoria compatible | `InscripcionPrograma` admite `EN_SEGUIMIENTO` ([`services/solapas.py:37`](../../../programas/services/solapas.py)) | el **tipo de estadía** residencial vs ambulatoria |
| Elegir plaza / sin plaza | `admitir_ciudadano()` y `poner_en_espera()` (`services/admisiones.py:86,103`) | criterio **DIS-05**: cama ocupada → error visible, **nunca degradar a espera en silencio** |
| Ingreso excepcional sobre capacidad | — | **quién autoriza + motivo + traza** |
| Ficha mínima por tipo | `CampoTipoDispositivo` (`models:1213`) tiene `seccion`, `obligatorio` | **marcar secciones mínimas al ingreso** |
| Turno y hora del ingreso | `Admision.fecha_ingreso` | **el turno** |
| Entrada automática en bitácora | — | ver P10 |
| RENAPER | servicios de identidad ya existentes | — |
| RBAC | `dispositivo.admitir` (`core/rbac.py:67`) | capacidad para «autorizar ingreso excepcional» (P15 la pide) |

**Reemplaza a.** [`AdmisionCreateView`](../../../programas/views/admisiones.py) /
`dispositivos:admitir` (hoy un formulario de una sola página).

**Conflictos.** C-5, C-7 (wizard sin golden).

**Esfuerzo.** **L**.

---

### P7 · Detalle de la estadía y ficha viva (`#p7`, L875-L908) · [`p07.jpg`](capturas/p07.jpg)

**Qué es y en qué flujo cae.** Pantalla de M3 + M4: todo lo que le pasa a una persona en la
institución. Usuario: «Teresa Gauna · Trabajadora social · equipo técnico».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3 · Pabellón A · plaza A-02», h1 «Ramírez, Jorge
  Daniel» + `badge dotb bg-info` «Alojado» + `badge bg-brand` «Reingreso», bajada
  *«DNI 28.556.001 · 45 años · ingreso 03/09/2026 19:40 · 5 días de permanencia · legajo
  ciudadano»* (link). Acciones: `.btn.s` «Cambiar plaza», `.btn.s` «Permiso de salida»,
  `.btn.t` «Trasladar», **`.btn.d` «Egresar»** (rojo).
- `.alert.w`: *«**Ficha al 45 %.** Faltan Situación laboral, Red de sostén y Salud. El plazo
  de 15 días vence el 18/09.»* → «Completar ahora».
- **`.split`.** Izquierda, surface con 5 solapas: **Ficha (activa)** · Movimientos `6` ·
  Novedades `3` · Adjuntos `2` · Historial de cambios. El cuerpo apila **secciones `.sec`**:

  | Sección | Progreso | Contenido |
  |---|---|---|
  | A · Datos personales | `.bar` 100 % | `.dl` Nivel de instrucción «Secundario incompleto» · Oficio «Albañilería» · Capacitaciones «Sí · soldadura (2023)» · Interés en formación «Electricidad» |
  | B · Situación laboral y económica | `.bar.w` 20 % + link «completar» | Empleo «Informal»; Ingreso mensual **«falta»** en `--dang`/600; Plan social «falta»; Total egresos «se calcula» (subtle) |
  | 3 · Situación habitacional y red de sostén | `.bar.w` 0 % + «completar» | *«Sin datos todavía. No es sección mínima al ingreso; plazo 15 días.»* |
  | 9 · Salud | `badge bg-warn` «Sensible · salud» + `.bar` 60 % | Cobertura «No» · Problemas declarados «Respiratorios · Salud mental» · Tratamiento «Ambulatorio · Hospital Perrando» |
  | 12 · Consumos y situaciones de crisis | `.sec.locked` + `badge bg-dang` «Sensible · psicosocial» | 🔒 *«Tu rol no accede a esta sección. La completa el equipo de psicología. Se muestra que existe y está al 80 %.»* |
  | J · Situación judicial | `.sec.locked` + `badge bg-dang` «Sensible · judicial» | 🔒 *«Restringida. Referencia externa: expediente en GENACH (no se duplica la carga).»* |

  `.sec.locked` se dibuja con `repeating-linear-gradient(135deg, #fff 0 8px, --g050 8px 16px)`
  (rayado diagonal).
- **Derecha, tres surfaces:**
  - «Línea de tiempo» + `.btn.t.sm` «+ Novedad», con `.tl` de 6 eventos; el punto del
    evento cambia de borde según tono (`w` naranja, `d` rojo, `g` verde, por defecto marca):
    08/09 16:48 turno Tarde L. Méndez «Ficha actualizada»; 06/09 08:10 Mañana P. Ortiz
    «Cambio de plaza A-11 → A-02 · motivo: convivencia»; 05/09 09:00 Dra. Salas «Novedad de
    salud · control» + `badge bg-warn` «sensible»; 03/09 19:40 «Ingreso · plaza A-11 ·
    reingreso · autorización previa PC-2291»; 03/09 15:20 Programa Central «Solicitud de
    ingreso autorizada · vigencia 72 h»; 14/03/2026 «Egreso · alta con derivación a
    Mírame/Vedia».
  - «Otras estadías en la red»: `badge dotb bg-info` «En seguimiento» + «Mírame/Vedia desde
    20/03/2026 · referente: T. Gauna».
  - «Adjuntos» + `badge bg-gray` «2»: 📎 DNI frente y dorso.pdf · 03/09 — 📎 Autorización
    PC-2291.pdf · 03/09 (emoji, no ícono).

**Mapeo al sistema de diseño.** Canónicos: `page_header`, tabs, surface, badges, `.bar`,
`.dl`. **NUEVAS:** `.sec` (sección de ficha con progreso y estado bloqueado) y `.tl`
(línea de tiempo). El 🔒 y los 📎 son **emoji**, no íconos del sistema → C-10.

**Arquetipo.** «Revisión compleja → **sin golden: frenar y devolver**»
([`arquetipos/pendientes.md`](../../../.claude/design/arquetipos/pendientes.md)). → C-7.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Estadía, persona, plaza, fecha de ingreso | `Admision` (`models:695`) | permanencia en días (derivable) |
| Respuestas de la ficha | `Admision.respuestas_f00` JSON (`models:746`) + `CampoTipoDispositivo.seccion` (`models:1227`) | **completitud por sección** y **versionado** de la ficha |
| Adjuntos | `ArchivoAdmision` (`models:873`), uno por campo ARCHIVO | adjuntos libres de la estadía |
| Sensibilidad de secciones | **no existe** | **nivel por sección** (general/social/salud/psicosocial/judicial) + capacidades RBAC correspondientes |
| Movimientos / línea de tiempo | `TrazaDispositivo` es del **dispositivo**, no de la estadía (`models:582-614`) | **traza por estadía** (inmutable, con turno, hora, responsable y motivo) |
| Novedades | — | ver P10 |
| Autorización previa «PC-2291 · vigencia 72 h» | — | **modelo nuevo** |
| «Otras estadías en la red» | `SolapasService` cruza inscripciones (`services/solapas.py:36-48`) | consulta de red por ciudadano |
| Acciones Cambiar plaza / Permiso / Trasladar / Egresar | `trasladar_admision()` y `egresar_admision()` (`services/admisiones.py:190,138`) | **cambio de plaza** y **permiso de salida** |
| RBAC | `dispositivo.egresar` | capacidades de sensibilidad (P15) |

**Reemplaza a.** No hay pantalla de detalle de estadía: hoy la admisión solo se ve como
fila en la solapa «Admisiones» del detalle del dispositivo
(`legajo/detail.html:125`). **Pantalla nueva.**

**Conflictos.** C-5, C-7, C-10.

**Esfuerzo.** **L**.

---

### P8 · Traslado en tránsito, visto desde el destino (`#p8`, L911-L934) · [`p08.jpg`](capturas/p08.jpg)

**Qué es y en qué flujo cae.** Bandeja de tránsitos entrantes; implementa el carril
«DESTINO» de F4. Usuario: «Mariana Ruiz · Recepción · Albergue Calcuta».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «Albergue Madre Teresa de Calcuta», h1 «Tránsitos entrantes» +
  `badge bg-warn` «2», bajada *«Personas que otro dispositivo está trasladando hacia acá.
  Recibirlas cierra la estadía en el origen.»*
- Surface con `table.dense`: Persona · Viene de · Inició · Tiempo · Plaza propuesta · Ficha ·
  Acciones. Fila 1: Gómez, Laura / CIS N.º 3 («plaza C-04 reservada») / 08/09 08:02 /
  `badge dotb bg-dang` «9 h · vencido» / «H2-03» + `badge bg-warn` «Reservada» / 90 % /
  `.btn.b.sm` «Recibir» + `.btn.t.sm` «Rechazar». Fila 2: Torres, Mabel / Parador Nocturno /
  08/09 15:30 / `badge dotb bg-warn` «1 h 20» / «sin plaza · va a espera» / 55 % /
  `.btn.s.sm` «A lista de espera» + «Rechazar».
- **Bloque demostrativo `.modal-wrap`** con dos capas:
  - Al fondo (opacidad .6) la surface «Lo que ve el origen (CIS N.º 3) en su tabla de
    estadías»: una fila con `badge bg-warn` «Reservada», `badge dotb bg-warn` «En tránsito →
    Calcuta · 9 h» y las acciones **«Trasladar» y «Egresar» deshabilitadas** (`.btn.s.sm.dis`)
    junto a `.btn.t.sm` «Cancelar traslado».
  - Encima, `.dim` + **modal** «Recibir a Laura Gómez» con ícono `truck` y bajada *«Cierra
    la estadía en CIS N.º 3 y abre una nueva acá, con el mismo legajo.»* Campos:
    Plaza\* («H2-03 · Habitación 2 · Disponible»); «Ficha del tipo Albergue» en `.nf.ro`
    *«Se copian las secciones comunes; las propias del Albergue quedan pendientes (mínimo:
    Datos personales).»*; «Observaciones del ingreso» (opcional); `.alert.i` *«Queda
    registrado: turno Tarde, 16:52, recepción M. Ruiz. La plaza C-04 del origen se
    libera.»* Pie: «Cancelar» + `.btn.b` «Confirmar recepción».

**Mapeo al sistema de diseño.** El modal es **IGUAL** al «Modal Becas accesible»
(560 px, radio 16, caja de ícono 40 px `bg-brand-soft`, pie `bg-secondary`, labels y
`nodo-field`). Tabla, badges y botones deshabilitados, canónicos. `.alert.i` dentro del
modal coincide con la «nota informativa» del canon de Becas.

**Arquetipo.** **Listado** para la bandeja + **Modal de alta/edición** para «Recibir»
(golden: modal «Nuevo programa» de `becas/config/programa_list.html`).

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Traslado | `trasladar_admision()` ([`services/admisiones.py:190`](../../../programas/services/admisiones.py)) y `Admision.origen_traslado` (`models:757`) — **hoy el traslado es instantáneo**: cierra el origen y abre el destino | **estado intermedio `EN_TRANSITO`**, con plaza reservada en el origen, vencimiento, recepción y rechazo |
| Bandeja de entrantes | — | **vista nueva** + capacidad «recibir traslado» (P15) |
| Rechazo con motivo | — | nuevo |
| «va a espera» | `poner_en_espera()` (`services/admisiones.py:103`) | enlazar espera con el tránsito |
| Bloqueo de egresar/trasladar en origen | — | nuevo |
| Copia de la ficha entre tipos | — | nuevo |
| Criterio §7 | **DIS-03**: *«El traslado tiene recepción, rechazo y vencimiento; rechazar o vencer libera el origen; existe "cancelar espera" con motivo»* ([README §7](../auditoria-2026-10/README.md)) | — |

**Reemplaza a.** [`TrasladoAdmisionView`](../../../programas/views/admisiones.py) /
`dispositivos:trasladar`, que hoy resuelve el traslado en un paso desde el origen.

**Conflictos.** Ninguno de diseño.

**Esfuerzo.** **M** en UI, **L** contando el estado de tránsito en el backend.

---

### P9 · Egreso (`#p9`, L937-L956) · [`p09.jpg`](capturas/p09.jpg)

**Qué es y en qué flujo cae.** Modal de egreso de M3. La bajada del mockup lo declara:
*«Modal con el patrón de Becas»*. Fondo: la ficha de «Soto, Ana» al 55 % de opacidad.

**Inventario visual.**

- Modal con ícono `users` en caja `bg-brand-soft`, título «Registrar egreso de Ana Soto»,
  bajada *«Ingreso 06/09/2026 09:15 · plaza B-07 · 2 días de permanencia»*.
- `.form` de dos columnas:
  - Fecha y hora\* «08/09/2026 · 17:05» + `.help` *«No puede ser anterior al ingreso.»*
  - Motivo\* select «Alta con derivación».
  - Destino\* (`.full`) select «Domicilio de familiar · Fontana».
  - Derivación con seguimiento (`.full`) select «Mírame / Vedia · seguimiento ambulatorio»
    + `.help` *«Crea una derivación que el destino acepta o rechaza; la persona pasa a "En
    seguimiento" allí.»*
  - Observaciones (`.full`) `.nf.ta.ph` «Opcional».
  - `.toggle.on` «Pertenencias devueltas y firmadas».
- `.alert.i`: *«Libera la plaza B-07 · genera la novedad en la bitácora del turno Tarde ·
  queda en el historial del legajo ciudadano.»*
- Pie: `.btn.t` «Cancelar» + **`.btn.d` «Confirmar egreso»** (rojo).

**Mapeo al sistema de diseño.** Modal, campos, ayudas, pie y nota informativa: **IGUAL**
al canon. **NUEVO:** `.toggle` (switch), que no existe en
[`nodo-forms.css`](../../../static/custom/css/nodo-forms.css).

**Arquetipo.** **Modal** — el núcleo lo dice en la misma fila: la golden del modal cubre
*«alta o edición corta sin salir de la pantalla, **y confirmación con motivo**»*
([`chaco-design-system.md:147`](../../../.claude/agents/chaco-design-system.md), ficha
[`arquetipos/modal.md`](../../../.claude/design/arquetipos/modal.md)). El anexo §3 lo había
fijado como decisión **D2** para **pantallas nuevas**, aclarando que *«Las legacy de
Dispositivos/Merenderos/Legajos siguen con Swal condicionado (Cambio 48)»*. El mockup
coincide con D2. → relevante para C-6.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Egreso | `egresar_admision(admision, usuario, fecha_egreso, motivo, destino)` ([`services/admisiones.py:138`](../../../programas/services/admisiones.py)); campos `fecha_egreso`, `motivo_egreso`, `destino_egreso`, `responsable_egreso` (`models:737-756`) | — |
| Motivo del **catálogo** | `motivo_egreso` es `TextField` libre | **catálogo configurable por tipo** (P14 lo lista: Alta · Alta con derivación · Abandono · Traslado · Fallecimiento · Otro) |
| Destino del catálogo | `destino_egreso` es `CharField` libre | catálogo |
| Derivación con seguimiento | `DerivacionPrograma` (`models:295`) ya existe con aceptar/rechazar | **enganchar el egreso con la derivación** |
| Pertenencias devueltas | — | campo nuevo |
| Fecha futura | — | criterio **DIS-06**: *«Egreso con fecha futura rechazado en servicio y form»* |
| Novedad en bitácora | — | ver P10 |
| Criterio §7 | **DIS-09**: *«La membresía no se cierra con esperas pendientes en otro dispositivo»* | — |

**Reemplaza a.** [`EgresoAdmisionView`](../../../programas/views/admisiones.py) /
`dispositivos:egresar` (hoy página propia, confirmación por SweetAlert2).

**Conflictos.** C-6 (SweetAlert vs modal con motivo: el mockup elige modal, el Cambio 48
había decidido Swal para Dispositivos).

**Esfuerzo.** **S**.

---

### P10 · Bitácora del turno y pase de guardia (`#p10`, L959-L988) · [`p10.jpg`](capturas/p10.jpg)

**Qué es y en qué flujo cae.** M5. Implementa F6 entero. Reemplaza el parte diario y los
cuadernos. Usuario: «Lucía Méndez · Operadora de turno · CIS 3».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3», h1 «Bitácora», bajada *«Un registro por turno; el
  pase de guardia deja constancia de quién entregó y quién recibió.»* Acciones:
  `.nf.pill` de navegación «‹ lunes 08/09/2026 ›», `.btn.s` «Partes anteriores», `.btn.s`
  «Exportar».
- **`.split3` con tres `.turno`:**
  - Mañana · 06:00-14:00 + `badge dotb bg-succ` «Cerrado» — «P. Ortiz · 9 entradas · cerró
    14:05 · recibió L. Méndez» — `.btn.t.sm` «Ver».
  - **Tarde · 14:00-22:00** (`.turno.on`: borde de marca + `box-shadow 0 0 0 3px var(--brand-tint)`)
    + `badge dotb bg-info` «Abierto» — «L. Méndez (vos) · 6 entradas · recibido de P. Ortiz
    14:05» — `.btn.b.sm` «+ Novedad» + `.btn.s.sm` «Cerrar turno».
  - Noche · 22:00-06:00 (`.turno.off`, opacidad .65) + `badge bg-gray` «Sin abrir» —
    «Se abre al recibir el pase de Tarde.»
- **`.split`.** Izquierda, surface «Turno Tarde · entradas» / *«Ingresos, egresos y permisos
  se generan desde la estadía; el resto lo carga el operador»* con `.chips` de filtro:
  «Todas» (on) · Incidentes · Salud · Alimentos. El cuerpo lista `.entry` (grilla
  `56px 110px 1fr`): hora · badge de tipo · contenido + `.who`:

  | Hora | Tipo | Contenido |
  |---|---|---|
  | 16:52 | `bg-info` Movimiento | «Traslado de L. Gómez sigue en tránsito hacia Calcuta (9 h). Seguimiento pendiente.» — *automática · L. Méndez* |
  | 16:48 | `bg-succ` Ingreso | «Ramírez, Jorge reingresa · plaza B-03 · autorización PC-2291» — *automática* |
  | 16:10 | `bg-dang` Incidente | «Discusión en comedor entre dos residentes, intervino equipo técnico, sin lesiones. Personas: Benítez, R. · Ojeda, F. · 📎 acta» + `badge bg-warn` «Seguimiento abierto» — *L. Méndez · **corregir** (crea versión)* |
  | 15:30 | `bg-warn` Permiso | «Pérez, Mario sale con permiso hasta 22:00 · plaza A-05 reservada · prestada a R. Díaz por 24 h» |
  | 14:40 | `bg-w` Alimentos | «Merienda servida · 36 raciones · faltó leche para mañana» |
  | 14:05 | `bg-brand` Pase | «Recibí el pase del turno Mañana de P. Ortiz · pendientes: control de C-07 en reparación, visita judicial 17:00» |

  - Derecha: surface «Censo del turno» + `badge bg-gray` «Calculado» con `.kv` de 8 filas
    (Plazas totales/operativas 44/42 · Ingresos del día 3 · Egresos del día 1 · Alojados
    ahora 37 · Con permiso de salida 1 · Préstamos vigentes 1 · Reservadas 2 ·
    **Disponibles 3** en negrita); y surface «Cerrar turno · pase de guardia» con textarea
    «Pendientes para el turno Noche», select «Recibe» («Responsable del turno Noche · se
    confirma al abrir») y `.btn.b` «Cerrar turno Tarde».

**Mapeo al sistema de diseño.** Canónicos: `page_header`, surface, badges, `.kv`, textarea.
**NUEVAS:** `.turno` (tarjeta de turno con estado), `.entry` (fila de bitácora), `.chips`
de filtro, `.nf.pill` de navegación de fecha.

**Arquetipo.** Detalle degradado. El mockup declara explícitamente que las entradas
*«se agregan, nunca se pisan»* y que corregir **crea una versión visible**.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Parte por turno | `RegistroDiario` (`models:807-850`): `dispositivo`+`fecha`+`turno` único, con `camas_totales`, `ingresos`, `egresos`, `ocupacion_nocturna`, `camas_disponibles` **no editables** y `observaciones` JSON | es un **snapshot**, no una bitácora: no tiene apertura, cierre, pase ni entradas |
| Cálculo del censo | `calcular_cantidades()` ([`services/registro_diario.py:16`](../../../programas/services/registro_diario.py)) | préstamos, permisos y reservadas |
| Firma | `RegistroDiario.firmado_por` (`models:827`) | **entregó / recibió** (dos personas) |
| **Entradas de bitácora** | — | **modelo nuevo**: tipo, hora, texto, personas involucradas, adjunto, origen (manual/automática), versión |
| Tipos de novedad configurables | — | nuevo (P14 los lista) |
| Entradas automáticas desde la estadía | — | nuevo |
| Ventana de regularización 7 días | — | nueva (configurable por tipo, P14) |
| Criterio §7 | **DIS-01/DIS-08**: *«Ningún filtro ni conteo por día usa `__date`/`Trunc*` sobre DateTimeField»* (tests `test_parte_diario_sql_sin_convert_tz`). **B3 del Cambio 48**: *«El parte (o su reemplazo) no pisa el turno»* ([`registro_diario.py:64-67`](../../../programas/services/registro_diario.py)) | — |

**Reemplaza a.** [`legajo/parte_diario.html`](../../../programas/templates/programas/dispositivos/legajo/parte_diario.html)
(21 líneas) y `ParteDiarioView` / `dispositivos:parte_diario`.

**Conflictos.** C-10 (emoji 📎).

**Esfuerzo.** **L**.

---

### P11 · Lista de espera y derivaciones (`#p11`, L991-L1008) · [`p11.jpg`](capturas/p11.jpg)

**Qué es y en qué flujo cae.** M6. Pantalla de red (ítem de menú `disp-espera`), no del
dispositivo. Usuario: «Andrea Alarcón · Supervisora de área».

**Inventario visual.**

- `.ph` sin `.back`: eyebrow «Programa Dispositivos», h1 «Lista de espera y derivaciones»,
  bajada *«14 personas esperan plaza en tu alcance · 6 derivaciones pendientes de
  respuesta»*. Acciones: `.btn.s` «Exportar», `.btn.b` «+ Derivar persona».
- Surface con **4 solapas**: Espera `14` (activa) · Derivaciones enviadas `6` ·
  Derivaciones recibidas `3` · **Dónde hay plazas**.
- Fila de `.nf.pill`: «Dispositivo: Todos», «Prioridad: Todas», «Origen: Todos».
- `table.dense`: # · Persona · Espera en · Desde · Prioridad · Origen · Plaza reservada ·
  Acciones. 4 filas:
  1. Acuña, Brisa («15 años») · UPI Resistencia · 07/09 22:15 · `badge dotb bg-dang`
     «Medida judicial» · «Derivación · Juzgado NNA 2» · «C-03» + `badge bg-warn` «Reservada»
     · `.btn.b.sm` «Promover».
  2. Torres, Mabel · Albergue Calcuta · 08/09 15:30 · `bg-warn` «Alta» · «Traslado desde
     Parador» + `badge bg-warn` «en tránsito» · — · `.btn.s.sm.dis` «Sin plaza».
  3. Villalba, Hugo · Parador Nocturno · `bg-gray` «Normal» · «Ingreso directo» · — ·
     `.btn.t.sm` «Plazas en la red».
  4. Sánchez, Elsa («79 años») · Hogar San José · 01/09 · `bg-warn` «Alta» ·
     «Derivación · Hospital Perrando» · — · «Plazas en la red».
- `.pager` «Página 1 de 2 · 14 personas».
- `.alert.i` al pie: *«**Sugerencia:** se liberó la plaza B-08 en CIS N.º 3, perfil
  compatible con Villalba, Hugo. La promoción sigue siendo manual.»* → «Revisar».

**Mapeo al sistema de diseño.** Todo canónico salvo `.nf.pill` y `.alert` (C-5). La solapa
«Dónde hay plazas» no está dibujada.

**Arquetipo.** **Detalle con solapas** sobre un listado (la golden `segmento_detail`
cubre el patrón).

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Espera | `EsperaAdmision` (`models:853-870`): `admision` OneToOne, `posicion`, `promovida`, con `UniqueConstraint(admision, promovida=False)` | **prioridad** y **origen** (derivación / traslado / ingreso directo) |
| Edad | `Ciudadano.fecha_nacimiento` | — |
| Promover | `promover_espera(espera, cama, usuario)` ([`services/admisiones.py:228`](../../../programas/services/admisiones.py)) | criterio **DIS-02**: *«`test_promover_rechaza_si_ya_esta_alojado`»*; **DIS-04**: *«no se promueve ni ingresa en un dispositivo no activo»* |
| Plaza reservada para quien espera | `Cama.Estado.RESERVADA` existe | el vínculo espera ↔ reserva |
| Derivaciones | `DerivacionPrograma` (`models:295-372`) con origen/destino y estado | **bandeja** y permisos (criterio **LEG-06** de §7: *«Las derivaciones tienen bandeja, permisos (SEC-12) y reinscripción por `activar_inscripcion`»*) |
| «Dónde hay plazas» | — | vista de red |
| Sugerencia automática | — | nueva |
| Vista de red | hoy la espera es **por dispositivo**: `dispositivos:espera` recibe `<int:pk>` ([`dispositivos_urls.py:23`](../../../programas/dispositivos_urls.py)) | **listado de red** |
| Paginación | — | PERF-17 |

**Reemplaza a.** `EsperaAdmisionListView` / `dispositivos:espera` (por dispositivo).

**Conflictos.** C-5.

**Esfuerzo.** **M**.

---

### P12 · Merendero: detalle (`#p12`, L1011-L1032) · [`p12.jpg`](capturas/p12.jpg)

**Qué es y en qué flujo cae.** Legajo del merendero: M1 + M11 + M12 de la rama Merenderos
de F1, estado «Merendero activo» de F7. Usuario: «Javier Paredes · Área de merenderos».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «MER-0142 · Barrio Los Pinos · Zona Sur · Resistencia», h1
  «Merendero Los Pinos» + `badge dotb bg-succ` «Activo», bajada *«Responsable: Marta
  Benítez · DNI 22.110.334 · martes, jueves y sábados 16 a 18 h · capacidad declarada 120
  raciones»*. Acciones: `.btn.s` «Editar legajo», `.btn.t` «Suspender», `.btn.s`
  «Exportar», `.btn.b` «+ Registrar entrega».
- **`.alert.w` de bloqueo duro:** *«**Documentación vencida:** la habilitación municipal
  venció el 31/08/2026. Las nuevas entregas quedan bloqueadas hasta renovarla (regla del
  área).»* → «Adjuntar renovación».
- **4 stat cards** a `repeat(4,1fr)`: «Raciones agosto» 2.860 / *merienda 1.540 · desayuno
  1.320*; «Cobertura» 86 % en `--dang` / *los kits equivalen a 2.460 raciones*;
  «Entregas 90 días» 6 / *última 28/08 · 12 kits*; «Documentación» 3 / 4 / *1 vencida*.
- Surface con **5 solapas**: Datos · Documentación `4` · **Entregas `6` (activa)** ·
  Prestación mensual · Historial.
- `table.dense`: Fecha · Kits / insumos · Equiv. raciones · Servicio · Entregó · Recibió ·
  Remito · Acciones. 3 filas; la tercera con `opacity:.55` y `badge bg-gray` «Anulada ·
  duplicada». Remitos como «📎 R-00881».

**Mapeo al sistema de diseño.** Canónicos salvo stat cards (C-2), `.alert` (C-5), los 📎
(C-10) y el `.kebab` de las dos filas vigentes (L1026-L1027), que es pieza nueva (N-11).

**Arquetipo.** **Detalle con solapas**.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Legajo | `Merendero` (`models:891-936`): código, nombre, domicilio, zona, barrio, `dias_horarios`, responsable, estado ACTIVO/SUSPENDIDO/CERRADO | **capacidad declarada**, **servicios que presta** |
| Entregas | `EntregaMercaderia` (`models:1010-1033`): fecha, `cantidad_kits`, `servicio`, `responsable_receptor`, `anulada` | **catálogo de kits**, **equivalencia en raciones**, **quién entregó**, **remito**, y **`motivo_anulacion`/`anulada_por`/`anulada_en`** (criterio **MER-02** de §7) |
| Documentación | `SolicitudMerendero.documentacion` es **un** FileField (`models:977`) | **documentos múltiples con vencimiento** y el bloqueo de entregas |
| Cobertura | — | el cálculo de F7 (raciones servidas vs equivalente entregado vs capacidad) |
| Suspender / cerrar | `cambiar_estado_merendero()` ([`services/merenderos.py:109`](../../../programas/services/merenderos.py)) con `estado_actualizado_por/_en` | criterio **MER-01**: *«Suspensión reversible con traza; la grilla de un suspendido o cerrado se consulta en solo lectura»* |
| Historial | — | no hay traza de merendero (sí la hay de dispositivo: `TrazaDispositivo`) |
| RBAC | `merendero.ver/editar/entregar` (`core/rbac.py:78-82`) | — |

**Reemplaza a.** [`merenderos/detail.html`](../../../programas/templates/programas/merenderos/detail.html)
(83 líneas, **sin solapas**: dos secciones apiladas, confirmaciones por SweetAlert2).

**Conflictos.** C-2, C-5, C-6, C-10.

**Esfuerzo.** **M**.

---

### P13 · Prestación alimentaria mensual (`#p13`, L1035-L1058) · [`p13.jpg`](capturas/p13.jpg)

**Qué es y en qué flujo cae.** M12; último paso de F7.

**Inventario visual.**

- `.ph` con `.back`, eyebrow «Merendero Los Pinos», h1 «Prestación mensual» + `badge dotb
  bg-info` «Septiembre 2026 · en carga», bajada *«Servicios del legajo: desayuno y merienda
  · días: martes, jueves y sábado · carga en raciones»*. Acciones: `.nf.pill`
  «‹ Septiembre 2026 ›», `.btn.s` «Exportar», `.btn.t` «Guardar», **`.btn.b.dis` «Cerrar
  mes»**.
- **`.split`.** Izquierda, surface con `.grilla`: Día · Desayuno · Merienda · Total · Obs. ·
  Firma. Filas con celdas centradas; los días que **no funciona** usan `td.off` con
  `colspan="5"` y el texto «no funciona»; la celda en edición lleva
  `outline:2px solid var(--brand)`; los totales van en `td.tot`; la última fila es «Total
  189 / 316 / 505». Fila de corte: «… | 13 días de funcionamiento en el mes».
- Derecha: surface «Cobertura del mes» + `badge dotb bg-warn` «Parcial» con `.kv`
  (Raciones servidas 505 · Equivalente entregado 1.440 (kits 28/08) · Capacidad declarada
  120 / día · Días cargados 3 de 13) y la nota *«La alerta de cobertura se evalúa al cierre
  del mes.»*; y surface «Reglas» con cuatro viñetas: raciones enteras ≥ 0 y el total no se
  edita; *«Carga el merendero o el área; cierra otro rol»*; *«Un mes cerrado se reabre solo
  con motivo y queda en la traza»*; *«Si el Ministerio define "marca por servicio", la celda
  pasa a Sí/No por configuración»*.

**Mapeo al sistema de diseño.** `page_header`, surface, `.kv`, badges: canónicos.
`.grilla` **DIFIERE** de la tabla real: hoy
[`merenderos/prestacion_mensual.html:34-60`](../../../programas/templates/programas/merenderos/prestacion_mensual.html)
usa `table-fixed` con `colgroup`, `thead` **sticky**, scroll vertical
`h-[clamp(12rem,calc(100dvh-31rem),28rem)]`, un `<input type="number" class="nodo-field">`
por celda y un `<output aria-live="polite">` para el total. El mockup muestra **texto
plano** y una sola celda en edición, sin sticky ni scroll. Además la tabla real **no usa**
`.nodo-th`/`.nodo-td`.

**Arquetipo.** **Formulario** (página) con una grilla propia. `.grilla` queda como pieza
nueva o como evolución de la tabla existente.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Cabecera mensual | `PrestacionMensual` (`models:1036-1065`): merendero, año, mes, `servicios` JSON, `observaciones_por_dia`, `anulada` | **estado** del mes (en carga / cerrado) y **quién cerró** |
| Línea diaria | `PrestacionDiaria` (`models:1074-1113`): día, servicio (DESAYUNO/ALMUERZO/MERIENDA/CENA), raciones, `firmado_por`, `anulada` | — |
| Días de funcionamiento | `Merendero.dias_horarios` es **texto libre** (`models:904`) | **días estructurados** para pintar «no funciona» |
| Totales | `total_del_dia()` (`models:1067`) | el total del mes |
| Cierre por otro rol | `guardar_prestacion()` ([`services/merenderos.py:128`](../../../programas/services/merenderos.py)) | **cierre, reapertura con motivo y separación de funciones** |
| Cobertura | — | el cálculo de F7 |
| «Marca por servicio» Sí/No | — | configuración |
| Exportar | — | nuevo |

**Reemplaza a.** [`merenderos/prestacion_mensual.html`](../../../programas/templates/programas/merenderos/prestacion_mensual.html)
(90 líneas) / `merenderos:prestacion`.

**Conflictos.** Uno real y poco obvio: el mockup **pierde el `thead` sticky y el scroll
contenido** que la pantalla productiva ya tiene para 31 días × N servicios. Implementarlo
«tal cual» es una regresión de usabilidad → C-11.

**Decisión del PM (06/10/2026, C-11 → A): el aspecto del mockup sobre lo que ya funciona.**
Se adoptan los días «no funciona» y los totales en `td.tot`, y se conservan el `thead`
sticky, el scroll contenido con `h-[clamp(…)]`, el `nodo-field` numérico por celda y el
`<output aria-live="polite">` de los totales. Nada de lo ganado en
`merenderos/prestacion_mensual.html` se pierde.

**Esfuerzo.** **M**.

---

### P14 · Configuración: tipos de dispositivo y reglas (`#p14`, L1061-L1087) · [`p14.jpg`](capturas/p14.jpg)

**Qué es y en qué flujo cae.** Configuración del tipo (base de M2, M3, M4, M5).
La bajada lo resume: *«Todo lo que hoy es código pasa a configuración»*.

**Inventario visual.**

- `.ph` con `.back`, eyebrow «Tipo de dispositivo», h1 «Abordaje Psicosocial» + `badge dotb
  bg-succ` «Activo», bajada *«18 dispositivos usan este tipo · 6 formularios configurados ·
  última edición 02/09»*. Acciones: `.btn.t` «Duplicar tipo», `.btn.b` «Guardar cambios».
- Surface con **5 solapas**: **Reglas (activa)** · Formularios `6` · Plazas · Alertas y
  umbrales · Catálogos. Cuerpo: `.form` de dos columnas con 11 campos:

  | Campo | Control | Valor del mockup |
  |---|---|---|
  | Tipos de plaza admitidos | `.chips` | Cama (on) · Cupo · Turno |
  | Asignación de plaza al ingresar | select | «Obligatoria (internación)» |
  | Autorización previa de ingreso | `.toggle.on` | «Exige autorización del Programa Central · vigencia 72 h» |
  | Ingreso excepcional sobre capacidad | select | «Permitido con autorización del Supervisor de área» |
  | Estadía ambulatoria (en seguimiento) | `.toggle.on` | «Permitida, compatible con una residencial» |
  | Préstamo de plaza | select | «Permitido · 12 o 24 h» |
  | Límite de permanencia con alerta | `.nf.ph` | «Sin límite (UPI/ECA: 48 h por medida judicial)» |
  | Ventana de regularización de bitácora | select | «7 días» |
  | Secciones mínimas de la ficha al ingresar (`.full`) | `.chips` | A · Datos personales (on) · 2 · Reingreso (on) · 3 · Situación laboral · 9 · Salud · 12 · Consumos (equipo técnico) (on). `.help`: *«El resto se completa en el plazo configurado (15 días) con alerta.»* |
  | Motivos de egreso | select | «Alta · Alta con derivación · Abandono · Traslado · Fallecimiento · Otro» |
  | Tipos de novedad de bitácora | select | «General · Incidente · Visita · Salud · Alimentos · Limpieza · Mantenimiento» |

- **`.split3`** con tres surfaces: «Umbrales de ocupación» (`.kv` con badges: Normal < 50 %,
  Exigida 50 a 79 %, Crítica ≥ 80 %); «Sensibilidad de secciones» (9 · Salud → `bg-warn`
  «salud»; 12 · Consumos y crisis → `bg-dang` «psicosocial»; J · Situación judicial →
  `bg-dang` «judicial»); «Otros tipos» (Adulto Mayor `badge bg-succ` «con ficha» · Albergue ·
  Parador · UPI · ECA · Residencia Universitaria · Fortalecimiento Familiar · CDI
  `badge bg-gray` «sin ficha aún»).

**Mapeo al sistema de diseño.** Canónicos: `page_header`, tabs, surface, `.form`, `.kv`,
badges. **NUEVAS:** `.chips` (selector múltiple) y `.toggle` (switch).

**Arquetipo.** **Detalle con solapas** + formulario adentro.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Tipo | `TipoDispositivo` (`models:444-474`): código, nombre, descripción, `maneja_camas`, `umbral_ocupacion_amarillo` (default 50), `umbral_ocupacion_rojo` (default 80), `activo` | — |
| **Umbrales 50/80** | **ya coinciden** con el mockup (`models:452,457`) y hay `clean()` que exige rojo > amarillo (`models:471-474`) | el tercer tramo «Normal» es implícito |
| Tipos de plaza (cama/cupo/turno) | `maneja_camas` es un booleano | **catálogo de 3 tipos** |
| Autorización previa, ingreso excepcional, préstamo, estadía ambulatoria, límite de permanencia, ventana de regularización, motivos de egreso, tipos de novedad, secciones mínimas | — | **9 campos de configuración nuevos** |
| Campos de la ficha | `CampoTipoDispositivo` (`models:1213-1257`) con `seccion`, `tipo_campo`, `opciones`, `obligatorio`, `rol_calculo`, `orden` | **sensibilidad por sección**, **sección como entidad** (hoy es un `CharField` del campo) |
| «18 dispositivos usan este tipo» | contable | — |
| Criterio §7 | **DIS-10 / V6-NEW-02**: *«El tipo no cambia con estadías cargadas; borrar un campo con archivos no da 500 (PROTECT + mensaje + baja lógica)»* | — |
| RBAC | `puede_configurar_dispositivos()` ([`services/dispositivos.py:52`](../../../programas/services/dispositivos.py)) | — |

**Reemplaza a.** [`dispositivos/config/tipo_detail.html`](../../../programas/templates/programas/dispositivos/config/tipo_detail.html)
y `tipo_form.html` / `dispositivos:tipo_detalle`.

**Conflictos.** Ninguno de diseño.

**Esfuerzo.** **L** (la UI es M; los 9 campos nuevos y su efecto en el motor son L).

---

### P15 · Roles, alcance y sensibilidad (`#p15`, L1090-L1110) · [`p15.jpg`](capturas/p15.jpg)

**Qué es y en qué flujo cae.** M7. Es el ABM de Roles del sistema, extendido. Menú
`admin-roles`.

**Inventario visual.**

- `.ph` con `.back`, eyebrow «Rol · categoría Programa · Dispositivos», h1 «Operador de
  turno · CIS 3», bajada *«6 usuarios · alcance: institución · Subsecretaría de Abordaje
  Integral»*. Acción: `.btn.b` «Guardar cambios».
- **`.split`.** Izquierda, surface «Capacidades» / *«Por acción, no por nombre de rol»*
  con `.roles` (grilla de 2) y cuatro `.role`, cada uno con su `<h5>` y una lista de
  `.toggle`:

  | Grupo | Capacidades (on en negrita) |
  |---|---|
  | Estadías | **Ingresar**, **Mover plaza / permiso**, **Egresar**, Autorizar ingreso excepcional, Recibir traslado |
  | Bitácora | **Cargar novedades**, **Cerrar turno**, Regularizar días anteriores |
  | Ficha · sensibilidad | **General y social**, Salud, Psicosocial, Judicial |
  | Institución | **Ver legajo**, Editar legajo, Validar (bloqueado si cargó), Exportar |

- Derecha: surface «Alcance» con `.chips` de nivel (**Institución** · Subsecretaría ·
  Total), `.chips` de instituciones («CIS N.º 3 ✕» · «+ agregar») y el párrafo explicativo:
  *«Un rol con alcance de **subsecretaría** ve todas las instituciones de la suya, sin que
  nadie se las asigne de a una. El **programa central** usa el alcance por institución con
  las que se le asignen, aunque sean de subsecretarías distintas. **Total** es el
  administrador central.»*
  Y surface «Reglas del motor» con cuatro viñetas: *«Quien registra un movimiento no puede
  validarlo ni confirmar su cierre»*; *«Ocultar no es bloquear: cada URL y POST se
  verifica»*; *«Un rol global con capacidades operativas no habilita instituciones: el
  alcance es obligatorio»*; *«Exportar secciones sensibles requiere el nivel correspondiente
  y queda auditado»*.

**Mapeo al sistema de diseño.** `page_header`, surface, listas: canónicos.
**NUEVAS:** `.toggle` y `.chips`; `.role` (tarjeta de grupo de capacidades) es una
variante de surface.

**Arquetipo.** **Detalle** (sin solapas) / formulario.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Rol = `Group` + `RolMeta` | [`core/rbac.py`](../../../core/rbac.py) y el ABM de Roles de `users` | — |
| Capacidades por acción | `CATALOGO` (`core/rbac.py:32`); Dispositivos tiene **6**: `dispositivo.ver/crear/editar/validar/admitir/egresar` (L63-L68) | el mockup necesita **~11**: mover plaza, permiso, recibir traslado, autorizar excepcional, cargar novedades, cerrar turno, regularizar, exportar, y **4 niveles de sensibilidad** |
| Alcance por institución | `AsignacionDispositivo` (`models:532-558`) une `Dispositivo` + `Group` | — |
| Alcance por subsecretaría | módulo con `"alcance": "programa"` (`core/rbac.py:60`) + `dispositivos_visibles()` | **nivel intermedio por subsecretaría** (hoy el alcance es institución o programa) |
| Separación de funciones | — | **el motor no la aplica**: `validar_dispositivo()` no compara con quien envió (`services/dispositivos.py:214`) |
| Auditoría de exportación de secciones sensibles | — | nueva |
| Sensibilidad de la ficha | — | nueva (ver P14, P18) |

**Reemplaza a.** El ABM de Roles de `users` (`rol_detail` / `rol_form`), ampliándolo.

**Conflictos.** Uno de encuadre: el mockup presenta las capacidades **agrupadas y con
toggles**, mientras el ABM real las muestra como árbol del `CATALOGO`. No es un choque de
reglas, pero sí un rediseño de una pantalla **transversal** que no es de Dispositivos → C-12.

**Decisión del PM (06/10/2026, C-12 → A): esta pantalla no se construye en la v2.** Entran
al `CATALOGO` de `core/rbac.py` las ~11 capacidades nuevas de Dispositivos y los niveles de
sensibilidad, y el ABM de Roles sigue mostrándolas como lo hace hoy. El rediseño del ABM
—grupos con switches y nivel de alcance por subsecretaría— es **proyecto aparte**, porque
toca Becas, Legajos, Usuarios y Merenderos a la vez.

**Esfuerzo.** **L** (toca `core/rbac.py`, que es la pieza única de autorización).

---

### P16 · Solapa Dispositivos en el Legajo Ciudadano (`#p16`, L1113-L1131) · [`p16.jpg`](capturas/p16.jpg)

**Qué es y en qué flujo cae.** La vuelta del programa al legajo de la persona. Menú
`ciudadanos`.

**Inventario visual.**

- `.ph` con `.back`, h1 «Ramírez, Jorge Daniel», bajada *«DNI 28.556.001 · 45 años · legajo
  activo · identidad validada con RENAPER»*. Acciones: `.btn.s` «Editar datos», `.btn.t`
  «Derivar» (ícono `truck`).
- Surface con solapas del legajo: Resumen · Datos personales · Grupo familiar · Becas ·
  **Dispositivos `2` (activa)** · Acompañamiento · Documentos.
- `.alert.i`: *«**Hoy:** alojado en CIS N.º 3 (Pabellón A · A-02) desde el 03/09/2026 y en
  seguimiento ambulatorio en Mírame / Vedia desde el 20/03/2026.»*
- `table.dense`: Institución · Tipo · Ingreso · Egreso · Estado · Motivo de egreso ·
  Acciones. 4 filas, dos activas y dos cerradas: `badge dotb bg-info` «Alojado» +
  `badge bg-brand` «Reingreso»; `bg-info` «En seguimiento»; `bg-gray` «Egresado» con «Alta
  con derivación a Mírame/Vedia»; `bg-gray` «Trasladado» con «Traslado a CIS N.º 3».
  Acción por fila: `.btn.s.sm` «Ver estadía».
- Nota al pie: *«Las secciones sensibles de cada ficha se muestran según tu rol. El
  historial se conserva aunque no haya estadía activa.»*

**Mapeo al sistema de diseño.** Todo canónico (`page_header`, tabs, `table.dense`, badges,
`.alert` con C-5).

**Arquetipo.** **Detalle con solapas**; es una solapa dentro de una pantalla existente.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Solapa del programa | `SolapasService.obtener_solapas_ciudadano()` ([`services/solapas.py:30`](../../../programas/services/solapas.py)) | — |
| **La solapa aparece solo con estadía alojada** | `if tipo_normalizado == "DISPOSITIVOS" and not inscripcion.tiene_admision_alojada: continue` (`services/solapas.py:53-54`) | el mockup pide que **se conserve el historial aunque no haya estadía activa** |
| **La solapa navega, no embebe** | `"url": reverse("legajos:dispositivos_ciudadano", …)` y `"contenido_embebido": False` (`services/solapas.py:65,71`) | el mockup la muestra **embebida como las demás** |
| Historial de estadías | `Admision` filtrado por ciudadano | — |
| Contador «2» | — | derivable |
| Estado «Trasladado» | `Admision.Estado.TRASLADADO` existe (`models:706`) | — |
| Criterio §7 | **DIS-09** (membresía) y la solapa de §4.10 de la auditoría | — |

**Reemplaza a.** La solapa actual de Dispositivos en
[`legajos/templates/legajos/ciudadano_detail.html`](../../../legajos/templates/legajos/ciudadano_detail.html)
(L389 y siguientes) + la vista `legajos:dispositivos_ciudadano`.

**Conflictos.** C-5.

**Esfuerzo.** **S**.

---

### P17 · Formularios del tipo de institución (`#p17`, L1134-L1171) · [`p17.jpg`](capturas/p17.jpg)

**Qué es y en qué flujo cae.** M4: configurador de formularios por tipo. Es la solapa
«Formularios» de la misma pantalla de P14.

**Inventario visual.**

- Mismo `.ph` que P14 (bajada «6 formularios · 18 dispositivos usan este tipo»), acciones
  `.btn.t` «Nuevo formulario» y `.btn.b` «Guardar cambios».
- Mismas 5 solapas, con **Formularios `6`** activa. `table.dense`: Formulario · Qué acción
  lo llama · Secciones · Campos · Estado · Acciones.

  | Formulario | Lo llama | Sec. | Campos | Estado |
  |---|---|---|---|---|
  | F-00 · Ingreso (*Ficha de admisión de la persona*) | Botón **Admitir** | 14 | 45 | `badge dotb bg-succ` «Base» |
  | Asignación de plaza | Asignar o cambiar plaza | 1 | 3 | «Base» |
  | F-01 · Novedades del turno (*Se completa una vez por turno*) | Bitácora · cierre de turno | 3 | 11 | «Base» |
  | Egreso | Botón **Egresar** | 2 | 7 | «Base» |
  | Traslado | Botón **Trasladar** | 1 | 5 | «Base» |
  | Evaluación interdisciplinaria (*Creado por el área el 04/09*) | «Sin asignar todavía» | 4 | 19 | `badge dotb bg-info` «Propio» |

- **`.split`.** Izquierda, surface «F-00 · Ingreso — secciones» / *«Arrastrá para ordenar.
  El nivel decide quién la ve.»* con `.kv`: A · Datos personales → `badge bg-gray` «general»
  + `badge bg-brand` «del Legajo Ciudadano»; 2 · Reingreso → «general»; 3 · Situación
  laboral e ingresos → `bg-info` «social»; 9 · Salud → `bg-warn` «salud»; 12 · Consumos y
  situaciones de crisis → `bg-dang` «psicosocial»; J · Situación judicial → `bg-dang`
  «judicial».
- Derecha: surface «Campos protegidos» *«Son columnas del sistema: se ven acá pero no se
  pueden borrar ni cambiar de tipo»* con `.chips` on: Fecha de ingreso · Plaza · Persona ·
  Reingreso. Y surface «Reglas del configurador» con cuatro viñetas: *«Un campo que ya tiene
  respuestas no se borra: se da de baja»*; *«Los formularios base no se eliminan ni cambian
  a qué acción responden»*; *«Un tipo nuevo se crea acá y arranca con los formularios base
  ya cargados»*; *«Los datos de identidad se muestran desde el Legajo Ciudadano: no se
  vuelven a preguntar»*.

**Mapeo al sistema de diseño.** Canónicos salvo `.chips`. El «arrastrá para ordenar» tiene
pieza canónica: **Drag & drop SortableJS** (`static/vendor/sortablejs/Sortable.min.js` +
`nodo-constructor.css`), con el contrato de manija `.grip` **y alternativa de teclado
obligatoria**, descrito en el inventario del agente de diseño. El mockup solo dice
«arrastrá» y no muestra la manija → al implementar hay que agregarla.

**Arquetipo.** **Detalle con solapas** + listado adentro.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Campos por tipo | `CampoTipoDispositivo` (`models:1213`): un campo pertenece a un `tipo_dispositivo` y tiene `seccion` como texto | **entidad `Formulario` por tipo** y **entidad `Sección`** |
| «Qué acción lo llama» | — | **nuevo**: hoy solo existe el F-00 (`Admision.respuestas_f00`) |
| Formularios base vs propios | — | nuevo |
| Baja lógica de campos respondidos | — | **decisión ya registrada**: Cambio 48, *«Baja lógica, no borrado, para los campos de tipo de dispositivo»*, task #313. Criterio **DIS-10** de §7 |
| Campos protegidos | — | nuevo |
| Niveles de sensibilidad por sección | — | nuevo |
| Reordenar | `nodo-constructor.js` / Sortable ya existe para Becas | adaptarlo |
| Datos del Legajo Ciudadano | `Ciudadano` | el marcado «viene del legajo» |

**Reemplaza a.** [`dispositivos/config/tipo_detail.html`](../../../programas/templates/programas/dispositivos/config/tipo_detail.html)
+ `campo_form.html` (hoy el ABM es de campos sueltos, sin noción de formulario).

**Conflictos.** Ninguno de diseño. Sí una **dependencia explícita registrada**: Cambio 58
dejó asentado que *«el F-00 de Dispositivos queda afuera»* del constructor de formularios de
Becas; P17 es, de hecho, un constructor propio para Dispositivos → Q5.

**Esfuerzo.** **L**.

---

### P18 · Sección sensible: bloqueo visible y aviso de lectura (`#p18`, L1174-L1217) · [`p18.jpg`](capturas/p18.jpg)

**Qué es y en qué flujo cae.** Variante de P7 vista por un rol **sin** el nivel de
sensibilidad. Usuario: «Carlos Ojeda · Operador de turno».

**Inventario visual.**

- `.ph` con eyebrow «Estadía · CIS N.º 3 · Pabellón A · A-02», h1 «Ramírez, Jorge Daniel» +
  `badge dotb bg-info` «Alojado», bajada «Ingreso 03/09/2026 · 11 días · ficha 68 %
  completa». Acciones: `.btn.s` «Imprimir ficha», `.btn.b` «Editar».
- Surface con 5 solapas (Ficha activa · Movimientos `7` · Novedades `12` · Adjuntos ·
  Historial). Dentro, **surfaces anidadas**, una por sección:
  - «3 · Situación laboral e ingresos» con `badge bg-info` «social» · **completa**; `.kv`
    Empleo «Informal» · Ocupación «Changas de albañilería» · Ingreso mensual estimado
    «$ 180.000».
  - «9 · Salud» con `badge bg-warn` «salud», **borde punteado** (`border-style:dashed`) y
    `badge dotb bg-gray` «Sin acceso»; cuerpo centrado con 🔒 a 26 px, *«Tu rol no accede a
    esta sección.»* en negrita y *«La completa el **equipo de Salud / Enfermería**. Está
    **completa al 100 %** y se actualizó el 12/09.»*
  - «12 · Consumos y situaciones de crisis» con `badge bg-dang` «psicosocial», mismo patrón:
    *«La completa el **equipo de psicología**. Está **completa al 80 %**.»*
- **`.split` demostrativo:**
  - Izquierda, surface «Y si tu rol sí accede» / *«Tener el permiso habilita; leer exige
    confirmarlo»* con un `.alert.i` que hace de compuerta: *«**Esta información es
    sensible.** Vas a abrir la sección **12 · Consumos y situaciones de crisis** de Ramírez,
    Jorge Daniel. Tu lectura queda registrada con tu nombre y la fecha y hora.»* +
    `.btn.b` «Entendido, abrir» y `.btn.t` «Cancelar». Debajo: *«El aviso aparece **cada
    vez** que se abre la sección. Dentro, el contenido no se puede copiar ni exportar sin el
    nivel, y lleva una marca de agua con el usuario y la hora.»*
  - Derecha, surface «Quién leyó qué» / *«Auditoría del programa»* con `table.dense`
    Usuario · Sección · Cuándo (3 filas con nombre + rol en `.sub`).

**Mapeo al sistema de diseño.** Canónicos salvo: la **surface con borde punteado** como
estado «sin acceso» (variante nueva), el 🔒 emoji (C-10), y el uso del `.alert.i` **con
botones adentro** como diálogo de confirmación, que no es lo que `_alerta.html` hace.

**Arquetipo.** **Detalle** + **confirmación**. El patrón real para «aviso que exige
confirmar» es `ModernModal.show({type:'confirm'})` o un modal propio; el mockup lo dibuja
inline por tratarse de una demostración.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Niveles de sensibilidad | `ciudadano.sensible` existe para Legajos (`core/rbac.py:42`) | **4 niveles propios** (general/social, salud, psicosocial, judicial) como capacidades |
| Sección con avance y equipo responsable | — | nuevo |
| Registro de lectura | — | **modelo de auditoría de lectura** nuevo |
| Marca de agua | — | nuevo |
| «No se puede copiar ni exportar» | — | ver §7 C-13: el Cambio 72 ya dejó por escrito al cliente que **impedir capturas no es técnicamente posible** |
| «Imprimir ficha» | — | nuevo |

**Reemplaza a.** Nada. Pantalla nueva.

**Conflictos.** C-10, C-13.

**Textos que cambian por decisión del PM (06/10/2026, C-13 → A).** El HTML del mockup no se
edita; se implementa con estos textos:

| Dónde | Dice el mockup | Se implementa |
|---|---|---|
| Pie de la compuerta de confirmación | *«El aviso aparece **cada vez** que se abre la sección. Dentro, el contenido no se puede copiar ni exportar sin el nivel, y lleva una marca de agua con el usuario y la hora.»* | **«El aviso aparece cada vez que se abre la sección. Dentro, el contenido lleva una marca de agua con tu nombre y la hora, y la exportación queda bloqueada sin el nivel. Impedir una captura de pantalla no es técnicamente posible en ningún sistema web.»** |

Las cuatro medidas que sí se implementan —compuerta de confirmación por apertura, registro
de lectura, marca de agua visual y bloqueo de exportación **del lado del servidor**— son las
que el Cambio 72 ya comunicó por escrito al Ministerio. El 🔒 de la sección bloqueada se
reemplaza por un ícono Font Awesome con `aria-hidden="true"` (C-10 → A).

**Esfuerzo.** **M** (la UI), **L** con el motor de sensibilidad y la auditoría de lectura.

---

### P19 · Detalle del dispositivo · solapa Infraestructura (`#p19`, L1220-L1293) · [`p19.jpg`](capturas/p19.jpg)

**Qué es y en qué flujo cae.** M14; implementa F8. Es la pantalla más densa del mockup.
Usuario: «Matías Fariña · Administrador superior».

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3 · CIS-003 · Resistencia», h1 «Infraestructura» +
  `badge dotb bg-dang` «Relevamiento vencido», bajada *«Última actualización 02/02/2026 ·
  cargó C. Ríos, equipo territorial · periodicidad 6 meses · próximo vencimiento
  02/08/2026»*. Acciones: `.btn.s` «Historial», `.btn.s` «Exportar ficha», **`.btn.b`
  «Relevar ya»** (ícono `clipboard`).
- `.alert.w`: *«**El relevamiento venció hace 49 días.** Se envió aviso por email al
  coordinador del programa el 02/08 y el 02/09. El dispositivo sigue operando normalmente:
  la alerta no bloquea nada.»* → «Asignar relevamiento».
- Surface con las **9 solapas del detalle** (Infraestructura activa) y, dentro, 4 stat
  cards: Tenencia «Comodato» (valor a 24 px) / *Iglesia Católica · vence 12/2027*;
  Habitaciones 14 / *3 pabellones · plano cargado*; Estado físico «Regular» / *3
  observaciones abiertas*; Vigencia «Vencida» en `--dang` / *49 días · cada 6 meses*.
- **`.split` (`align-items:flex-start`).** Izquierda, surface «Ubicación geolocalizada» /
  *«Coordenadas, no solo dirección: se usa en presentaciones ante programas nacionales»* +
  `.btn.s.sm` «Ajustar punto»:
  - `.mapa`: **SVG dibujado a mano** (640×260) con calles, manzanas, el predio en
    `--brand-200`/`--brand`, un pin y los rótulos «Av. Sarmiento» y «Calle Güemes».
    **No es un mapa real.**
  - `.kv`: Domicilio «Av. Sarmiento 1250, Resistencia» · Coordenadas «-27.45112 ·
    -58.98634» · Precisión `badge bg-succ` «Tomada en campo con GPS» · Superficie declarada
    «1.840 m²» · Plano / layout «📎 plano-cis3-2026.pdf».
  - `.alert.i`: *«**Predio compartido:** el mismo edificio aloja tres instituciones. Los
    datos de tenencia, servicios y estado físico son del **predio**; cada institución
    mantiene su propio legajo.»*
  - `table.dense` «Institución en este predio · Tipo · Sector que ocupa · Legajo»: CIS N.º 3
    («acá estás»), Parador Nocturno anexo, Sotai Resistencia.
- Derecha: surface «Servicios disponibles» / *«Agua de red y fuente alternativa son campos
  separados»* con `.svc` de 6 tarjetas (ícono en caja tonal + nombre + detalle + badge):
  Luz «SECHEEP · medidor propio» `bg-succ` Sí; Agua de red «SAMEEP» Sí; Fuente alternativa
  «cisterna de 5.000 l» `bg-info` Respaldo; Internet «fibra 100 Mb» Sí; Conectividad móvil
  «señal intermitente» `bg-warn` Parcial; Grupo electrógeno «sin equipo» `bg-gray` No.
  Y surface «Estado físico» + `badge dotb bg-warn` «Regular» con `.kv` (Condición general
  «Regular» · Techos y cubiertas `bg-warn` «Con daños» · Instalación eléctrica `bg-succ`
  «Buena» · Sanitarios `bg-warn` «Faltan 2 duchas» · En obra o refacción «No · *si lo
  estuviera, la periodicidad pasa a 1 mes*») y `.alert.w` con las 3 observaciones abiertas.
- Surface «Registro fotográfico» / *«Histórico: cada relevamiento agrega su tanda, no pisa
  la anterior»* + `.btn.s.sm` «Comparar dos fechas»: `.tl` con 3 eventos; los dos primeros
  despliegan `.fotos` (grilla `auto-fill minmax(88px,1fr)`, celdas 4:3 grises con ícono
  `camera` y rótulo: fachada, pab. A/B/C, cocina, sanitarios, patio, techo).
- Surface «Historial de relevamientos» + `badge bg-gray` «3» con `table.dense` Fecha ·
  Responsable · Tipo · Estado físico · Fotos · Informe · Acciones.
- **Notas (L1292):** *««Relevar ya» solo aparece para el Administrador superior»*;
  *«Merenderos: esta solapa no se muestra en su detalle en esta etapa»*.

**Mapeo al sistema de diseño.** Canónicos: `page_header`, tabs, surface, `table.dense`,
`.kv`, badges, `.alert` (C-5), stat cards (C-2). **NUEVAS: `.mapa`, `.svc`, `.fotos`/`.foto`,
`.tl`** (compartida con P7).

**Arquetipo.** **Detalle con solapas**, con tres piezas nuevas adentro.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Coordenadas | `Dispositivo.latitud/longitud` (`models:499-500`) ya existen | la **precisión** y el ajuste del punto |
| **Edificio / predio** | **no existe ningún modelo `Edificio` ni `Predio`** | **entidad nueva N:M con `Dispositivo`** — Cambio 85 ya la identificó como *«la pieza más estructural del pedido»* |
| Tenencia, habitaciones, superficie, plano, estado físico, servicios | — | **todos nuevos** (del predio, no del dispositivo) |
| Registro fotográfico histórico | — | **nuevo**: tanda por relevamiento, nunca pisa |
| Vigencia y periodicidad | [`core/services/vencimientos.py`](../../../core/services/vencimientos.py) es un **registro genérico de reglas** (`registrar(regla)`, L43) | **la regla** de infraestructura (6 meses / 1 mes en obra, aviso a 30 días) |
| Aviso por email | `EMAIL_BACKEND` por SMTP ya operativo | el disparador |
| «Relevar ya» | — | nuevo + **capacidad RBAC «Administrador superior»**, que hoy no existe como figura |
| Historial de relevamientos | — | ver P21 |
| Mapa interactivo | **no hay librería de mapas en el repo**; la CSP de `SecurityHeadersMiddleware` prohíbe CDN | → C-14 |
| Merenderos | fuera de alcance por decisión del mockup (L409, L1292) | — |

**Reemplaza a.** Nada. Solapa nueva.

**Conflictos.** C-2, C-5, C-10, **C-14** (mapa).

**Decisión del PM (06/10/2026, C-14 → B): sin mapa embebido.** El `.mapa` del mockup se
implementa como coordenadas legibles + enlace «ver en el mapa» que abre fuera
(`target="_blank" rel="noopener"`) + el plano del edificio como adjunto, que es lo que el
Cambio 85 ya había previsto para el plano. No se vendoriza Leaflet ni se toca la CSP; el mapa
interactivo queda como ampliación posterior si el Ministerio lo pide.

**Esfuerzo.** **L** (es la pantalla más cara: entidad nueva + 3 piezas nuevas); el mapa deja
de pesar: la ubicación sin mapa son ~2 h y se construye en la Ola 0.

---

### P20 · Detalle del dispositivo · solapa Consumos y contratos (`#p20`, L1296-L1335) · [`p20.jpg`](capturas/p20.jpg)

**Qué es y en qué flujo cae.** M16; implementa F10. El mockup insiste en que **no tiene
entrada propia en el sidebar** (L682, L1334): vive dentro del detalle porque los importes
son de cada institución.

**Inventario visual.**

- `.ph` con `.back`, eyebrow «CIS N.º 3 · CIS-003 · Resistencia», h1 «Consumos y contratos»,
  bajada *«4 ítems activos · 1 vencido sin pago · próximo vencimiento en 5 días»*.
  Acciones: `.btn.s` «Exportar», `.btn.b` «+ Nuevo ítem».
- Dos `.alert`: `d` *«**Luz venció el 10/09 sin pago registrado.** Se escaló a la Dirección
  de Abordaje Psicosocial el 11/09.»* → «Adjuntar comprobante»; `w` *«**Alquiler vence el
  25/09** · faltan 5 días. El aviso automático se envió el 18/09 al responsable
  institucional y al coordinador.»* → «Registrar pago».
- Surface con las 9 solapas (Consumos activa), fila de `.nf.pill` («Tipo: Todos», «Estado:
  Todos», «Período: 2026») + `.btn.t.sm` «Ver ítems dados de baja», y `table.dense`:
  Ítem · contrato · Importe · Último pago · Vence · Comprobante · Estado · Acciones.

  | Ítem | Importe | Vence | Comprobante | Estado | Acción |
  |---|---|---|---|---|---|
  | Alquiler del inmueble (*mensual · contrato 2024-118, vence 12/2027*) | $ 1.450.000 | 25/09/2026 *en 5 días* | 📎 rec-0825.pdf | `bg-warn` Por vencer | «Registrar pago» + ⋮ |
  | Luz (*bimestral · SECHEEP, cuenta 44-9182*) | $ 312.400 | 10/09/2026 *hace 10 días* | **«falta»** en `--dang` | `bg-dang` Vencido · escalado | `.btn.b.sm` «Adjuntar» + ⋮ |
  | Agua (*mensual · SAMEEP, cuenta 11-3320*) | $ 88.900 | 05/10/2026 | 📎 rec-0905.pdf | `bg-succ` Al día | «Ver» + ⋮ |
  | Internet (*mensual · Telecom, fibra 100 Mb*) | $ 62.000 | 08/10/2026 | 📎 rec-0908.pdf | `bg-succ` Al día | «Ver» + ⋮ |

  `.pager` reutilizado como pie informativo: «4 ítems activos · total mensual estimado
  $ 1.757.150» + «Ver historial de pagos».
- `.split`: izquierda surface «Próximos vencimientos» / *«Los mismos datos que alimentan el
  widget del Dashboard»* con `.tl` de 4 eventos; derecha surface «Reglas» (5 viñetas: alerta
  **7 días antes**; registrar el pago **exige comprobante**; vencido sin pago **escala**;
  *«Nada se bloquea»*; *«Un ítem no se borra: se da de baja con motivo»*) y surface
  «Escalamiento» + `badge bg-dang` «1 activo» con `.kv`.

**Mapeo al sistema de diseño.** Canónicos salvo `.nf.pill`, `.kebab`, `.tl` y `.alert`
(C-5). El `.pager` usado como pie de totales es un uso fuera de contrato de
`_paginacion.html` (que es paginación, no resumen) → variante.

**Arquetipo.** **Detalle con solapas** + listado.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Ítems, importes, contratos, pagos, comprobantes | **nada** | **modelo nuevo** (`ItemConsumo` + `PagoConsumo` con adjunto) |
| Vencimiento y aviso a 7 días | `core/services/vencimientos.py` (registro de reglas) | la regla |
| Escalamiento | — | **necesita el organigrama**: pendiente registrado en el Cambio 85 — *«El modelo de alcance es plano… sin el organigrama el escalado se implementa contra la subsecretaría»* |
| Baja lógica con motivo | — | nueva |
| Widget del Dashboard | — | ver P22 |
| RBAC | — | capacidad nueva (quién ve importes) |

**Reemplaza a.** Nada. Solapa nueva.

**Conflictos.** C-5, C-10. Y una **pregunta de alcance**: el mockup muestra importes en
pesos dentro del legajo institucional sin decir qué rol los ve → Q6.

**Esfuerzo.** **M**.

---

### P21 · Relevamientos: listado y asignación (`#p21`, L1338-L1383) · [`p21.jpg`](capturas/p21.jpg) + [`p21-b.jpg`](capturas/p21-b.jpg)

**Qué es y en qué flujo cae.** M15; implementa F9. **Ítem nuevo del menú Dispositivos**
(`disp-relev`). Usuario: «Andrea Alarcón · Coordinadora del programa». El tablero trae
**dos frames**: el listado y, debajo, el modal de asignación.

**Inventario visual — frame 1 (listado).**

- `.ph` sin `.back`: eyebrow «Programa Dispositivos», h1 «Relevamientos», bajada
  *«Asignación y seguimiento de los relevamientos edilicios de los dispositivos de tu
  alcance.»* Acciones: `.btn.s` «Exportar», `.btn.b` «+ Nuevo relevamiento».
- 4 stat cards: Asignados 9 / *sobre 18 dispositivos de alojamiento*; Al día 11 / *dentro de
  su periodicidad*; Por vencer 3 / *vencen en los próximos 30 días*; Vencidos 2 / *CIS N.º 3
  y Hogar San José*.
- `.fcard` compacta con `badge bg-gray` «1 activo» y tres `.nf.pill` («Estado: Todos»,
  «Asignado a: Todos», «Tipo: Alojamiento 24/7») + «+ Agregar filtro».
- Surface con **3 solapas**: En curso `9` (activa) · Completados `24` · Sin relevar nunca `2`.
- `table.dense`: Dispositivo · Asignado a · Vence · Periodicidad · Última carga · Estado ·
  Acciones. 6 filas; «Asignado a» con nombre + `.sub` «territorial · Zona Sur», o «Sin
  asignar» en subtle; «Vence» con `.sub` relativo («hace 49 días», «en 10 días»);
  periodicidad «6 meses» o «1 mes» + `badge bg-warn` «en obra»; estados `bg-dang` «Vencido»,
  `bg-warn` «Por vencer», `bg-succ` «Al día», `bg-info` «Asignado · en campo», `bg-gray`
  «Sin relevar». Acciones: «Reasignar» / `.btn.b.sm` «Asignar» / «Ver» + `.kebab` ⋮.
- `.pager` «Página 1 de 2 · 9 relevamientos en curso».

**Inventario visual — frame 2 (modal «Asignar relevamiento · Hogar San José»).**

Ícono `clipboard`; bajada *«Se le crea la tarea al territorial y le llega a la app. El
dispositivo no la puede autocompletar.»* Campos: Dispositivo\* (`.nf.ro` «Hogar San José ·
HOG-SJ»); Periodicidad\* («6 meses (normal)», `.help` *«Si el dispositivo está en obra, pasa
a 1 mes.»*); Agente territorial\* («Claudia Ríos · Zona Sur», `.help` *«La lista solo trae
agentes **externos a Hogar San José**.»*); **«No disponibles para esta asignación»** con
`.chips` al 55 % de opacidad (M. Gauna, R. Benítez, L. Paniagua, todos «personal de
HOG-SJ»); Vence\* «05/10/2026»; Prioridad «Alta · relevamiento vencido»; Indicaciones para
el territorial (textarea). Cierra con `.alert.w`: *«**Nunca se asigna al personal de la
institución relevada.** … lo valida una tercera persona: ni vos ni quien carga.»*
Pie: «Cancelar» + `.btn.b` «Asignar relevamiento».

**Notas (L1382):** menú ⋮ = ver informe, reasignar, cambiar el vencimiento, **marcar en
obra** (cambia la periodicidad a 1 mes); *«El territorial no ve este menú»*.

**Mapeo al sistema de diseño.** Listado y modal, canónicos. Stat cards (C-2), `.fcard` con
píldoras (pieza nueva), `.kebab` (nueva), `.chips` deshabilitados (nueva).

**Arquetipo.** **Listado** + **Modal de alta/edición**.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| **Relevamiento edilicio** | **no existe** | **modelo nuevo** |
| ⚠️ Colisión de nombre | `Relevamiento` **ya existe** y es de **Becas** (`models:1761`, convocatorias y formularios) | el modelo nuevo **no puede llamarse `Relevamiento`**; tampoco conviene reusar las capacidades `relevamiento.ver/gestionar` (`core/rbac.py:91-92`), que son de Becas |
| Agente territorial | `AsignacionTerritorial` existe pero es de **Becas** (`models:2426`) | figura de territorial para Dispositivos |
| «Solo agentes externos al dispositivo» | — | **regla nueva**, cruzada contra `AsignacionDispositivo` (`models:532`) |
| Periodicidad / en obra / vencimiento | `core/services/vencimientos.py` | la regla |
| App de campo | **otro repositorio** (`Chaco-mobile`) | **declarado fuera de las 827 h** (Cambio 85); la alternativa sin costo es *«cargar el relevamiento desde el navegador del celular»* |
| Informe oficial + validación por un tercero | — | nuevo |
| Paginación | — | PERF-17 |

**Reemplaza a.** Nada. Pantalla e ítem de menú nuevos.

**Conflictos.** C-2. Y el **choque de nombres** con el `Relevamiento` de Becas, que hay que
resolver antes de modelar → Q4.

**Esfuerzo.** **L**.

---

### P22 · Dashboard configurable por rol (`#p22`, L1386-L1432) · [`p22.jpg`](capturas/p22.jpg) + [`p22-b.jpg`](capturas/p22-b.jpg)

**Qué es y en qué flujo cae.** M17; «implementa F11» (flujo que **no existe** en el
mockup, ver Q1). También trae **dos frames**: la configuración y la vista del territorial.

**Inventario visual — frame 1 (configuración, usuario Administrador).**

- `.ph` con `.back`, eyebrow «Tableros personalizados», h1 «Dashboard · configuración por
  rol», bajada *«Lo que cada rol ve al entrar, siempre dentro del alcance que ya define P15
  (institución · subsecretaría · total).»* Acciones: `.btn.s` «Vista previa», `.btn.t`
  «Restablecer», `.btn.b` «Guardar cambios».
- `.split`. Izquierda, surface «Widgets del tablero» / *«Se alimentan de M8; el alcance del
  rol recorta los datos, no hace falta configurarlo dos veces»* + `.btn.t.sm` «+ Agregar
  widget», con `.roles` de 2 columnas y cuatro grupos de `.toggle` (16 widgets; **10 en `on`**,
  aunque el `kv` de la derecha diga «9 de 16» — contradicción del propio mockup, ver Q10):

  | Grupo | Widgets (on en negrita) |
  |---|---|
  | Ocupación y capacidad | **Ocupación de la red**, **Plazas disponibles ahora**, **Dispositivos en estado crítico**, Lista de espera por dispositivo |
  | Movimiento | **Próximos ingresos autorizados**, **Tránsitos abiertos**, Egresos del mes, Reingresos detectados |
  | Infraestructura `badge bg-brand` «nuevo» | **Relevamientos vencidos**, **Relevamientos por vencer (30 d)**, Dispositivos en obra, **Observaciones de estado físico abiertas** |
  | Consumos y contratos `badge bg-brand` «nuevo» | **Vencimientos en 7 días**, **Vencidos sin pago (escalados)**, Gasto mensual por dispositivo, Contratos de alquiler por vencer |

- Derecha: surface «Rol que estás configurando» con `.chips` (Administrador on · Director /
  Coordinador · Agente territorial al 50 % de opacidad), `.alert.d` *«**Agente territorial:
  sin acceso a este módulo.** Su rol es capturar datos en campo. No ve tableros ni
  estadísticas y el ítem «Dashboard» no aparece en su menú.»* y `.kv` (Alcance heredado
  «Total» · Widgets activos «9 de 16» · Usuarios con este rol «4»). Y surface «Quién arma y
  quién ve» con `.kv`: Administrador `bg-succ` «Arma y ve»; Director / Coordinador «Arma y
  ve»; Responsable institucional `bg-info` «Ve, alcance institución»; Agente territorial
  `bg-dang` «Sin acceso». Nota: *«La jerarquía fina (ministro → subsecretario → director →
  operadores) se ajusta cuando llegue el organigrama oficial.»*
- Surface «Recordatorios personalizados» / *«Para vencimientos propios de cada institución
  que no cubren las alertas automáticas de F8 y F10»* + `.btn.b.sm` «+ Nuevo recordatorio»,
  con `table.dense`: Recordatorio · Dispositivo · Fecha · Repite · Avisa a · Canal ·
  Acciones. 3 filas (habilitación de bomberos, control de tanques de agua, vencimiento de
  comodato) con `badge bg-info` «Email + plataforma».

**Inventario visual — frame 2 (vista del agente territorial).**

El mismo shell con `data-hide="dashboard,reportes,config,programas,mer,admin,disp-tablero,disp-espera,disp-bit,disp-conf,disp-relev"`:
el sidebar queda con Inicio, Ciudadanos, Dispositivos → Instituciones/Estadías, y nada más.
`.ph` con eyebrow «Así ve el sistema el agente territorial», h1 «Mis tareas», bajada
*«Sin Dashboard, sin Reportes y sin el menú Relevamientos: las tareas le llegan
asignadas.»*; `.alert.i` «2 relevamientos asignados»; `.split` con dos surfaces de tarea
(CIS N.º 3 con `badge dotb bg-dang` «Vencido» y `.btn.b.sm` «Cargar relevamiento»; UPI
Resistencia con `bg-warn` «Vence en 2 días», `.bar.w` 40 % y «Continuar carga»).

**Notas (L1431):** *«Un solo ítem de menú: el Dashboard ya existe en el sidebar, así que se
lo hace configurable en vez de agregar una segunda entrada»*; *«ocultar no es solo visual,
cada URL y cada POST se verifica igual que en P15»*.

**Mapeo al sistema de diseño.** Canónicos: `page_header`, surface, `table.dense`, `.kv`,
`.bar`, badges, `.alert` (C-5). **NUEVAS:** `.toggle`, `.chips`, `.kebab`.

**Arquetipo.** «Dashboard → **sin golden: frenar y devolver**»
([`arquetipos/pendientes.md`](../../../.claude/design/arquetipos/pendientes.md)) para
el tablero resultante; la pantalla de **configuración** en sí es un detalle/formulario y sí
tiene molde. → C-7.

**Mapeo a datos y backend.**

| Dato | Origen hoy | Falta |
|---|---|---|
| Dashboard | existe el ítem «Dashboard» en el sidebar (`opciones.html:107`) y la capacidad `dashboard.ver` | **catálogo de widgets y armado por rol** |
| Widgets | los datos salen de M8 (P1) | todo |
| Recordatorios personalizados | — | **modelo nuevo** (fecha, repetición, destinatarios, canal) |
| Canal «Email + plataforma» | SMTP operativo; `nodo-toast` para plataforma | el modelo de notificación |
| «El territorial no ve el ítem» | el sidebar ya condiciona por capacidad (`opciones.html:615,628`) | la figura de rol territorial de Dispositivos |
| Jerarquía ministro → operadores | — | **pendiente del organigrama** (Cambio 85) |

**Reemplaza a.** Amplía el Dashboard existente; no reemplaza pantallas de
`/dispositivos/` ni `/merenderos/`.

**Conflictos.** C-5, C-7.

**Esfuerzo.** **L**.

---

## 5. Tabla resumen

La columna **Conflictos** remite a §7, donde los quince están **decididos** (06/10/2026). Las
pantallas marcadas *sin golden* ya no quedan frenadas sin salida: por C-7 van al final del
plan, después de que se construyan las goldens que les faltan.

| # | Pantalla | Arquetipo | Piezas nuevas | Modelos / campos nuevos | Conflictos (§7, decididos) | Esf. |
|---|---|---|---|---|---|---|
| P1 | Tablero de la red | **sin golden** (dashboard) | `.nf.pill` | agregación de red; **modelo de alerta operativa** | C-2 C-3 C-5 C-7 | L |
| P2 | Instituciones (listado) | Listado | eyebrow en `page_header` | `Dispositivo`: categoría, área, nivel de confianza; estados INAUGURACION_PENDIENTE y SUSPENDIDO; paginación | — | M |
| P3 | Alta con anti-duplicado | Formulario (variante 2 col.) | `.chips`, pie de acciones en card | 4 campos + servicios; duplicado por distancia; separación de funciones | C-5 C-8 | M |
| P4 | Detalle del dispositivo | Detalle con solapas | `.nf.pill`, `.kebab` | `Sector`; `Admision.EN_TRANSITO`; permiso de salida; préstamo; reingreso de red | C-2 C-5 C-6 C-9 | L |
| P5 | Sectores y plazas | Detalle (degradado) | `.plazas`/`.plz`, `.legendmini`/`.sq`, panel lateral | `Sector`; `Cama.PRESTADA`; motivo de fuera de servicio; vencimiento de reserva | — | M |
| P6 | Ingreso de una persona | **sin golden** (wizard) | `.stepper` backoffice, selector de plaza | `clave_alojamiento` (DIS-02); CUIL; ingreso excepcional; secciones mínimas; turno | C-5 C-7 | L |
| P7 | Estadía y ficha viva | **sin golden** (caso complejo) | `.sec` (+`locked`), `.tl` | traza por estadía; sensibilidad por sección; autorización previa; versionado | C-5 C-7 C-10 | L |
| P8 | Tránsitos entrantes | Listado + Modal | — | estado de tránsito con reserva, vencimiento, recepción y rechazo (DIS-03) | — | M/L |
| P9 | Egreso | Confirmación con motivo (Modal) | `.toggle` | catálogo de motivos y destinos; pertenencias; fecha futura (DIS-06) | C-6 | S |
| P10 | Bitácora y pase de guardia | Detalle (degradado) | `.turno`, `.entry`, `.chips`, `.nf.pill` | **entradas de bitácora** con versión; apertura/cierre; pase; regularización | C-10 | L |
| P11 | Espera y derivaciones | Detalle con solapas | `.nf.pill` | prioridad y origen en `EsperaAdmision`; bandeja de derivaciones (LEG-06); vista de red | C-5 | M |
| P12 | Merendero: detalle | Detalle con solapas | `.kebab` | capacidad declarada; catálogo de kits; equivalencia; remito; `motivo_anulacion` (MER-02); documentación con vigencia | C-2 C-5 C-6 C-10 | M |
| P13 | Prestación mensual | Formulario + `.grilla` | `.grilla` (o evolución de la actual) | estado del mes y cierre por otro rol; días estructurados | C-11 | M |
| P14 | Configuración del tipo | Detalle con solapas | `.chips`, `.toggle` | 9 campos de configuración; sección como entidad; sensibilidad | — | L |
| P15 | Roles, alcance y sensibilidad | Detalle / formulario | `.toggle`, `.chips`, `.role` | ~11 capacidades nuevas en `CATALOGO`; alcance por subsecretaría; separación de funciones | C-12 | L |
| P16 | Solapa del Legajo Ciudadano | Detalle con solapas | — | solapa embebida y con historial completo | C-5 | S |
| P17 | Formularios del tipo | Detalle con solapas | `.chips` (+ Sortable existente) | entidad `Formulario`/`Sección`; campos protegidos; baja lógica (DIS-10) | — | L |
| P18 | Sección sensible | Detalle + confirmación | surface punteada «sin acceso» | 4 niveles de sensibilidad; **auditoría de lectura** | C-10 C-13 | M/L |
| P19 | Solapa Infraestructura | Detalle con solapas | `.svc`, `.fotos`, `.tl` + bloque de ubicación sin mapa (C-14 → B) | **`Edificio`/`Predio` N:M**; tenencia, servicios, estado físico, fotos; regla de vigencia | C-2 C-5 C-10 **C-14** | L |
| P20 | Solapa Consumos y contratos | Detalle con solapas | `.nf.pill`, `.kebab`, `.tl` | `ItemConsumo` + `PagoConsumo`; regla de vencimiento; escalamiento | C-5 C-10 | M |
| P21 | Relevamientos | Listado + Modal | `.kebab`, `.chips` deshabilitados | **modelo de relevamiento edilicio** (con otro nombre, Q4); territorial de Dispositivos | C-2 | L |
| P22 | Dashboard configurable | **sin golden** (dashboard) | `.toggle`, `.chips`, `.kebab` | catálogo de widgets por rol; **recordatorios personalizados** | C-5 C-7 | L |

**Reparto:** 2 S · 7 M · 2 M/L · 11 L. Cuatro pantallas (P1, P6, P7, P22) caen en arquetipos que
el agente de diseño hoy manda **frenar y devolver**. Por la decisión de C-7 **van al final**:
se arranca por las 18 que sí tienen golden mientras, en paralelo, se cierra la Ola 6 y se
construyen las goldens de dashboard, wizard y caso complejo. Ninguna de las cuatro se
implementa con una excepción escrita al freno.

---

## 6. Piezas canónicas nuevas que habría que agregar al sistema de diseño

Cada una exige su fila en
[`.claude/agents/chaco-design-system.md`](../../../.claude/agents/chaco-design-system.md)
**en el mismo PR** que la cree, o `check_design_agent.py` falla (hook y CI).

| # | Pieza | Qué es | Dónde aparece |
|---|---|---|---|
| N-1 | `eyebrow` en `{% page_header %}` | línea 12,5 px uppercase en `--text-fg-brand` sobre el `<h1>` | todas menos P1, P4 y P16 (**19 de 22**) |
| N-2 | Filtro rápido en píldora (`.nf.pill`) | `nodo-field` de 36 px, radio completo, «Campo: valor ⌄»; filtra sin abrir la tarjeta | P1 P4 P10 P11 P13 P20 P21 |
| N-3 | Chips de selección múltiple (`.chip`) | píldora 4×12 px, borde base; activa `#FFEAF6`/`#FFB9DC`/`#A11F60` (los tonos de `badge-brand`) | P3 P10 P14 P15 P17 P21 P22 |
| N-4 | Switch (`.toggle`) | pista 34×18 px, perilla 14 px; `on` = `--bg-brand`. **No existe** en `nodo-forms.css` | P9 P14 P15 P22 |
| N-5 | Stepper de backoffice | 4 pasos con círculo de 28 px y conector de 56 px; estados `done`/`on`. Semántica de `portal/inscripcion/_stepper.html` | P6 |
| N-6 | Mapa de plazas (`.plazas`/`.plz`) | grilla `auto-fill minmax(84px,1fr)` con 5 estados tonales + leyenda `.legendmini` | P5 P6 |
| N-7 | Línea de tiempo (`.tl`) | riel de 2 px, punto de 10 px con borde tonal por severidad, «cuándo» en 12 px subtle | P7 P19 P20 |
| N-8 | Sección de ficha (`.sec`) con progreso y bloqueo | header `bg-secondary` con título, badge de sensibilidad y medidor; variante `locked` rayada | P7 (y P18 como surface punteada) |
| N-9 | Tarjeta de turno (`.turno`) | card con estado `on` (anillo `--bg-brand-tint`) / `off` (opacidad .65) | P10 |
| N-10 | Entrada de bitácora (`.entry`) | grilla `56px 110px 1fr`: hora tabular, badge de tipo, cuerpo + autoría | P10 |
| N-11 | Menú de fila (`.kebab`) | botón ⋮ de 28 px con menú; hoy las acciones de fila son `.nodo-icon-btn` sueltos | P4 P12 P20 P21 P22 |
| N-12 | Tarjeta de servicio (`.svc`) | ícono en caja tonal + nombre + detalle + badge de disponibilidad | P19 |
| N-13 | Galería fotográfica histórica (`.fotos`) | grilla `auto-fill minmax(88px,1fr)` de celdas 4:3, anidada en la línea de tiempo | P19 |
| N-14 | ~~Mapa geolocalizado (`.mapa`)~~ → **bloque de ubicación sin mapa** | coordenadas legibles + enlace «ver en el mapa» que abre fuera + plano adjunto | P19 (y P3 «Geolocalizado») |
| N-15 | Grupo de capacidades (`.role`) | card con `<h5>` y lista de switches | P15 P22 |
| N-16 | Grilla mensual (`.grilla`) | tabla día × servicio con totales, días inhabilitados y celda en edición | P13 |

### Qué quedó aprobado el 06/10/2026

Las decisiones de §7 **aprueban seis piezas de sistema** y las ponen primeras en el orden de
§8. Son las que habilitan la v2: se construyen **antes** de la primera pantalla y cada una
actualiza, en su propio diff, la fila del inventario o la ficha de `.claude/design/` que
toca. Están creadas como tasks del análisis **M0** en GitHub.

| Pieza | Decisión | Estado |
|---|---|---|
| Variante **«tablero»** de `_stat_card.html` (grande) + la chica para listados; se revisa CMP-23 | C-2 → C | **Aprobada** · ~1 día |
| **Hero** de pantalla de inicio de programa (Inicio + tableros de programa, y nada más) | C-3 → C | **Aprobada** · ~½ día |
| Ampliación de **`_alerta.html`** con `icono` y `accion_url`/`accion_texto` | C-5 → B | **Aprobada** · ~½ día |
| **N-11 · menú de fila** accesible (`.kebab`) | C-9 → A | **Aprobada** · ~1 día |
| Variante **`btn-fit`** sin ancho mínimo, para headers densos y celdas | C-15 → B | **Aprobada** · ~½ día |
| **N-14 reconvertida**: ubicación sin mapa (coordenadas + link externo + plano adjunto) | C-14 → B | **Aprobada** · ~2 h — el mapa embebido con Leaflet queda **descartado** en la v2 |

Las demás piezas de la tabla (N-1 a N-10, N-12, N-13, N-15, N-16) **no tienen decisión
todavía**: se proponen como novedad al construir la primera pantalla que las usa, siguiendo
el protocolo del agente canónico (si traen novedad, se frena y se devuelve al llamador).
**N-15** además depende de C-12: como el ABM de Roles no se rediseña en la v2, su único
consumidor vivo pasa a ser P22, que va al final del plan.

---

## 7. Conflictos · **los 15 decididos el 06-oct-2026**

Quince. **Los quince quedaron decididos por el PM el 06/10/2026** y cada uno lleva su línea
`Decisión tomada` debajo de sus opciones; el análisis original se conserva entero, porque es
lo que explica el costo de la opción elegida. Los seis primeros (C-1 a C-6) y C-15 son
decisiones **de sistema**, no de pantalla, y por eso encabezan el orden de implementación
de §8. El registro formal es el **Cambio 134** de
[`requerimientos.md`](../requerimientos.md).

| Conflicto | Decisión | En una línea |
|---|---|---|
| C-1 Tokens | **A** | Traducir cada token del mockup a su semántico. |
| C-2 Stat cards | **C** | Variante canónica «tablero» (grande) + la chica para listados; se revisa CMP-23. |
| C-3 Hero | **C** | Pieza canónica solo para Inicio y tableros de programa. |
| C-4 Íconos | **A** | Font Awesome en el contenido, como fija D3. |
| C-5 Alertas | **B** | Ampliar `_alerta.html` con `icono` y `accion_url`/`accion_texto`. |
| C-6 Confirmaciones | **A** | v2 con modal D2; legacy con SweetAlert2 hasta que se reemplacen. |
| C-7 Pantallas sin golden | **C + A** | Arrancar por las 18 con golden; construir las goldens que faltan en paralelo. |
| C-8 Duplicado fuera de alcance | **B** | Bloquear sin nombrar la institución ajena. |
| C-9 Menú ⋮ | **A** | Crear la pieza «menú de fila» accesible (N-11). |
| C-10 Emoji | **A** | Íconos del set con `aria-hidden`. |
| C-11 Prestación mensual | **A** | Aspecto del mockup, conservando sticky, scroll, inputs y `aria-live`. |
| C-12 ABM de Roles | **A** | Capacidades al `CATALOGO`; el rediseño del ABM es proyecto aparte. |
| C-13 «No se puede copiar» | **A** | Las cuatro medidas reales y se corrige el texto del mockup. |
| C-14 Mapa | **B** | Coordenadas + link externo + plano adjunto; sin librería de mapas. |
| C-15 `min-width` | **B** | Variante `btn-fit` sin ancho mínimo para headers densos y celdas. |

### C-1 · Tokens con nombre propio vs tokens semánticos `DECIDIDO 06/10/2026`

**Choque.** El mockup declara `--brand`, `--g050`, `--succ`, `--dang`, `--warn`, `--navy`,
`--gradient`. El sistema usa `--bg-*`, `--text-*`, `--border-*`, `--color-*`
([`chaco-tokens.css`](../../../static/custom/css/chaco-tokens.css)) y el agente lo exige:
*«usar `--bg-*`, `--text-*`, `--border-*` y `--font-*`, no valores visuales ad hoc»*.
Los **valores** coinciden (§0), los nombres no.

| Opción | Costo |
|---|---|
| **A.** Traducir cada token del mockup a su semántico al implementar | nulo visualmente; es la lectura natural de «tal cual» (mismo píxel, otro nombre) |
| **B.** Publicar los alias del mockup como tokens nuevos | duplica el vocabulario y rompe el dark mode, que se define sobre los semánticos (`chaco-tokens.css:342+`) |

*Recomendación del análisis: A. «Tal cual» es el resultado visual, no el nombre de la
variable.*

**Decisión tomada (06-oct-2026, PM):** A — cada token del mockup se traduce a su semántico
(`--bg-*`, `--text-*`, `--border-*`, `--font-*`) al implementar; el píxel es el mismo y el
dark mode se mantiene.

### C-2 · Stat cards: el mockup clona la métrica que el sistema está retirando `DECIDIDO 06/10/2026`

**Choque.** El `.stat` del mockup (L132-L141) es idéntico a `.stat-card` de
[`inicio.html:84-137`](../../../templates/inicio.html): caja de ícono de **52 px**, valor
**32 px / 800**, ícono con `var(--gradient-brand)`. La pieza canónica es
[`components/_stat_card.html`](../../../templates/components/_stat_card.html), y el canon dice
lo contrario: *«Sin gradiente ni cajas de 52 px»*
([`chaco-design-system.md:171`](../../../.claude/agents/chaco-design-system.md)), con la
prohibición detallada en su ficha —*«Cajas de ícono de 52 px, `var(--gradient-brand)`, valores
`text-3xl` o `font-extrabold`: quedaron fuera del canon»*
([`.claude/design/componentes/stat_card.md:45-46`](../../../.claude/design/componentes/stat_card.md),
hallazgo **CMP-23**)—. El anexo §3 pone además a `inicio.html` entre las *«pantallas a
alinear»* con la golden de la franja de métricas.
Aparece en P1, P4, P12, P19, P21.

| Opción | Costo |
|---|---|
| **A.** Implementar con `_stat_card.html` canónico | las métricas se ven **más chicas** que en el mockup (ícono 32 px, valor 24 px, sin sombra); el cliente nota la diferencia contra el link que aprobó |
| **B.** Implementar tal cual el mockup | 5 pantallas nuevas nacen fuera del canon y con la deuda CMP-23; el ratchet de `design_audit` no lo frena (no es regla P1) pero el revisor sí |
| **C.** Revisar CMP-23: que la franja «grande» sea una **variante** canónica del tablero y la chica quede para listados | ~1 día de trabajo de sistema + actualizar el inventario; deja las dos convivencias explicadas |

**Decisión tomada (06-oct-2026, PM):** C — la franja grande pasa a ser una **variante
canónica «tablero»** de `_stat_card.html` (la chica queda para listados) y CMP-23 se revisa
en el mismo diff que la crea.

### C-3 · Hero con gradiente en una pantalla operativa `DECIDIDO 06/10/2026`

**Choque.** P1 abre con `.hero` (gradiente de marca, h1 de 30 px, botón blanco), copiado de
`.ini-hero`. El agente de diseño dice, para backoffice: *«No crear landing pages para
backoffice operativo. La primera pantalla debe ser la herramienta usable»* y *«No introducir
un framework visual paralelo, gradientes nuevos, cards decorativas, **hero sections** ni
layouts de marketing»*. El hero existe en producción, pero solo en **Inicio**.

| Opción | Costo |
|---|---|
| **A.** Tal cual el mockup | el tablero de Dispositivos pasa a tener una franja de bienvenida; contradice la regla escrita |
| **B.** Reemplazar el hero por `{% page_header %}` con la misma bajada | se pierde la franja que el cliente vio; sin costo de desarrollo |
| **C.** Declarar el hero pieza canónica **de pantalla de inicio de programa** (Inicio + tableros de programa) y nada más | ~medio día; legitima lo que ya existe y acota el uso |

**Decisión tomada (06-oct-2026, PM):** C — el hero se declara pieza canónica **solo** para
Inicio y tableros de programa; fuera de esas dos superficies la regla «sin hero en
backoffice operativo» sigue intacta.

### C-4 · Familia de íconos: Heroicons del mockup vs Font Awesome del canon `DECIDIDO 06/10/2026`

**Choque.** El mockup usa **Heroicons outline inline** (`I = {home, grid, users, …}`,
L1440-L1466). El sistema usa Font Awesome: la regla P1 `ICONARIA` de
[`design_audit.py`](../../../scripts/design_audit.py) solo controla `<i class="fas …">`, el
shell **precarga `fa-solid-900.woff2`** y los componentes (`_stat_card`, `_estado_vacio`,
`.nodo-icon-btn`) reciben el nombre FA. **Pero la mezcla ya existe en producción:**
[`list_filters.html`](../../../templates/components/list_filters.html) y el sidebar
(`opciones.html:616-645`) usan Heroicons inline.

| Opción | Costo |
|---|---|
| **A.** Traducir cada ícono del mockup a su equivalente FA | los glifos no son idénticos (FA es más lleno que Heroicons outline); nada de infraestructura |
| **B.** Usar Heroicons inline como el mockup | 22 pantallas con SVG inline; hay que extender `ICONARIA` para que los exija con `aria-hidden`; convive con FA en el mismo shell |
| **C.** Introducir Heroicons como **set del programa** con un sprite y un tag | ~2 días de sistema; el resultado es el del mockup y queda auditable |

**Decisión tomada (06-oct-2026, PM):** A — cada ícono del mockup se traduce a su equivalente
Font Awesome en el contenido, que es exactamente lo que fija D3 (Cambios 129 y 132);
Heroicons queda solo en el shell.

### C-5 · Alertas inline: el mockup lleva ícono y acción; la pieza no `DECIDIDO 06/10/2026`

**Choque.** `.alert` del mockup (L147-L153): radio 12, padding `12px 16px`, **ícono de
18 px** a la izquierda y un **link de acción subrayado a la derecha** («Resolver», «Ver
legajo», «Completar ahora»). [`components/_alerta.html`](../../../templates/components/_alerta.html)
es `rounded-lg … p-4 text-sm` con `strong` + `p`, **sin ícono y sin acción** (salvo la nota
informativa). Aparece en **15 de 22** pantallas (todas menos P2, P5, P10, P13, P14, P15 y P17).

| Opción | Costo |
|---|---|
| **A.** Usar `_alerta.html` tal como está y poner la acción fuera del bloque | las alertas pierden el link contextual que el mockup usa como camino principal |
| **B.** **Ampliar `_alerta.html`** con `icono` y `accion_url`/`accion_texto` opcionales | ~medio día; es una pieza canónica → el mismo diff actualiza el inventario; **es la opción que más barato cierra el mockup** |
| **C.** Pieza nueva paralela | duplica contrato; el agente lo clasifica «Duplicado o conflictivo» |

**Decisión tomada (06-oct-2026, PM):** B — se amplía `components/_alerta.html` con `icono` y
`accion_url`/`accion_texto` opcionales, sin romper los consumidores actuales (los tres
parámetros son opcionales y el render sin ellos no cambia).

### C-6 · Confirmaciones: SweetAlert2 (Cambio 48) vs modal con motivo (D2) `DECIDIDO 06/10/2026`

**Choque.** Dispositivos y Merenderos hoy confirman con **SweetAlert2**
(`legajo/detail.html:138-172`, `merenderos/detail.html:63-82`), y eso **es una decisión
registrada**: Cambio 48 — *«en confirmaciones Dispositivos está mejor parado: usa
SweetAlert2… Se decide extraer un include propio del módulo y no copiar el de Becas»*. El
mockup confirma con **modales propios** (P8, P9, P21), que es el arquetipo «Confirmación con
motivo» del anexo §3 (decisión **D2**) — el cual aclara que las **legacy** siguen con Swal.

| Opción | Costo |
|---|---|
| **A.** Pantallas v2 con modal (D2); las legacy que sobrevivan, con Swal | dos mecanismos conviviendo durante la migración; es lo que el anexo ya previó |
| **B.** Todo con Swal, como pide el Cambio 48 | contradice D2 y el mockup; Swal no da bien el formulario de P9 (5 campos + toggle) |
| **C.** Migrar también las legacy a modal en el mismo frente | +esfuerzo en pantallas que la v2 reemplaza igual |

*Nota: el Cambio 48 no fijó el mecanismo para pantallas **nuevas**, solo defendió lo
existente. Técnicamente A no lo contradice.*

**Decisión tomada (06-oct-2026, PM):** A — las pantallas de la v2 confirman con el modal del
arquetipo D2; las legacy siguen con SweetAlert2 hasta que la v2 las reemplace, sin frente de
migración propio.

### C-7 · Cuatro pantallas sin golden: el agente manda frenar `DECIDIDO 06/10/2026`

**Choque.** El núcleo del agente es taxativo: *«Pendiente · wizard, revisión compleja y
dashboard … **No hay golden: frenar y devolver al llamador**»*
([`chaco-design-system.md:149`](../../../.claude/agents/chaco-design-system.md) +
[`arquetipos/pendientes.md`](../../../.claude/design/arquetipos/pendientes.md)). P1 y P22 son
dashboards, P6 es un wizard, P7 es revisión compleja. Y §7 de la auditoría declara
**precondición transversal**: *«la Ola 6 terminada antes de la primera task de pantalla»* —
con el Cambio 132 (PR #579) la Ola 6 va por el **paso 5 de 7**.

| Opción | Costo |
|---|---|
| **A.** Construir primero las goldens que faltan (wizard, caso complejo, dashboard) y después las 4 pantallas | demora el arranque; deja el molde para las 18 restantes |
| **B.** Implementar las 4 con permiso explícito de saltar el freno, documentando la excepción | riesgo de que cada una invente su molde (es exactamente lo que midió la línea base de la Ola 6) |
| **C.** Empezar por las 18 que sí tienen golden (P2, P3, P4, P5, P8…) mientras se cierra la Ola 6 | **sin costo**: reordena, no recorta |

**Decisión tomada (06-oct-2026, PM):** C + A en paralelo — se arranca por las 18 pantallas
con golden mientras se cierra la Ola 6 y se construyen las goldens de dashboard, wizard y
caso complejo; P1, P6, P7 y P22 van al final, ya con molde. Queda descartada la opción B: no
hay excepción para saltar el freno del agente.

### C-8 · El error de duplicado filtra datos fuera del alcance `DECIDIDO 06/10/2026`

**Choque.** P3 muestra: *«El código ya está en uso por una institución **fuera de tu
alcance**»* y el panel lateral nombra la institución, su código, su estado y su área. F2 lo
declara regla: *«código duplicado bloquea y explica aunque esté fuera del alcance»*. Eso
revela existencia, nombre y estado de registros que el usuario no puede ver, lo que choca
con la disciplina de alcance de `core/rbac.py` y con el criterio *«Ocultar no es bloquear»*
que el propio mockup enuncia en P15.

| Opción | Costo |
|---|---|
| **A.** Tal cual el mockup | se asume la filtración; conviene dejarla por escrito como decisión del Ministerio |
| **B.** Bloquear sin nombrar: *«El código ya está en uso. Pedí el traspaso al administrador central.»* | pierde el atajo operativo que el mockup buscaba; sin costo |
| **C.** Nombrar solo con una capacidad nueva («ver duplicados fuera del alcance») | ~medio día |

**Decisión tomada (06-oct-2026, PM):** B — bloquear sin nombrar. **Texto que reemplaza al del
mockup en P3:** *«El código ya está en uso. Pedí el traspaso al administrador central.»* El
panel lateral de «Posibles duplicados» no muestra nombre, código, estado ni área de
instituciones fuera del alcance del usuario.

### C-9 · El menú ⋮ de fila no existe como pieza `DECIDIDO 06/10/2026`

**Choque.** `.kebab` aparece en P4, P12, P20, P21 y P22 con acciones **deshabilitadas con
motivo**. El canon de tabla densa pide acciones como `.nodo-icon-btn` con `aria-label` *«con
el registro»*, no un menú. Un menú desplegable necesita foco atrapado, Escape y
`aria-expanded`/`aria-controls` para ser accesible.

| Opción | Costo |
|---|---|
| **A.** Crear la pieza «menú de fila» accesible (N-11) | ~1 día; la reusan 5 pantallas |
| **B.** Acciones visibles en la fila como hoy | filas muy anchas: P4 tiene 4 acciones por fila |

**Decisión tomada (06-oct-2026, PM):** A — se crea la pieza «menú de fila» accesible (N-11),
con foco atrapado, cierre con Escape, `aria-expanded`/`aria-controls` y acciones
deshabilitadas con motivo legible.

### C-10 · Emoji en lugar de íconos `DECIDIDO 06/10/2026`

**Choque.** El mockup usa 🔒 (P7 L889-890, P18 L1185), 📎 (P7 L904, P10 L974, P12 L1026,
P19 L1251, P20 L1307) y 📝 (P13 L1044) como íconos. Los emoji no tienen color controlable,
varían por sistema operativo y los lectores de pantalla los leen con su nombre Unicode.

| Opción | Costo |
|---|---|
| **A.** Reemplazar por íconos del set con `aria-hidden` | nulo; cambio visual mínimo |
| **B.** Tal cual | inconsistencia tipográfica y de accesibilidad |

**Decisión tomada (06-oct-2026, PM):** A — 🔒, 📎 y 📝 se reemplazan por íconos del set
(Font Awesome, por C-4) con `aria-hidden="true"`; ningún emoji queda como ícono en la v2.

### C-11 · P13 pierde el `thead` sticky que la pantalla productiva ya tiene `DECIDIDO 06/10/2026`

**Choque.** [`merenderos/prestacion_mensual.html:34-60`](../../../programas/templates/programas/merenderos/prestacion_mensual.html)
tiene encabezado pegajoso, scroll contenido con `h-[clamp(…)]`, un `nodo-field` numérico por
celda y `<output aria-live="polite">` para los totales. El `.grilla` del mockup es texto
plano, sin sticky ni scroll. Implementar «tal cual» es una **regresión**.

| Opción | Costo |
|---|---|
| **A.** Conservar sticky, scroll, inputs y `aria-live`, adoptando del mockup solo el aspecto (días «no funciona», totales en `td.tot`) | sin costo; mantiene lo ganado |
| **B.** Tal cual el mockup | regresión de usabilidad en una grilla de 31 días |

**Decisión tomada (06-oct-2026, PM):** A — se adopta el **aspecto** del mockup (días «no
funciona», totales en `td.tot`) conservando lo que la pantalla productiva ya tiene: `thead`
sticky, scroll contenido, `nodo-field` numérico por celda y `<output aria-live="polite">`.

### C-12 · P15 rediseña una pantalla transversal `DECIDIDO 06/10/2026`

**Choque.** El ABM de Roles es **transversal** (`users`), no de Dispositivos, y
[`core/rbac.py`](../../../core/rbac.py) es *«la pieza única de autorización del backoffice»*.
P15 le cambia la presentación (grupos con switches) y le suma un nivel de alcance
(subsecretaría) que afecta a **todos** los programas.

| Opción | Costo |
|---|---|
| **A.** Agregar las capacidades de Dispositivos al `CATALOGO` sin tocar la pantalla | nulo; el mockup queda sin cumplir en P15 |
| **B.** Rediseñar el ABM como el mockup | toca Becas, Legajos, Usuarios y Merenderos a la vez; hay que verificar consumidores en todos los programas |
| **C.** Pantalla de rol **específica de Dispositivos**, conviviendo con el ABM general | duplica la autorización en dos lugares — contraindicado por CLAUDE.md |

**Decisión tomada (06-oct-2026, PM):** A — las capacidades de Dispositivos se agregan al
`CATALOGO` de `core/rbac.py` **sin tocar la pantalla** del ABM de Roles. El rediseño del ABM
(grupos con switches, nivel de alcance por subsecretaría) sale del alcance de la v2 y va como
**proyecto aparte**, porque es transversal a Becas, Legajos, Usuarios y Merenderos. P15 queda
sin cumplir visualmente en esta versión.

### C-13 · «No se puede copiar ni exportar» ya fue respondido al cliente `DECIDIDO 06/10/2026`

**Choque.** P18 promete: *«Dentro, el contenido no se puede copiar ni exportar sin el nivel,
y lleva una marca de agua con el usuario y la hora.»* El **Cambio 72** registra lo contrario,
ya comunicado por escrito al Ministerio: *«El documento aclara al cliente que «inhabilitar
capturas o copias», como quedó en la minuta del 19/06, **no es técnicamente posible** en
ningún sistema web, y enumera las cinco medidas que sí se implementan en su lugar.»*

| Opción | Costo |
|---|---|
| **A.** Implementar solo lo que sí se puede (compuerta de confirmación, auditoría de lectura, marca de agua visual, bloqueo de exportación del servidor) y **ajustar el texto del mockup** | sin costo; es coherente con lo ya comunicado |
| **B.** Intentar bloquear la copia en el navegador | falsa promesa; se vulnera con la consola |

**Decisión tomada (06-oct-2026, PM):** A — se implementan las cuatro medidas reales
(compuerta de confirmación antes de abrir, auditoría de lectura, marca de agua visual con
usuario y hora, y bloqueo de exportación **en el servidor**) y se corrige el texto del
mockup. **Texto que reemplaza al de P18:** *«Dentro, el contenido lleva una marca de agua con
tu nombre y la hora, y la exportación queda bloqueada sin el nivel. Impedir una captura de
pantalla no es técnicamente posible en ningún sistema web.»* Es lo mismo que el Cambio 72 ya
comunicó por escrito al Ministerio.

### C-14 · El mapa de P19 no tiene librería y la CSP bloquea los CDN `DECIDIDO 06/10/2026`

**Choque.** P19 pide ubicación geolocalizada con mapa («se usa en presentaciones ante
programas nacionales»). El mockup dibuja un **SVG a mano**. En el repo **no hay librería de
mapas**, y `config.middlewares.security_headers.SecurityHeadersMiddleware` impone CSP (por
eso SortableJS está vendorizado, *«sin CDN por la CSP»*).

| Opción | Costo |
|---|---|
| **A.** Vendorizar Leaflet + tiles de un proveedor permitido en la CSP | ~2 días + decidir el proveedor de tiles y su licencia; hay que abrir `img-src`/`connect-src` |
| **B.** Sin mapa: coordenadas, un enlace «ver en el mapa» que abre fuera y el plano como adjunto | ~2 horas; cumple el uso declarado (presentaciones) con el PDF del plano |
| **C.** Imagen estática del mapa generada al guardar el punto | ~1 día + dependencia de un servicio externo con clave |

**Decisión tomada (06-oct-2026, PM):** B — sin librería de mapas: coordenadas visibles, un
enlace «ver en el mapa» que abre fuera (`target="_blank" rel="noopener"`) y el plano del
edificio como adjunto. No se toca la CSP. Leaflet queda como ampliación posterior, solo si el
Ministerio lo pide.

### C-15 · Los botones del mockup no tienen el `min-width` del sistema `DECIDIDO 06/10/2026`

**Choque.** El `.btn` del mockup (L109) es `height:40px;padding:0 16px` y **sin ancho mínimo**:
cada botón mide lo que mide su texto. Los botones reales llevan `min-width` por tamaño —
`btn-xs` 128 px, `btn-sm` 143 px, `btn-base` 151 px, `btn-lg` 170 px, `btn-xl` 186 px
([`nodo-buttons.css:37-70`](../../../static/custom/css/nodo-buttons.css)). Implementado con la
pieza real, **toda fila de acciones queda bastante más ancha que en el mockup**, y el efecto se
acumula donde hay varias: P4 tiene 4 botones en el header, P12 tiene 4, P2 tiene 3 más el
«Ver detalle» de cada fila, y P8 mete dos botones dentro de la celda de acciones.

Es el único punto donde «tal cual el mockup» y «usar la pieza canónica» dan **layouts
distintos sin que ninguna de las dos partes esté mal**: el mockup no inventó nada, simplemente
no copió esa declaración.

| Opción | Costo |
|---|---|
| **A.** Usar `btn-nodo` tal cual | las barras de acciones y las celdas de la última columna crecen respecto del mockup; en P4 y P12 es muy visible |
| **B.** Habilitar una variante **sin ancho mínimo** para acciones compactas (p. ej. `btn-fit`) y usarla en headers densos y celdas de tabla | ~medio día; toca una pieza canónica, así que el mismo diff actualiza el inventario y su ficha |
| **C.** Sacar el `min-width` del sistema | afecta a Becas, Legajos, Usuarios y Portal; fuera del alcance de la v2 |

*Conviene decidirlo antes de la primera pantalla: con A, el resultado no se va a parecer al
link que el cliente aprobó, y la diferencia no se arregla pantalla por pantalla.*

**Decisión tomada (06-oct-2026, PM):** B — se agrega a `nodo-buttons.css` una variante
`btn-fit` **sin ancho mínimo**, de uso acotado a headers densos y celdas de tabla. El
`min-width` del sistema no se toca: sigue vigente para Becas, Legajos, Usuarios y Portal.

---

## 8. Orden de implementación · **fijado el 06-oct-2026**

Ordenado por **dependencias de datos y de piezas**, no por valor para el cliente. Con los 15
conflictos decididos, el orden queda en tres tramos: **primero las tareas de sistema**,
después **las 18 pantallas que tienen golden**, y **al final P1, P6, P7 y P22** —las cuatro
sin golden— ya con su molde construido (C-7 → C + A en paralelo).

**Ola 0 — tareas de sistema (bloquean la primera pantalla).** Es el análisis **M0** en
GitHub. C-1, C-4, C-6, C-10, C-11, C-12 y C-13 no generan tarea propia: son reglas que cada
pantalla aplica al implementarse.

1. Cerrar la **Ola 6** del agente de diseño: con el Cambio 132 ya están el núcleo, las fichas
   de arquetipo y componentes y los consumidores; faltan los **pasos 6 y 7** (ejercicio de
   control y registro final). Es precondición explícita de §7 de la auditoría.
2. **Variante «tablero» de stat card** (C-2 → C), con la revisión de CMP-23 en el mismo diff
   — la usan P1, P4, P12, P19 y P21. *~1 día.*
3. **Ampliación de `_alerta.html`** con `icono` y `accion_url`/`accion_texto` (C-5 → B) — la
   usan **15 de 22** pantallas. *~½ día.*
4. **Variante `btn-fit`** sin ancho mínimo (C-15 → B) — sin ella ninguna barra de acciones
   se parece al mockup, y la diferencia no se arregla pantalla por pantalla. *~½ día.*
5. **Menú de fila accesible** N-11 (C-9 → A) — lo reusan P4, P12, P20, P21 y P22. *~1 día.*
6. **Hero de inicio de programa** (C-3 → C), acotado a Inicio y tableros de programa. *~½ día.*
7. **Bloque de ubicación sin mapa** (C-14 → B): coordenadas, enlace externo y plano adjunto.
   *~2 h.*
8. **N-1 (eyebrow) en `{% page_header %}`**: lo usan **19 de 22** pantallas. Sin decisión de
   §7 — se propone como novedad al abrir la primera pantalla que lo necesita (P2).
9. **Goldens que faltan** —dashboard, wizard y caso complejo— en paralelo con las Olas 1 a 5.
   No bloquean las 18 pantallas con golden; sí bloquean el tramo final.

**Ola 1 — el legajo institucional (sin dependencias nuevas).** Las 18 pantallas con golden
empiezan acá.
10. **P2** Instituciones — arquetipo listado, golden lista, paginación (PERF-17).
11. **P3** Alta con anti-duplicado — el servicio de duplicados ya existe; el mensaje va con
    el texto de C-8 (bloquea sin nombrar).
12. **P14** Configuración del tipo — habilita casi todo lo demás (reglas, umbrales,
    catálogos, secciones mínimas).
13. **P17** Formularios del tipo — depende de P14 (entidad Sección) y de la baja lógica
    (DIS-10 / task #313).

**Ola 2 — capacidad y estadías (núcleo operativo).**
14. **Modelo `Sector`** + `Cama.PRESTADA` + motivo de fuera de servicio → **P5**.
15. **`clave_alojamiento`** (DIS-02) + reingreso de red. *El modelo va acá; la pantalla
    **P6** es un wizard y espera su golden (tramo final).*
16. **Estado `EN_TRANSITO`** con reserva, vencimiento, recepción y rechazo (DIS-03) → **P8**.
17. Catálogos de egreso + fecha futura (DIS-06) + enganche con `DerivacionPrograma` → **P9**.
18. **P4** detalle del dispositivo — consume 14-17; conviene **después**, no antes.

**Ola 3 — ficha, sensibilidad y bitácora.**
19. Sensibilidad por sección + capacidades en `CATALOGO` + auditoría de lectura → **P18**.
    Por C-12, **P15 no se implementa en la v2**: las capacidades entran al `CATALOGO` y el
    ABM de Roles queda como está.
20. Traza por estadía + completitud por sección + versionado. *El motor va acá; la pantalla
    **P7** es revisión compleja y espera su golden (tramo final).*
21. Entradas de bitácora, apertura/cierre, pase de guardia, regularización → **P10**
    (respetando DIS-01/DIS-08: sin `Trunc*` sobre `DateTimeField`).
22. Prioridad y origen en la espera + bandeja de derivaciones (LEG-06) → **P11**.
23. **P16** solapa del legajo — barata una vez que el motor de la ficha (20) existe.

**Ola 4 — Merenderos.**
24. Documentación con vigencia + catálogo de kits + equivalencia + anulación (MER-02) →
    **P12**.
25. Días estructurados + cierre del mes por otro rol (MER-01) → **P13**, con el aspecto del
    mockup **sobre** el sticky, el scroll, los inputs y el `aria-live` que ya existen (C-11).

**Ola 5 — el edificio (bloque que el Ministerio puede postergar entero).**
26. Entidad **`Edificio`/`Predio`** N:M + tenencia, servicios, estado físico, fotos.
27. Regla de vigencia sobre `core/services/vencimientos.py` → **P19**, con la ubicación sin
    mapa de C-14 (la pieza ya está construida en la Ola 0).
28. Modelo de relevamiento edilicio (con el nombre que salga de Q4) → **P21**.
29. `ItemConsumo` + `PagoConsumo` + regla de 7 días + escalamiento → **P20**.

**Ola 6 — las cuatro pantallas sin golden, al final.** Precondición: la golden de su
arquetipo construida (punto 9) y la Ola 6 del agente cerrada. Hasta entonces el agente de
diseño frena y devuelve, y eso no se saltea.
30. **P6** asistente de ingreso — *wizard*; consume el modelo del punto 15.
31. **P7** estadía y ficha viva — *revisión compleja*; consume el motor del punto 20.
32. Agregación de red + modelo de alerta operativa → **P1** — *dashboard*.
33. Catálogo de widgets por rol + recordatorios → **P22** — *dashboard*.

El Cambio 85 ya había separado el bloque del edificio como **etapa 5 completa**, con este
argumento: *«las cuatro primeras hablan de las personas… y la quinta habla del edificio…
así el Ministerio puede aprobar o postergar una sin tocar la otra»*. Este orden lo respeta:
mover P6 y P7 al tramo final mueve **la pantalla**, no el modelo ni el motor, que siguen en
su ola original y siguen alimentando al resto.

---

## 9. Preguntas abiertas

**Q1 · ¿Qué es F11?** La intro y el sidebar del mockup anuncian «F8 a F11» (L305, L347) y
P22 dice «Implementa F11» (L1387), pero el mockup **no tiene** un tablero `#f11`. Coincide
con el pendiente del Cambio 85. ¿Falta dibujarlo o F11 es solo la etiqueta del módulo M17?

**Q2 · ¿El mockup es la versión final?** El Cambio 85 dejó como pendiente *«Las tres
pantallas nuevas no están en el mockup»*; el archivo se actualizó el 20/09 (`c75a6b61`) y
**ya las trae** (P19, P20, P21) más P22. Ese pendiente está obsoleto y **no hay entrada de
requerimientos que registre la actualización**: el Cambio 72 documenta 18 pantallas y hoy
son 22. ¿Se registra ahora como cambio aparte?

**Q3 · Vocabulario: «Instituciones» o «Legajos de dispositivos».** El mockup titula
«Instituciones» (P2) y la pantalla productiva «Legajos de dispositivos»
(`legajo/list.html:10`). El ítem del sidebar también cambia («Legajos» → «Instituciones»).
¿Se adopta el vocabulario del mockup en toda la superficie?

**Q4 · Cómo se llama el relevamiento edilicio.** `Relevamiento` ya existe y es de **Becas**
(`models:1761`), igual que las capacidades `relevamiento.ver/gestionar` (`core/rbac.py:91`)
y la memoria del proyecto sobre el vocabulario «relevamiento vs caso». Hay que elegir otro
nombre de modelo, de URL y de capacidad antes de modelar P21, o la ambigüedad se propaga.

**Q5 · ¿Un constructor o dos?** El Cambio 58 dejó asentado que *«el F-00 de Dispositivos
queda afuera»* del constructor de formularios de Becas. P17 es, de hecho, un constructor
para Dispositivos. ¿Se extiende el de Becas (`DisenoFormulario`/`ItemDiseno`, `models:2998`)
o se construye uno propio?

**Q6 · ¿Quién ve los importes?** P20 muestra alquiler e importes dentro del legajo
institucional sin declarar capacidad. ¿Alcanza con `dispositivo.ver` o va con una capacidad
propia?

**Q7 · Responsive.** El mockup solo tiene un breakpoint a 1100 px y ahí **oculta el
sidebar**; ninguna pantalla está diseñada para celular. P10 (bitácora) y P21 (relevamientos)
son las candidatas a uso móvil real. ¿Se diseñan o se asume escritorio?

**Q8 · «Administrador superior».** P19 restringe «Relevar ya» al *«Administrador superior»*
y P22 nombra una jerarquía ministro → subsecretario → director → operadores. El modelo de
alcance es plano (institución / subsecretaría / total) y el **organigrama sigue pendiente
desde el 16/09** (Cambio 85). ¿Se implementa contra la subsecretaría, como ya se había
previsto?

**Q9 · Merenderos y el edificio.** El mockup los deja fuera de M14 y M15 *«en esta etapa»*
(L347, L409, L1292). ¿Queda confirmado, o entran más adelante con el mismo modelo de predio?

**Q10 · ¿Cuántos widgets quedan activos en P22?** El mockup se contradice: el panel de widgets
deja **10** `.toggle` en `on` (L1394-L1397) y el `kv` de la derecha dice «Widgets activos ·
**9 de 16**» (L1404). Son datos de ejemplo, pero hay que saber cuál refleja la intención antes
de armar el catálogo.

---

## 10. Qué se verificó

- Mockup leído entero: 1517 líneas, 32 tableros (10 flujos + 22 pantallas), hoja de estilo
  principal (L21-L300) y el script del shell (L1437-L1516).
- Código contrastado: `programas/models/__init__.py`, `services/{dispositivos,admisiones,camas,merenderos,registro_diario,indicadores,solapas}.py`,
  `dispositivos_urls.py`, `merenderos_urls.py`, `core/rbac.py`, `core/services/vencimientos.py`,
  `legajos/models/base.py`, las 6 plantillas de `dispositivos/legajo/`, las 6 de
  `merenderos/`, `templates/includes/{base,navbar}.html`, `sidebar/opciones.html`,
  `templates/inicio.html`, `templates/components/{list_filters,_paginacion,_estado_vacio,_alerta,_stat_card}.html`
  y `static/custom/css/{chaco-tokens,nodo-badges,nodo-buttons,nodo-forms,nodo-tables,dynamic-list-filters}.css`.
- Documentación consultada: `CLAUDE.md`, el núcleo `.claude/agents/chaco-design-system.md` y
  las fichas de `.claude/design/` (arquetipos y componentes) tal como quedaron tras el
  Cambio 132, `docs/internal/auditoria-2026-10/README.md` §6 y §7, `anexo-agente-diseno.md` §3
  y `scripts/design_audit.py` (`ARQUETIPOS`, `GOLDENS`, reglas P1).
- Requerimientos: Cambios **36**, **48**, **58**, **72**, **85** y **132** (`scripts/requerimientos.py --ver`).
- Capturas: 34 imágenes generadas con Chromium headless a 1760 px desde el HTML local.



