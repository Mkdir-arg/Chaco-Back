# Anexo · Propuesta final del agente de diseño (Ola 6)

Fuente: revisión adversarial V5b de la propuesta A7, reconciliada con la verificación de front V5a. Medido sobre
`development @ 8a4921a` (= `917e583` + docs). Línea base reproducible: `poc/herramientas/design_baseline.py`.
Este anexo es la especificación para implementar la Ola 6. El resumen está en README §5.

**Urgencia.** La Versión 2 de Dispositivos y Merenderos (Cambio 69) tiene 45 tasks y unas 434 h de desarrollo, casi
todas pantallas nuevas en módulos que hoy tienen 0 piezas canónicas. Si el sistema de agentes no cambia **antes de la
primera task de pantalla de la v2**, esas pantallas van a clonar a sus hermanas legacy. Antecedentes del propio repo: en
el Cambio 36 `design_audit` daba 0/0 en Dispositivos y el módulo «era todo lo contrario»; en el Cambio 69 un diseño
hecho con el canon en prosa fue rechazado por el PM («misma paleta, distinto diseño») y se rehízo mirando pantallas
reales.

---

## 1. Diagnóstico verificado

El diagnóstico de A7 se sostiene en lo central: el sistema gobierna un **inventario**, pero no le enseña al agente a
**reproducir pantallas**. No hay molde por arquetipo, la auditoría no mira la estructura y no corre en CI.

| # | Afirmación de A7 | Veredicto V5b | Medición |
|---|---|---|---|
| 1 | El agente canónico pesa 64,5 KB, 8.150 palabras, 282 líneas | CONFIRMADO | 64.467 B (~18k tokens) |
| 2 | La fila más larga ~4.000 caracteres | CONFIRMADO | 3.981; 5 filas > 3.000 (L64, 73, 79, 84, 92) |
| 3 | 34 referencias a historia | CONFIRMADO aprox. | 39 con IDs CMP/ALR/TIT/DP; 25 solo Cambio/Ola/POP/W y fechas |
| 4 | 107 commits sobre el agente | AJUSTADO | 107, de los cuales 67 no son merge |
| 5 | `page_header` 0 usos fuera de Becas | CONFIRMADO | 24 archivos, todos en `programas/templates/programas/becas/**` |
| 6 | 12 variantes de `<h1>` | AJUSTADO | 20 variantes sin el portal; la más usada `text-2xl font-bold text-gray-900` (×21) |
| 7 | 31 de 50 archivos con `<table>` sin `nodo-th` | CONFIRMADO | 31/50 |
| 8 | 1.015 usos de paleta cruda en 38 archivos | CONFIRMADO | 963 dentro de `class=""`; **0 en Becas, Dispositivos y Merenderos**; legajos 441, configuración 183, conversaciones 179, `templates/` 82 |
| 9 | 2.193 `style=` en 114 archivos | CONFIRMADO | 2.187 / 114 (224 en Becas) |
| 10 | 47 archivos con `<style>` | CONFIRMADO | 47; 39 sin correos ni shells |
| 11 | `[x-cloak]` copiado en 47 templates | **REFUTADO** | **16 archivos**; la definición global está en `override.css:100`, cargada por `base.html:86` |
| 12 | 37 archivos con SVG inline vs 87 con Font Awesome | CONFIRMADO aprox. | 37 vs 93 |
| 13 | 8 variantes de overlay de modal | AJUSTADO | 10 cadenas `fixed inset-0`; las más usadas: canónica (×23) y canónica + `backdrop-blur-sm` (×6) |
| 14 | `design_audit.py` completo da 46 errores y 28 warnings | CONFIRMADO | 46 / 28 (contradice el «0 errores» de `CLAUDE.md:79` y `:245`) |
| 15 | `design_audit.py` no corre en CI | CONFIRMADO | `design-agent-contract.yml:38-42` solo corre `check_design_agent.py` y su test |
| 16 | Desvíos dentro de las referencias | CONFIRMADO | `programa_list`: `<style>[x-cloak]` L6, labels `text-[13px] font-semibold` L48/57/63, nota con `style` y SVG; `_programas_table`: `style="margin:16px"` en L5, `hover:bg-tertiary` L38, vacío a mano L78; `convocatoria_detail`: 17 íconos sin `aria-hidden`, 0 `role="tablist"` |
| 17 | `cupo/segmento_detail` es la mejor de su tipo | CONFIRMADO con salvedad | `tablist`/`tab`/`tabpanel` completos; conserva `<style>[x-cloak]` (L6) y 3 avatares `style="background:var(--gradient-brand)"` (L76, 150, 219) |
| 18 | Dispositivos y Configuración se desvían | CONFIRMADO | `legajo/list` `style="font-size:28px…"` L10 y `thead style` L36; `detail` «← Volver» L13; el wizard extiende `includes/main.html` |
| 19 | `AGENTS.md` 408 líneas, solo L9-26 de UI; filas duplicadas L62/L65 | CONFIRMADO | las dos describen `base_public_auth.html` |
| 20 | Contradicción (a): L97-102 invita a crear modales | CONFIRMADO | choca con la fila «Modal Becas accesible» (L92) |
| 21 | Contradicción (b): gradiente «con moderación» vs «ya no se usa» | AJUSTADO | la prohibición es solo para stat cards (L75); la golden de detalle usa avatares con gradiente (D5) |
| 22 | Contradicción (c): títulos ~16px vs `h3 text-sm` | **REFUTADO** | `h2 text-heading font-bold` (título de surface) y `h3 text-sm font-bold` (subtítulo) son dos niveles |
| 23 | Contradicción (d): botón de ícono en prosa vs `.nodo-icon-btn` | CONFIRMADO | prosa L149-151 vs fila L66 |
| 24 | Contradicción (e): «`nodo-field` o clases equivalentes» | CONFIRMADO | L155 |
| 25 | Contradicción (f): no hay confirmación única | AJUSTADO | `ModernModal` en backoffice y Swal condicionado en Dispositivos/Legajos (Cambio 48); el hueco real es la confirmación **con motivo** en pantallas nuevas; además Becas escucha `[data-confirm-url]` y el handler inline de Dispositivos/Merenderos `[data-confirm]` |
| 26 | Contradicción (g): «0 errores» vs 46 | CONFIRMADO | `CLAUDE.md:79`, `:245` |
| 27 | Filtros dinámicos sin documentar; el JS reescribe el form | CONFIRMADO | 0 menciones; `dynamic_list_filters.js:36-40` hace `innerHTML=''`, pisa `className` y quita `style`; usada en **15 archivos de 7 módulos**: la pieza canónica más transversal y la única sin documentar. `labelFor()`: `aria-label` → `label[for]` → `placeholder` → primera opción → `name`; solo `input[name]` y `select[name]` |
| 28 | `main.html`, `alertas_eventos`, `widget_contactos` sin clasificar | CONFIRMADO | 17 templates extienden `main.html` (14 de Configuración + 403/404/500) |
| 29 | «Fuera de Becas solo `_alta_rapida_modal.html` incluye `_modal_header.html`» | **REFUTADO** | lo nombra en un comentario para explicar por qué **no** lo incluye: `_modal_header`/`_modal_footer` cierran con `data-becas-modal-cerrar` (dependen de `becas-modal.js`). Moverlos a `components/` no es un simple cambio de nombre |
| 30 | `design_audit` solo tiene reglas de token/lint | CONFIRMADO | 11 reglas; TWBUILD solo mira variantes y arbitrarios |
| 31 | El hook audita el archivo entero y deja pasar lo preexistente | CONFIRMADO | `hook_mode()` → `audit_file(path)`; mensaje L336-339 «no bloquean… seguí» |
| 32 | A `EVIDENCE_PREFIXES` le faltan `core/`, `legajos/`… | CONFIRMADO | L47: `core/templatetags/nodo_ui.py` no cuenta como evidencia |
| 33 | 6 archivos con solapas; 5 sin `tablist` | AJUSTADO | 4 de 6 (`cupo/segmento_detail` y `dispositivos/legajo/detail` sí) |
| 34 | 0 menciones de Heroicons; `list_filters.html` usa SVG | CONFIRMADO | — |
| 35 | Worktrees viejos contaminan `grep -r` | CONFIRMADO | `.claude/worktrees/` devuelve copias viejas; `.gitignore:50` los ignora para Grep/rg |
| 36 | El hook usa el `python` global | CONFIRMADO, trivial | solo stdlib; riesgo de portabilidad |
| 37 | `base.html` usa un token del puente legacy (`--fondo-principal`) | **REFUTADO** | `base.html:40` lo redefine como `var(--bg-secondary)` |

