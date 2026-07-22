# :material-clipboard-check-multiple-outline: Reporte de Pruebas

!!! abstract "Plantilla"
    Cierre formal de una ronda de pruebas. Documenta el **resultado por criterio de aceptación**, los defectos encontrados y la recomendación final (desplegar / repetir / rechazar).

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-bookmark-outline: **Caso base relacionado** | *Login / Registro / etc.* |
| :material-link-variant: **Issue de requerimiento** | `#<N>` — *Título* |
| :material-bug-outline: **Issue de testing** | `#<N>` |
| :material-calendar-outline: **Fecha de ejecución** | `YYYY-MM-DD` |
| :material-account-outline: **Ejecutado por** | *Nombre del tester* |
| :material-server: **Entorno** | Staging / Producción / Local |
| :material-source-commit: **Versión / Commit** | *hash corto* |

---

## :material-chart-box-outline: Resumen

| :material-counter: Criterios totales | :material-check-circle: OK | :material-close-circle: Fallaron | :material-clock-outline: Pendientes |
|:-:|:-:|:-:|:-:|
| **N** | **N** | **N** | **N** |

!!! success "Resultado general"
    **Aprobado** / **Aprobado con observaciones** / **Rechazado**

---

## :material-format-list-checks: Resultados por criterio de aceptación

| # | Criterio | Resultado | Observaciones |
|:-:|---|:-:|---|
| 1 | *Descripción* | :material-check-circle: OK / :material-close-circle: Fallo / :material-clock-outline: Pendiente | *Nota* |
| 2 | *Descripción* | :material-check-circle: OK / :material-close-circle: Fallo / :material-clock-outline: Pendiente | *Nota* |
| 3 | *Descripción* | :material-check-circle: OK / :material-close-circle: Fallo / :material-clock-outline: Pendiente | *Nota* |

---

## :material-checkbox-multiple-marked-outline: Casos probados

- [ ] :material-road-variant: Flujo principal (camino feliz)
- [ ] :material-form-textbox: Validaciones de campos obligatorios
- [ ] :material-alert-circle-outline: Manejo de errores y mensajes al usuario
- [ ] :material-arrow-expand-horizontal: Casos borde (valores límite, datos vacíos)
- [ ] :material-history: Regresión: funcionalidades existentes no afectadas
- [ ] :material-shield-account-outline: Permisos y acceso por rol

---

## :material-bookmark-multiple-outline: Referencia al caso base

| Campo | Valor |
|---|---|
| **Caso base** | *Link o nombre del caso maestro* |
| **Versión del caso base** | `YYYY-MM-DD` o versión |
| **Instancia actual** | *Link a esta corrida* |

---

## :material-bug-outline: Observaciones y defectos encontrados

??? danger "Defecto 1 (si aplica)"
    - **Descripción:** *Qué falla*
    - **Pasos para reproducir:** *Cómo se reproduce*
    - **Severidad:** :material-alert-octagon-outline: Alta / :material-alert-outline: Media / :material-information-outline: Baja
    - **Issue creado:** `#<N>` (si se abrió un issue de bug)

---

## :material-image-multiple-outline: Evidencia

!!! note ""
    *Links a capturas, videos o logs de la ejecución de pruebas.*

---

## :material-flag-checkered: Conclusión y recomendación

!!! quote ""
    *Indicar si se puede desplegar, si hay items bloqueantes o si se requiere una nueva ronda de pruebas antes del despliegue.*

---

!!! info "Publicación"
    - Reporte publicado en [mkdir-arg.github.io/Chaco-Back](https://mkdir-arg.github.io/Chaco-Back/)
    - :material-check-decagram-outline: Aprobado por el cliente: *Nombre y fecha, o "Pendiente de aprobación"*
