# :material-cash-multiple: Módulo Financiero

!!! abstract "Seguimiento de presupuesto y consumo"
    Vista consolidada mensual del presupuesto, horas consumidas y estimaciones comprometidas. Permite al cliente tener visibilidad centralizada del estado financiero del proyecto.

---

## :material-calendar-month: Meses activos

<div class="grid cards" markdown>

-   :material-calendar-check: **Junio 2026**

    ---

    :material-wallet-outline: Presupuesto: **714 horas**  
    :material-clock-check-outline: Consumido: **167 horas** (23%)  
    :material-calculator-variant-outline: Estimado: **654 horas** (92%)  
    :material-alert-circle-outline: Saldo: **-107 horas** (excedido)

    **Estado:** :material-circle:{ style="color: #ef4444" } Presupuesto excedido

    [:octicons-arrow-right-16: Ver dashboard](mes-2026-06.md)

</div>

---

## :material-archive-outline: Histórico de meses cerrados

!!! info "Aún no hay meses cerrados"
    Los meses completados aparecerán acá con su resumen final de consumo vs estimado.

| Mes | Presupuesto | Consumido | Estimado | Saldo | Estado |
|---|---:|---:|---:|---:|:-:|
| — | — | — | — | — | — |

---

## :material-chart-line: Indicadores del proyecto

### Salud financiera

| Indicador | Valor | Estado |
|---|---:|:-:|
| **Compromiso total (consumo + estimado)** | 821h | :material-circle:{ style="color: #ef4444" } Excede presupuesto (+107h) |
| **Consumo real (acumulado)** | 167h | :material-circle:{ style="color: #f59e0b" } 23% del presupuesto |
| **Desviación vs estimado** | Por determinar | :material-clock-outline: Pendiente |

---

## :material-information-outline: Cómo interpretar los dashboards

<div class="grid cards" markdown>

-   :material-wallet-outline: **Presupuesto mensual**

    Horas contratadas y disponibles para el mes. Se acuerda al inicio del período.

-   :material-clock-check-outline: **Consumo real**

    Horas trabajadas y registradas en el detalle de consumo de cada versión.

-   :material-calculator-variant-outline: **Estimado comprometido**

    Horas estimadas para funcionalidades aprobadas que aún no se ejecutaron.

-   :material-alert-circle-outline: **Saldo disponible**

    Presupuesto - (Consumo real + Estimado comprometido). Margen para nuevos requerimientos.

</div>

---

## :material-alert-decagram-outline: Sistema de alertas

| Color | Significado | Acción recomendada |
|:-:|---|---|
| :material-circle:{ style="color: #10b981" } Verde | Saldo > 15% del presupuesto | Operación normal |
| :material-circle:{ style="color: #f59e0b" } Ámbar | Saldo entre 5% y 15% | Monitorear de cerca |
| :material-circle:{ style="color: #ef4444" } Rojo | Saldo < 5% o comprometido al 100% | Bloquear nuevos compromisos |

---

[:material-home: Volver al inicio](../index.md){ .md-button }
