# :material-calculator-variant-outline: Planilla de Estimación de Horas

!!! abstract "Plantilla"
    Estimación formal de un requerimiento. Se presenta como **rango (mínimo / máximo)** para contemplar variabilidad. La aprobación queda registrada como comentario en el Issue antes de iniciar el desarrollo.

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-link-variant: **Issue** | `#<número>` — *Título del requerimiento* |
| :material-calendar-outline: **Fecha de estimación** | `YYYY-MM-DD` |
| :material-account-edit-outline: **Estimado por** | *Nombre del estimador* |

---

## :material-text-box-outline: Descripción del requerimiento

!!! quote ""
    *Resumen breve del requerimiento a estimar.*

---

## :material-format-list-numbered: Desglose por etapa

| Etapa | Horas mín. | Horas máx. | Notas |
|---|:-:|:-:|---|
| :material-clipboard-search-outline: Análisis | *N* | *N* | *Observaciones* |
| :material-book-open-page-variant-outline: Documentación | *N* | *N* | *Observaciones* |
| :material-code-braces: Desarrollo | *N* | *N* | *Observaciones* |
| :material-test-tube: Pruebas | *N* | *N* | *Observaciones* |
| :material-school-outline: Capacitación | *N* | *N* | Solo si aplica |
| :material-rocket-launch-outline: Despliegue | *N* | *N* | *Observaciones* |
| **:material-sigma: TOTAL** | **N** | **N** | |

---

## :material-shield-check-outline: Supuestos y condiciones

!!! info "Si alguno cambia, la estimación puede variar"

    - [x] El entorno de staging está disponible y funcionando.
    - [x] No hay cambios de alcance durante el desarrollo.
    - [x] El cliente responde consultas dentro de 24 horas hábiles.
    - [ ] *Agregar otros supuestos*

---

## :material-alert-octagon-outline: Riesgos que pueden impactar la estimación

| Riesgo | Probabilidad | Impacto estimado |
|---|:-:|:-:|
| *Riesgo* | Alta / Media / Baja | +*N* hs |

---

## :material-wallet-outline: Saldo de horas del cliente

| Concepto | Valor |
|---|---|
| :material-counter: **Saldo actual** | *N hs* *(a validar con el coordinador antes de confirmar)* |
| :material-clock-alert-outline: **Horas requeridas (rango)** | *N – N hs* |
| :material-check-circle-outline: **¿Saldo suficiente?** | Sí / No — si no, indicar qué hacer |

---

## :material-check-decagram-outline: Aprobación del cliente

!!! quote "Constancia de aprobación"
    La estimación fue presentada y aprobada por:

    - :material-account-outline: **Nombre:** *Referente ICORE*
    - :material-calendar-check-outline: **Fecha de aprobación:** `YYYY-MM-DD`
    - :material-message-outline: **Medio:** Comentario en issue / Email

---

!!! warning "Antes de iniciar el desarrollo"
    Registrar la aprobación como **comentario en el issue `#N`**.