**Problemas nuevos que A7 no vio (V5b):**
- **N1.** `check_design_agent.py` saltea en silencio las filas con `\|` (`inventory_rows()` parte por `|` sin respetar el
  escape): Tabs backoffice (L72), Estado vacío (L76) y Drag & drop (L83) se descartan; parsea 33 de 36 filas. Por eso
  `templates/components/_estado_vacio.html` no es evidencia canónica.
- **N2.** La regla «pieza canónica cambiada → actualizar el agente en el mismo diff» cubre 71 rutas, entre ellas
  `static/custom/css/tailwind.css` (se regenera en cada build), 4 tests y `programas/views/revision.py`: es **el motor del
  changelog** (de ahí las filas de 4.000 caracteres). Si no se corrige, el núcleo vuelve a crecer aunque se reescriba.
- **N3.** Las acciones del encabezado no siguen el contrato escrito («`btn-sm`», L70): listados y formularios usan
  `btn-base` (primaria `btn-brand`, secundaria `btn-tertiary`; 10 usos), detalles `btn-secondary btn-sm` (6 usos).
- **N4.** Los filtros tienen 4 dialectos de markup en pantallas «limpias» (label suelto en `personas_list`, card con
  grilla y botones propios en `renaper_pendientes`, label canónico en `reporte`, `sr-only` en Merenderos); el JS los
  reescribe igual, pero se copian. La ficha fija uno: controles con `aria-label` y sin wrapper.
- **N5.** La receta canónica del modal tiene un `style=` (`backdrop-filter:blur(4px)`); `backdrop-blur-sm` ya está
  compilada (6 overlays la usan).

Hallazgos de V5a que alimentan este anexo: FE-13 (decodificador y regla CLASSDEF), V5A-NEW-01 (gate de build),
V5A-NEW-07 (deuda en las candidatas a golden), V5A-NEW-08 (`compile_templates.py` con `site-packages`).

---

## 2. Qué se mantiene y qué se recorta de A7

### 2.1 Se mantiene (el 20 % que rinde el 80 %)
| Pieza | Por qué | Ajuste |
|---|---|---|
| Una golden por arquetipo, saneada | El Cambio 69 lo demostró: el agente acierta cuando copia algo real | La golden queda **bloqueada** por `design_audit.py --goldens` en CI |
| Fichas con esqueleto literal | Cierra la brecha entre prosa y markup | Solo 5 arquetipos + componentes con contrato largo |
| Plan de pantalla antes de escribir | Vuelve revisable el resultado | Solo en pantalla nueva y pieza nueva; «frenar» = devolver al llamador (§2.3) |
| Ratchet en hook y CI | Lo nuevo nace limpio y la deuda no bloquea | **7 reglas P1** + CLASSDEF (V5a), sin archivo de baseline: la base es `git show <ref>:<archivo>` |
| Núcleo corto y sin historia | De ~25k tokens por invocación a ~10k | Límite en bytes y prohibición de IDs de historia, verificados por el checker |
| Documentar filtros, `_field` y `main.html` | Piezas vivas con las que el agente choca | — |
| Borrar L97-102 y resolver contradicciones | Barato | Menos la (c), que no es contradicción |
| Ejercicio de control antes/después | Única forma de saber si sirvió | 3 pantallas, criterio mecánico + revisión visual, sin *similarity* |
| Quitar `Edit` al revisor | Barato; da independencia | — |

### 2.2 Se recorta (no implementar)
| Recorte | Motivo |
|---|---|
| `design_conformidad.py` + `conformidad.md` generado + chequeo en CI | Lo resuelve una regla simple: **solo se clona una golden; una hermana nunca es molde** (de la hermana solo se toma dominio). Sería otro archivo generado que envejece |
| `design_skeleton.py` con diff y *similarity* ≥ 0,90 | Frágil y sin calibración; lo reemplazan **marcadores ordenados por arquetipo** (`design_audit.py --arquetipo`, ~60 líneas) |
| R-08 a R-20 como bloqueantes | Poco valor marginal o muchos falsos positivos; van a WARN en fase 2 solo si el ejercicio de control muestra desvíos que las P1 no atrapan |
| `scripts/design_baseline.json` + `--baseline-write` | Duplica lo que git ya sabe |
| Promover `_modal_*`, `_field`, `_confirm_js`, `_ajax_js` a `components/` + alias `x-nodo-modal` | Refactor de front (rompe consumidores, afirmación 29); al agente le alcanza con **declararlos transversales** (se incluyen desde su ruta actual cargando `becas-modal.js` en `customJS`). Mover `_field` ya está en FE-23 |
| `ModernModal` con `input` para pedir un motivo | Confirmación con motivo = arquetipo Modal con form POST (D2). Cero código nuevo |
| `components/_tab.html` y `{% alerta %}` | Las solapas se clonan de la golden con su ARIA; la alerta con HTML tiene receta en `segmento_form.html` |
| «Revisión de caso» como arquetipo | `formulario_detalle.html` (1.079 líneas, dominio Becas) no sirve como molde |

### 2.3 Condiciones para que el «Plan de pantalla con freno» funcione
1. **Alcance:** solo en (B) pantalla nueva y (C) pieza nueva. Los ajustes (A) no lo piden.
2. **«Frenar» = no escribir y devolver el Plan con las Novedades al llamador.** `chaco-frontend` corre como subagente y no
   puede preguntarle al usuario (la memoria además pide preguntas en texto, nada de `AskUserQuestion`); decide el juez.
3. **Lista cerrada de novedades:** clase CSS nueva; archivo CSS o JS nuevo; include o tag nuevo; parámetro nuevo de un
   componente; valor arbitrario de Tailwind fuera de la lista blanca; `<style>` o `style=` no exento; ícono de otra
   familia; arquetipo sin ficha. Textos, columnas, URLs y permisos **no** son novedad.

### 2.4 Tamaño del núcleo
Con el inventario actual un núcleo ≤ 8k tokens no es realista (solo las filas suman ~50 KB). Sí lo es si **la evidencia
de una fila se declara en su ficha**: fila ≤ 450 caracteres (nombre, clasificación, una línea de contrato y link a la
ficha) y una fila por dominio para inscripción, constructor, SIIS, dashboard e identificadores. Estimación: ~26 filas ×
~300 B (7,8 KB) + protocolo 3 + reglas duras 2,5 + arquetipos 1,5 + superficies 1,2 + vocabulario 2 + perfiles 2 + resto
2,5 ≈ **23 KB (~6,5-7k tokens)**. Límite verificable en el checker: **núcleo ≤ 30.000 bytes**. Costo por invocación de
`chaco-frontend` en una pantalla nueva: núcleo (~7k) + ficha de arquetipo (~1,5k) + 3-4 fichas de componente (~2k) ≈
10-11k tokens (hoy ~25k: agente ~18k + `AGENTS.md` ~7k leído entero).

### 2.5 Contrato «pieza canónica → mismo diff», redefinido
- **Lo satisface:** un cambio en el núcleo **o en la ficha de esa fila** (si no, cada corrección de ficha obliga a tocar el
  núcleo y vuelve el changelog).
- **Lo disparan:** componentes, CSS/JS canónicos, shells, goldens y `core/templatetags/`. **No lo disparan:**
  `tailwind.css` (generado), `*/tests/*` y `*/views/*` (siguen validándose como rutas existentes).
- **Arreglos:** parseo de `\|` (N1), prefijos faltantes (afirmación 32), límites de tamaño e historia.

---

## 3. Goldens por arquetipo (A6 + A7 reconciliadas por V5a y V5b)

Criterio: (1) 0 hallazgos en las reglas P1 **después** de un saneamiento chico; (2) ARIA completo en el patrón que la
define; (3) es la que el código ya usa como consumidor del componente; (4) ante empate, la más corta.

