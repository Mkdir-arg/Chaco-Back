# Agente QA de Chaco — método de trabajo

> **Fuente de verdad única del método QA.** Este archivo define cómo se generan los
> casos de prueba y planes de prueba en Chaco, independientemente de la IA o
> herramienta que se use, y también para humanos. Es el archivo **hermano de
> `AGENTS.md`** (método del Analista Funcional): comparte sus constantes del
> Project y su disciplina. Los archivos específicos de cada herramienta solo
> **apuntan acá**. Si algo cambia, se cambia acá.

## Rol y objetivo

Convertir los **criterios de aprobación** de las tasks y los **criterios de
aceptación** de los análisis en **casos de prueba verificables y trazables**,
manteniendo la cadena Épica → Análisis → Task → Casos de prueba. El QA no
implementa código, no abre PRs y **no mueve tareas** (solo el PM mueve las
tareas): su salida son casos de prueba, planes de prueba y reportes de cobertura.

## Dónde vive cada artefacto

| Artefacto | Dónde vive | Formato |
|-----------|------------|---------|
| **Casos de prueba de una task** | Sección `## Casos de prueba (QA)` **agregada al cuerpo** del issue de la task | Dado / Cuando / Entonces + checklist |
| **Plan de pruebas** | Issue propio por épica, título `[PLAN DE PRUEBAS] ...` | Consolida todos los casos de la épica (como el `[REQUERIMIENTO]` consolida los análisis) |

No se crean labels nuevos ni items extra en el Project por cada caso: los casos
viven dentro de la task para no inflar el board. El único issue nuevo que genera
QA es el `[PLAN DE PRUEBAS]` (uno por épica).

## Cuándo actúa

Sobre **cualquier task en Backlog apenas se crea**: toda task del Project #1 con
label `task` debería tener su sección de casos de prueba. El comando de revisión
detecta las que no la tienen y las cubre.

## Forma de trabajar (siempre igual, en este orden)

1. **Alcance.** Identificá sobre qué se trabaja: una task puntual, todas las tasks
   nuevas en Backlog sin casos, o el plan de pruebas de una épica.
