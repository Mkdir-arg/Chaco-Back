# Estados del Project Chaco — máquina de estados y gates

> **Fuente de verdad única de los estados.** Define qué significa cada Status del
> Project #1 (https://github.com/users/Mkdir-arg/projects/1/) **según el Tipo**
> del item, y qué condiciones (**gates**) deben cumplirse para pasar de uno a
> otro. La comparten los tres métodos: `AGENTS.md` (Analista), `QA.md` (QA) y
> `PM.md` (PM Assistant). Si algo cambia, se cambia acá.
>
> **Regla madre, siempre vigente:** los agentes NO mueven items entre estados.
> **Solo el PM humano mueve las tareas.** Este archivo le da al PM las reglas
> para mover, y a `/pm:salud` las reglas para auditar.

## Estados disponibles

`Backlog` · `Ready` · `In progress` · `In review` · `In QA` · `Done` ·
`Roadmap` · `Blocked`

## Máquina de estados por Tipo

### Task (`task`)

```
Backlog → Ready → In progress → In review → In QA → Done
                     (Blocked: desde cualquier estado, y vuelve al que estaba)
```

| Estado | Significa | Dueño (assignee) |
|---|---|---|
| Backlog | Creada por el Analista, todavía no es elegible para desarrollar | — (puede no tener) |
| Ready | Cumple el gate de Ready; un dev puede tomarla | El dev que la va a hacer |
| In progress | Se está desarrollando | El dev |
| In review | PR abierta, en revisión | El dev (autor del PR) |
| In QA | PR mergeada; se están ejecutando los casos de prueba | Quien ejecuta las pruebas |
| Done | Todos los casos pasan y los criterios de aprobación están tildados | — |
| Blocked | No puede avanzar; el cuerpo dice por qué y de quién depende | Quien destrabó/persigue el bloqueo |

**Gates de Task:**

| Transición | Condiciones (todas) |
|---|---|
| Backlog → Ready | Análisis de origen en `Definido` · `EstimacionHoras` cargada · **sección `## Casos de prueba (QA)` presente** · exactamente **un** assignee · Prioridad y Modulo cargados |
| Ready → In progress | El assignee empezó a trabajarla |
| In progress → In review | PR abierta y vinculada a la task |
| In review → In QA | PR aprobada y **mergeada** |
| In QA → Done | Todos los `TC-*` con `- [x] Pasa` · checklist de criterios de aprobación completa |
| → Blocked | Comentario en el issue: qué bloquea, de quién depende, desde cuándo |

**La regla nueva más importante: sin casos de QA no hay Ready.** Una task sin su
sección de casos no es elegible para desarrollo. Por eso el flujo correcto es que
la task **nazca con casos** (handoff Analista → QA, ver abajo).

### Análisis (`analisis`)

```
Backlog → In progress → Done
```

| Estado | Significa |
|---|---|
| Backlog | Creado, interrogatorio sin empezar o sin retomar |
| In progress | Estado interno `En análisis`: hay preguntas abiertas / interrogatorio en curso |
| Done | Estado interno `Definido`: sin preguntas abiertas, pasó el control estricto y sus sub-issues están generados |

Gate Backlog/In progress → Done: el cuerpo dice `Estado: Definido`, sección
"Preguntas abiertas" vacía o "Ninguna", y sub-issues listados como checklist.
Los análisis **no** pasan por Ready/In review/In QA.

### Épica (`epica`) — agrupador, NO carga estado

Las épicas se usan para **agrupar tareas y temas**: su Status no cuenta la
historia de la funcionalidad (para eso está el Requerimiento, abajo). Convención
mínima para que el tablero no mienta:

```
Backlog (mientras la épica está viva) → Done (cuando cerró todo lo suyo)
```

No se les hace seguimiento de estado intermedio. El avance de una épica se lee
por sus tasks y por su `[REQUERIMIENTO]`.

### Requerimiento (`[REQUERIMIENTO]`, Tipo `Requerimiento`) — el tracker macro

**Es el item que representa la funcionalidad de punta a punta** en el tablero
(la épica no carga estado). Quien quiera saber "¿cómo viene el ABM de Usuarios?"
mira el Requerimiento, no la épica ni las tasks una por una.

```
Backlog → In progress → In QA → Done
```

