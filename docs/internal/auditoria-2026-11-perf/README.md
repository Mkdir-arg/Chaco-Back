# Auditoría de performance y código de DATAÑACH (Chaco) — noviembre 2026

Serie de tres capítulos con el mismo método ([METODO.md](METODO.md)): **Becas → Emergencia → Dispositivos**. SHA auditado: `4140bb8073e271cf6ebccb1f08533d44553baf5a` (`development`, 19-nov-2026). Cada capítulo trae su resumen, índice de fichas, plan por olas, reglas para no repetirlo, descartados, línea de base, decisiones del cliente, plan de la pasada 2 y las fichas. Nada se implementa sin aprobación del PM: las olas salen a issues (en Backlog, Iteration 7) y cada una es su propio PR.

Es la continuación de [auditoria-2026-10](../auditoria-2026-10/README.md). Lo que octubre descartó o difirió se cita por su ID en cada ficha y no se reabre sin un hecho nuevo.

## Estado al 19-nov-2026

| Módulo | Informe | Fichas | Esfuerzo | ALTA | Olas a issues | Limpieza opcional | Ya resuelto |
|---|---|---|---|---|---|---|---|
| Becas | [becas.md](becas.md) | 151 | 624 h | 9 | olas 0-7: 71 fichas, 262 h | olas 8-13: 80 fichas, 362 h | B-SEG-01 (#1202, Cambio 494) |
| Emergencia | [emergencia.md](emergencia.md) | 93 | 312 h | 3 | olas 0-6: 66 fichas, 232 h | olas 7-9: 27 fichas, 80 h | E-SEG-01 (#1204, Cambio 496) y E-ERR-01 (#1205, Cambio 497) |
| Dispositivos | [dispositivos.md](dispositivos.md) | 93 | 318 h | 3 | olas 0-10: 71 fichas, 264 h | olas 11-12: 22 fichas, 54 h | — |
| **Total** | | **337** | **1.254 h** | **15** | **208 fichas, 758 h** | **129 fichas, 496 h** | 3 fichas |

Esfuerzo con S = 2 h, S-M = 4 h, M = 8 h, L = 20 h. Ninguna ficha es CRÍTICA.

| Severidad | Becas | Emergencia | Dispositivos | Total |
|---|---|---|---|---|
| CRÍTICA | 0 | 0 | 0 | 0 |
| ALTA | 9 | 3 | 3 | 15 |
| MEDIA | 73 | 38 | 39 | 150 |
| BAJA | 58 | 45 | 44 | 147 |
| INFO | 11 | 7 | 7 | 25 |
| **Total** | **151** | **93** | **93** | **337** |

| Eje | Becas | Emergencia | Dispositivos | Total |
|---|---|---|---|---|
| SEG · Seguridad y RBAC | 4 | 1 | 7 | 12 |
| ERR · Errores y corrección | 30 | 18 | 14 | 62 |
| PERF · Rendimiento | 25 | 15 | 10 | 50 |
| DAT · Datos y operación | 2 | 1 | 1 | 4 |
| LIM · Código limpio y arquitectura | 73 | 54 | 51 | 178 |
| FE · Front (sin estética) | 17 | 4 | 10 | 31 |
| **Total** | **151** | **93** | **93** | **337** |

## Qué sale a issues y qué es limpieza opcional

- **A issues (una por ola, no por ficha):** corrección, seguridad, rendimiento medible y las olas «de fondo» que mueven reglas de dominio fuera de las vistas. Son 208 fichas y unas 758 h (incluye 3 fichas y 10 h ya resueltas: quedan 205 fichas y 748 h).
- **Limpieza opcional (backlog):** helpers duplicados, constantes, tamaño de archivos, JS inline y mapeos de tono. Son 129 fichas y unas 496 h; entran cuando una ola de corrección toca el mismo archivo, no antes.
- **Orden:** la seguridad confirmada primero; lo de rendimiento va **después de medir** (ver «Mediciones pendientes»); las olas de fondo van después de las correcciones que tocan los mismos archivos.

| Módulo | Olas que van primero | Lo que hay que mirar antes de abrir el issue |
|---|---|---|
| Becas | Ola 0 (altas a SIIS que se saltean la lista «no enviar», B-SEG-04 con el detalle reservado hasta el arreglo) y Ola 1 (la carga del padrón deja tomada la convocatoria y el link público espera más de 10 s) | B-PERF-01 espera la medición; el XSS del export (B-SEG-01) ya salió |
| Emergencia | Ola 0 (queda E-ERR-04 y el seguimiento de las dos ALTA, [sección 10](emergencia.md)) y Ola 1 (idempotencia desde la web) | La Ola 2 es performance y va después de medir |
| Dispositivos | Ola 0 (roles propios, agente asignado, texto libre en el historial) y Ola 1 (orden global de candados) | El orden de candados se verifica contra ingreso, egreso, cambio de plaza y reserva antes de tocar código |

## Decisiones de cliente pendientes

Cada decisión trae su **propuesta por defecto**, que se aplica si el cliente no contesta (sección 7 de cada informe). Las que el juez dejó explícitamente para el cliente:

- **B-LIM-02 · estados del relevamiento.** Unificar las reglas entre backoffice y app (finalizar desde `FINALIZANDO` en todos los canales, reabrir limpia siempre `cerrado_automaticamente_en`, reabrir exige el período actual). Va en un PR **coordinado con Chaco-mobile** y con los tests de contrato RED-11/RED-03 en el mismo diff.
- **B-LIM-15 · cupo ocupado del dashboard.** Alinearlo con el de Cupo (segmento entero) o conservar el recorte por alcance con otro nombre.
- **D-ERR-02 · dispositivo cerrado.** Si los mutadores rechazan solo `CERRADO` (default) o todo lo que no sea `ACTIVO`, y si se puede cerrar con personas alojadas o reservas.
- **E-ERR-03 · vencimientos de Emergencia.** Frecuencia del cron y qué corre al arrancar el contenedor; ya es un pendiente del PM en `requerimientos.md`.
- **E-ERR-01 · identidad al confirmar.** Se aplicó el default en #1205 (rechazar si el nombre no coincide); el cliente confirma o corrige, y decide si el responsable con identidad a revisar (Cambio 486) también completa los vacíos del legajo.

| Informe | Decisiones | Fichas |
|---|---|---|
| [becas.md §7](becas.md) | 19 | B-SEG-02, B-SEG-03, B-SEG-04, B-ERR-01, B-ERR-05, B-ERR-19, B-ERR-20, B-LIM-02, B-LIM-04, B-LIM-14, B-LIM-15, B-LIM-26, B-LIM-41, B-LIM-45, B-LIM-67, B-FE-05, B-FE-08, B-PERF-01, B-PERF-08 |
| [emergencia.md §7](emergencia.md) | 12 (E-FE-01 es del juez) | E-ERR-01, E-ERR-03, E-ERR-04, E-ERR-07, E-ERR-08, E-ERR-15, E-ERR-17, E-LIM-05, E-PERF-12, E-PERF-14, E-PERF-15, E-FE-01 |
| [dispositivos.md §7](dispositivos.md) | 16 | D-SEG-02, D-ERR-02 (y su guarda), D-ERR-03, D-SEG-05, D-PERF-01, D-PERF-05, D-ERR-04, D-SEG-06, D-SEG-07, D-LIM-38, D-LIM-36, D-FE-03, D-LIM-07, D-LIM-50, D-LIM-08 |

## Qué ya se arregló

| Ficha | PR | Cambio | Qué cambió | Seguimiento |
|---|---|---|---|---|
| B-SEG-01 | #1202 | 494 | El 400 del export del dashboard de Becas sale como texto plano (XSS reflejado) | Etiquetas `#seguridad` en los Cambios previos (en este PR) |
| E-SEG-01 | #1204 | 496 | El reenvío de «Ingresar igual» ya no devuelve los integrantes de un caso de otro dispositivo | [emergencia.md §10](emergencia.md), puntos 1 a 3 |
| E-ERR-01 | #1205 | 497 | Confirmar a un integrante con el DNI de otro legajo y otro nombre se rechaza, con la excepción del responsable con identidad a revisar (Cambio 486) | [emergencia.md §10](emergencia.md), puntos 4 a 6 |

## Mediciones pendientes

- **Becas:** la pasada 2 de los exports ya se midió en el banco (el XLSX de respuestas tarda 18,7 s y el de beneficiarios 8 s, B-PERF-25 y B-PERF-26); el resto de las PERF MEDIA o mayores sigue PLAUSIBLE hasta medir (becas.md §8).
- **Emergencia y Dispositivos: pendiente de medición.** El banco no siembra ni mide sus rutas hoy. El PR `perf/banco-emergencia-dispositivos` agrega `scripts/perf_mysql/escenarios_emergencia.py` y `escenarios_dispositivos.py` (con el volumen mayor: 500 plazas y 20.000 estadías en el dispositivo grande) y las rutas en `bench_mysql.py`. Hasta que llegue, la sección 8 de esos informes es solo el plan de medición y no trae números; **sin número, una ficha PERF ALTA baja a INFO**. No se toca `seed_perf` (lo usa el CI de performance).
- **PoC:** las confirmadas (E-SEG-01, E-ERR-01, D-ERR-01, D-SEG-01) quedan como «PoC reproducida; test en el PR que la arregla».

## Reglas propuestas

Cada informe consolida las suyas en la sección 4: 76 en Becas (28 control mecánico, 39 skill, 9 checklist), 17 en Emergencia y 15 en Dispositivos. Ninguna se aplicó en este PR: **no se editó nada bajo `.claude/`**; las aplica quien mantiene las skills. Las tres que las PoC y las auditorías de #1204 y #1205 dejaron listas para sumar ya:

| # | Tipo | Destino | Regla | Fichas |
|---|---|---|---|---|
| RP-1 | skill + rúbrica | `.claude/skills/seguridad-django/SKILL.md` (API de campo) y `.claude/skills/auditoria/rubricas/` (seguridad) | **La idempotencia por `uuid_cliente` pasa la guarda de alcance en todas las ramas `ya_existia`.** Es un atajo de lectura: el objeto que devuelve el reenvío pasa la misma guarda que un GET de ese objeto (dispositivo de la URL, alcance vigente), también en la rama de carrera del `UNIQUE`. En la revisión: por cada `ya_existia`/`ya_estaba`, ¿qué alcance se exigió sobre el objeto **encontrado**, no sobre el de la URL? | E-SEG-01 (#1204) y su seguimiento 1 |
| RP-2 | skill | `.claude/skills/seguridad-django/SKILL.md` (datos personales) | **Toda resolución por DNI que escribe compara el nombre** (`nombre_en_conflicto`): toda resolución de persona por DNI que escribe sobre el legajo o le abre una estadía compara nombre y apellido declarados con el legajo encontrado; el DNI solo identifica, no autoriza a escribir. | E-ERR-01 (#1205) |
| RP-3 | control mecánico + skill | `users/tests/` o `programas/tests/test_roles_atajos.py` (ratchet) y `.claude/skills/seguridad-django/SKILL.md` | **Todo atajo que otorga roles aplica la misma guarda que el ABM de usuarios** (la guarda del ABM de usuarios, patrón de #1114). Un test recorre los servicios y vistas que otorgan grupos y exige que importen la guarda, con lista congelada, y un test de comportamiento por atajo, con mutación. | D-SEG-01 (R-2 de dispositivos.md) |

## Archivos

| Archivo | Qué es |
|---|---|
| [METODO.md](METODO.md) | El método de la serie: revisores por tajada, alcance, pasos, banco y modelos |
| [becas.md](becas.md) | Capítulo 1 · Becas, 6 tajadas, 151 fichas |
| [emergencia.md](emergencia.md) | Capítulo 2 · Emergencia, 4 tajadas, 93 fichas, con la sección 10 de seguimiento |
| [dispositivos.md](dispositivos.md) | Capítulo 3 · Dispositivos, 4 tajadas, 93 fichas, con las 8 resoluciones del juez |

Notas cruzadas entre capítulos: D-ERR-06 cubre también `programas/views/diseno.py:287` de Becas (nota en [becas.md](becas.md), Ola 6); D-LIM-26 es B-LIM-38 de Becas (arreglo único); el orden de candados es el mismo para Emergencia (E-LIM-15) y Dispositivos (D-ERR-01).

El registro del trabajo está en el Cambio 505 de [requerimientos.md](../requerimientos.md).
