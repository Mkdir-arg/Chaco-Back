# -*- coding: utf-8 -*-
"""Audita la coherencia del registro de horas del cliente.

Comprueba que cada numero publicado en docs/client/financiero/ se corresponda con la suma
de las filas del registro dia por dia: totales de seccion, totales mensuales, tablas por
programa y por persona, contador del proyecto, indice financiero y portada.

Uso:  python scripts/auditar_horas.py [raiz-del-repo]
Sale con codigo 1 si encuentra una diferencia.
"""

import io
import os
import re
import sys

RAIZ = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIN = os.path.join(RAIZ, "docs", "client", "financiero")
fallos = []


def ok(cond, msg):
    print(("  OK    " if cond else "  FALLA ") + msg)
    if not cond:
        fallos.append(msg)


def leer(p):
    return io.open(p, encoding="utf-8").read()


def cant(c):
    """Devuelve horas desde '8 h', '2,5 h', '480 min', '13 h 25 min' o '—'."""
    c = c.strip().strip("*")
    if c in ("—", "-", ""):
        return None
    m = re.fullmatch(r"([\d.]+) h (\d{1,2}) min", c)
    if m:
        return int(m.group(1).replace(".", "")) + int(m.group(2)) / 60
    m = re.fullmatch(r"(\d+) min", c)
    if m:
        return int(m.group(1)) / 60
    m = re.fullmatch(r"([\d.]+)(?:,(\d))? h(?: \(100%\))?", c)
    if m:
        return float(m.group(1).replace(".", "")) + (int(m.group(2)) / 10 if m.group(2) else 0)
    return None


det = leer(os.path.join(FIN, "detalle-tareas.md"))
lineas = det.split("\n")
PAT_ENT = re.compile(r"^\| ([0-3]\d(?:[-–][0-3]\d)?)/(0[6-9]|1[0-2]) \|")
PAT_DIA = re.compile(r"^\| (\d{4})-(\d{2})-(\d{2}) \|")

print("=== 1. Filas del registro, por mes ===")
mes_h, mes_per, mes_prog = {}, {}, {}
for ln in lineas:
    c = [x.strip() for x in ln.split("|")]
    m = PAT_ENT.match(ln)
    if m:
        mes, per, prog, h = m.group(2), c[2], c[3], cant(c[-3])
    else:
        m = PAT_DIA.match(ln)
        if not m:
            continue
        mes, per, h = m.group(2), c[2], cant(c[-2])
        prog = c[3] if len(c) >= 8 else None
    if h is None:
        fallos.append(f"fila sin consumo legible: {ln[:70]}")
        continue
    mes_h[mes] = mes_h.get(mes, 0) + h
    mes_per.setdefault(mes, {})[per] = mes_per.setdefault(mes, {}).get(per, 0) + h
    if prog in ("Becas", "Transversal", "Dispositivos"):
        mes_prog.setdefault(mes, {})[prog] = mes_prog.setdefault(mes, {}).get(prog, 0) + h


def hm(x):
    return f"{int(round(x * 60)) // 60} h {int(round(x * 60)) % 60:02d} min"


for k in sorted(mes_h):
    print(f"  {k}: {hm(mes_h[k])} en filas")

print("\n=== 2. Totales mensuales publicados vs filas ===")
DECL = {"06": 499 + 12 / 60, "07": 500.0, "08": 803.5, "09": 839.0, "10": 430.5}
for k in sorted(DECL):
    ok(abs(mes_h.get(k, 0) - DECL[k]) < 0.02, f"{k}: publicado {hm(DECL[k])} vs filas {hm(mes_h.get(k, 0))}")

print("\n=== 3. Totales de cada sección por entregable ===")
acum = 0.0
for ln in lineas:
    if PAT_ENT.match(ln):
        h = cant([x.strip() for x in ln.split("|")][-3])
        acum += h or 0
        continue
    mt = re.match(r"^\| *\| *\| *\| \*\*Total ([^*]+)\*\* \| *\| \*\*([^*]+)\*\* \|", ln)
    if mt:
        d = cant(mt.group(2))
        ok(abs(acum - d) < 0.01, f"Total {mt.group(1)}: publicado {d} h vs filas {acum:g} h")
        acum = 0.0