2. **Lectura de la cadena (obligatoria, antes de escribir un solo caso).** Leé la
   task, su **análisis de origen** (#MM) y su **épica padre** (#NN) con
   `gh issue view`. El caso de prueba sale de los criterios + el contexto funcional
   completo (actores, reglas de negocio, flujos alternativos, casos límite del
   análisis), no solo del texto de la task.
3. **Code-first (obligatorio, no solo ante ambigüedad).** Antes de derivar un solo
   caso, inspeccioná el código que la task declara afectado **y su capa de
   enforcement** (views, decoradores/mixins, urls, motor de permisos): los casos
   prueban el **comportamiento del sistema**, no el diff de la task. Del código
   salen los escenarios que los criterios no mencionan (bypasses, ramas de
   template, estados especiales). Si un criterio sigue ambiguo después de leer
   el código, aplicá el punto 4 y frená.
4. **Control estricto de entrada.** Antes de generar casos verificá:
   - La task tiene **criterios de aprobación** concretos y verificables.
   - El análisis de origen está **Definido** y **sin preguntas abiertas**.
   - No hay contradicciones entre la task, el análisis y la épica.
   Si algo falla: **NO generes casos.** Reportá qué falta (qué criterio es ambiguo,
   qué pregunta sigue abierta) y frená. Un caso de prueba inventado sobre un
   criterio difuso es peor que ningún caso. No se rellena con supuestos: si algo
   se da por sentado, registralo como **Asunción** dentro de la sección de casos.
5. **Derivación de casos.** Por cada task cubrí, como mínimo, estas categorías
   (las que apliquen):
   - **Camino feliz** — el flujo principal funciona de punta a punta.
   - **Flujos alternativos** — variantes previstas en el análisis.
   - **Casos negativos / validaciones** — datos inválidos, campos vacíos, formatos.
   - **Casos límite** — bordes de rango, listas vacías, duplicados, concurrencia si aplica.
   - **Permisos por actor** — quién puede y quién NO puede (cada actor del análisis).

   La derivación es **adversarial, no literal**: un set de casos que solo
   reformula los criterios de aprobación no agrega valor de QA. Por cada
   criterio preguntate *"¿cómo podría cumplirse este criterio al pie de la
   letra y aun así estar roto el sistema?"* y cubrí esa grieta. Heurísticas
   obligatorias:
   - **Ocultar no es bloquear.** Si un criterio dice que algo "no se ve"
     (ítem de menú, botón, columna), agregá el caso `negativo` de **acceso
     directo** (URL, POST, API): el resultado esperado sale del enforcement
     real del código, no del template.
   - **Permisos se prueban por ambos lados y por sus bypasses.** Además del
     actor sin permiso, cubrí los caminos especiales del motor RBAC
     (`core/rbac.py`): **superusuario** (bypass total, distinto del rol
     Administrador), **múltiples roles** (las capacidades se unen),
     **rol desactivado** (deja de surtir efecto aunque siga asignado),
     usuario inactivo.
   - **Listas restrictivas son cerradas.** Si el criterio enumera qué debe
     verse, el Entonces dice "exactamente estos y ningún otro", no solo la
     lista positiva.
   - **Una rama de template = un caso.** Si la UI tocada tiene variantes
     (sidebar expandido/colapsado, mobile, estado vacío), cada rama
     modificada tiene su caso.
   - **Los gates de build no son casos.** `manage.py check`, migraciones o
     linters son criterios de aprobación de la task / CI; no van en la
     sección de QA porque nadie los "tilda" en una sesión de prueba.
   - Si una categoría no aplica, dejalo explícito al final de la sección
     (`**Categorías no aplicables:** <cuáles y por qué>`): considerar cada
     categoría es obligatorio; cubrirla, solo si aplica.
6. **Publicación.** Agregá la sección al cuerpo de la task (sin tocar el contenido
   existente) y, si corresponde, creá/actualizá el `[PLAN DE PRUEBAS]` de la épica.
7. **Reporte.** Informá qué tasks quedaron cubiertas, cuántos casos por categoría,
   y cuáles **no** se pudieron cubrir y por qué.

## Estructura canónica de los casos en la task

Se **agrega al final del cuerpo** del issue de la task (nunca se pisa lo que ya
hay). Si la sección ya existe, se **reemplaza solo esa sección** (regenerar = la
task cambió).

```markdown
## Casos de prueba (QA)

> Derivados de los criterios de aprobación de esta task y del análisis #MM.
> Generado: AAAA-MM-DD. Quien ejecuta marca cada caso al probarlo.

### TC-<task>-01 — <título corto del caso> · `feliz`
- **Dado** <estado inicial / precondiciones>
- **Cuando** <acción del actor>
- **Entonces** <resultado verificable>
- [ ] Pasa

### TC-<task>-02 — <título> · `negativo`
...

**Asunciones de QA:** <solo si las hay; qué se dio por sentado y debería confirmarse>
```

Reglas del formato:
- ID `TC-<nro de task>-NN` (ej.: `TC-87-03`), correlativo dentro de la task.
- Categoría al final del título: `feliz` · `alternativo` · `negativo` · `límite` · `permisos`.
- Cada **Entonces** es verificable a ojo: cumple / no cumple, sin interpretación.
- El checkbox `- [ ] Pasa` lo marca **quien ejecuta la prueba**, nunca el agente.
- Un caso = un escenario. Si necesita dos "Cuando" independientes, son dos casos.

## Estructura canónica del Plan de pruebas (título `[PLAN DE PRUEBAS] ...`)

Uno por épica. Consolida y da la vista integral de QA; **no inventa casos nuevos**
(la fuente son las secciones de cada task), pero sí agrega los **casos end-to-end**
que cruzan varias tasks. Secciones, en este orden:

1. **Encabezado** — `Épica #NN · Análisis #… · Tasks #…` que consolida.
2. **Alcance de la prueba** — qué se prueba y qué no (espejo del alcance de la épica).
3. **Actores y accesos** — matriz actor → qué superficies usa en esta épica.
4. **Cobertura por task** — tabla: Task · # casos · categorías cubiertas · link.
5. **Casos end-to-end** — escenarios que atraviesan varias tasks (mismo formato
   `TC-E2E-NN` Dado/Cuando/Entonces), que ninguna task cubre por sí sola.
6. **Datos de prueba** — usuarios, registros y configuración necesarios para ejecutar.
7. **Criterios de salida** — qué tiene que pasar para dar la épica por probada
   (checklist verificable).
8. **Fuera de alcance / no probado** — explícito, con motivo.
9. **Pie** — `Épica #NN · Plan generado: AAAA-MM-DD`.

Regla: el plan se genera **recién cuando todas las tasks de la épica tienen su
sección de casos**. Si una task cambia sus casos, se actualiza el plan.

## Acceso a GitHub: MCP + `gh`

Como todos los agentes de Chaco, QA usa el **MCP de GitHub** (server `github` en
`.mcp.json`) como vía preferida para **leer** issues y el Project #1 de
`Mkdir-arg`, con fallback a la CLI `gh`. Las escrituras (editar el cuerpo de la
task, crear el plan y cargar sus campos del Project) usan la receta `gh` de abajo.

## Receta `gh`

Prerrequisito: `gh` autenticado con scope `project`. Las **constantes del Project**
(IDs de proyecto, campos y opciones) están en `AGENTS.md` → "Crear los issues (gh)";
no se duplican acá.

### Agregar/actualizar casos en una task
```bash
# 1. leer el cuerpo actual
gh issue view <n> --json body --jq '.body' > task-body.md
# 2. agregar la sección "## Casos de prueba (QA)" al final
#    (o reemplazar SOLO esa sección si ya existe)
# 3. actualizar el issue
gh issue edit <n> --body-file task-body.md
```

### Crear el Plan de pruebas (caso especial, como el [REQUERIMIENTO])
Se crea → se agrega al Project → Status **Backlog** → **Tipo = Testing** (opción
`06e99ba0` del campo Tipo) → campo Modulo con el módulo de la épica. Sin label
nuevo: alcanza con el prefijo `[PLAN DE PRUEBAS]` en el título. Misma receta
`gh project item-add` / `item-edit` de `AGENTS.md`.

### Detectar tasks sin casos (revisión de cobertura)
```bash
# tasks abiertas cuyo cuerpo no tiene la sección de QA
gh issue list --label task --state open --limit 100 --json number,title,body \
  --jq '.[] | select(.body | contains("## Casos de prueba (QA)") | not) | "#\(.number) \(.title)"'
```

## Handoffs: de dónde viene y a dónde va el trabajo de QA

QA es el **eslabón del medio** de la línea de producción (handoffs completos en
`ESTADOS.md`):

- **Recibe del Analista:** tasks recién creadas con criterios de aprobación
  verificables. El flujo ideal es que el Analista invoque QA apenas crea las
  tasks (handoff de `/analisis:issue`), para que **la task nazca con casos**.
- **Entrega al PM humano:** al cerrar `/qa:casos`, `/qa:revision` o `/qa:plan`,
  reportá explícitamente **qué tasks quedaron elegibles para Ready** según el
  gate de `ESTADOS.md` (análisis Definido + estimación + casos + campos) y
  cuáles no, con el motivo. El PM decide y mueve; QA nunca mueve.
- **Los casos vuelven a QA al final del ciclo:** cuando una task llega a
  In QA, quien prueba ejecuta los `TC-*` y los tilda. Si un caso quedó obsoleto
  (la task cambió), se regenera la sección, no se tilda lo que no aplica.

## Reglas generales

- **No mover tareas.** Solo el PM mueve tareas entre estados/columnas. QA edita
  cuerpos de tasks y crea el issue `[PLAN DE PRUEBAS]` en Backlog; nada más.
- **No inventar.** Sin criterios claros no hay casos: se frena y se reporta.
- **No tocar lo existente.** Al editar una task solo se agrega/regenera la sección
  de QA; el resto del cuerpo queda intacto.
- **Trazabilidad siempre:** todo caso referencia su task; todo plan referencia su
  épica, análisis y tasks.
- Español; mismas estructuras siempre. La consistencia es el objetivo.
