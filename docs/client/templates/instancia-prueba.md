# :material-clipboard-play-outline: Instancia de Prueba

!!! abstract "Plantilla"
    Una **ejecución concreta** de un caso base. Cada instancia (`EX-…`) referencia siempre a **un único caso base** (`CB-…`) y captura el resultado de esa corrida específica.

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-tag-outline: **Código de instancia** | `EX-LOGIN-2026-05-15` |
| :material-bookmark-outline: **Caso base relacionado** | *Login / Registro de ciudadano / etc.* |
| :material-link-variant: **Issue relacionado** | `#<número>` |
| :material-calendar-outline: **Fecha de ejecución** | `YYYY-MM-DD` |
| :material-server: **Entorno** | local / staging / producción |
| :material-source-commit: **Versión / Commit** | *hash corto* |
| :material-account-outline: **Ejecutado por** | *Nombre* |

---

## :material-bookmark-multiple-outline: Referencia al caso base

| Campo | Valor |
|---|---|
| **Caso base** | *Link o nombre del caso base* |
| **Motivo de la ejecución** | Regresión / Validación post cambio / Sprint / etc. |

---

## :material-format-letter-case: Convención de nombres

!!! info "Reglas"
    - :material-bookmark: **Casos base:** `CB-<NOMBRE>`
    - :material-clipboard-play-outline: **Instancias de prueba:** `EX-<NOMBRE>-<YYYY-MM-DD>`
    - :material-link-variant: **Regla:** una instancia siempre debe referenciar **un único** caso base.

---

## :material-checkbox-multiple-marked-outline: Preparación

- [ ] Entorno listo
- [ ] Datos de prueba cargados
- [ ] Dependencias habilitadas
- [ ] Accesos verificados

---

## :material-clipboard-check-outline: Resultado de la ejecución

| Criterio | Estado | Observación |
|---|:-:|---|
| *Criterio* | :material-check-circle: OK / :material-close-circle: FALLO / :material-clock-outline: PENDIENTE | *Nota* |
| *Criterio* | :material-check-circle: OK / :material-close-circle: FALLO / :material-clock-outline: PENDIENTE | *Nota* |

---

## :material-image-multiple-outline: Evidencia

!!! note ""
    *Capturas, links, logs o referencias a reportes.*

---

## :material-flag-checkered: Conclusión

=== ":material-check-circle: Aprobado"

    La instancia cumple todos los criterios sin observaciones.

=== ":material-alert-circle-outline: Aprobado con observaciones"

    La instancia cumple los criterios principales pero quedan notas para próximas iteraciones.

=== ":material-close-circle: Rechazado"

    Uno o más criterios fallaron. Requiere corrección y nueva ejecución.
