# Implementación de la automatización diaria de Chaco

Estado: pendiente de autorización de ejecución

Fecha: 2026-07-22

Última revisión operativa: 2026-07-23

Diseño aprobado: `docs/plans/2026-07-22-chaco-trabajo-diario-codex-design.md`

## Resultado esperado

Entregar una única tarea programada de Codex, inicialmente pausada, que ejecute el
contrato aprobado de forma segura sobre el Project #1. La selección y agrupación
funcional, el preflight, la evidencia, la recuperación y las transiciones se ejecutan
desde el prompt operativo y se respaldan exclusivamente en Project, Issues, PRs y la
memoria de la automatización. No se crea un helper ni estado local de coordinación.

La automatización no se habilita hasta que:

- el código y las reglas estén integrados en `development`;
- `gh` tenga `read:project` y `project`;
- el snapshot real read-only pase;
- un smoke supervisado cubra mutaciones, puente de decisión, reanudación y entorno;
- GitHub, Git, Docker y filesystem funcionen sin pedir permisos durante un run;
- el horario efectivo se confirme en la UI;
- el usuario autorice activar la recurrencia.

## Límite de responsabilidades

| Componente | Decide o ejecuta |
| --- | --- |
| Codex | Comprende el pedido, inspecciona el código, agrupa por concepto, redacta el Brief, implementa, prueba y revisa |
| GitHub | Fuente durable de planes, decisiones, Project, comentarios, ramas, PR y checks |
| Memoria de la automatización | Punteros y snapshots; nunca habilita una mutación si GitHub no coincide |
| Docker Compose | Entorno final de aceptación respaldado por una imagen del head SHA |
| Usuario | Autoriza o rechaza cada versión del Plan de grupo y revisa el PR final |

## Archivos previstos

| Archivo | Cambio |
| --- | --- |
| `docker-compose.yml` | Hacer que una variable opcional definida vacía permanezca vacía |
| `docker-compose.acceptance.yml` | Stack sin bind mount, puertos seguros e imagen etiquetada por SHA |
| `.dockerignore` | Excluir scratch de la automatización del contexto de imagen |
| `docs/plans/2026-07-22-chaco-trabajo-diario-codex-prompt.md` | Prompt canónico versionado de la tarea programada |
| `docs/plans/2026-07-22-chaco-trabajo-diario-codex-design.md` | Diseño aprobado y auditado |
| `docs/plans/2026-07-22-chaco-trabajo-diario-codex-implementation.md` | Este plan |
| `CONTEXT.md` | Lenguaje compartido |
| `ESTADOS.md` | Gates y excepción automática acotada |
| `AGENTS.md` | Alcance permitido para futuros agentes |

No se agregan paquetes, scripts de coordinación, leases locales, base de datos de
coordinación, Issue coordinador, workflow de CI adicional ni archivo mutable de estado
dentro del repositorio.

## Fase 1 — Aislar y congelar el contrato

1. Crear un worktree aislado desde el último `origin/development` con rama
   `codex/chaco-daily-automation`.
2. Trasladar únicamente los archivos nombrados en este plan; no incorporar cambios de
   la rama o checkout actual del usuario.
3. Confirmar que diseño, glosario, `ESTADOS.md` y `AGENTS.md` dicen lo mismo sobre:
   - reserva previa a autorización;
   - Sello y Evento de decisión;
    - Task y Requerimiento;
    - ownership y compensación;
    - Matriz de dependencias, Cápsula operativa y reconciliación GitHub-first;
    - Blocked e In review;
    - prohibiciones de merge, aprobación propia, force-push, datos productivos y
      estado local de coordinación.
4. Mantener la automatización deshabilitada mientras estos archivos no estén en
   `development`.

Gate: diff documental coherente y sin preguntas abiertas.

## Fase 2 — Validar el contrato operativo sin estado local

Antes de habilitar mutaciones, revisar mediante snapshots read-only y escenarios
documentados que el prompt pueda demostrar:

1. identidad exacta `juanikitro`, scopes requeridos, Project único, campos/opciones
   resueltos por nombre, paginación completa e Iteration vigente;
2. elegibilidad: Task abierta, Ready, único assignee correcto, QA, prioridad, módulo,
   estimación, épica y análisis válidos;
3. Matriz de dependencias completa: cada relación debe estar integrada en
   `development`, ordenada dentro del mismo grupo o cubierta por un único PR padre
   calificado; cualquier otra situación se excluye;
4. vínculo Task → Requerimiento sin ambigüedad y sin reclamar movimientos ajenos;
5. Plan, Sello, Evento, Cápsula y decisiones concordantes, con colisiones resueltas
   por la evidencia durable y no por memoria local;
6. recuperación: sin rama/commit/PR se puede compensar por ownership; con alguno de
   ellos se conserva `In progress`; una contradicción detiene toda mutación;
