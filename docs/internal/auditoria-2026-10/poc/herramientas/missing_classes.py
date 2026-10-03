# FE-13 / regla CLASSDEF: clases usadas en templates/JS que ningún CSS cargable declara.
# Uso: python missing_classes.py <raiz_del_repo> [tailwind_alternativo.css]  (cssclasses.py al lado). Salida JSON.
"""Clases usadas en templates/JS que ningún CSS cargable declara.

Uso: python missing_classes.py <raiz_worktree> [css_tailwind_alternativo]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cssclasses import clases_css  # noqa: E402

ROOT = Path(sys.argv[1])
TW = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "static/custom/css/tailwind.css"

EXCL_DIRS = {".git", ".venv", ".venv312", ".venv-e2e", "node_modules", "staticfiles", "docs", ".claude", "media"}
EXCL_STATIC = (
    "static/admin",
    "static/silk",
    "static/debug_toolbar",
    "static/django_extensions",
    "static/rest_framework",
    "static/drf_spectacular_sidecar",
    "static/vendor",
)


def walk(pattern):
    for p in ROOT.rglob(pattern):
        rel = p.relative_to(ROOT).as_posix()
        if any(part in EXCL_DIRS for part in p.relative_to(ROOT).parts):
            continue
        yield p, rel


# 1) Universo de clases declaradas
tw = clases_css(TW.read_text(encoding="utf-8", errors="replace"))
otros = set()
for p, rel in walk("*.css"):
    if rel.startswith(("static/vendor/fontawesome", "static/vendor/sweetalert2")) or not rel.startswith(EXCL_STATIC):
        if rel.endswith("tailwind.css"):
            continue
        otros |= clases_css(p.read_text(encoding="utf-8", errors="replace"))
# FA y SweetAlert2 vendor
for vend in ("static/vendor/fontawesome", "static/vendor/sweetalert2"):
    for p in (ROOT / vend).rglob("*.css"):
        otros |= clases_css(p.read_text(encoding="utf-8", errors="replace"))
# <style> inline de templates
STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
inline = set()
tpl_files = list(walk("*.html"))
for p, rel in tpl_files:
    t = p.read_text(encoding="utf-8", errors="replace")
    for m in STYLE_RE.finditer(t):
        inline |= clases_css(re.sub(r"\{[{%].*?[%}]\}", " ", m.group(1)))
DECL = tw | otros | inline

# 2) Clases usadas
CLASS_ATTR = re.compile(r"""(?<![:\w-])class\s*=\s*(["'])(.*?)\1""", re.S)
BIND_ATTR = re.compile(r"""(?:x-bind:|:)class\s*=\s*(["'])(.*?)\1""", re.S)
STR_IN_BIND = re.compile(r"""'([^']*)'|`([^`]*)`""")
CLASSLIST = re.compile(r"""classList\.(?:add|remove|toggle|contains|replace)\(([^)]*)\)""")
QUOTED = re.compile(r"""['"]([^'"]+)['"]""")
DJVAR = re.compile(r"\{\{.*?\}\}", re.S)
DJTAG = re.compile(r"\{%.*?%\}", re.S)
DJCOMMENT = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|\{#.*?#\}", re.S)
TOKEN_OK = re.compile(r"^!?-?[a-zA-Z_][\w:/\[\]().,%#!\-+*'=>&~]*$")

uso = defaultdict(set)  # clase -> {archivo}


def add_tokens(s, rel):
    s = DJVAR.sub("\u00a7", s)
    s = DJTAG.sub(" ", s)
    s = re.sub(r"\$\{[^}]*\}", "\u00a7", s)
    for tok in s.split():
        if "\u00a7" in tok or not TOKEN_OK.match(tok) or tok.endswith("-") or tok.endswith(":"):
            continue
        uso[tok].add(rel)


def scan_text(t, rel, is_js=False):
    t = DJCOMMENT.sub(" ", t)
    for m in CLASS_ATTR.finditer(t):
        add_tokens(m.group(2), rel)
    for m in BIND_ATTR.finditer(t):
        for sm in STR_IN_BIND.finditer(m.group(2)):
            add_tokens(sm.group(1) or sm.group(2) or "", rel)
    for m in CLASSLIST.finditer(t):
        for q in QUOTED.finditer(m.group(1)):
            add_tokens(q.group(1), rel)
    # className = '...'
    for m in re.finditer(r"""className\s*[+]?=\s*(['"`])(.*?)\1""", t, re.S):
        add_tokens(m.group(2), rel)
    # escapes en JS: class=\"...\"
    for m in re.finditer(r'class=\\"(.*?)\\"', t):
        add_tokens(m.group(1), rel)


for p, rel in tpl_files:
    scan_text(p.read_text(encoding="utf-8", errors="replace"), rel)
for p, rel in walk("*.js"):
    if rel.startswith("static/custom/js/") or "/static/" in rel and not rel.startswith(EXCL_STATIC):
        if rel.startswith(EXCL_STATIC):
            continue
        scan_text(p.read_text(encoding="utf-8", errors="replace"), rel, is_js=True)
# templatetags de python que devuelven HTML con class=
for p, rel in walk("*.py"):
    if "templatetags" in rel:
        scan_text(p.read_text(encoding="utf-8", errors="replace"), rel)

faltan = {c: sorted(fs) for c, fs in uso.items() if c not in DECL and c.lstrip("!") not in DECL}
json.dump({"faltan": faltan, "n_uso": len(uso), "n_decl": len(DECL)}, sys.stdout, ensure_ascii=False, indent=1)