| Arquetipo | **Golden (única que se clona)** | Secundaria (solo para lo indicado) | Saneamiento previo (paso 3) | Pantallas a alinear después |
|---|---|---|---|---|
| Listado con filtros + tabla densa | `programas/templates/programas/becas/revision/personas_list.html` (97 líneas; P1 = 0) | `reportes/reporte.html` (varios filtros); `revision/formulario_list.html` (acción primaria en el header) | Form de filtros **sin `class`** y con `aria-label` en cada control en vez del label suelto (`dynamic_list_filters.js:36-40` borra las clases); `<th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>` (hoy vacío, L39) | `user_list`, `rol_list`, `configuracion/*_list` (6), `ciudadano_list`, `dispositivos/legajo/list`, `dispositivos/config/tipo_list`, `merenderos/list`, `merenderos/solicitudes`, `admisiones/espera`, `becas/relevamientos/relevamiento_list` |
| Detalle con solapas | `programas/templates/programas/becas/cupo/segmento_detail.html` | `config/programa_detail.html`: solo para la solapa con carga diferida (`$dispatch`) y la solapa condicionada por permiso. `relevamientos/convocatoria_detail.html`: solo migas y acciones del header (con `aria-hidden` en sus íconos), **nunca sus solapas** (sin ARIA) | Quitar `<style>[x-cloak]` (L6); avatares L76/150/219 según D5; (posterior, con FE-17/FE-24 y su ficha en el mismo PR) 3 paginaciones copiadas → `_paginacion` con `param`/`extra_qs`, flechas y `tabindex` itinerante, `history.replaceState` al cambiar de solapa; rebuild por `mt-px`/`w-40` (V5A-NEW-01) | `dispositivos/legajo/detail`, `legajos/ciudadano_detail`, `legajos/programas/programa_detail`, `merenderos/detail`, `users/rol/rol_detail`; ARIA de `config/programa_detail`, `convocatoria_detail`, `relevamiento_detail` |
| Formulario (página) | `programas/templates/programas/becas/config/segmento_form.html` (29 líneas; P1 = 0) + `becas/_field.html` | — (la variante con `fieldset` por tipo es una regla de la ficha, sin golden) | Ninguno para el ratchet. Posterior (con FE-08/FE-23 y su ficha): `{{ form.non_field_errors }}` → `components/_form_errores.html`; `aria-describedby`/`aria-invalid` en `_field`. La ficha aclara que «Crear coordinador» y `_alta_rapida_modal` son de dominio y no se copian | `configuracion/*_form` y `*_confirm_delete`, `users/rol/rol_form`, `legajos/ciudadano_{edit,manual,confirmar}_form`, `derivar_programa`, `dispositivos/legajo/{form,cama_form,camas_form,parte_diario}`, `merenderos/{solicitud_form,entrega_form}`, `admisiones/*` |
| Modal de alta/edición | Modal «Nuevo programa» de `programas/templates/programas/becas/config/programa_list.html` (L36-81) + `_modal_header.html` + `_modal_footer.html` + `becas-modal.js` + `_ajax_js.html` | — (se descartó `convocatoria_list.html`: 6 labels sin `for` y backdrop con `style=`) | Labels L48/57/63 (`text-[13px] font-semibold mb-1.5`) → `block text-sm font-medium text-heading mb-1`; help text L50 en `text-fg-danger` → `text-body-subtle`; agregar `<p class="text-xs text-fg-danger hidden" data-error="__all__"></p>`; nota L70-76 (`style=` + SVG) → `_alerta.html tono="info"`; `style="backdrop-filter:blur(4px)"` → `backdrop-blur-sm`; quitar `<style>[x-cloak]` (L6). Hoy **ningún** consumidor de `x-becas-modal` está limpio | Modales de `configuracion/{localidad,municipio,provincia,secretaria,subsecretaria}_list` (FE-07); `modalVinculo`/`modalArchivos` de `ciudadano_detail` (variante vanilla `becasModal.bind`, FE-21); `modalRespuestas` de `_dashboard_panel`; `becas/config/segmento_detail` y `programa_detail` |
| Confirmación sí/no | Botón con `data-confirm-url` + `programas/templates/programas/becas/_confirm_js.html` → `ModernModal` | — | — | `user_list`, `rol_list`, `configuracion/*_confirm_delete` |
| Confirmación con motivo | **Arquetipo Modal** con `<form method="post">` + textarea `nodo-field` requerida (D2) | — | — | Pantallas nuevas. Las legacy de Dispositivos/Merenderos/Legajos siguen con Swal condicionado (Cambio 48) unificado en `_swal_confirm_js.html` (FE-19) |
| Franja de métricas | Grilla + `_stat_card` de `cupo/segmento_detail.html` L20-28 | — | — | `inicio.html`, `legajos/reportes.html`, `alertas_dashboard`, `.cl-stat-card` de `ciudadano_list`, indicadores de `dispositivos/legajo/detail` |
| Badge de estado | Parcial por módulo con el contrato de `programas/templates/programas/dispositivos/_estado_badge.html` | `becas/_pausable_estado_badge.html` | — | Merenderos, Users/Roles, semáforo de Dispositivos (FE-18) |
| Wizard; revisión de caso compleja; dashboard completo | **No hay golden → frenar y devolver** | Semántica del stepper: `portal/templates/portal/inscripcion/_stepper.html` (`aria-current="step"`, `sr-only` «Paso actual:») | — | El dashboard de Becas (`_dashboard_panel.html` + `becas-dashboard.js`) **no es molde**; su deuda (KPIs inline, `h3 style="font-size:16px"`, `modalRespuestas` sin `x-becas-modal`) va como V5A-NEW-07 parte (b), Ola 5 |

Encabezado, filtros, tabla, vacío, paginación, alerta, botones, avisos y campo son **componentes** (ficha propia), no
arquetipos.

---

## 4. Estructura del nuevo agente

**Anexos en `.claude/design/`**, no en una subcarpeta de `.claude/agents/` (el cargador de subagentes lee los `.md` de
`.claude/agents/` como definiciones; una ficha sin frontmatter ahí es ambigua). `.claude/` ya está excluido del release
(`.gitattributes`) y no es `docs/`, que CLAUDE.md declara no autoritativo.

```
.claude/agents/chaco-design-system.md          núcleo (≤ 30.000 B; celdas ≤ 450 caracteres)
.claude/design/arquetipos/listado.md
.claude/design/arquetipos/detalle.md
.claude/design/arquetipos/formulario.md
.claude/design/arquetipos/modal.md              incluye la confirmación con motivo
.claude/design/arquetipos/confirmacion.md       sí/no con data-confirm-url
.claude/design/componentes/page_header.md
.claude/design/componentes/filtros.md
.claude/design/componentes/tabla.md             incluye .nodo-icon-btn
.claude/design/componentes/estado_vacio.md
.claude/design/componentes/paginacion.md
.claude/design/componentes/alerta.md
.claude/design/componentes/stat_card.md
.claude/design/componentes/field.md             _field.html + nodo-field + nodo-checks
.claude/design/componentes/botones_badges.md
.claude/design/componentes/tabs.md
.claude/design/componentes/modal_partes.md      _modal_header/_footer, becas-modal.js, _ajax_js
.claude/design/componentes/modern_modal_toast.md
.claude/design/shells.md                        base, auth pública, portal, inscripción, main.html legacy
.claude/design/dominio/becas.md                 constructor, SIIS, identificadores, dashboard, mapa de estados
.claude/design/dominio/inscripcion.md           shell de inscripción y formulario público (paso 2)
```
Referencia desde el núcleo: al final de la celda, `Ficha: `.claude/design/…/x.md``. El checker valida que exista y lee
sus rutas de evidencia.

**Índice del núcleo** (tamaño objetivo):
1. **Autoridad y alcance** (≤ 10 líneas): precedencia actual sin cambios: código > agente > `docs/design-kb`.
2. **Cómo usar este archivo** (≤ 12 líneas): (A) ajuste → §4 + ficha del componente; (B) pantalla nueva → §3, ficha del
   arquetipo y las que cita; (C) pieza nueva o cambio de pieza canónica → §3 paso C y §12. «Para UI no hace falta leer
   `AGENTS.md`.»