print("\n=== 4. Tablas «por programa» ===")
TRAS = {"09": 103.5, "10": 92.5}
TABLAS = [
    ("06", "Consumo de junio por programa"),
    ("07", "Consumo de julio por programa"),
    ("08", "Esfuerzo real de agosto por programa"),
    ("09", "Consumo de septiembre por programa"),
    ("10", "Consumo de octubre por programa"),
]
for mes, titulo in TABLAS:
    i = next((k for k, ln in enumerate(lineas) if titulo in ln), None)
    if i is None:
        ok(False, f"falta la tabla «{titulo}»")
        continue
    tabla, total_decl = {}, None
    for ln in lineas[i : i + 14]:
        c = [x.strip() for x in ln.split("|")]
        if len(c) != 4:
            continue
        if c[1].startswith("**"):
            total_decl = cant(c[2])
        elif cant(c[2]) is not None:
            tabla[re.sub(r"\s*\(.*", "", c[1])] = cant(c[2])
    suma = sum(tabla.values())
    ok(
        total_decl is not None and abs(suma - total_decl) < 0.02,
        f"{titulo}: filas de la tabla suman {hm(suma)} vs total declarado {hm(total_decl or 0)}",
    )
    esperado = mes_h[mes] + TRAS.get(mes, 0)
    ok(
        abs(suma - esperado) < 0.02,
        f"{titulo}: total {hm(suma)} vs registro{' + traslado' if mes in TRAS else ''} {hm(esperado)}",
    )
    if mes in ("09", "10"):
        reg = dict(mes_prog.get(mes, {}))
        reg["Becas"] = reg.get("Becas", 0) + TRAS[mes]
        for p in sorted(set(tabla) | set(reg)):
            ok(
                abs(tabla.get(p, 0) - reg.get(p, 0)) < 0.02,
                f"{titulo} — {p}: {hm(tabla.get(p, 0))} vs filas {hm(reg.get(p, 0))}",
            )

print("\n=== 5. Acumulado por persona ===")
i = next(k for k, ln in enumerate(lineas) if "Consumo por persona — acumulado del proyecto" in ln)
cab = [x.strip() for x in lineas[i + 2].split("|")]
cols = {}
for j, x in enumerate(cab):
    for nombre, mes in (("Junio", "06"), ("Julio", "07"), ("Agosto", "08"), ("Septiembre", "09"), ("Octubre", "10")):
        if x.startswith(nombre):
            cols[j] = mes
suma_col, suma_tot, total_fila = {}, 0.0, None
for ln in lineas[i + 3 :]:
    if not ln.startswith("|"):
        break
    c = [x.strip() for x in ln.split("|")]
    if set(c[1]) <= set("-: ") or not c[1]:
        continue
    if c[1].startswith("**Total"):
        total_fila = {j: cant(x) for j, x in enumerate(c) if cant(x) is not None}
        continue
    for j, mes in cols.items():
        if c[j] not in ("—", ""):
            suma_col[j] = suma_col.get(j, 0) + float(c[j].replace(",", "."))
    suma_tot += cant(c[-2]) or 0
for j, mes in cols.items():
    ok(
        abs(suma_col.get(j, 0) - mes_h[mes]) < 0.6,
        f"columna {cab[j]}: personas suman {suma_col.get(j, 0):g} vs registro {mes_h[mes]:g}",
    )
    ok(
        total_fila and abs(total_fila.get(j, 0) - mes_h[mes]) < 0.02,
        f"fila Total, {cab[j]}: {hm(total_fila.get(j, 0))} vs registro {hm(mes_h[mes])}",
    )
ok(
    abs(suma_tot - sum(mes_h.values())) < 0.2,
    f"totales por persona suman {hm(suma_tot)} vs registro completo {hm(sum(mes_h.values()))}",
)

print("\n=== 6. Contador del proyecto ===")
m = re.search(r"\*\*([\d.]+) minutos\*\* \(([\d.]+) h (\d{2}) min\)", det)
mins, hh = int(m.group(1).replace(".", "")), int(m.group(2).replace(".", "")) * 60 + int(m.group(3))
ok(mins == hh, f"contador: {m.group(1)} min = {mins} vs {m.group(2)} h {m.group(3)} min = {hh}")
ok(
    abs(mins / 60 - sum(mes_h.values())) < 0.02,
    f"contador {hm(mins / 60)} vs suma de todas las filas {hm(sum(mes_h.values()))}",
)
desg = re.findall(
    r"(Junio|julio|agosto|septiembre|octubre) ([0-9]+) h ([0-9]{2}) min",
    next(ln for ln in det.split(chr(10)) if ln.strip().startswith("Junio 499")),
)
if desg:
    sd = sum(int(a) * 60 + int(b) for _, a, b in desg)
    ok(sd == mins, f"desglose del contador {sd} min vs contador {mins} min")
    for nombre, a, b in desg:
        mes = {"junio": "06", "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10"}[nombre.lower()]
        ok(
            abs(int(a) + int(b) / 60 - mes_h[mes]) < 0.02,
            f"desglose — {nombre}: {a} h {b} min vs registro {hm(mes_h[mes])}",
        )

