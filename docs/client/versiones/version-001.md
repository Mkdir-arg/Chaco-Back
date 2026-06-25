# :material-package-variant-closed: Versión 001

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En progreso

-   :material-calendar-range: **Período**

    3 jun → 24 jun 2026

-   :material-counter: **Avance**

    —

-   :material-clock-outline: **Horas consumidas**

    167h 3min

</div>

!!! abstract "Objetivo"
    Definir el funcionamiento del **Programa Becas** y desarrollar el **motor RBAC base** para dejar el sistema de permisos operativo.

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado | Hs est. | Hs reales |
|:-:|---|:-:|:-:|:-:|:-:|
| 1 | Programa Becas (análisis) | Alta | En análisis | — | 85h |
| 2 | Motor RBAC base | Alta | Completado | — | 68h |

---

## :material-account-plus-outline: Funcionalidad 1 — Programa Becas { #funcionalidad-1 }

!!! info "Funcionalidad"
    Programa de **relevamiento territorial** para el otorgamiento de becas: los
    equipos de campo registran a las personas, el programa valida la información y
    administra el **cupo** disponible y la **lista de espera**.

### :material-format-list-checks: Tareas

| Tarea | Estado | Hs est. | Hs reales |
|---|:-:|:-:|:-:|
| 1. [Análisis funcional del Programa Becas](../funcionalidades/programa-becas.md) | En progreso | — | — |

### :material-clipboard-text-outline: Requerimientos

| ID | Descripción | Prioridad | Estado |
|---|---|:-:|:-:|
| RQ-01 | Relevar y dejar definido el funcionamiento del Programa Becas. | Alta | En análisis |

### :material-check-decagram-outline: Criterios de aceptación

- [ ] El funcionamiento del programa queda documentado y validado con el cliente.

---

## :material-account-arrow-right-outline: Funcionalidad 2 — ABM de roles y permisos { #funcionalidad-2 }

!!! info "Funcionalidad"
    Gestión de **roles y permisos**: permite dar de alta, modificar y dar de baja
    roles, y definir a qué puede acceder cada uno dentro del sistema.

### :material-format-list-checks: Tareas

| Tarea | Estado | Hs est. | Hs reales |
|---|:-:|:-:|:-:|
| 1. Análisis funcional del ABM de roles y permisos | Por iniciar | — | — |

### :material-clipboard-text-outline: Requerimientos

| ID | Descripción | Prioridad | Estado |
|---|---|:-:|:-:|
| RQ-01 | Administrar roles (alta, baja y modificación) y sus permisos de acceso. | Alta | Por iniciar |

### :material-check-decagram-outline: Criterios de aceptación

- [ ] Se pueden crear, editar y eliminar roles, y asignarles permisos.

---

## :material-package-variant-closed-remove: Qué quedó fuera de esta versión

| Funcionalidad | Motivo | ¿Próxima versión? |
|---|---|:-:|

---

## :material-calendar-star: Eventos y reuniones

| # | Evento | Fecha | Integrantes | Minuta |
|:-:|---|:-:|---|:-:|
| 1 | Reunión 1 — Inicio de proyecto | 2026-06-03 | **ICORE:** Agostina Coppola, Matías Fariña · **Ministerio:** Guido Cortiglia, Claudia Miserachs, Walter Giordano | [Ver minuta](../minutas/reunion-inicio-proyecto-2026-06-03.md) |

---

## :material-timer-sand-complete: Detalle de consumo de horas

Consulta el detalle de consumo por persona y motivo de la Versión 001.

[:material-table-arrow-right: Ver detalle de consumo](version-001-consumo-horas.md){ .md-button .md-button--primary }