7. política de siguiente acción: cualquier plan no terminal bloquea un grupo nuevo;
8. consulta financiera por Task y escritura compatible con las columnas vigentes de
   `docs/client/financiero/detalle-tareas.md`, sin alterar filas históricas.

Los ejemplos de revisión son sintéticos y saneados: no incluyen cuerpos reales,
credenciales, tokens ni datos productivos.

Gate: una tabla de escenarios read-only demuestra resultados esperados, evidencia a
leer y la acción prohibida para cada caso límite; no se crean scripts ni tests nuevos
solo para coordinar.

## Fase 3 — Operar con GitHub y memoria como único estado

El prompt operativo implementa el protocolo sin helper dedicado:

1. Antes de reanudar, compensar, reservar o activar, relee Project, Tasks,
   Requerimientos, comentarios, reacciones, Eventos, PRs, ramas, HEAD, checks, cierre
   financiero y la Cápsula. Compara con memoria; GitHub prevalece.
2. Si existe discrepancia, publica o recupera un Evento de recuperación y actualiza la
   Cápsula después de que la evidencia sea concordante. No muta Project ni Git mientras
   la discrepancia continúe.
3. Para reservar, vuelve a comprobar elegibilidad y Matriz de dependencias, publica
   comentario canónico, referencias y Cápsula, relee Status antes de cada transición y
   conserva ownership explícito para una eventual compensación.
4. Para una decisión, exige Sello y Evento concordantes de la versión exacta. Una
   observación no muta; un rechazo sin código compensa solo lo propio; con código,
   rama o PR pausa y conserva evidencia.
5. Cada cambio material actualiza la única Cápsula de la Task ancla con fase, snapshot,
   PR/HEAD, bloqueo, respuesta esperada y próximo paso. La Cápsula nunca es fuente de
   autorización.
6. Ninguna ruta crea otro grupo mientras haya un estado no terminal. Una carrera o
   marcador duplicado detiene las escrituras y requiere reconciliación.

### Lectura y escritura de GitHub

1. Consultar el Project paginado y resolver los campos en vivo; no confiar en la vista
   visible ni en IDs cacheados.
2. Usar los mecanismos existentes de GitHub para comentarios, reacciones, Project y
   PRs, conservando IDs y enlaces devueltos como evidencia.
3. Redactar motivos de inclusión/exclusión sin volcar cuerpos completos ni secretos.
4. Antes de cada escritura, releer el recurso exacto y confirmar plan, versión,
   ownership y estado esperado. Un recurso cambiado, ausente o ambiguo falla cerrado.

### Activación Git y PR

1. Rechazar un worktree sucio.
2. Hacer `fetch` y partir de `origin/development` o de la rama remota del plan.
3. Trabajar en detached HEAD para no competir con branches locales de otros worktrees.
4. Crear el commit vacío `chore(plan): iniciar <PG>` cuando la rama aún no exista.
5. Empujar explícitamente HEAD a la branch remota esperada, solo fast-forward.
6. Crear o recuperar un único PR draft por head; nunca aprobar, mergear, borrar branch
   ni usar force-push.

Gate: una simulación read-only y la revisión del prompt demuestran que ninguna acción
de coordinación depende de un helper, lease, token o archivo local, y que los errores
de GitHub se clasifican sin exponer secretos ni stdout sensible.

## Fase 4 — Entorno de aceptación seguro

1. Cambiar en `docker-compose.yml` la interpolación de
   `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` para que una variable definida vacía no reciba
   el default; el comportamiento histórico se conserva si la variable está ausente.
2. Crear `docker-compose.acceptance.yml` y comprobar con la versión instalada de
   Compose que:
   - elimina el bind mount `.:/app`;
   - construye una imagen etiquetada con el head SHA;
   - publica la app solo en `127.0.0.1`;
   - no publica MySQL ni Redis al host;
   - fuerza `RENAPER_TEST_MODE=True`;
   - deja vacíos los comandos opcionales;
   - conserva volúmenes sin permitir `down -v`.
3. Guardar la configuración local en una ruta estable externa a los worktrees,
   `C:\Users\Juanito\.config\chaco-automation\.env.local`, con permisos restringidos.
   Se crea a partir del ejemplo con valores solo locales, nunca productivos, y no se
   imprime ni se copia al repo.
4. Justo antes del build, exigir worktree limpio, obtener el SHA completo, añadir
   label OCI `org.opencontainers.image.revision` y etiquetar la imagen con ese SHA.
   Comprobar también que no haya scratch ignorado inesperado dentro del contexto y
   excluir `.tmp_*` en `.dockerignore`. Después del build registrar y verificar image
   ID o digest.
