---
hide:
  - navigation
---

# Chaco — Centro de Control del Proyecto

!!! abstract "Espacio único de seguimiento"
    Toda la información funcional y técnica del proyecto en un solo lugar: alcance, metodología, versiones, evidencias y plantillas operativas. Mantenido por el equipo, accesible para el cliente.

---

## :material-radar: Estado del proyecto

<div class="grid cards" markdown>

-   :material-progress-clock: **Estado actual**

    ---

    :material-circle:{ .lg .middle style="color: #f59e0b" } **En ejecución**

    Versión activa en curso, entregas iterativas confirmadas.

-   :material-rocket-launch-outline: **Versión activa**

    ---

    [**Versión 001**](versiones/version-001.md) — Programa Becas y RBAC

    Gestión de roles y análisis funcional del Programa Becas.

-   :material-cash-check-outline: **Estado financiero**

    ---

    **Junio 2026 (cerrado):** 499h consumidas de 500h (100%) — dentro del presupuesto

    [:octicons-arrow-right-16: Ver dashboard](financiero/mes-2026-06.md)

-   :material-calendar-clock: **Última actualización**

    ---

    **2 de julio 2026**

    Documentación viva — se actualiza al cierre de cada versión.

</div>

---

## :material-compass-outline: Accesos principales

<div class="grid cards" markdown>

-   :material-flag-checkered:{ .lg .middle } **Proyecto**

    ---

    Bases del trabajo conjunto entre ICORE y el cliente.

    [:octicons-arrow-right-16: Kick Off](kickoff.md)
    [:octicons-arrow-right-16: Equipo](team.md)
    [:octicons-arrow-right-16: Metodología](methodology.md)
    [:octicons-arrow-right-16: Arquitectura](architecture.md)
    [:octicons-arrow-right-16: Minutas](minutas/index.md)

-   :material-package-variant-closed:{ .lg .middle } **Versiones**

    ---

    Planificación y seguimiento de entregas iterativas.

    [:octicons-arrow-right-16: Todas las versiones](versiones/index.md)
    [:octicons-arrow-right-16: Versión actual](versiones/version-001.md)

-   :material-cash-multiple:{ .lg .middle } **Financiero**

    ---

    Presupuesto, consumo y estimaciones mensuales.

    [:octicons-arrow-right-16: Dashboard financiero](financiero/index.md)
    [:octicons-arrow-right-16: Junio 2026](financiero/mes-2026-06.md)

</div>

---

## :material-sitemap: Flujo operativo

```mermaid
flowchart LR
    A([Requerimiento]) --> B[Validar alcance]
    B --> C[Priorizar y<br/>asignar a sprint]
    C --> D[Ejecutar<br/>con trazabilidad]
    D --> E[Validar con<br/>pruebas y evidencia]
    E --> F([Cerrar sprint<br/>con reporte])

    classDef step fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b
    classDef start fill:#ddd6fe,stroke:#7c3aed,color:#2e1065
    class B,C,D,E step
    class A,F start
```

1. **Registrar** el requerimiento y validar alcance.
2. **Priorizar** y asignar al sprint correspondiente.
3. **Ejecutar** desarrollo con trazabilidad en issues y PR.
4. **Validar** con pruebas funcionales y evidencia.
5. **Cerrar** sprint con reporte de resultados.

---

## :material-account-group-outline: Qué revisar según tu rol

=== ":material-clipboard-text-outline: Referente funcional"

    | Para qué | Ir a |
    |---|---|
    | Alinear objetivos y alcance | [Kick Off](kickoff.md) |
    | Entender el ciclo de trabajo | [Metodología](methodology.md) |
    | Seguir avances y entregas | [Versiones](versiones/index.md) |

=== ":material-code-tags: Desarrollo"

    | Para qué | Ir a |
    |---|---|
    | Stack, capas y decisiones técnicas | [Arquitectura](architecture.md) |
    | Versión activa y backlog | [Versiones](versiones/index.md) |
    | Estimar requerimientos | [Plantilla de estimación](templates/estimacion.md) |

=== ":material-checkbox-marked-circle-outline: QA y validación"

    | Para qué | Ir a |
    |---|---|
    | Diseñar casos de prueba base | [Caso de prueba base](templates/caso-prueba-base.md) |
    | Registrar ejecuciones | [Instancia de prueba](templates/instancia-prueba.md) |
    | Cerrar la ronda de testing | [Reporte de pruebas](templates/reporte-pruebas.md) |

---

## :material-map-marker-path: Navegación recomendada

!!! tip "Si recién empezás"
    [**Kick Off**](kickoff.md) :material-arrow-right: [**Metodología**](methodology.md) :material-arrow-right: [**Versión actual**](versiones/version-001.md)

    Tres páginas y tenés el contexto completo para participar.
