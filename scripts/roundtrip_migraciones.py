#!/usr/bin/env python
"""Las migraciones del PR, ida y vuelta, contra el motor real y sobre datos (RED-17).

El CI arma el esquema desde los modelos (`DJANGO_SYNCDB_PROJECT_APPS=True`), así que
hasta hoy una migración podía entrar sin que nada la ejecutara, y el camino de vuelta
—el que se recorre a las tres de la mañana con producción caída— no lo probaba nadie.
Este script corre la secuencia completa contra un motor de verdad:

1. **ida hasta la base del PR**, con el código de la base (`--arbol-base`);
2. **semilla** (`seed_perf`), también con el código de la base: las migraciones del PR
   tienen que correr sobre filas, no sobre tablas vacías (28 `RunPython` en 27 archivos
   nunca habían iterado nada);
3. **foto del esquema** de la base (`verificar_columnas_obligatorias --guardar`);
4. **ida del PR** sobre esos datos;
5. **comparación de columnas obligatorias** contra la foto: una columna que recién ahora
   queda `NOT NULL` sin `DEFAULT` rompe toda alta apenas se baja la release (RED-14).
   Acá se ve venga de un `AddField` o de un `AlterField`, que es el agujero que el gate
   estático de `check_migraciones.py` no podía tapar;
6. **vuelta** hasta la base, app por app;
7. **ida de nuevo** y `migrate --check`;
8. **coherencia esquema ↔ `django_migrations`** (`verificar_esquema_migraciones
   --estricto`, OPS-01): `migrate --check` solo mira si queda algo por aplicar, así que
   una tabla que la vuelta no pudo borrar —en MariaDB el DDL no es transaccional,
   RED-15— lo pasaría sin decir nada.

**Las barreras de reversa no son un rojo.** Ocho migraciones abortan a propósito con
`IrreversibleError` cuando se las desaplica (paso D.4 del runbook, Cambios 117 y 135):
si el plan de vuelta cruza una, el script lo registra como *esperado* y sigue. Lo que sí
es rojo es cualquier otro error, y que la ida posterior no deje el esquema al día.

    python scripts/roundtrip_migraciones.py --arbol-base ../base
    python scripts/roundtrip_migraciones.py --arbol-base ../base --base origin/development
    python scripts/roundtrip_migraciones.py --arbol-base ../base --escala 50 --sin-semilla

No importa Django: orquesta `manage.py` con `subprocess` en los dos árboles, para que el
código de cada etapa sea el que de verdad corresponde a esa etapa.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_POR_DEFECTO = "origin/development"

# Orden de vuelta: primero lo que depende de los demás. Django arrastra solo las
# dependencias, así que el orden es prolijidad del log, no corrección.
ORDEN_DE_APPS = ("programas", "legajos", "conversaciones", "portal", "dashboard", "users", "core", "configuracion")

# El texto que las ocho barreras ponen en su `IrreversibleError` (Cambios 117 y 135).
BARRERA = re.compile("barrera de reversa", re.IGNORECASE)

# `0074_algo.py` -> `0074_algo`
MIGRACION = re.compile(r"^\d{4}_.+$")


class Rojo(RuntimeError):
    """Un paso que falló por algo que no es una barrera declarada."""


def _git(*argumentos: str) -> str:
    corrida = subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True)
    if corrida.returncode != 0:
        raise Rojo(f"git {' '.join(argumentos)}: {corrida.stderr.strip()}")
    return corrida.stdout


def apps_con_migraciones_nuevas(base: str) -> list[str]:
    """Las apps que el PR **agrega** migraciones (`git diff --diff-filter=A`)."""
    salida = _git("diff", "--name-only", "--diff-filter=A", f"{base}...HEAD", "--", "*/migrations/*.py")
    apps = {
        linea.split("/")[0] for linea in salida.split() if linea.endswith(".py") and not linea.endswith("__init__.py")
    }
    return [app for app in ORDEN_DE_APPS if app in apps] + sorted(apps - set(ORDEN_DE_APPS))


def ultima_migracion(arbol: Path, app: str) -> str:
    """La migración más alta de `app` en ese árbol, o `zero` si no tiene ninguna.

    `zero` es el destino que Django entiende para «desaplicá la app entera»: es lo que
    corresponde cuando el PR crea la carpeta `migrations/` de una app que no la tenía.
    """
    carpeta = arbol / app / "migrations"
    if not carpeta.is_dir():
        return "zero"
    nombres = sorted(ruta.stem for ruta in carpeta.glob("*.py") if MIGRACION.match(ruta.stem))
    return nombres[-1] if nombres else "zero"


def destinos_de_reversa(arbol_base: Path, apps: list[str]) -> list[tuple[str, str]]:
    return [(app, ultima_migracion(arbol_base, app)) for app in apps]


def _correr(argumentos: list[str], *, cwd: Path, titulo: str, tolerar_barrera: bool = False) -> str:
    """Corre `manage.py …` y devuelve su salida; aborta salvo que sea una barrera."""
    print(f"\n=== {titulo} ===", flush=True)
    print(f"$ (cd {cwd}) {' '.join(argumentos)}", flush=True)
    corrida = subprocess.run(
        [sys.executable, "manage.py", *argumentos],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ,
    )
    salida = (corrida.stdout or "") + (corrida.stderr or "")
    print(salida.rstrip(), flush=True)
    if corrida.returncode == 0:
        return salida
    if tolerar_barrera and BARRERA.search(salida):
        print(
            "   ^ barrera de reversa: el aborto es el comportamiento correcto "
            "(runbook D.4 de docs/internal/processes.md), no un rojo del job.",
            flush=True,
        )
        return salida
    raise Rojo(f"{titulo}: `manage.py {' '.join(argumentos)}` salió con {corrida.returncode}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migraciones ida y vuelta contra el motor real (RED-17).")
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help=f"rama base del PR ({BASE_POR_DEFECTO})")
    parser.add_argument("--arbol-base", required=True, type=Path, help="worktree con el código de la base")
    parser.add_argument("--escala", type=int, default=200, help="--scale de seed_perf (default: 200)")
    parser.add_argument("--sin-semilla", action="store_true", help="saltear seed_perf (diagnóstico)")
    args = parser.parse_args(argv)

    arbol_base = args.arbol_base.resolve()
    if not (arbol_base / "manage.py").exists():
        print(f"no hay un árbol de Django en {arbol_base}", file=sys.stderr)
        return 2

    apps = apps_con_migraciones_nuevas(args.base)
    destinos = destinos_de_reversa(arbol_base, apps)
    print(f"roundtrip: base={args.base} arbol_base={arbol_base}")
    print(f"roundtrip: apps con migraciones nuevas: {', '.join(apps) if apps else '(ninguna)'}")

    with tempfile.TemporaryDirectory() as temporal:
        foto = Path(temporal) / "esquema-base.json"
        try:
            _correr(["migrate", "--noinput"], cwd=arbol_base, titulo="1/7 · ida hasta la base del PR")
            if args.sin_semilla:
                print("\n=== 2/7 · semilla salteada (--sin-semilla) ===")
            else:
                _correr(
                    ["seed_perf", "--scale", str(args.escala)],
                    cwd=arbol_base,
                    titulo=f"2/7 · datos con el código de la base (seed_perf --scale {args.escala})",
                )
            # La foto se saca desde el árbol del PR aunque el esquema sea todavía el de
            # la base: `verificar_columnas_obligatorias` nace en este PR y el árbol de la
            # base no lo tiene. Lee `information_schema`, así que el código con el que se
            # la saque da igual; lo que importa es el momento.
            _correr(
                ["verificar_columnas_obligatorias", "--guardar", str(foto)],
                cwd=RAIZ,
                titulo="3/7 · foto del esquema de la base",
            )
            _correr(["migrate", "--noinput"], cwd=RAIZ, titulo="4/7 · ida del PR, sobre los datos sembrados")
            _correr(
                ["verificar_columnas_obligatorias", "--comparar", str(foto), "--base", args.base],
                cwd=RAIZ,
                titulo="5/7 · columnas que el PR vuelve obligatorias (RED-14, AlterField incluido)",
            )

            if destinos:
                for app, destino in destinos:
                    _correr(
                        ["migrate", app, destino, "--noinput"],
                        cwd=RAIZ,
                        titulo=f"6/7 · vuelta: {app} -> {destino}",
                        tolerar_barrera=True,
                    )
            else:
                print("\n=== 6/7 · vuelta: el PR no agrega migraciones, no hay nada que desaplicar ===")

            _correr(["migrate", "--noinput"], cwd=RAIZ, titulo="7/8 · ida de nuevo")
            _correr(["migrate", "--check"], cwd=RAIZ, titulo="7/8 · coherencia: migrate --check")
            # `migrate --check` solo mira si queda algo por aplicar: con el esquema roto
            # y `django_migrations` al día contesta que todo bien. El paso que falta —y
            # que el Anexo B pedía— es el inverso: que no haya quedado una tabla que
            # ningún modelo nombra, que es lo que deja una reversa cortada en MariaDB
            # (RED-15). `--estricto` porque acá la base es efímera: no hay nada ajeno.
            _correr(
                ["verificar_esquema_migraciones", "--estricto"],
                cwd=RAIZ,
                titulo="8/8 · coherencia esquema <-> django_migrations (OPS-01, con el inverso de RED-15)",
            )
        except Rojo as error:
            print(f"\nroundtrip: ROJO — {error}", file=sys.stderr)
            return 1

    print("\nroundtrip: OK — ida, vuelta e ida de nuevo contra el motor real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