5. El Brief y la Ficha de aceptación reproducible declaran comandos existentes de
   bootstrap/seed, orden, origen sintético, identidades o roles de prueba,
   postcondiciones, URL, pasos por criterio y resultado esperado.
6. `up --wait` o polling acotado debe terminar con `/health/` válido y datos esperados
   comprobados; la Ficha registra esa evidencia antes de presentarse al usuario.
7. La Ficha declara SHA, Project de Compose, labels, puertos, limitaciones conocidas y
   un comando de apagado que detiene solo el stack propio y conserva los volúmenes.
8. Registrar esos datos en la Cápsula y Eventos del plan. La rotación localiza por
   labels y detiene solo el stack propio.

Validación estática, sin usar secretos reales:

```powershell
docker compose --env-file .env.local.example `
  -f docker-compose.yml `
  -f docker-compose.acceptance.yml `
  config --quiet
```

Además de la sintaxis, renderizar `config --format json` y afirmar mecánicamente:

- `app` solo publica `127.0.0.1:8000`;
- `mysql` y `redis` no tienen puertos de host;
- `app` no conserva el bind mount del código;
- imagen y label usan el SHA completo esperado;
- `RENAPER_TEST_MODE` es verdadero y los comandos opcionales están vacíos.

La prueba runtime de Docker requiere una autorización separada al ejecutar esta fase,
porque construye imágenes, inicia contenedores y una base local.

## Fase 5 — Versionar el prompt operativo

Crear `docs/plans/2026-07-22-chaco-trabajo-diario-codex-prompt.md` con dos capas:

1. Contrato innegociable breve, embebido luego en la tarea programada:
   - el run es standalone: no conserva chat, worktree ni estado local anterior;
   - identidad, allowlist y prioridad de continuidad;
   - snapshot GitHub-first, estado esperado, relectura e idempotency key en toda
     mutación, sin lease ni archivo local;
   - cero escrituras ante ambigüedad, scope faltante o conflicto;
   - máximo un plan nuevo por ejecución y ninguno mientras exista un plan no terminal;
   - Matriz de dependencias completa y excluyente antes de reservar;
   - una Cápsula operativa por plan y reconciliación GitHub-first antes de reanudar;
   - código solo con Sello + Evento vigentes;
   - observación no decide; rechazo libera antes de código y pausa después de código;
   - autorización aplica decisión, abre PR y activa o encola inmediatamente;
   - transiciones exactas de Task y Requerimiento;
   - una unidad funcional activa a la vez;
   - bootstrap limpio y detached desde la rama remota correcta;
   - entrega solo con validación, Standards, Spec y CI del head/base actuales;
   - cierre financiero estructurado por Task, sin inferir consumo ni reescribir filas
     históricas;
   - prohibiciones de secretos, producción, force-push, merge, `down -v` y estado
     local de coordinación.
2. Procedimiento que obliga a leer, en orden:
   - verificar remoto, worktree limpio y capacidades sin pedir aprobación;
   - hacer `fetch` y posicionarse en detached HEAD de `origin/development`;
   - `AGENTS.md` y cualquier instrucción local aplicable;
   - `ESTADOS.md`;
   - diseño, prompt y `CONTEXT.md`;
   - `QA.md` cuando corresponda;
    - snapshot vivo GitHub-first, Cápsula y memoria reconciliada;
   - si hay una Unidad activa, cambiar después a detached HEAD de su branch remota;
   - código focalizado, empezando por modelos según el método del repo.

El prompt ordena usar únicamente las interfaces existentes de GitHub para las
escrituras de coordinación y registrar la evidencia en Project, Issues y PRs. Codex
conserva la responsabilidad semántica de agrupar, implementar, validar y ejecutar las
dos revisiones frescas. Las preferencias de notificación se configuran en Codex y no
se incluyen dentro del prompt.

Cada paso lógico de implementación termina con commit, push fast-forward y checkpoint
en el PR. Antes de una validación larga o de devolver el turno, no puede quedar como
única copia trabajo funcional sin commit dentro del worktree efímero.

Una respuesta exacta del usuario en la misma tarea persiste Sello y Evento concordantes
para esa versión. Si autoriza y no hay otra Unidad activa, Codex continúa la
implementación; si rechaza, confirma la compensación o la pausa. Una ejecución
programada posterior solo consume el estado ya persistido en GitHub.

## Fase 6 — Validación focalizada

Sin Docker ni mutaciones GitHub, revisar el diff documental con `git diff --check` y,
si hay cambios de documentación pública, ejecutar `python -m mkdocs build --strict`.
La validación estática de Compose se mantiene en la Fase 4; no se instala ninguna
herramienta de forma silenciosa.

La integración read-only verifica:

1. que scopes insuficientes llevan a cero escrituras;
2. identidad, Project, campos, opciones, iteración, paginación y motivos de
   elegibilidad desde un snapshot vivo;
3. Matriz Task → dependencia → evidencia y vínculos Task → Requerimiento con datos
   actuales, sin congelar ejemplos históricos como verdad;
4. que la memoria se contradiga de forma controlada con el snapshot y produzca
   reconciliación, no una mutación;
5. que un plan no terminal produzca `wait` y no una propuesta nueva;
6. que la plantilla financiera use el formato vigente sin modificar filas históricas.

No se corre una suite nueva solo para coordinación; la validación adicional se decide
por el diff real y los checks existentes del PR.

## Fase 7 — Publicación y revisión de la implementación

Con autorización explícita para Git:

1. Crear commits Conventional Commits, agrupados por documentación, prompt y entorno.
2. Stagear solo los archivos nombrados; no usar `git add -A`.
3. Push de `codex/chaco-daily-automation` y PR draft a `development`.
4. Ejecutar dos revisiones frescas e independientes:
   - Standards: reglas del repo, seguridad, idempotencia y mantenibilidad.
   - Spec: cobertura exacta del diseño aprobado.
5. Corregir y repetir hasta cero hallazgos dentro del diff y contratos afectados.
6. Esperar CI del último head, inspeccionar también Ruff/Bandit informativos y
   verificar base/mergeability.
7. Convertir el PR en listo; no aprobarlo ni fusionarlo.

La automatización no se crea todavía: un worktree standalone debe poder leer el prompt
y las reglas desde `development`.

## Fase 8 — Crear la tarea programada después del merge

1. Verificar que el PR anterior fue fusionado y que `origin/development` contiene los
   documentos, prompt y configuración esperados.
2. Completar manualmente el refresh de scopes de `gh` y repetir el snapshot
   GitHub-first read-only.
3. Preparar el venv compartido y la ruta externa de `.env.local`; comprobar existencia,
   permisos y valores seguros sin imprimirlos.
4. En una tarea Codex regular con worktree, ejecutar el smoke completo antes del modo
   desatendido:
   - bootstrap detached desde `origin/development`;
   - reconciliación GitHub-first y recuperación inyectada sin estado local;
   - reserva y compensación sobre un item reversible expresamente autorizado;
   - Sello + Evento de decisión, PR y reconstrucción desde la rama remota;
   - transición negativa para Blocked/deliver;
   - build, health y parada exacta del stack sin borrar volúmenes.
5. Verificar que `fetch`, escrituras GitHub, push, PR, Python y Docker funcionan con la
   política desatendida sin abrir pedidos de permiso. Confirmar que la computadora, la
   app, el repo, la red y esas capacidades estarán disponibles al horario programado.
6. Consultar el Project local mediante `codex_app__list_projects` y crear mediante
   `codex_app__automation_update` una única automatización:
   - nombre: `Trabajo diario asignado en Chaco`;
   - proyecto local Chaco;
   - ejecución en worktree standalone;
   - lunes a viernes a las 09:30 locales;
   - modelo de alta capacidad y razonamiento alto;
   - notificaciones normales;
   - estado inicial pausado.
7. Verificar en la UI proyecto, prompt, horario efectivo, zona local, worktree y
   política de avisos.
8. No depender de una operación API `run now`. Si la UI instalada ofrece ejecución
   manual puede usarse como comprobación adicional, pero el smoke previo sigue siendo
   obligatorio.
9. Tras confirmación final, cambiar esa misma automatización a activa. Su primera
   ejecución programada puede publicar y reservar como máximo un grupo.
10. Comprobar comentario, referencias, Tasks, Requerimientos y respuesta en Codex. Si
    falla, pausar, reconciliar y no crear una segunda automatización.

## Rollback

- Antes del primer run: pausar o eliminar la automatización; no hay estado GitHub que
  revertir.
- Reserva parcial: reconciliar por ownership con evidencia de GitHub; nunca hacer
  cambios manuales masivos.
- Rechazo sin código: Tasks a Ready, Requerimiento propio a Backlog si cumple el gate,
  PR vacío cerrado y branch conservada.
- Problema del protocolo: pausar la automatización, mantener Project/PR como evidencia
  y corregir el prompt o las reglas mediante un PR normal.
- Entorno local: detener solo el Project Compose identificado, sin `down -v`; borrar
  volúmenes requiere otra autorización.

## Definición de terminado

- Reglas, prompt y configuración integrada en `development`.
- Validación focalizada y CI del PR verdes.
- Scopes, identidad, Project e iteración verificados en vivo.
- Dry-run sin escrituras revisado.
- Automatización única visible en Codex con horario correcto.
- Primer Plan de grupo reservado de forma completa e idempotente.
- Una autorización o rechazo de prueba persiste reacción y Evento concordantes.
- No existen duplicados, estados parciales ni cambios fuera de la allowlist.
