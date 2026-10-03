# FE-05: bloques definidos en un template hijo que ningún ancestro declara (Django los descarta en silencio).
# Base para el flag --bloques de scripts/compile_templates.py. Correr desde la raíz del repo.
"""Bloques definidos en un template hijo que ningún ancestro declara (se descartan en silencio)."""

import re
import subprocess
from pathlib import Path

files = [
    f
    for f in subprocess.check_output(["git", "ls-files", "-z", "*.html"], text=True).split("\0")
    if f and not f.startswith(("docs/", ".claude")) and "/templates/" in "/" + f
]
by_name = {}
for f in files:
    parts = f.split("/")
    i = len(parts) - 1 - parts[::-1].index("templates")
    by_name["/".join(parts[i + 1 :])] = f

BLOCK = re.compile(r"{%\s*block\s+([\w-]+)")
EXT = re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']')


def ancestors_blocks(name, seen=None):
    seen = seen or set()
    f = by_name.get(name)
    if not f or name in seen:
        return set(), False
    seen.add(name)
    t = Path(f).read_text(encoding="utf-8", errors="replace")
    blocks = set(BLOCK.findall(t))
    m = EXT.search(t)
    if m:
        b2, ok = ancestors_blocks(m.group(1), seen)
        if not ok:
            return blocks, False
        blocks |= b2
    return blocks, True


for name, f in sorted(by_name.items()):
    t = Path(f).read_text(encoding="utf-8", errors="replace")
    m = EXT.search(t)
    if not m:
        continue
    parent_blocks, ok = ancestors_blocks(m.group(1))
    if not ok:
        continue
    own = BLOCK.findall(t)
    # bloques anidados dentro de otro bloque del hijo también cuentan como definidos por el hijo
    lost = [b for b in own if b not in parent_blocks]
    # descartar los anidados: si el bloque está dentro de otro bloque que el padre sí tiene, se renderiza igual
    real = []
    for b in lost:
        pos = re.search(r"{%\s*block\s+" + re.escape(b) + r"\b", t).start()
        before = t[:pos]
        opened = len(BLOCK.findall(before)) - len(re.findall(r"{%\s*endblock", before))
        if opened == 0:
            real.append(b)
    if real:
        print(f, "-> bloques sin destino:", real, "(extends", m.group(1) + ")")
