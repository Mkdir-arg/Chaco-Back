# ruff: noqa: F841  (herramienta descartable de la auditoría: variables de depuración del parser)
# FE-13: parser de clases declaradas en un CSS con escapes completos (\2c , \:, \/).
# Base del decodificador nuevo de scripts/design_audit.py (TWBUILD) y de la regla CLASSDEF.
"""Parser robusto de clases declaradas en un CSS (escapes CSS completos)."""

import re
from pathlib import Path


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def clases_css(css: str) -> set[str]:
    css = _strip_comments(css)
    out = set()
    i, n = 0, len(css)
    # Solo nos interesan selectores: recorremos todo y tomamos '.ident' fuera de bloques de declaración.
    depth_decl = False
    buf_sel = []
    # Estrategia simple: separar por '{' y '}' ; la parte antes de '{' es selector o at-rule prelude.
    for m in re.finditer(r"([^{}]*)\{", css):
        sel = m.group(1)
        if sel.strip().startswith("@"):
            continue
        # quitar strings de atributos
        j = 0
        L = len(sel)
        while j < L:
            c = sel[j]
            if c == "." and j + 1 < L and (sel[j + 1].isalpha() or sel[j + 1] in "-_\\"):
                j += 1
                name = []
                while j < L:
                    c = sel[j]
                    if c == "\\":
                        # escape
                        h = re.match(r"[0-9a-fA-F]{1,6}", sel[j + 1 : j + 7])
                        if h:
                            name.append(chr(int(h.group(0), 16)))
                            j += 1 + len(h.group(0))
                            if j < L and sel[j] in " \t\n":
                                j += 1
                        else:
                            name.append(sel[j + 1] if j + 1 < L else "")
                            j += 2
                    elif c.isalnum() or c in "-_" or ord(c) > 127:
                        name.append(c)
                        j += 1
                    else:
                        break
                out.add("".join(name))
            elif c == "[":
                # saltar selectores de atributo
                k = sel.find("]", j)
                j = k + 1 if k != -1 else L
            else:
                j += 1
    return out


def clases_archivo(p: Path) -> set[str]:
    return clases_css(p.read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    import sys

    a = clases_archivo(Path(sys.argv[1]))
    b = clases_archivo(Path(sys.argv[2]))
    print("solo en", sys.argv[1], len(a - b))
    for c in sorted(a - b):
        print("  +", c)
    print("solo en", sys.argv[2], len(b - a))
    for c in sorted(b - a):
        print("  -", c)
