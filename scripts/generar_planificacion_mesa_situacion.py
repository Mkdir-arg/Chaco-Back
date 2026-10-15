"""Genera el anexo de planificación y sus gráficos a partir de horas verificables.

Ejecutar con el venv del repositorio y matplotlib instalado. No cambia dependencias
de la aplicación. Los SVG y PNG se publican como archivos estáticos de MkDocs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs/client/propuestas"
ASSETS = DOCS / "assets"
DATA = json.loads((ASSETS / "planificacion-mesa-horas.json").read_text(encoding="utf-8"))
CAPACITY = DATA["capacity_per_person_month"]
PLANS = DATA["plans"]
COLORS = {"analisis": "#0f766e", "desarrollo": "#2563eb", "qa": "#7c3aed", "capacitacion": "#b45309"}
LINE_COLORS = ["#0f766e", "#2563eb", "#7c3aed"]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none", "svg.hashsalt": "mesa-situacion-plan-v1", "axes.spines.top": False, "axes.spines.right": False, "axes.labelcolor": "#334155", "text.color": "#172554"})


def number(value):
    return f"{value:,}".replace(",", ".")


def pct(value, total):
    return f"{value / total * 100:.1f}".replace(".", ",") + "%"


def monthly(plan):
    return [sum(values[i] for values in plan["hours"].values()) for i in range(plan["months"])]


def active_people(plan, role):
    values = plan["hours"][role]
    if role == "Análisis funcional":
        values = [a + b for a, b in zip(values, plan["hours"]["Manuales y capacitación"])]
    return [math.ceil(value / CAPACITY) for value in values]


def validate():
    proposal = (DOCS / "mesa-situacion-el-nino.md").read_text(encoding="utf-8-sig")
    section = proposal.split("### Distribución por disciplina", 1)[1].split("### Distribución de las horas", 1)[0]
    rows = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 4 and all(cell.replace(".", "").isdigit() for cell in cells[1:]):
            rows.append([int(cell.replace(".", "")) for cell in cells[1:]])
    assert len(rows) == 6, "La propuesta debe contener las seis disciplinas presupuestadas"
    for index, plan in enumerate(PLANS):
        expected = [row[index] for row in rows]
        assert [sum(v) for v in plan["hours"].values()] == expected
        assert sum(monthly(plan)) == plan["total"] == sum(expected)
        assert all(len(v) == plan["months"] for v in plan["hours"].values())
        assert all(v >= 0 for values in plan["hours"].values() for v in values)
        assert max(active_people(plan, "Desarrollo")) <= plan["max_developers"]
        assert max(active_people(plan, "Análisis funcional")) <= 2
        for role in ("QA", "UX/UI", "Gestión"):
            assert max(active_people(plan, role)) <= 1
        totals = monthly(plan)
        assert all(a >= b for a, b in zip(totals, totals[1:])), "La dedicación debe descender"
        assert all(0 <= start < end <= plan["months"] for _, start, end, _, _ in plan["phases"])
        assert all(0 < month <= plan["months"] for _, month, _, _ in plan["milestones"])
        print(f'{plan["name"]}: {totals} = {plan["total"]} h; capacidad por perfil OK')


def save(fig, stem):
    fig.savefig(ASSETS / f"{stem}.svg", bbox_inches="tight", facecolor="white", metadata={"Date": None})
    svg = ASSETS / f"{stem}.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
    fig.savefig(ASSETS / f"{stem}.png", bbox_inches="tight", facecolor="white", dpi=160)
    plt.close(fig)


def gantt(plan):
    phases, milestones = plan["phases"], plan["milestones"]
    count = len(phases)
    fig, ax = plt.subplots(figsize=(13.5, count * 0.44 + 2.5))
    fig.subplots_adjust(left=0.28, right=0.97, top=0.79, bottom=0.18)
    for m in range(plan["months"]):
        if m % 2 == 0:
            ax.axvspan(m, m + 1, color="#f1f5f9", zorder=0)
    for row, (label, start, end, kind, _) in enumerate(phases):
        ax.barh(row, end - start, left=start, height=0.56, color=COLORS[kind], zorder=3)
    milestone_row = count + 0.25
    for code, month, _, _ in milestones:
        ax.scatter(month, milestone_row, marker="D", s=48, color="#172554", zorder=4, clip_on=False)
        ax.text(month, milestone_row + 0.42, code, ha="center", va="top", fontsize=9, weight="bold")
    ax.set_yticks(list(range(count)) + [milestone_row], [p[0] for p in phases] + ["Hitos de entrega"])
    ax.tick_params(axis="y", length=0, pad=12)
    ax.set_xticks([i + 0.5 for i in range(plan["months"])], [f"Mes {i + 1}" for i in range(plan["months"])])
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", length=0, pad=10)
    ax.set_xlim(0, plan["months"] + 0.12)
    ax.set_ylim(count + 1.15, -0.7)
    for edge in ax.spines.values():
        edge.set_visible(False)
    for month in range(plan["months"] + 1):
        ax.axvline(month, color="#cbd5e1", linewidth=0.6, zorder=1)
    fig.suptitle(f'{plan["name"]} | Gantt por etapas', x=0.04, ha="left", fontsize=20, weight="bold", y=0.97)
    fig.text(0.04, 0.88, f'{number(plan["total"])} horas totales · {plan["months"]} meses de planificación · mayor dedicación inicial', fontsize=11)
    handles = [Patch(color=COLORS[k], label=t) for k, t in [("analisis", "Definición"), ("desarrollo", "Desarrollo"), ("qa", "Pruebas"), ("capacitacion", "Piloto y capacitación")]]
    handles.append(Line2D([], [], color="#172554", marker="D", linestyle="", label="Hito"))
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.03, 0.025), ncol=5, frameon=False)
    save(fig, f'gantt-{plan["slug"]}')


def curves():
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.subplots_adjust(top=0.76, bottom=0.18, wspace=0.28)
    for plan, color in zip(PLANS, LINE_COLORS):
        values = monthly(plan)
        xs = list(range(1, plan["months"] + 1))
        axes[0].plot(xs, values, marker="o", linewidth=2.5, color=color, label=f'{plan["name"]} ({number(plan["total"])} h)')
        cumulative = [0]
        for value in values:
            cumulative.append(cumulative[-1] + value / plan["total"] * 100)
        axes[1].plot(range(plan["months"] + 1), cumulative, marker="o", linewidth=2.5, color=color)
    axes[0].set_title("Horas asignadas por mes", loc="left", pad=14, weight="bold")
    axes[1].set_title("Horas acumuladas (% del total)", loc="left", pad=14, weight="bold")
    axes[0].set_ylim(0, 1150)
    axes[1].set_ylim(0, 108)
    axes[0].set_ylabel("Horas-persona")
    axes[1].set_ylabel("Porcentaje de horas")
    for ax in axes:
        ax.set_xticks(range(1, 9), [f"M{i}" for i in range(1, 9)])
        ax.set_xlabel("Mes desde el inicio acordado")
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Distribución del esfuerzo: mayor dedicación en los primeros meses", x=0.04, ha="left", fontsize=17, weight="bold", y=0.97)
    fig.text(0.04, 0.87, "Referencia para planificar la inversión; los importes requieren tarifas por perfil y condiciones de facturación.", fontsize=10)
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False)
    save(fig, "curva-esfuerzo")


def month_span(start, end):
    first, last = math.floor(start) + 1, math.ceil(end)
    return f"M{first}" if first == last else f"M{first}–M{last}"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"] + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def document():
    sections = ["""# :material-chart-gantt: Planificación de las tres propuestas

