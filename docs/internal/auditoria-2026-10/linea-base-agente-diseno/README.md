# Línea base «antes» del agente de diseño (Ola 6, paso 0)

Medición del **estado actual** del sistema de agentes de diseño, tomada antes de tocar nada. Es la mitad «antes» del
ejercicio de control del **paso 6** (`anexo-agente-diseno.md` §9): las mismas tres pantallas se le van a pedir de nuevo
al agente reescrito y la comparación es el único criterio objetivo para decir si la Ola 6 sirvió.

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
| `antes/<n>-<pantalla>/<template>.html` | El template tal como lo entregó el agente actual, literal |
| `antes/<n>-<pantalla>/design_audit.txt` | `scripts/design_audit.py <template>` — hallazgos P1 |
| `antes/<n>-<pantalla>/arquetipo.txt` | `scripts/design_audit.py --arquetipo <a> <template>` — marcadores |
| `repo-completo.txt` | La corrida completa del repo: la deuda que el ratchet congela |

Los `.html` de acá **no son templates de la app**: no están en ningún directorio de templates, no los ve
`compile_templates.py` y `design_audit.py` excluye `docs/` entero, así que no cuentan como deuda del repo.

## Resultado

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

## Cómo repetir esto en el paso 6

1. Worktree descartable sobre `origin/development`, con la Ola 6 ya aplicada.
2. Los mismos tres prompts, literales, uno por subagente `chaco-frontend`, en paralelo y sin pistas de diseño.
3. Por cada pantalla: `design_audit.py --ratchet`, `--arquetipo <a> <archivo>` y `check_design_agent.py --changed`.
4. Después, `chaco-design-reviewer` independiente sobre las tres.
5. Llenar la misma tabla de arriba con la columna «después» y compararlas. **Criterio:** las tres al primer intento con
   Plan de pantalla, la golden correcta, 0 nuevos y marcadores OK.