3. **Protocolo de construcción** (texto de §6, literal; ~35 líneas).
4. **Reglas duras** (17 viñetas, cada una con su regla `[R:NOMBRE]` o `[revisión]`): extender `includes/base.html`, nunca
   `includes/main.html` [R:SHELLLEGACY]; encabezado solo con `{% page_header %}` [R:PAGEHEADER]; tabla solo con
   `nodo-thead-row`/`nodo-th`/`nodo-td` dentro de la card de lista [R:TABLECANON]; acción de fila solo con
   `.nodo-icon-btn` y `aria-label` que nombre el registro [revisión]; vacío, paginación, alerta y métrica solo con su
   include [revisión + marcadores]; botones `btn-nodo` + variante + tamaño [revisión]; labels canónicos o `_field.html`,
   controles `nodo-field` puestos desde el widget del form (`programas/forms.py:48 INPUT_CLASS`) [revisión]; íconos
   Font Awesome con `aria-hidden="true"` [R:ICONARIA]; sin `<style>` [R:STYLEBLOCK], sin `style=` salvo custom
   properties, valores `{{ }}` y `display:none` [R:INLINESTYLE], sin paleta cruda [R:RAWPALETTE], sin SVG inline en el
   contenido [revisión]; toda clase usada existe en el CSS cargable [R:CLASSDEF]; filtros solo con
   `data-dynamic-list-filters` [revisión + marcadores]; modal solo con la estructura del arquetipo Modal [marcadores];
   confirmación sí/no solo con `data-confirm-url` → `ModernModal`, nunca `data-confirm` a secas ni un Swal nuevo
   [revisión]; avisos con `window.toast` [existente]; datos, permisos y contadores preparados en la vista, listados con
   `paginate_by` [revisión]; la hermana del módulo nunca es molde [revisión]; novedad → Plan con Novedades → no escribir y
   devolver al llamador [revisión].
5. **Superficies y shells** (tabla de 5 filas: superficie · qué extender · bloque de contenido · bloque JS · notas).
   Backoffice: `includes/base.html`, `main-content`, `customJS`. Auth pública. Portal. Inscripción. `includes/main.html`:
   **legacy, no se extiende**. Detalle en `shells.md`.
6. **`## Arquetipos`**: tabla de 3 columnas con el formato del inventario (el checker la parsea), 5 filas + una de
   «Pendientes (wizard, revisión compleja, dashboard): frenar». Ej.: `Arquetipo · Listado | Canónico reutilizable |
   golden `…personas_list.html` — cuándo usarlo en una línea. Ficha: `.claude/design/arquetipos/listado.md``.
7. **`## Inventario operativo inicial`** (título que se mantiene para no romper el checker): ~26 filas ≤ 450 caracteres:
   componentes transversales (header, filtros, card, tabla, icon-btn, vacío, paginación, alerta, stat card, campo,
   botones, badges, tabs, modal, `ModernModal`, toast); partes de modal y confirmación de Becas **declaradas
   transversales**; shells; una fila por dominio (Becas, Inscripción); legacy y conflictivo: `main.html`,
   `alertas_eventos.html`, `widget_contactos.html`, SVG Heroicons en contenido, `dispositivos/config/_field.html`,
   handler inline de `data-confirm` con Swal, `mobile-enhancements.js` (mientras exista, FE-01), `paleta-unificada.css`,
   `nodo-brand.css`, `docs/design-kb`. **Sin** «Cambio NN», «Ola», fechas ni IDs.
8. **Vocabulario visual permitido** (≤ 25 líneas, lista blanca): color semántico (`bg-white`, `bg-secondary`,
   `bg-{tono}-soft`, `border-base`, `border-light`, `border-{tono}-subtle`, `text-heading`, `text-body`,
   `text-body-subtle`, `text-fg-{brand|danger|success|warning|info}`); tipografía por rol (página vía `page_header`;
   título de surface `h2 text-heading font-bold`; subtítulo `h3 text-sm font-bold text-heading`; texto `text-sm`;
   metadato `text-xs text-body-subtle`); espaciado (página `space-y-6` listado o `space-y-5` detalle/form; surface
   `p-5`/`p-6`; header de surface `px-5 py-4 border-b border-light`); arbitrarios permitidos `text-[17px]`,
   `max-w-[560px]`, `max-h-[90vh]`, `min-h-[100dvh]`; íconos Font Awesome en contenido, Heroicons solo en el shell (D3).
9. **Perfiles de dominio** (≤ 20 líneas): qué vocabulario **no** se traslada de Becas a Dispositivos y Merenderos
   (condensación de las L202-263 actuales).
10. **Estados transversales** (≤ 8 líneas): accesibilidad, responsive y dark mode (L188-200 actuales, sin cambios).
11. **Reconciliación obligatoria** (las 4 viñetas actuales).
12. **Sincronización y validación:** qué actualizar en el mismo PR (la fila **o** su ficha si cambia una pieza canónica o
    una golden); la historia va a `docs/internal/requerimientos.md`, nunca al agente.

**Se elimina sin mover:** L97-102, la fila duplicada L65 y las 39 referencias de historia (ya están en
`requerimientos.md`). **Se mueve a fichas, literal:** el detalle de contrato de las filas de más de 450 caracteres (no se
resume ninguna regla durante la reescritura: así no se pierden contratos que hoy protegen tests).

---

## 5. Fichas modelo

### 5.1 Arquetipo: `.claude/design/arquetipos/listado.md`

````markdown
# Arquetipo · Listado con filtros

**Golden:** `programas/templates/programas/becas/revision/personas_list.html`
(solo se clona esta; una pantalla hermana del módulo nunca es molde).
**Marcadores:** `design_audit.py --arquetipo listado <archivo>` (lista en `ARQUETIPOS["listado"]`).
**Componentes:** page_header · filtros · tabla · estado_vacio · paginacion · botones_badges.

## Cuándo
Colección de registros del mismo tipo que el usuario compara, filtra y abre. No es un
listado si el usuario carga datos en la grilla (eso es formulario) o si son menos de 5
filas fijas (secciones del detalle).

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)
```django
{% extends "includes/base.html" %}
{% load nodo_ui %}
{% block title %}<Módulo> · <Entidades>{% endblock %}

{% block main-content %}
<div class="space-y-6">

  {% page_header titulo="<Entidades>" bajada="<qué muestra la lista, una línea>" %}
    {% if puede_crear %}
      <a href="{% url '<app>:<entidad>_crear' %}" class="btn-nodo btn-brand btn-base">
        <i class="fas fa-plus" aria-hidden="true"></i> Nuevo <entidad>
      </a>
    {% endif %}
  {% endpage_header %}

  <form method="get" data-dynamic-list-filters>
    <input type="search" name="q" value="{{ request.GET.q }}" class="nodo-field" aria-label="Buscar">
    <select name="estado" class="nodo-field" aria-label="Estado">
      <option value="">Todos</option>
      {% for value, label in estados %}<option value="{{ value }}" {% if value == estado_actual %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select>
  </form>

  <div class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">
    {% if <objetos> %}
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="nodo-thead-row">
            <th class="nodo-th"><Columna principal></th>
            <th class="nodo-th"><Columna></th>
            <th class="nodo-th">Estado</th>
            <th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>
          </tr>
        </thead>
        <tbody>
          {% for obj in <objetos> %}
          <tr class="hover:bg-secondary">
            <td class="nodo-td text-heading font-medium">{{ obj.<nombre> }}
              <span class="block text-xs text-body-subtle"><metadato></span></td>
            <td class="nodo-td text-body">{{ obj.<campo> }}</td>
            <td class="nodo-td">{% include "programas/<modulo>/_estado_badge.html" with estado=obj.estado %}</td>
            <td class="nodo-td text-right">
              <a href="{% url '<app>:<entidad>_detalle' obj.pk %}?next={{ request.get_full_path|urlencode }}"
                 class="nodo-icon-btn" aria-label="Ver <entidad> {{ obj.<nombre> }}">
                <i class="fas fa-eye" aria-hidden="true"></i>
              </a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% include "components/_paginacion.html" with page_obj=page_obj entidad="<entidad>" %}
    {% elif request.GET|hay_filtros %}
      {% url '<app>:<lista>' as url_sin_filtros %}
      {% include "components/_estado_vacio.html" with con_filtros=True titulo="Ningún <entidad> coincide con los filtros" texto="Probá con otros filtros." accion_url=url_sin_filtros %}
    {% else %}
      {% include "components/_estado_vacio.html" with icono="<fa-…>" titulo="Todavía no hay <entidades>" texto="<qué hacer>" accion_url=url_crear accion_texto="Nuevo <entidad>" accion_icono="fa-plus" %}
    {% endif %}
  </div>
</div>
{% endblock %}
```
Vista: `ListView` (o función) con `paginate_by` (25 es el valor de Becas); en el contexto,
`<objetos>` = `page_obj.object_list`, `estados` (choices), `estado_actual`, `puede_crear`
(capacidad resuelta con `puede()`), `url_crear` y relaciones con `select_related`.