print("\n=== 7. Páginas de cada mes ===")
for mes, arch, presup, imputado in (
    ("06", "mes-2026-06.md", 500, None),
    ("07", "mes-2026-07.md", 500, None),
    ("08", "mes-2026-08.md", 700, 700),
    ("09", "mes-2026-09.md", 850, 850),
    ("10", "mes-2026-10.md", 850, None),
):
    s = leer(os.path.join(FIN, arch))
    esperado = mes_h[mes] + TRAS.get(mes, 0)
    prog, per = {}, {}
    for ln in s.split("\n"):
        c = [x.strip() for x in ln.split("|")]
        if len(c) == 5 and re.fullmatch(r"[\d.]+", c[2]) and re.fullmatch(r"\d+%", c[3]):
            prog[re.sub(r"\[([^\]]+)\].*", r"\1", c[1])] = float(c[2])
        if len(c) == 6 and re.fullmatch(r"[\d.]+", c[3]) and re.fullmatch(r"\d+%", c[4]):
            per[c[1]] = float(c[3])
    if prog:
        sp = sum(v for k, v in prog.items() if not k.startswith("**"))
        tp = next((v for k, v in prog.items() if k.startswith("**")), None)
        ok(abs(sp - esperado) < 0.02, f"{arch}: por programa suma {sp:g} vs esperado {esperado:g}")
        ok(tp is None or abs(tp - sp) < 0.02, f"{arch}: total por programa {tp} vs suma {sp:g}")
    if per:
        sper = sum(v for k, v in per.items() if not k.startswith("**"))
        tper = next((v for k, v in per.items() if k.startswith("**")), None)
        base = mes_h[mes]
        ok(abs(sper - base) < 0.6, f"{arch}: por persona suma {sper:g} vs registro {base:g}")
        ok(tper is None or abs(tper - sper) < 0.02, f"{arch}: total por persona {tper} vs suma {sper:g}")
        for p, v in per.items():
            if p.startswith("**") or mes in ("06", "07", "08"):
                continue
            ok(
                abs(v - mes_per[mes].get(p, 0)) < 0.02,
                f"{arch}: {p} declara {v:g} h vs filas {mes_per[mes].get(p, 0):g} h",
            )

print("\n=== 8. Índice financiero y portada ===")
idx, port = leer(os.path.join(FIN, "index.md")), leer(os.path.join(RAIZ, "docs", "client", "index.md"))
oct_t = mes_h["10"] + TRAS["10"]
saldo, pct = 850 - oct_t, round(oct_t / 850 * 100)
ok(hm(oct_t) in idx, f"índice: consumido de octubre {hm(oct_t)}")
ok(hm(saldo) in idx, f"índice: saldo de octubre {hm(saldo)}")
ok(f"({pct}%)" in idx, f"índice: porcentaje de octubre {pct}%")
corto = hm(oct_t).replace(" h ", "h ").replace(" min", "min")
breve = f"{int(oct_t)}h" if not oct_t % 1 else corto  # en punto, la portada escribe «523h»
ok(corto in port or breve in port, f"portada: consumido de octubre «{corto}» o «{breve}»")
ok(f"({pct}%)" in port, f"portada: porcentaje de octubre {pct}%")
ok(
    "942 h 30 min" in leer(os.path.join(FIN, "mes-2026-09.md"))
    and "92 h 30 min" in leer(os.path.join(FIN, "mes-2026-10.md")),
    "cadena del traslado septiembre → octubre",
)

print("\n" + "=" * 64)
print("AUDITORÍA OK — todo cierra" if not fallos else f"{len(fallos)} DIFERENCIAS:")
for f in fallos:
    print("  -", f)
sys.exit(1 if fallos else 0)