## Gantt, entregables, equipo y distribución de horas

| Campo | Detalle |
|---|---|
| Proyecto | Mesa de Situación del Fenómeno El Niño, Provincia del Chaco |
| Fecha | 15 de octubre de 2026 |
| Estado | Escenarios propuestos para revisión; dedicaciones e hitos a confirmar |
| Criterio de planificación | Concentrar equipo y esfuerzo al comienzo para adelantar entregables utilizables |
| Referencia | [Comparación funcional y estimación de las tres alternativas](mesa-situacion-el-nino.md) |

!!! abstract "Cómo leer este anexo"
    La propuesta base mantiene su estimación en horas. Este anexo distribuye esas mismas horas en escenarios de equipo y calendario. Se elige una alternativa: sus horas y sus meses no se suman con los de las otras.

## 1. Criterio de planificación

Se propone incorporar desde el comienzo a los analistas y al equipo de desarrollo de la alternativa elegida. Diseño y QA acompañan las primeras entregas; el trabajo avanza por circuitos y la dedicación se reduce a medida que se completa el alcance.

La primera versión utilizable de mapa y población se plantea al cierre del mes 2. Operativa e Integral incorporan las cuatro mesas en una versión operativa al cierre del mes 4. En Integral, los movimientos avanzados y el seguimiento completo se entregan después, según los hitos indicados.