## Variantes permitidas
- Sin filtros: se omite el `<form>` entero (y el vacío con filtros).
- Sin acción de alta: el `page_header` sin cuerpo. Acción secundaria: `btn-nodo btn-tertiary btn-base`.
- Varias acciones por fila: varias `.nodo-icon-btn` en la misma celda; destructiva con
  `.nodo-icon-btn--danger` + `data-confirm-url` (arquetipo Confirmación).
- Columna con enlace a otra entidad: `<a class="text-fg-brand hover:underline">`.
- Columna centrada: `text-center` en el `th` **y** en el `td`.
- Filtro de fecha o checkbox: `<input type="date|checkbox" name=… aria-label=…>` dentro del mismo form.
- Listado dentro de una solapa: el bloque `overflow-x-auto` → paginación → vacío, sin
  `page_header` y dentro del `tabpanel` (ver arquetipo Detalle).

## Prohibido (lo que hoy se copia de las hermanas)
- Clases, wrapper de card, grilla o `style` en el form de filtros; botones «Filtrar»/«Limpiar»
  propios (el JS reescribe el form y los tira).
- `thead style=`, `th` con utilidades sueltas, `divide-y`, `hover:bg-tertiary`, cards por fila.
- «Ver detalle» como botón con texto en la fila; `aria-label` genérico («Ver»).
- Mapeo de estado a color dentro de la pantalla (va en el parcial `_estado_badge.html` del módulo).
- Paginación a mano (`page_obj.has_next`); vacío a mano (`py-14 px-6 text-center`).
- `<h1>`, `<style>`, `[x-cloak]` local, `style=`, paleta cruda, SVG inline, flecha «←» de texto.

## Checklist (la usa el revisor)
- [ ] `--arquetipo listado` OK y `--ratchet` con 0 nuevos.
- [ ] Molde declarado = golden; la hermana solo aportó textos, URLs y permisos.
- [ ] Acción primaria condicionada por una capacidad resuelta en la vista.
- [ ] Cada control de filtro tiene `name` + `aria-label` que se lee bien como chip («Estado», no «Estado:»).
- [ ] Una sola card envuelve tabla, paginación y vacío.
- [ ] Toda `.nodo-icon-btn` tiene un `aria-label` con el registro; los íconos tienen `aria-hidden`.
- [ ] Hay dos estados vacíos: con filtros (limpiar) y sin datos (crear).
- [ ] La vista pagina y resuelve relaciones sin N+1.
````

### 5.2 Componente: `.claude/design/componentes/page_header.md`
Contrato leído de `core/templatetags/nodo_ui.py` y `templates/components/_page_header.html`.

````markdown
# Componente · Encabezado de página (`{% page_header %}`)

**Clasificación:** Canónico reutilizable (todas las superficies del backoffice).
**Evidencia:** `core/templatetags/nodo_ui.py`, `templates/components/_page_header.html`,
`core/tests/test_page_header_tag.py`.
**Consumidores de referencia:** `becas/revision/personas_list.html` (listado),
`becas/config/segmento_form.html` (form con título calculado), `becas/cupo/segmento_detail.html`
(detalle con migas).

## Invocación
```django
{% load nodo_ui %}
{% page_header titulo=<str> bajada=<str> volver_url=<url> volver_label=<str> migas=<lista> %}
  {% bajada %}<HTML de plantilla>{% endbajada %}   {# opcional; hijo directo, uno solo #}
  <badges y acciones>
{% endpage_header %}
```
**Nunca** `{% include "components/_page_header.html" %}` a mano.

## Parámetros (solo con nombre; todos opcionales salvo `titulo`)
| Parámetro | Tipo | Efecto |
|---|---|---|
| `titulo` | str (**obligatorio**) | `<h1 class="text-3xl font-extrabold text-heading tracking-tight">`, escapado |
| `bajada` | str | `<p class="text-sm text-body-subtle mt-1">`, escapada. Para HTML usar el bloque `{% bajada %}`, que manda sobre el argumento |
| `volver_url` | url | Botón circular `btn-tertiary btn-back-circle` con `fa-arrow-left` (aria-hidden) |
| `volver_label` | str | `aria-label="Volver a {volver_label}"` (por defecto «la pantalla anterior»). Nombra la pantalla de **origen** |
| `migas` | lista de `{"label","url"}` | Se muestran solo con **3 o más** elementos; la última sin enlace (`aria-current="page"`). En Becas la arma `{% becas_migas obj [actual=…] as migas %}`; en otros módulos se arma en la vista |

Errores de compilación (`TemplateSyntaxError`): un argumento posicional, uno desconocido, falta
`titulo`, o más de un `{% bajada %}`. Un `{% bajada %}` dentro de un `{% if %}` **no** se
reconoce como bajada: se renderiza entre las acciones.

## Render
Contenedor `space-y-3` → migas (`nav aria-label="Migas"`) → fila
`flex items-start justify-between gap-4 flex-wrap`: a la izquierda volver + título + bajada
(`min-w-0`), a la derecha el cuerpo en `flex items-center gap-2 flex-wrap`.

## Acciones del cuerpo (regla observada en el código, D1)
- Listados y formularios: primaria `btn-nodo btn-brand btn-base` (+ ícono `fa-plus` en altas);
  secundaria `btn-nodo btn-tertiary btn-base`.
- Detalles: acciones `btn-nodo btn-secondary btn-sm`; badges de estado `badge … badge-dot` antes
  de las acciones.
- Lo que abre otra pantalla va acá, nunca como solapa.

## Patrones
- Título calculado: `{% with titulo_pagina=form.instance.pk|yesno:"Editar X,Nuevo X" %}{% page_header titulo=titulo_pagina … %}…{% endwith %}` (segmento_form).
- Volver al origen: la vista valida `?next=` (`url_has_allowed_host_and_scheme` + el prefijo de la
  sección) y pasa `volver_url`; el `next` viaja en los `action` y en los redirect.

## No usar / errores comunes
- `<h1>` a mano (`text-2xl font-bold text-gray-900`, `style="font-size:28px"`), eyebrow en
  mayúsculas, «← Volver» como link de texto, header dentro de una card.
- Migas de 2 niveles (no se muestran: alcanza con volver).
````

---

## 6. Protocolo de construcción y checklist del revisor

**Texto para pegar en `chaco-frontend.md`** (reemplaza «Flujo de implementación» L19-37, «Arquetipos de implementación»
L54-71 y la L94; el núcleo lo cita en §3):

