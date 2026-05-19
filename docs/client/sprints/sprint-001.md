# :material-sprout: Sprint 001 — Gestión base de ciudadanos

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En progreso

-   :material-calendar-range: **Período**

    12 may → 23 may 2026

-   :material-counter: **Avance**

    1 / 2 funcionalidades

-   :material-clock-outline: **Horas estimadas**

    36 hs totales

</div>

!!! abstract "Objetivo"
    Implementar el flujo completo de **ingreso y derivación de ciudadanos**: desde el registro inicial hasta la derivación a un programa con trazabilidad en el legajo.

---

## :material-clipboard-list-outline: Alcance del sprint

Este sprint cubre **dos funcionalidades centrales** del módulo de Legajos:

| # | Funcionalidad | Prioridad | Estado | Hs est. | Hs reales |
|:-:|---|:-:|:-:|:-:|:-:|
| 1 | [**Registro de ciudadano**](#registro-de-ciudadano) | :material-alert-octagon-outline: Alta | :material-check-circle: Completado | 16 | 14 |
| 2 | [**Derivación a programa**](#derivacion-a-programa) | :material-alert-octagon-outline: Alta | :material-progress-clock: En progreso | 20 | — |

---

## :material-account-plus-outline: Registro de ciudadano { #registro-de-ciudadano }

!!! success "Funcionalidad completada"
    Permite al operador **registrar un ciudadano nuevo** en el sistema, con verificación de duplicados y consulta automática a **RENAPER** para autocompletar datos.

### :material-format-list-checks: Tareas

| Tarea | Estado | Hs est. | Hs reales |
|---|:-:|:-:|:-:|
| Validación de DNI duplicado en el formulario | :material-check-circle: | 3 | 2 |
| Integración con RENAPER y autocompletado | :material-check-circle: | 5 | 5 |
| Formulario de registro manual (fallback) | :material-check-circle: | 3 | 3 |
| Estado "pendiente de verificación" para legajos sin DNI | :material-check-circle: | 2 | 2 |
| Auditoría de creación (quién y cuándo) | :material-check-circle: | 1 | 1 |
| Tests y validación | :material-check-circle: | 2 | 1 |
| **Subtotal** | | **16** | **14** |

### :material-clipboard-text-outline: Requerimientos

| ID | Descripción | Prioridad | Estado |
|---|---|:-:|:-:|
| **RF-001-01** | El sistema verifica si el DNI ya existe antes de crear un legajo nuevo | Alta | :material-check-circle: |
| **RF-001-02** | El sistema consulta RENAPER y autocompleta nombre, apellido y fecha de nacimiento | Alta | :material-check-circle: |
| **RF-001-03** | Si RENAPER no responde, el sistema habilita el formulario manual sin bloquear el flujo | Alta | :material-check-circle: |
| **RF-001-04** | El sistema permite registrar un ciudadano sin DNI, marcándolo como pendiente de verificación | Media | :material-check-circle: |
| **RF-001-05** | El formulario valida el formato del DNI antes de consultar | Alta | :material-check-circle: |
| **RF-001-06** | El sistema registra quién creó el legajo y en qué fecha | Alta | :material-check-circle: |
| **RF-001-07** | El operador puede adjuntar una foto al momento del registro | Baja | :material-pause-circle-outline: Postergado |

### :material-check-decagram-outline: Criterios de aceptación

- [x] Dado un operador con permisos, cuando ingresa un DNI existente, entonces el sistema muestra el legajo existente y no crea uno nuevo.
- [x] Dado un operador con permisos, cuando ingresa un DNI nuevo y RENAPER responde, entonces el sistema autocompleta los datos.
- [x] Dado un operador con permisos, cuando RENAPER no responde, entonces el sistema habilita el formulario manual.
- [x] Dado un operador con permisos, cuando registra sin DNI, entonces el legajo queda en estado "pendiente de verificación".
- [x] Dado un usuario sin permisos, cuando intenta acceder al formulario, entonces recibe un error 403.

---

## :material-account-arrow-right-outline: Derivación a programa { #derivacion-a-programa }

!!! info "Funcionalidad en progreso"
    Permite al operador **derivar un ciudadano a un programa social** con flujo de aceptación/rechazo por parte del dispositivo receptor y trazabilidad completa en el legajo.

### :material-format-list-checks: Tareas

| Tarea | Estado | Hs est. | Hs reales |
|---|:-:|:-:|:-:|
| Formulario de derivación (programa, dispositivo, motivo) | :material-progress-clock: | 4 | — |
| Flujo de aceptación y rechazo por el receptor | :material-clock-outline: | 6 | — |
| Notificación interna al receptor | :material-clock-outline: | 3 | — |
| Bloqueo de derivación duplicada al mismo programa | :material-clock-outline: | 2 | — |
| Historial de derivaciones en el legajo | :material-clock-outline: | 3 | — |
| Anulación de derivación pendiente (admin) | :material-clock-outline: | 1 | — |
| Vencimiento automático por plazo configurable | :material-clock-outline: | 1 | — |
| **Subtotal** | | **20** | **—** |

### :material-clipboard-text-outline: Requerimientos

| ID | Descripción | Prioridad | Estado |
|---|---|:-:|:-:|
| **RF-002-01** | El operador puede iniciar una derivación desde el legajo del ciudadano | Alta | :material-progress-clock: |
| **RF-002-02** | El formulario incluye programa destino, dispositivo, motivo y observaciones | Alta | :material-progress-clock: |
| **RF-002-03** | El sistema notifica al dispositivo receptor al crear la derivación | Alta | :material-clock-outline: |
| **RF-002-04** | El receptor puede aceptar o rechazar con motivo obligatorio al rechazar | Alta | :material-clock-outline: |
| **RF-002-05** | El sistema bloquea derivar a un ciudadano ya inscripto en el mismo programa | Alta | :material-clock-outline: |
| **RF-002-06** | El legajo muestra el historial completo de derivaciones | Alta | :material-clock-outline: |
| **RF-002-07** | El administrador puede anular una derivación en estado pendiente | Media | :material-clock-outline: |
| **RF-002-08** | El sistema marca como vencida una derivación sin respuesta tras el plazo configurado | Media | :material-clock-outline: |

### :material-check-decagram-outline: Criterios de aceptación

- [ ] Dado un operador con permisos, cuando inicia una derivación, entonces el sistema la registra como "Pendiente" y notifica al receptor.
- [ ] Dado un operador receptor, cuando acepta, entonces el ciudadano queda inscripto y el estado cambia a "Aceptada".
- [ ] Dado un operador receptor, cuando rechaza sin motivo, entonces el sistema no permite enviar el formulario.
- [ ] Dado un ciudadano ya inscripto en un programa, cuando se intenta derivarlo al mismo programa, entonces el sistema bloquea la acción.
- [ ] Dado un administrador, cuando anula una derivación pendiente, entonces el estado cambia a "Anulada" y se notifica a ambos operadores.

---

## :material-package-variant-closed-remove: Qué quedó fuera de este sprint

| Funcionalidad | Motivo | ¿Próximo sprint? |
|---|---|:-:|
| Adjuntar foto al registro (RF-001-07) | Baja prioridad, no bloquea el flujo principal | :material-check: Sí |
| Derivaciones entre instituciones | Requiere análisis funcional propio | :material-help-circle-outline: A definir |
| Reportes de derivaciones | Requiere análisis funcional propio | :material-help-circle-outline: A definir |