| Estado | Significa |
|---|---|
| Backlog | Requerimiento consolidado; el desarrollo de sus tasks no arrancó |
| In progress | Al menos una task de la épica está en desarrollo (In progress/In review) |
| In QA | **La funcionalidad completa está en prueba integral**: las tasks están mergeadas y se está ejecutando el `[PLAN DE PRUEBAS]` |
| Done | Plan de pruebas ejecutado y pasando; la funcionalidad quedó entregada |

**Gates del Requerimiento:**

| Transición | Condiciones |
|---|---|
| Backlog → In progress | Alguna task de la épica salió de Ready |
| In progress → In QA | Todas las tasks del alcance en Done o In QA · `[PLAN DE PRUEBAS]` creado |
| In QA → Done | Todos los casos del plan (incl. `TC-E2E-*`) con `- [x] Pasa` |

No pasa por Ready ni In review (no es una unidad de desarrollo). El assignee en
In QA es **quien ejecuta la prueba integral**.

### Plan de pruebas (`[PLAN DE PRUEBAS]`, Tipo `Testing`)

```
Backlog → Done
```

Es documentación consolidada: `Backlog` = creado/actualizable, `Done` = ejecutado
completo y la épica cerrada. El "está en prueba" macro **no** lo carga el plan
sino el Requerimiento en In QA (el plan es *lo que* se ejecuta, el requerimiento
muestra *que* se está ejecutando).

## Dueños (assignees) — reglas

1. **Nada sale de Backlog sin exactamente un assignee.** Un solo nombre: el que
   lo tiene en la mano *ahora*. Si son dos, nadie es.
2. El assignee **cambia con el estado** si cambia la mano: en In QA el assignee
   es quien prueba, no quien desarrolló.
3. **`ResponsableFuncional`** (campo del Project, por épica y análisis): quién
   responde las dudas funcionales. Es estable; el assignee rota.
4. **`FechaCompromiso`**: solo para fechas comprometidas con el cliente
   (Ministerio). Vacío = no hay compromiso externo.
5. **`Iteration`**: el sprint al que pertenece el item. Toda task en
   Ready/In progress/In review/In QA debe tener iteración asignada.

## Handoffs entre agentes (la línea de producción)

| De | A | Qué se entrega | Disparador |
|---|---|---|---|
| **Analista** → **QA** | Tasks recién creadas en Backlog | Tasks con criterios de aprobación verificables | Al cerrar `/analisis:issue`, el Analista ofrece correr `/qa:casos` sobre las tasks nuevas: **la task nace con casos** |
| **QA** → **PM humano** | Tasks con casos + `[PLAN DE PRUEBAS]` | Lista de tasks que ya cumplen el gate de Ready | Al cerrar `/qa:plan` o `/qa:revision`, QA reporta cuáles tasks quedaron elegibles para Ready |
| **PM humano** → **equipo** | Movimientos en el tablero | Tasks en Ready con assignee e iteración | Decisión humana, con los gates de este archivo |
| **PM Assistant** → **todos** | Informe de salud | Violaciones de gates + qué rol corrige cada una | `/pm:salud` (idealmente al inicio de semana) |

## Auditoría (`/pm:salud`)

El **séptimo chequeo** de `/pm:salud` (los otros 6 están en `PM.md` → "2. Salud")
verifica las violaciones de esta máquina:
- Tasks en Ready+ sin casos de QA, sin estimación, sin assignee único o sin iteración.
- Análisis en Done con preguntas abiertas en el cuerpo.
- Épicas en estados intermedios (Ready/In progress/In review/In QA): son
  agrupadores, solo Backlog o Done.
- `[REQUERIMIENTO]` **desincronizado** de sus tasks: en Backlog con tasks ya en
  desarrollo; en In QA sin `[PLAN DE PRUEBAS]` o con tasks sin terminar; en Done
  con casos del plan sin pasar. (En Ready o In review: estado inválido.)
- `[PLAN DE PRUEBAS]` en estados de flujo (solo Backlog o Done).
- Items Blocked sin comentario de causa o bloqueados hace más de 7 días.
- Tasks In QA cuyo `- [ ] Pasa` no avanza hace más de 5 días.

## Campos del Project (referencia rápida)

Los IDs de proyecto, campos y opciones viven en `AGENTS.md` → "Crear los issues
(gh)". `Size` y `Estimate` (defaults de GitHub) **no se usan**: la estimación es
`EstimacionHoras`.