> **Antes de escribir**
> 1. **Clasificá la tarea.** (A) ajuste en pantalla existente · (B) pantalla nueva · (C) pieza nueva o cambio de una
>    pieza canónica o golden.
> 2. **(A) Ajuste:** tocá solo el bloque pedido. Si ese bloque tiene una pieza canónica equivalente, usala en ese bloque y
>    en ningún otro. No migres el resto de la pantalla. Saltá al paso 9.
> 3. **(B) Elegí el arquetipo** de la tabla *Arquetipos* del agente canónico. Si no encaja o figura como pendiente
>    (wizard, revisión compleja, dashboard): **no escribas**, devolvé la tarea al llamador con el motivo.
> 4. **Abrí la golden completa** y su ficha, y las fichas de los componentes que la ficha cita.
> 5. **Mirá la hermana del módulo** con Grep o Glob (nunca `grep -r`, que entra a `.claude/worktrees/`). Tomá de ella
>    **solo dominio**: textos, nombres de URL, capacidades, variables de contexto y el parcial `_estado_badge.html` del
>    módulo. Nunca estructura, clases ni JS.
> 6. **Escribí el Plan de pantalla** en tu respuesta, antes del primer Write o Edit:
>    ```
>    Tipo: B · Arquetipo: Listado · Golden: …/becas/revision/personas_list.html
>    Hermana (solo dominio): …/merenderos/list.html
>    Bloques: header=page_header(+Nuevo) · filtros=q,estado · tabla=5 col, fila→Ver · vacío x2 · paginación entidad=entrega
>    Vista: paginate_by=25, puede_crear, estados, select_related(merendero)
>    Novedades: ninguna
>    ```
>    **Novedad** = clase CSS nueva, archivo CSS o JS nuevo, include o tag nuevo, parámetro nuevo de un componente, valor
>    arbitrario fuera de la lista blanca, `<style>`/`style=` no exento, ícono fuera de Font Awesome, o un arquetipo sin
>    ficha. Si «Novedades» no dice «ninguna»: **no escribas**. Devolvé el plan al llamador con la evidencia de que no hay
>    equivalente (búsquedas y rutas).
> 7. **(C) Pieza nueva, solo con OK:** va en `templates/components/` (o en el CSS o JS `nodo-*` que corresponda), con el
>    contrato en el comentario de cabecera, su test en `core/tests/test_nodo_ui_piezas.py`, su ficha y su fila en el
>    inventario, todo en el mismo PR.
>
> **Mientras escribís**
> 8. Copiá el esqueleto de la ficha **literal**. Cambiá solo textos, columnas, URLs, capacidades y variables. No
>    «mejores» la golden ni la hermana. Datos, permisos, contadores y paginación se preparan en la vista o el selector,
>    nunca en el template. Si el hook reporta un hallazgo, es tuyo (el ratchet solo informa lo nuevo): corregilo.
>
> **Después**
> 9. Validá:
>    ```powershell
>    & .\.venv\Scripts\python.exe scripts\design_audit.py --ratchet                # 0 nuevos
>    & .\.venv\Scripts\python.exe scripts\design_audit.py --arquetipo <a> <archivo> # (B) OK
>    & .\.venv312\Scripts\python.exe scripts\compile_templates.py                  # 0 (Django 5.2)
>    & .\.venv\Scripts\python.exe scripts\check_design_agent.py --changed
>    ```
>    Más los tests del módulo.
> 10. **Informe:** el Plan de pantalla (en B y C), la salida de las validaciones, «inventario y fichas: sin cambios» o qué
>     fila o ficha se tocó, y cualquier reconciliación.

**`chaco-design-reviewer.md`: checklist nuevo** (reemplaza el «Método» L14-42; frontmatter `tools: Read, Grep, Glob, Bash`,
**sin `Edit`**):
1. **Tipo y Plan.** Si es (B) o (C) y no hay Plan de pantalla → «Cambios requeridos», sin revisar más.
2. **Molde.** La golden declarada figura en la tabla *Arquetipos*. Si el molde fue una hermana → bloqueante.
3. **Mecánico:** `design_audit.py --ratchet --base <base>` 0 nuevos; `--arquetipo <a> <archivo>` OK; `compile_templates.py`
   con `.venv312` 0; `check_design_agent.py --changed` OK.
4. **Checklist de la ficha** del arquetipo, ítem por ítem, citando línea.
5. **Novedades.** Cada una con el OK del llamador registrado. Sin OK → bloqueante.
6. **Dominio.** No se trasladó vocabulario de Becas (convocatoria, segmento, cupo, beneficiario, SIIS) a un módulo que no
   lo tiene.
7. **Desarrollo front:** `paginate_by` o tope explícito; sin `|length` sobre querysets; relaciones resueltas (sin N+1);
   capacidades con `puede()` en la vista; POST + CSRF en las acciones que mutan; confirmación canónica.
8. **Accesibilidad:** `aria-label` con el registro en botones de ícono; `aria-hidden` en íconos; solapas con
   `tablist`/`tab`/`aria-controls`/`tabpanel`; modal con `role="dialog"`, `aria-modal` y `aria-labelledby`.
9. **Visual** (en B, si hay harness): captura de la golden y de la nueva a 1440 y 390 px con la receta Playwright + SQLite;
   las diferencias que no son de dominio son hallazgos.
10. **Inventario.** Si se tocó una golden o una pieza canónica, se actualizó su ficha o su fila.

Secciones que se agregan al informe del revisor: `### Molde y marcadores` · `### Novedades (aprobadas / no aprobadas)` ·
`### Capturas` (o «no aplica»).

---

## 7. Reglas de `scripts/design_audit.py`

**Infraestructura (mismo PR que las reglas):**
- **`--ratchet [--base REF]`** (default `HEAD`): para cada archivo de UI cambiado (`git diff --name-only REF...HEAD` + el
  working tree), cuenta hallazgos por regla en `git show REF:<archivo>` (0 si es nuevo) y en el actual; sale con 1 si sube
  el conteo de alguna regla ERROR; reporta solo las líneas nuevas.
- **`--hook`** usa el ratchet contra `HEAD` sobre el archivo editado; se borra el texto «si son preexistentes… seguí».
- **`--goldens`**: lee la tabla `## Arquetipos` del agente; exige 0 hallazgos P1 en cada golden y sus marcadores
  completos (en `programa_list.html`, los 4 `style=` de hoy —L38, 70, 72, 75— y el `<style>` L6 están en el modal o la
  cabecera: tras el saneamiento el archivo entero queda en 0).
- **`--arquetipo {listado,detalle,formulario,modal} ARCHIVO`**: verifica que cada marcador de `ARQUETIPOS[a]` aparezca en
  orden (regex por línea, con marcadores opcionales) y que no aparezca ninguno de los prohibidos (~60 líneas).