### Supuestos del escenario

- M1 es el primer mes desde el inicio acordado. Para distribuir capacidad, cada mes representa un bloque de cuatro semanas; el calendario real se ajustará con la fecha de inicio y los días laborables.
- Se asignan hasta 140 horas de trabajo por persona y mes de planificación. La capacidad incluye las actividades de su disciplina, como revisión y correcciones en desarrollo. Es un supuesto de planificación a confirmar.
- Los totales son los escenarios centrales: 3.250, 4.750 y 6.250 horas. Cada disciplina conserva exactamente sus horas de la propuesta base.
- Los referentes validan cada entrega antes de los circuitos que dependen de ella. Las observaciones se incorporan al trabajo del período siguiente; una demora de validación requiere revisar los hitos.
- Los módulos usan los formatos y reglas acordados. Las decisiones del primer mes habilitan el desarrollo paralelo; el análisis detallado continúa por circuito.
- La mesa de ayuda funcional opcional se contrata aparte y no forma parte de estas curvas. Las ampliaciones independientes tampoco están incluidas.

La inversión se representa mediante horas asignadas. Para convertirla en importes se necesitan tarifas por perfil y condiciones de facturación. El porcentaje de horas acumuladas mide esfuerzo asignado, no porcentaje de funcionalidades aceptadas.

## 2. Comparación de escenarios
"""]
    sections.append(table(["Alternativa", "Horas", "Meses del escenario", "Desarrolladores al inicio", "Horas en M1–M2", "% del total en M1–M2"], [[p["name"], number(p["total"]), p["months"], p["max_developers"], number(sum(monthly(p)[:2])), pct(sum(monthly(p)[:2]), p["total"])] for p in PLANS]))
    sections.append("""
En Integral, los primeros cuatro meses concentran 3.800 horas, el 60,8% del total, y culminan con las cuatro mesas en su versión operativa. El resto del esfuerzo completa los circuitos avanzados, las validaciones y la capacitación.

![Curvas mensuales y acumuladas de horas para las tres alternativas](assets/curva-esfuerzo.svg)

