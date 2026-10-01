# Ola 6 (agente de diseño): cuenta las reglas P1 propuestas (RAWPALETTE, INLINESTYLE, STYLEBLOCK, SHELL,
# PAGEHEADER, TABLECANON, ICONARIA) y las de fase 2, en total y por módulo. Correr desde la raíz del repo.
# Argumentos opcionales: rutas de goldens para ver sus hallazgos. Solo stdlib.
import collections
import re
import subprocess
import sys

files = [
    f
    for f in subprocess.run(["git", "ls-files", "*.html"], capture_output=True, text=True).stdout.split("\n")
    if f and not f.startswith("docs/") and "/email/" not in f and "/vendor/" not in f
]
SHELLS = {
    "templates/includes/base.html",
    "portal/templates/portal/base.html",
    "portal/templates/portal/inscripcion/base_inscripcion.html",
    "users/templates/user/base_public_auth.html",
    "templates/includes/main.html",
}
PAL = r"(?<![\w-])(?:[a-z0-9-]+:)*(?:bg|text|border|ring|divide|from|via|to|placeholder)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}(?:/\d+)?\b"
CLS = re.compile(r'(?<![-:\w])class="([^"]*)"')
DYN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)


def rules(path, t):
    r = collections.Counter()
    for m in CLS.finditer(t):
        r["RAWPALETTE"] += len(re.findall(PAL, m.group(1)))
        for c in DYN.sub(" ", m.group(1)).split():
            if re.match(
                r"^(?:[a-z0-9-]+:)*(?:text|p[xytblr]?|m[xytblr]?|gap|w|h|min-w|max-w|max-h|min-h|rounded|leading|tracking|top|left|right|bottom|z)-\[[^\]]+\]$",
                c,
            ) and c not in {"text-[17px]", "max-w-[560px]", "max-h-[90vh]", "min-h-[100dvh]"}:
                r["TWARBITRARY"] += 1
    for m in re.finditer(r'\sstyle="([^"]*)"', t):
        v = DYN.sub("", m.group(1))
        v = re.sub(r"--[\w-]+\s*:[^;]*;?", "", v)
        if v.strip(" ;"):
            r["INLINESTYLE"] += 1
    if path not in SHELLS:
        r["STYLEBLOCK"] += len(re.findall(r"<style\b", t))
    r["XCLOAK"] += len(re.findall(r"\[x-cloak\]\s*\{", t))
    r["SHELL"] += len(re.findall(r'\{%\s*extends\s+["\']includes/main\.html["\']', t))
    if re.search(r'extends\s+["\']includes/base\.html', t) and "<h1" in t and "{% page_header" not in t:
        r["PAGEHEADER"] += 1
    r["TABLECANON"] += len(re.findall(r"<th\b(?![^>]*\bnodo-th\b)", t)) + len(re.findall(r"<thead[^>]*style=", t))
    r["ICONARIA"] += len(re.findall(r'<i\s+class="fa[srb]?\s[^"]*"(?![^>]*aria-hidden)', t)) + len(
        re.findall(r'<i\s+class="fa-(?:solid|regular|brands)\s[^"]*"(?![^>]*aria-hidden)', t)
    )
    r["ICONSVG"] += len(re.findall(r'<svg\b[^>]*stroke="currentColor"', t))
    r["LABELCANON"] += sum(
        1
        for m in re.finditer(r'<label[^>]*class="([^"]*)"', t)
        if " ".join(sorted(m.group(1).split()))
        not in {" ".join(sorted(x.split())) for x in ["block text-sm font-medium text-heading mb-1", "sr-only"]}
    )
    r["BTNBOOT"] += len(
        re.findall(
            r'class="[^"]*\bbtn (?:btn-(?:primary|outline-\w+|success|info|light|dark|warning|secondary|danger))\b', t
        )
    )
    r["EMPTYHAND"] += 0 if path.endswith("_estado_vacio.html") else len(re.findall(r"py-14 px-6 text-center", t))
    r["PAGEHAND"] += 0 if path.endswith("_paginacion.html") else len(re.findall(r"page_obj\.has_(?:next|previous)", t))
    r["CONFIRMHAND"] += len(re.findall(r"Swal\.fire\(", t))
    return r


tot = collections.Counter()
nf = collections.Counter()
bymod = collections.defaultdict(collections.Counter)
for f in files:
    try:
        t = open(f, encoding="utf-8").read()
    except Exception:
        continue
    r = rules(f, t)
    for k, v in r.items():
        if v:
            tot[k] += v
            nf[k] += 1
        mod = f.split("/")[0] if not f.startswith("programas/templates/programas/") else "programas/" + f.split("/")[3]
        bymod[mod][k] += v
for k in sorted(tot):
    print(f"{k:12} usos={tot[k]:5} archivos={nf[k]}")
print()
keys = ["RAWPALETTE", "INLINESTYLE", "STYLEBLOCK", "PAGEHEADER", "TABLECANON", "ICONARIA", "LABELCANON"]
print("mod".ljust(22), " ".join(k[:8].rjust(8) for k in keys))
for m in sorted(bymod):
    print(m.ljust(22), " ".join(str(bymod[m][k]).rjust(8) for k in keys))
print()
G = sys.argv[1:]
for f in G:
    t = open(f, encoding="utf-8").read()
    r = rules(f, t)
    print(f, {k: v for k, v in r.items() if v})