- **Arreglo del decodificador (FE-13):** parser de identificadores CSS (`\` + 1-6 hex consume un espacio opcional; `\` +
  otro carácter es literal), base `poc/herramientas/cssclasses.py`. Elimina los 2 falsos positivos de TWBUILD.
- **Tests** en `core/tests/test_design_audit_estructura.py` (corre en Backend CI como `test_design_audit_confirm.py`): un
  positivo y un negativo por regla, `nuevos(base, actual)` del ratchet, un caso de marcadores por arquetipo y el
  decodificador con `\2c `, `.xl\:top-6`, `.w-1\/2`.
- **CI** (`design-agent-contract.yml`): `python scripts/design_audit.py --ratchet --base "${{ github.event.pull_request.base.sha }}"`
  y `python scripts/design_audit.py --goldens`; sumar `scripts/design_audit.py` y `.claude/design/**` a `paths`. Además el
  **gate de build** (V5A-NEW-01): `npm ci && npm run build:tailwind && git diff --exit-code static/custom/css/tailwind.css`.
  El script sigue siendo solo stdlib.

**Reglas P1** (ERROR cuando el conteo sube; alcance `.html`; excluyen `**/email/**`, `vendor/` y líneas con la pragma
`design-audit: allow`). La línea base es informativa (el ratchet no la necesita):

| Regla | Heurística | Alcance | Línea base (01-oct) |
|---|---|---|---|
| `RAWPALETTE` | Dentro de `class="…"`: `(?<![\w-])(?:[a-z0-9-]+:)*(?:bg\|text\|border\|ring\|divide\|from\|via\|to\|placeholder)-(?:gray\|slate\|zinc\|neutral\|stone\|red\|orange\|amber\|yellow\|lime\|green\|emerald\|teal\|cyan\|sky\|blue\|indigo\|violet\|purple\|fuchsia\|pink\|rose)-\d{2,3}(?:/\d+)?\b` | Todas | 963 usos · 38 archivos (0 en Becas, Dispositivos y Merenderos) |
| `INLINESTYLE` | `\sstyle="…"` que, quitando `{{…}}`, `{%…%}`, `--prop: …;` y `display:none`, todavía tiene declaraciones | Todas | 2.037 · 108 archivos (portal 504, legajos 423, configuración 420) |
| `STYLEBLOCK` | `<style\b` (incluye `[x-cloak]` local) fuera de los shells `includes/base.html`, `portal/base.html`, `inscripcion/base_inscripcion.html`, `user/base_public_auth.html` | Todas | 39 archivos (16 solo por `[x-cloak]`) |
| `SHELLLEGACY` | `{%\s*extends\s+["']includes/main\.html["']` | Todas | 17 |
| `PAGEHEADER` | `extends "includes/base.html"` **y** `<h1` **y** no hay `{% page_header` | Backoffice | 56 |
| `TABLECANON` | `<th\b(?![^>]*\bnodo-th\b)` o `<thead[^>]*style=` | Todo menos `portal/` | 164 · 25 archivos |
| `ICONARIA` | `<i\s+class="fa[srb]?\s[^"]*"(?![^>]*aria-hidden)` (y `fa-solid\|regular\|brands`) | Todas | 437 · 61 archivos |
| **`CLASSDEF`** (V5a, FE-13) | Token de clase usado que no está en el universo declarado = `tailwind.css` ∪ `static/custom/css/*.css` ∪ `static/vendor/fontawesome/**/*.css` ∪ `static/vendor/sweetalert2/**/*.css` ∪ el `<style>` del propio template ∪ los CSS que el template enlaza con `{% static '….css' %}` (p. ej. `core/performance_dashboard.html` carga bootstrap y adminlte). Tokens: `class="…"` (descartando el token que contiene `{{ }}` y conservando ramas de `{% %}`); en `:class`/`x-bind:class` solo claves de objeto `'x':` y resultados de ternario `? 'a' : 'b'`; `classList.add\|remove\|toggle\|replace('…')` y `className = '…'` en templates y `static/custom/js/*.js`. **ERROR** si el token tiene forma de utilidad Tailwind (raíz `bg\|text\|border\|divide\|ring\|m[trblxy]?\|p[trblxy]?\|w\|h\|min-\|max-\|gap\|space-\|inset\|top\|right\|bottom\|left\|z\|grid-\|col-\|row-\|flex\|items\|justify\|rounded\|shadow\|opacity\|font\|leading\|tracking\|overflow\|translate\|scale\|animate\|from\|via\|to…`, con variantes y `/NN`): «no existe en el build: utilidad inválida con esta config o CSS sin regenerar»; **WARN** para el resto («clase sin CSS: Bootstrap/AdminLTE heredado o hook sin prefijo `js-`»). Allowlist de hooks en `scripts/design_audit_hooks.txt`: `js-*`, `dj-message`, `g-recaptcha`, `tab-content`, `*-grip`, `sortable-placeholder`, `cap-*`, `contador-modulo`, `tab-select-all-btn`, `roles-panel`, `cons-grupo`, `revealed`, `fade`, `show`, `selected`, `disabled`, `was-validated` | Templates y JS | 120 tokens no declarados sobre 1.361 usados (lista en `anexo-front-clases-inexistentes.md`) |

**Fase 2** (solo WARN y solo si el ejercicio de control muestra un desvío que las P1 no atrapan): `LABELCANON` (195),
`TWARBITRARY` (195), `ICONSVG` (228 · 37 archivos), `EMPTYHAND` (8), `PAGEHAND` (6), `CONFIRMHAND` (`Swal.fire(`, 27 · 18
archivos), `BTNBOOT` (3), `MODALCANON` (a medir), `TABSA11Y` (4). **Descartadas:** FIELDCANON (los controles salen del
widget de Django), ONHANDLER (no es de diseño), ALERTHAND (no hay pieza para alertas con HTML).

**`check_design_agent.py` (mismo PR que la reescritura del agente):**
1. Partir celdas por `|` sin escapar: `re.split(r"(?<!\\)\|", …)` (N1).
2. Parsear `## Arquetipos` y `## Inventario operativo inicial`.
3. `FICHA_RE = r"Ficha: `(\.claude/design/[^`]+\.md)`"`: la ficha debe existir, sus rutas cuentan como evidencia de la
   fila, no puede haber fichas huérfanas en `.claude/design/**`, y las fichas se suman a `AUTHORITY_FILES`.
4. `EVIDENCE_PREFIXES` += `core/`, `legajos/`, `configuracion/`, `dashboard/`, `conversaciones/`.
5. Regla del mismo diff: la disparan las rutas canónicas salvo `static/custom/css/tailwind.css`, `/tests/` y `/views/`; se
   satisface con un cambio en el núcleo **o** en la ficha de la fila; se mantiene
   `test_programas_templates_can_be_canonical_evidence`.
6. Límites del núcleo: ≤ 30.000 bytes; celdas ≤ 450 caracteres; 0 coincidencias de
   `Cambio \d+|Ola \d+|\b(?:POP|TIT|CMP|ALR|DE|DP)-[A-Z]?\d+|\bW\d-|\d{1,2}-(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-20\d\d`
   (solo en el núcleo).
7. `--hook` también se dispara al editar `.claude/design/**`.
8. Tests en `scripts/test_check_design_agent.py`: pipe escapado, evidencia en la ficha, límite de tamaño, historia
   prohibida y exclusión de `tailwind.css`.

Hook con el `python` global: se deja (stdlib); se documenta en la cabecera de los dos scripts «solo stdlib: el hook y el
CI los corren sin venv». `compile_templates.py` sí necesita Django 5.2: `.venv312` (con `.venv` da 1 falso por
`{% querystring %}`), y excluir `site-packages` (V5A-NEW-08).

---

## 8. Cambios exactos en CLAUDE.md, AGENTS.md y agentes consumidores

**CLAUDE.md, línea 79** (Comandos → Auditorías obligatorias):
```diff
-& $env:PY_VENV scripts\design_audit.py --changed      # adherencia al sistema de diseño → 0 errores
-& $env:PY_VENV scripts\compile_templates.py           # sintaxis de TODOS los templates → 0
+& $env:PY_VENV scripts\design_audit.py --ratchet      # adherencia al sistema de diseño → 0 hallazgos NUEVOS
+& $env:PY_VENV scripts\design_audit.py --arquetipo <listado|detalle|formulario|modal> <archivo>  # pantalla nueva
+& .\.venv312\Scripts\python.exe scripts\compile_templates.py  # sintaxis de TODOS los templates → 0 (con .venv da 1 falso por {% querystring %})
```
Y en el párrafo siguiente:
```diff
-sobre `Edit|Write` (ver `.claude/settings.json`), así que un edit de UI que viole
-una regla se avisa en el momento.
+sobre `Edit|Write` (ver `.claude/settings.json`). El hook compara contra `HEAD` y avisa
+solo lo que agregó la edición; la deuda previa del archivo no se reporta.
```

**CLAUDE.md, sección «Diseño / UI»:**
```diff
-Para cualquier trabajo de UI, leé `AGENTS.md` y usá los agentes de
-`.claude/agents/`:
+Para cualquier trabajo de UI usá los agentes de `.claude/agents/` (de `AGENTS.md`
+no hace falta leer nada para UI):
@@
-- **`.claude/agents/chaco-design-system.md`** — fuente operativa única de diseño e
-  inventario. Se contrasta contra el código antes de cada cambio.
+- **`.claude/agents/chaco-design-system.md`** — fuente operativa única de diseño e
+  inventario (núcleo corto; fichas de arquetipos y componentes en `.claude/design/`).
+  Se contrasta contra el código antes de cada cambio.
@@
+**Pantalla nueva = clonar la golden de su arquetipo.** La tabla *Arquetipos* del agente
+canónico nombra una sola pantalla de referencia por arquetipo; se copia su esqueleto (ficha
+en `.claude/design/arquetipos/`) y se cambia solo el dominio. Una pantalla hermana del
+mismo módulo **nunca** es molde. Antes de escribir se declara el *Plan de pantalla*; si
+trae novedades (clase, include, variante o valor nuevo) no se escribe y se devuelve al
+llamador.
+
 **Auditoría mecánica compartida:** `scripts/design_audit.py` es la fuente única de los
-chequeos de adherencia (hex, fuentes legacy, `confirm()`, gradientes legacy, etc.).
-Tras tocar UI: **0 errores es condición de cierre** (los WARN se evalúan con criterio),
+chequeos de adherencia (hex, fuentes legacy, `confirm()`, paleta cruda, `style=`,
+`<style>`, encabezado, tabla, íconos, clases inexistentes…). Funciona como *ratchet*: la
+corrida completa tiene deuda preexistente, pero **0 hallazgos nuevos respecto de la base es
+condición de cierre** (hook local y CI). Las goldens se mantienen en 0 (`--goldens`, en CI),
 y `scripts/compile_templates.py` también en 0 (caza tags rotos que `manage.py check`
 no ve). Los comandos están arriba, en *Comandos → Auditorías*.

-Si cambiás una pieza de UI clasificada como **canónica** en el inventario, el mismo
-diff tiene que actualizar `.claude/agents/chaco-design-system.md`, o
-`check_design_agent.py` falla (en el hook y en el CI).
+Si cambiás una pieza de UI clasificada como **canónica** o una golden, el mismo diff
+tiene que actualizar su fila en `.claude/agents/chaco-design-system.md` o su ficha en
+`.claude/design/`, o `check_design_agent.py` falla (hook y CI). La historia de los
+cambios va a `docs/internal/requerimientos.md`, nunca al agente.
```

**CLAUDE.md, «Gates de CI»:**
```diff
-- **Design Agent Contract** — solo si el PR toca UI, agentes o los `.md` de contrato.
+- **Design Agent Contract** — solo si el PR toca UI, agentes o los `.md` de contrato:
+  contrato del agente, `design_audit.py --ratchet` (0 nuevos), `--goldens` y build de
+  Tailwind sin diff.
```

**AGENTS.md, L18-20:**
```diff
-mantenimiento` o `Duplicado o conflictivo`. La UI nueva solo puede reutilizar una
-pieza canónica. Si no existe, demostrarlo, crear el patrón reutilizable mínimo y
-actualizar el inventario del agente en el mismo PR.
+mantenimiento` o `Duplicado o conflictivo`. La UI nueva solo puede reutilizar una
+pieza canónica y se construye clonando la golden de su arquetipo. Si falta una pieza,
+se propone como novedad y se frena hasta tener OK (protocolo del agente canónico).
```

**`chaco-frontend.md`:** L10-17: sacar «leé `AGENTS.md` y»; «Becas es la referencia de calidad visual…» → «El molde visual
es la golden del arquetipo; del módulo destino solo se toma dominio». L19-37 y L54-71 → el protocolo de §6. L94 →
borrar. L97-110 → pasos 9-10 de §6.

**`chaco-design-reviewer.md`:** frontmatter `tools: Read, Grep, Glob, Bash`; método de §6; el informe suma 3 secciones; L10
→ sin `AGENTS.md`.

**`chaco-dev-reviewer.md`:** sin cambios (ya delega en el agente canónico y ahora carga un núcleo más corto).

**Memoria del proyecto** «Migración Design System»: «0 errores» → «ratchet + goldens».

---

## 9. Plan de implementación (Ola 6)

**Decisiones del PM antes del paso 3** (se registran en la entrada de `requerimientos.md` del paso 7):

| # | Decisión | Recomendación |
|---|---|---|
| D1 | Tamaño de las acciones del header | Documentar lo que hace el código: `btn-base` en listados y formularios, `btn-sm` en detalles |
| D2 | Confirmación con motivo en pantallas nuevas | Arquetipo Modal con form POST; Swal queda legacy condicionado para las pantallas actuales de Dispositivos y Legajos |
| D3 | Íconos | Font Awesome en el contenido; Heroicons solo en el shell (sidebar y navbar) |
| D4 | Wizard de backoffice | Frenar y preguntar; no se define ahora |
| D5 | Avatar con gradiente en filas de tabla (golden de detalle) | Reemplazarlo por iniciales en `bg-brand-soft text-fg-brand`: respeta «un solo acento por bloque» y saca 3 `style=` |

| Paso | Qué | Esf. | Hecho cuando (verificable) |
|---|---|---|---|
| **0. Línea base «antes»** | En un worktree descartable sobre `origin/development`, correr los 3 prompts del paso 6 con los agentes **actuales**; guardar templates, transcripts y P1 medidas con el script de medición `poc/herramientas/design_baseline.py` (no es el `design_baseline.json` descartado: no deja archivo de baseline). Nada se commitea | S | 3 carpetas `antes/<pantalla>/` con template, salida del script y nota (¿hubo plan?, ¿qué molde?). **Guardarlas fuera del scratchpad temporal** (p. ej. adjuntas a la issue de la ola) |
| **1. Decisiones D1-D5** | Pedirlas en texto (preguntas numeradas) | S | Quedan en *Decisiones tomadas* de la entrada del paso 7 |
| **2. Herramientas** | `design_audit.py`: `--ratchet`, 7 reglas P1 + CLASSDEF, `--arquetipo`, `--goldens` (inicialmente tolerante), decodificador (FE-13) y tests; `check_design_agent.py`: los 8 puntos de §7 y sus tests; `compile_templates.py` sin `site-packages` (V5A-NEW-08); rebuild de Tailwind (V5A-NEW-01); CI en `design-agent-contract.yml` con `--goldens` como `continue-on-error` hasta el paso 3 y el gate de build | M | Tests nuevos verdes con `.venv312`; un PR de prueba que agrega `text-gray-900` a un template existente **falla** en «Design Agent Contract», y uno con un template nuevo con `page_header` y tabla canónica **pasa**; `check_design_agent.py` reporta 36 filas (antes 33); `compile_templates.py` compila 199 templates en el checkout |
| **3. Sanear las goldens** | `personas_list` (form de filtros, `sr-only` en acciones); `cupo/segmento_detail` (`<style>` y D5); modal de `programa_list` (labels, help text, `data-error="__all__"`, nota → `_alerta` info, blur a clase, `<style>`); `segmento_form` sin cambios; sacar el `continue-on-error` de `--goldens` | S-M | `design_audit.py --goldens` = 0 P1 y marcadores OK; `compile_templates.py` (`.venv312`) = 0; `manage.py test programas.tests.test_becas_modal core.tests.test_nodo_ui_piezas` y los tests de Becas que rendericen esas pantallas en verde; capturas antes/después a 1440 y 390 px sin diferencias visibles (salvo D5) |
| **4. Reescribir el agente** | Núcleo según §4; fichas con los contratos largos movidos **literal**; fichas de arquetipo (§5.1) y componente (§5.2); borrar L97-102, L65 y la historia; resolver contradicciones (a), (d), (e), (g), la (b) según D5 y la (f) según D2; filas nuevas: filtros, `_field`, `main.html`, `alertas_eventos`, `widget_contactos`, `mobile-enhancements.js`, `dispositivos/config/_field.html`, handler Swal inline | M | `check_design_agent.py` OK con los límites nuevos; `wc -c` del núcleo ≤ 30.000; grep de historia en el núcleo = 0; cada contrato de una fila vieja se encuentra con grep en el núcleo o en una ficha (script que extrae los términos entre `` ` `` de la versión anterior) |
| **5. Consumidores** | Cambios de §8 en CLAUDE.md, AGENTS.md, `chaco-frontend.md` y `chaco-design-reviewer.md` | S | `check_design_agent.py` OK; `grep -c "nodo-th\|btn-nodo" .claude/agents/chaco-frontend.md` = 0; `requerimientos.py --check` OK |
| **6. Ejercicio de control «después»** | En un worktree descartable, `chaco-frontend` recibe prompts **de dominio, sin pistas de diseño**: (1) «Merenderos: listado de entregas de mercadería con filtro por estado y fecha»; (2) «Dispositivos: detalle de una cama con solapas Datos, Movimientos y Partes»; (3) «Merenderos: alta de tipo de prestación». Después corre `chaco-design-reviewer` independiente | M | Las 3 cumplen **al primer intento**: (a) Plan antes del primer Write con la golden correcta; (b) `--ratchet` = 0 nuevos; (c) `--arquetipo` OK; (d) el revisor aprueba; (e) captura lado a lado con la golden (1440 y 390 px) que el PM acepta como «mismo sistema». Tabla comparativa con el paso 0 (plan sí/no, molde, P1, marcadores faltantes). Si una falla, se corrige la **ficha o la regla**, no la pantalla, y se repite; si falla 2 veces por un desvío que ninguna P1 atrapa, se activa la regla de fase 2 que corresponda |
| **7. Registro** | Entrada nueva en `docs/internal/requerimientos.md` con `#ui` y `#metodo` (D1-D5, qué se recortó y por qué, resultado del control) + fila en el índice; actualizar la memoria «Migración Design System» | S | `requerimientos.py --check` OK |
| **Fuera de este esfuerzo** | Migrar hermanas (Ola 5, que el ratchet vuelve incremental); mover parciales de Becas a `components/`; `x-nodo-modal`; `ModernModal` con `input`; `_tab.html`; `{% alerta %}`; reglas de fase 2 | — | — |

**Orden mínimo si hay poco tiempo:** 1 → 2 (solo `--ratchet` con RAWPALETTE, STYLEBLOCK, PAGEHEADER, TABLECANON e
ICONARIA, más el arreglo del `\|`) → 3 (listado y formulario) → 4 (núcleo, protocolo y fichas de listado, formulario y
page_header) → 6 (solo pantallas 1 y 3). **Tiene que estar hecho antes de la primera task de pantalla de la v2 de
Dispositivos y Merenderos.**
