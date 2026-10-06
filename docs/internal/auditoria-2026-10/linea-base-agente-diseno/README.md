# Ejercicio de control del agente de diseño (Ola 6, pasos 0 y 6)

Las dos mitades del único criterio objetivo para decir si la Ola 6 sirvió: las **mismas tres pantallas**, pedidas con
los **mismos prompts de dominio sin ninguna pista de diseño**, primero a los agentes de antes (`antes/`, paso 0) y
después a los agentes reescritos (`despues/`, paso 6). El método está en `anexo-agente-diseno.md` §9.

**Resultado:** las tres fallaban antes, las tres cumplen después. El resumen comparativo está más abajo, en
*[Antes y después](#antes-y-después)*.

---

## Mitad «antes» (paso 0)

- **Cuándo:** 05-oct-2026, sobre `origin/development @ 88a19c1e`.
- **Con qué:** los agentes **actuales** (`chaco-frontend` sin tocar, núcleo de 66.965 B), uno por pantalla, en paralelo.
- **Prompts:** los tres del paso 6, **de dominio y sin ninguna pista de diseño** (ni arquetipo, ni golden, ni canon):
  1. «Merenderos: listado de entregas de mercadería con filtro por estado y fecha»
  2. «Dispositivos: detalle de una cama con solapas Datos, Movimientos y Partes»
  3. «Merenderos: alta de tipo de prestación»
- **Única restricción agregada:** escribir el template en un archivo nuevo fuera del árbol de la app y no tocar nada
  existente, para que la corrida no ensucie el repo. No se dio ninguna indicación de estilo ni de estructura.

## Qué hay en esta carpeta

| Ruta | Qué es |
|---|---|
| `antes/<n>-<pantalla>/<template>.html` | El template tal como lo entregó el agente **de antes**, literal |
| `antes/<n>-<pantalla>/design_audit.txt` | `scripts/design_audit.py <template>` — hallazgos P1. **Medido con el template fuera de `docs/`** (ver el aviso de abajo) |
| `antes/<n>-<pantalla>/arquetipo.txt` | `scripts/design_audit.py --arquetipo <a> <template>` — marcadores |
| `despues/<n>-<pantalla>/<template>.html` | El template tal como lo entregó el agente **reescrito**, literal |
| `despues/<n>-<pantalla>/plan.txt` | El *Plan de pantalla* que declaró el agente antes del primer `Write` |
| `despues/<n>-<pantalla>/design_audit.txt` y `arquetipo.txt` | Las mismas dos mediciones que en `antes/` |
| `despues/<n>-<pantalla>/revision.md` | Dictamen de `chaco-design-reviewer`, en sesión independiente |
| `despues/ratchet.txt` | `design_audit.py --ratchet` sobre las tres juntas |
| `repo-completo.txt` | La corrida completa del repo: la deuda que el ratchet congela |

Los `.html` de acá **no son templates de la app**: no están en ningún directorio de templates, no los ve
`compile_templates.py` y `design_audit.py` excluye `docs/` entero, así que no cuentan como deuda del repo.

> ⚠️ **Esa misma exclusión vuelve inservible medirlos donde están.** `design_audit.py <archivo>` y `--ratchet`
> apuntados a una ruta de `docs/` auditan **cero archivos** y aun así imprimen `0 error(es), 0 P1, 0 warning(s)` con
> exit 0: un verde falso. Para medir hay que copiarlos fuera de `docs/` primero — receta exacta en
> *[Cómo repetir esto](#cómo-repetir-esto)*, paso 3. `--arquetipo` es la excepción: lee el archivo donde esté.

Las
pantallas del ejercicio **no se mergean como producto**: son evidencia, no features. Sus vistas, URLs y modelos nunca
se escribieron (los agentes solo los describieron en el informe), y en los tres casos falta backend real para que
anden: el parcial de badge de Merenderos, la URL `merenderos:entregas`, la ruta `dispositivos:cama_detalle` y el
modelo `TipoPrestacion` con su capacidad RBAC.

## Resultado de la mitad «antes»

| # | Pantalla | ¿Plan de pantalla antes de escribir? | Molde declarado | ¿Es la golden del arquetipo? | P1 | Marcadores del arquetipo |
|---|---|---|---|---|---:|---|
| 1 | Listado de entregas (Merenderos) | **No** (razonamiento implícito, sin plan escrito) | `becas/revision/formulario_list.html` + `merenderos/list.html` para dominio | **No** (la golden es `becas/revision/personas_list.html`) | 0 | OK |
| 2 | Detalle de cama (Dispositivos) | Sí, informal (en la respuesta, no como artefacto) | `dispositivos/legajo/detail.html` — **la hermana del módulo** | **No** (la golden es `becas/cupo/segmento_detail.html`) | **10** | **8 desvíos** |
| 3 | Alta de tipo de prestación (Merenderos) | Sí, informal | `becas/config/pregunta_form.html` | **No** (la golden es `becas/config/segmento_form.html`) | 0 | **1 desvío** |

**Las tres fallan el criterio del paso 6, y cada una por un motivo distinto.** Ninguna usó la golden de su arquetipo y
ninguna escribió un Plan de pantalla como artefacto revisable.

1. **Listado.** Mecánicamente impecable y estructuralmente correcta: el molde fue otra pantalla limpia de Becas, así que
   salió bien. Es el caso que muestra que hoy **el resultado depende de qué hermana le toque mirar al agente**, no de una
   regla. El agente dijo además que leyó el inventario del núcleo entero («páginas 1-104»): ~18k tokens para una pantalla.
2. **Detalle.** El caso que la Ola 6 existe para evitar. El agente eligió como molde **la pantalla hermana del módulo**
   (`dispositivos/legajo/detail.html`) porque es «el único detalle con tabs que ya vive en Dispositivos», y heredó su
   deuda entera: `<h1>` a mano en vez de `{% page_header %}`, `<style>[x-cloak]` local, «← Volver» como link de texto,
   3 `style=` y 5 íconos sin `aria-hidden`; y las solapas quedaron sin `aria-controls` ni `role="tabpanel"`. Es
   exactamente el antecedente del Cambio 36 («`design_audit` daba 0/0 en Dispositivos y el módulo era todo lo
   contrario») repitiéndose con el sistema actual.
3. **Formulario.** El agente copió el markup de `becas/_field.html` **a mano, en línea**, en vez de incluirlo, y lo
   justificó: «para no acoplar el template de Merenderos a una ruta de Becas». Es una decisión razonable con la
   información que tiene el agente hoy —el inventario no declara ese parcial como transversal— y es la que multiplica
   los dialectos de campo. La ficha de arquetipo lo cierra declarándolo transversal (§2.2 del anexo).

**Lo que el `design_audit` no atrapaba.** Las pantallas 1 y 3 dan **0 P1** y aun así ninguna clona su golden: la 3
reimplementa un componente canónico y la 1 dependió de la suerte del molde. Es la confirmación de que el gate de token
no alcanza, que es la premisa de todo el anexo: hacen falta **marcadores de arquetipo** además de reglas de token.

## Deuda del repo que el ratchet congela

Corrida completa de `scripts/design_audit.py` sobre `88a19c1e` (detalle en `repo-completo.txt`):

| Severidad | Total |
|---|---:|
| ERROR (reglas de token/lint) | **42** |
| P1 (las 8 reglas estructurales) | **3.627** |
| WARN | 110 |

| Regla P1 | Hallazgos | Archivos |
|---|---:|---:|
| `INLINESTYLE` | 1.942 | 105 |
| `RAWPALETTE` | 949 | 36 |
| `ICONARIA` | 398 | 60 |
| `TABLECANON` | 156 | 24 |
| `CLASSDEF` | 70 | 63 |
| `PAGEHEADER` | 56 | 56 |
| `STYLEBLOCK` | 39 | 39 |
| `SHELLLEGACY` | 17 | 17 |

Los números del anexo (`§7`, medidos sobre `917e583`) son los mismos salvo lo que bajó con los PRs de la Ola R:
RAWPALETTE 963 → 949, INLINESTYLE 2.037 → 1.942, TABLECANON 164 → 156, ICONARIA 437 → 398; STYLEBLOCK, SHELLLEGACY y
PAGEHEADER no se movieron. **Desde acá la deuda solo puede bajar:** el ratchet corta cualquier PR que suba el conteo de
una regla en un archivo.

---

## Mitad «después» (paso 6)

- **Cuándo:** 06-oct-2026, sobre `origin/development @ c09d078e` (Ola 6 pasos 0 a 5 ya aplicados: #574, #577, #579).
- **Con qué:** los agentes **reescritos** (`chaco-frontend` con el protocolo nuevo, núcleo de 25.819 B en el checkout
  —25.548 normalizado a LF, que es lo que mide el checker— y 21 fichas en `.claude/design/`), uno por pantalla, en
  paralelo. Después, `chaco-design-reviewer` en **tres sesiones independientes**, una por pantalla, que no vieron la
  sesión que escribió el template.
- **Prompts:** los mismos tres, literales, de dominio y sin ninguna pista de diseño (ni arquetipo, ni golden, ni canon).
- **Única restricción agregada:** la misma de la mitad «antes» — escribir el template en un archivo nuevo fuera del
  árbol de la app y no tocar nada existente.

### Resultado

| # | Pantalla | ¿Plan de pantalla antes de escribir? | Molde declarado | ¿Es la golden del arquetipo? | P1 | Marcadores | Revisor |
|---|---|---|---|---|---:|---|---|
| 1 | Listado de entregas (Merenderos) | **Sí**, como artefacto, antes del primer `Write` | `becas/revision/personas_list.html` | **Sí** | 0 | OK | Aprobado |
| 2 | Detalle de cama (Dispositivos) | **Sí**, como artefacto, antes del primer `Write` | `becas/cupo/segmento_detail.html` | **Sí** | 0 | OK | Aprobado (1 hallazgo menor) |
| 3 | Alta de tipo de prestación (Merenderos) | **Sí**, como artefacto, antes del primer `Write` | `becas/config/segmento_form.html` | **Sí** | 0 | OK | Aprobado |

`design_audit.py --ratchet` sobre las tres juntas: **0 hallazgos nuevos en 3 archivos**.
`check_design_agent.py --changed`: OK. Los tres templates compilan con el motor de Django 5.2 (`.venv312`), y
`compile_templates.py` sigue en 199 / 0 errores.

### Antes y después

| Criterio del paso 6 | Antes (05-oct) | Después (06-oct) |
|---|---|---|
| Plan de pantalla como artefacto, antes del primer `Write` | 0 de 3 (una sin plan, dos con razonamiento informal en la respuesta) | **3 de 3** |
| Molde = la golden de su arquetipo | **0 de 3** | **3 de 3** |
| P1 (`design_audit`) | 0 · **10** · 0 | **0 · 0 · 0** |
| Marcadores de arquetipo | OK · **8 desvíos** · **1 desvío** | **OK · OK · OK** |
| `--ratchet` | — (no existía el ratchet al medir) | **0 nuevos en 3 archivos** |
| Revisor independiente | no se corrió (nada que aprobar: 2 de 3 ya fallaban el gate mecánico) | **3 de 3 aprobadas** |
| Molde fue la hermana del módulo | **sí, en la pantalla 2** (heredó su deuda entera) | **no, en ninguna** |
| Componente canónico reimplementado a mano | **sí, en la pantalla 3** (`_field.html` copiado en línea) | **no, en ninguna** |
| Núcleo leído por invocación | 66.965 B (el agente dijo haber leído «páginas 1-104») | 25.819 B + las fichas que cita el arquetipo |

**Las tres cumplen al primer intento.** No hubo que corregir ninguna ficha ni activar ninguna regla de fase 2: el
anexo preveía que, si una pantalla fallaba, se arreglara la ficha o la regla y se repitiera el ejercicio. No hizo falta.

### Qué cerró cada pieza de la Ola 6

Las tres fallas de la línea base tenían causa distinta, y cada una la cerró una pieza distinta:

1. **Listado (antes: mecánicamente impecable, pero por suerte del molde).** El agente de antes acertó porque le tocó
   mirar una hermana limpia de Becas. Ahora el molde no depende de la suerte: está nombrado en la tabla `## Arquetipos`
   y el Plan lo declara por escrito. Mismo resultado mecánico, por una regla en vez de por azar.
2. **Detalle (antes: 10 P1 y 8 marcadores faltantes).** Es el caso que la Ola 6 existía para evitar. El agente de antes
   clonó `dispositivos/legajo/detail.html` —la hermana— «porque es el único detalle con tabs que ya vive en
   Dispositivos» y heredó `<h1>` a mano, `<style>[x-cloak]`, «← Volver» de texto, 3 `style=`, 5 íconos sin
   `aria-hidden` y solapas sin ARIA. El agente reescrito clonó la golden: **0 P1**, y el revisor verificó uno por uno
   que **ninguno** de esos defectos de la hermana aparece. Lo cerró la regla «la hermana nunca es molde» + la ficha de
   arquetipo con su esqueleto literal.
3. **Formulario (antes: 0 P1 y aun así mal).** El agente de antes copió el markup de `becas/_field.html` **a mano, en
   línea**, razonando «para no acoplar Merenderos a una ruta de Becas». El núcleo nuevo declara ese parcial
   **transversal** y el agente reescrito lo incluyó sin dudar. Lo cerró una fila del inventario, no una regla mecánica:
   la pantalla daba 0 P1 en los dos casos.

El punto 3 es la confirmación de la premisa del anexo: **el gate de token no alcanza**. Dos de las tres pantallas de la
línea base daban 0 P1 y ninguna clonaba su golden.

### El hallazgo que sobrevivió, y por qué no se arregló con una regla

El revisor de la pantalla 2 encontró **un** desvío: `{{ partes|length }}` sobre un queryset (L142) para un texto
informativo, cuando el contador ya estaba resuelto en la vista como `n_partes`. Es no bloqueante y de corrección
trivial, pero vale anotarlo: **ninguna regla P1 lo atrapa, y ninguna regla de la fase 2 del anexo lo atraparía**. No es
un desvío de diseño (no hay clase, token ni estructura de por medio): es una regla de **desarrollo front**, que vive en
el método del revisor. Lo cazó el revisor, que es exactamente su lugar en el sistema. Por eso **no se activó ninguna
regla de fase 2**: hacerlo sería mover a `design_audit` un chequeo que no es suyo.

### Desvíos del método, para que la medición se lea bien

- **Sin capturas.** El criterio (e) del paso 6 pide una captura lado a lado con la golden a 1440 y 390 px que el PM
  acepte como «mismo sistema». No se tomó: necesita el harness Playwright, que es local y no está commiteado, y
  necesita al PM. **Queda como pendiente del PM**, no del desarrollo. Los otros cuatro criterios —(a) Plan con la
  golden correcta, (b) `--ratchet` 0 nuevos, (c) `--arquetipo` OK, (d) el revisor aprueba— se cumplen los cuatro.
- **Una de las tres sesiones implementadoras corrió sus validaciones desde el checkout principal** en vez del worktree
  del ejercicio. No afecta el resultado: todas las mediciones de esta carpeta las volvió a correr la sesión que
  coordina el ejercicio, desde el worktree, y son las que están en los `.txt`.

## Cómo repetir esto

1. Worktree descartable sobre `origin/development`.
2. Los mismos tres prompts, literales, uno por subagente `chaco-frontend`, en paralelo y sin pistas de diseño, con la
   única restricción de escribir en un archivo nuevo fuera del árbol de la app.
3. **Medir con los archivos FUERA de `docs/`.** ⚠️ `design_audit.py <archivo>` y `--ratchet` filtran por
   `EXCLUDE_PARTS`, que incluye `"docs"`: apuntados a una ruta de esta carpeta **auditan cero archivos e imprimen
   igual `0 error(es), 0 P1, 0 warning(s)` con exit 0**. Es un verde falso, no una medición. (`--arquetipo` **sí** lee
   el archivo donde esté: el modo de arquetipo no pasa por ese filtro. Control negativo:
   `--arquetipo listado despues/02-dispositivos-cama/cama_detail.html` reporta 1 desvío.)

   La forma correcta es copiar los templates a una carpeta de trabajo en la raíz del repo y medir ahí:

   ```powershell
   # desde la raíz del worktree
   $PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"
   New-Item -ItemType Directory -Force _ejercicio_control | Out-Null
   Copy-Item -Recurse docs\internal\auditoria-2026-10\linea-base-agente-diseno\despues\* _ejercicio_control\
   & $PY scripts\design_audit.py _ejercicio_control\01-merenderos-entregas\entrega_list.html
   & $PY scripts\design_audit.py --arquetipo listado _ejercicio_control\01-merenderos-entregas\entrega_list.html
   & $PY scripts\design_audit.py --ratchet          # ve los 3 como archivos sin trackear
   & $PY scripts\check_design_agent.py --changed
   Remove-Item -Recurse -Force _ejercicio_control   # scratch: no se commitea
   ```

   Es lo que se hizo para generar los `.txt` de esta carpeta; cada uno lleva en su cabecera el comando exacto. Las
   rutas que se ven adentro son las de `_ejercicio_control/`, que es donde vivían los archivos al medirlos.
4. Después, `chaco-design-reviewer` independiente sobre cada una, pasándole el Plan de pantalla que declaró el
   implementador.
5. Llenar la tabla de *Antes y después*. **Criterio:** las tres al primer intento con Plan de pantalla, la golden
   correcta, 0 P1, 0 nuevos, marcadores OK y el revisor aprobando.
