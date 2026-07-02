#!/usr/bin/env python3
r"""Compila TODOS los templates del repo con el motor real de Django.

Detecta errores de sintaxis de template (tags rotos, bloques sin cerrar,
comentarios JSX `{{/* */}}`, filtros inexistentes) que `manage.py check`
NO ve porque no renderiza. No necesita DB ni contexto: solo get_template(),
que parsea y compila cada archivo.

Uso:
    & .\.venv\Scripts\python.exe scripts\compile_templates.py

Exit 0 = todos compilan · Exit 1 = hay templates rotos (los lista).
Complementa a scripts/design_audit.py: ese valida DISEÑO, este valida SINTAXIS.
"""
import os
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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dirs = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    dirs += [Path(d) for d in get_app_template_dirs("templates")]
    # Solo templates del repo (no site-packages)
    dirs = [d for d in dirs if str(Path(d).resolve()).lower().startswith(str(REPO).lower())]

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
    return 1 if errors else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    # os._exit: evita el crash en la finalización del intérprete que provocan
    # los atexit de dependencias (silk) y devolvería -1 aun con todo OK.
    os._exit(code)
