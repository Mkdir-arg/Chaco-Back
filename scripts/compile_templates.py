#!/usr/bin/env python3
r"""Compila TODOS los templates del repo con el motor real de Django.

Detecta errores de sintaxis de template (tags rotos, bloques sin cerrar,
comentarios JSX `{{/* */}}`, filtros inexistentes) que `manage.py check`
NO ve porque no renderiza. No necesita DB ni contexto: solo get_template(),
que parsea y compila cada archivo.

Con ``--bloques`` suma el chequeo de FE-05: un ``{% block %}`` de primer nivel que un
hijo define y **ningún ancestro declara** no es un error de sintaxis —Django lo descarta
en silencio— pero su contenido nunca llega al navegador. Así se perdía la cascada
Secretaría → Subsecretaría del wizard de programas, que vivía en un ``extra_js`` que el
shell del backoffice no tiene.

Uso:
    & .\.venv\Scripts\python.exe scripts\compile_templates.py
    & .\.venv\Scripts\python.exe scripts\compile_templates.py --bloques

Exit 0 = todos compilan · Exit 1 = hay templates rotos (los lista).
Complementa a scripts/design_audit.py: ese valida DISEÑO, este valida SINTAXIS.
"""

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-key")

import django

django.setup()

from django.conf import settings
from django.template import TemplateSyntaxError
from django.template.loader import get_template
from django.template.utils import get_app_template_dirs

BLOCK_RE = re.compile(r"{%\s*block\s+([\w-]+)")
EXTENDS_RE = re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']')

# FE-05: bloques sin destino que ya estaban cuando se encendió el flag. Cada uno tiene
# dueño y muere con su ficha; la lista no crece. `(nombre del template, bloque)`.
BLOQUES_SIN_DESTINO_CONOCIDOS = set()
# FE-20 cerrada (Cambio 167): las tres páginas de error ya no extienden el wrapper
# legacy —que se borró— y dejaron de declarar `menu-adicional`.
# LEG-06 cerrada (Cambio 195): se borraron `legajos/dashboard_simple.html` y
# `legajos/historial_contactos.html`, las dos pantallas muertas que aportaban las
# tres entradas que quedaban. La lista queda vacía y no crece.


def _mapa_de_templates(dirs: list[Path]) -> dict[str, Path]:
    """Nombre tal como lo pide ``get_template`` → archivo (gana la primera coincidencia)."""
    mapa: dict[str, Path] = {}
    for base in dirs:
        if not base.is_dir():
            continue
        for archivo in base.rglob("*.html"):
            mapa.setdefault(archivo.relative_to(base).as_posix(), archivo)
    return mapa


def _bloques_de_los_ancestros(nombre: str, mapa: dict[str, Path], vistos=None) -> tuple[set[str], bool]:
    """Bloques declarados por el template y su cadena de herencia.

    El segundo valor es ``False`` cuando la cadena no se pudo resolver entera (un
    ancestro que no existe o un ``{% extends %}`` con variable): ahí no se concluye nada.
    """
    vistos = vistos or set()
    archivo = mapa.get(nombre)
    if archivo is None or nombre in vistos:
        return set(), False
    vistos.add(nombre)
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    bloques = set(BLOCK_RE.findall(texto))
    padre = EXTENDS_RE.search(texto)
    if padre:
        heredados, completa = _bloques_de_los_ancestros(padre.group(1), mapa, vistos)
        if not completa:
            return bloques, False
        bloques |= heredados
    return bloques, True


def bloques_sin_destino(dirs: list[Path]) -> list[tuple[str, str, str]]:
    """``(template, bloque, padre)`` por cada bloque de primer nivel que nadie declara."""
    mapa = _mapa_de_templates(dirs)
    huerfanos: list[tuple[str, str, str]] = []
    for nombre, archivo in sorted(mapa.items()):
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        padre = EXTENDS_RE.search(texto)
        if not padre:
            continue
        declarados, completa = _bloques_de_los_ancestros(padre.group(1), mapa)
        if not completa:
            continue
        for bloque in BLOCK_RE.findall(texto):
            if bloque in declarados:
                continue
            # Un bloque anidado dentro de otro que el padre sí declara se renderiza igual.
            posicion = re.search(r"{%\s*block\s+" + re.escape(bloque) + r"\b", texto).start()
            antes = texto[:posicion]
            if len(BLOCK_RE.findall(antes)) - len(re.findall(r"{%\s*endblock", antes)) == 0:
                huerfanos.append((nombre, bloque, padre.group(1)))
    return huerfanos


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dirs = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    dirs += [Path(d) for d in get_app_template_dirs("templates")]
    # Solo templates del repo. El filtro por prefijo no alcanza: los venv del
    # proyecto (`.venv`, `.venv312`) viven **adentro** del checkout, así que sus
    # `site-packages` pasaban el prefijo y el script compilaba los templates de
    # Django, DRF y django-silk — 349 en esta máquina contra 199 en un árbol
    # limpio. Un error de terceros no es nuestro y el número deja de ser
    # comparable entre máquinas y el CI (V5A-NEW-08).
    dirs = [
        d
        for d in dirs
        if str(Path(d).resolve()).lower().startswith(str(REPO).lower())
        and "site-packages" not in Path(d).resolve().as_posix()
    ]

    seen, errors, ok = set(), [], 0
    for base in dirs:
        if not base.is_dir():
            continue
        for f in base.rglob("*.html"):
            rel = f.relative_to(base).as_posix()
            if rel in seen:
                continue  # el loader resuelve la primera coincidencia
            seen.add(rel)
            try:
                get_template(rel)
                ok += 1
            except TemplateSyntaxError as e:
                errors.append((rel, f"SYNTAX: {e}"))
            except Exception as e:  # noqa: BLE001 — reportar cualquier fallo de carga
                errors.append((rel, f"{type(e).__name__}: {e}"))

    print(f"compilados OK: {ok}")
    print(f"ERRORES: {len(errors)}")
    for rel, msg in errors:
        print(f"  {rel}\n    {msg[:200]}")

    if "--bloques" in sys.argv:
        huerfanos = [h for h in bloques_sin_destino(dirs) if (h[0], h[1]) not in BLOQUES_SIN_DESTINO_CONOCIDOS]
        print(f"BLOQUES SIN DESTINO: {len(huerfanos)}")
        for nombre, bloque, padre in huerfanos:
            print(
                f"  {nombre}\n    {{% block {bloque} %}} no existe en {padre} ni en sus ancestros: Django lo descarta"
            )
        if huerfanos:
            return 1

    return 1 if errors else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    # os._exit: evita el crash en la finalización del intérprete que provocan
    # los atexit de dependencias (silk) y devolvería -1 aun con todo OK.
    os._exit(code)