[Abrir gráfico](assets/curva-esfuerzo.svg) · [Descargar PNG](assets/curva-esfuerzo.png)
""")
    for idx, plan in enumerate(PLANS, start=3):
        name, slug, n = plan["name"], plan["slug"], plan["months"]
        sections.append(f"## {idx}. Propuesta {name}\n\n**Escenario:** {number(plan['total'])} horas distribuidas en {n} meses de planificación.\n\n![Gantt de {name}, con etapas y hitos](assets/gantt-{slug}.svg)\n\n[Abrir Gantt](assets/gantt-{slug}.svg) · [Descargar PNG](assets/gantt-{slug}.png)\n\n### Etapas y entregables\n")
        sections.append(table(["Etapa", "Ventana propuesta", "Resultado"], [[phase[0], month_span(phase[1], phase[2]), phase[4]] for phase in plan["phases"]]))
        sections.append("\nLa tabla indica los meses involucrados; las barras del Gantt muestran los solapamientos dentro de cada mes. Las horas de análisis y gestión continúan acompañando las entregas según la asignación mensual.\n\n### Hitos de aceptación\n")
        sections.append(table(["Hito", "Cierre propuesto", "Entregable", "Cómo se verifica"], [[code, f"M{month}", title, criterion] for code, month, title, criterion in plan["milestones"]]))
        sections.append("\nCada hito depende de la validación de los anteriores que alimentan su circuito. Los circuitos avanzados se validan sobre una versión operativa ya integrada.\n\n### Equipo propuesto por mes\n")
        rows = []
        for role in ["Análisis funcional", "Desarrollo", "QA", "UX/UI", "Gestión"]:
            label = "Analistas (incluye manuales y capacitación)" if role == "Análisis funcional" else role
            rows.append([label] + active_people(plan, role))
        sections.append(table(["Perfil / personas participantes"] + [f"M{i}" for i in range(1, n + 1)], rows))
        sections.append(f"\nUn desarrollador asume la conducción técnica dentro de las horas de Desarrollo. Los {plan['max_developers']} desarrolladores iniciales cubren backend, frontend e integración. QA y diseño participan desde el arranque. Las cantidades indican personas participantes, con dedicación parcial cuando corresponda; las horas de la tabla siguiente son la asignación concreta. Manuales y capacitación se reparten entre los analistas, sin contar personal adicional.\n\n### Horas asignadas por perfil y mes\n")
        rows = [[role] + [number(v) for v in values] + [number(sum(values))] for role, values in plan["hours"].items()]
        values = monthly(plan)
        rows.append(["**Total mensual**"] + [f"**{number(v)}**" for v in values] + [f"**{number(sum(values))}**"])
        rows.append(["% del esfuerzo total"] + [pct(v, plan["total"]) for v in values] + ["100%"])
        cumulative = []
        current = 0
        for value in values:
            current += value
            cumulative.append(number(current))
        rows.append(["Horas acumuladas"] + cumulative + [number(plan["total"])])
        sections.append(table(["Disciplina"] + [f"M{i}" for i in range(1, n + 1)] + ["Total"], rows))
        sections.append("\nLos porcentajes se redondean a un decimal. Las horas de las tablas mensuales son las mismas del presupuesto de esfuerzo, distribuidas por período.\n")
    sections.append("""## 6. Qué se entrega y qué habilita el avance

Cada entrega incluye una demostración con datos de prueba, casos verificables y registro de observaciones. Una versión utilizable permite probar el circuito incluido con usuarios habilitados; la conformidad final exige los casos de aceptación y las pruebas de concurrencia acordadas para la alternativa.

La capacitación acompaña las entregas y se refuerza en el cierre. Los hitos funcionales orientan el seguimiento y la aceptación; cualquier esquema de facturación por hito se acuerda por separado.

La planificación deberá ajustarse si cambia el alcance, la dedicación real o la disponibilidad de los referentes. El esfuerzo total seguirá expresándose en horas y cada revisión identificará qué entregables y asignaciones cambian.

## 7. Datos de planificación

Las tablas y los gráficos se generan con una única distribución de horas por perfil. Puede descargarse el [archivo de datos](assets/planificacion-mesa-horas.json) para revisar las asignaciones. Las sumas por disciplina coinciden con la [propuesta funcional](mesa-situacion-el-nino.md#6-horas-de-trabajo-por-alternativa).
""")
    (DOCS / "planificacion-mesa-situacion-el-nino.md").write_text("\n\n".join(sections).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    validate()
    for plan in PLANS:
        gantt(plan)
    curves()
    document()
    print("Anexo, tres Gantt y curva de esfuerzo generados.")
