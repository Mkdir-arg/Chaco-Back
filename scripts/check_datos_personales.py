#!/usr/bin/env python
"""Gate «Sin datos personales»: ningún volcado de personas entra al repo ni al release.

Existe porque los tres volcados del organismo —la respuesta de RENAPER de 10.321
personas con domicilio, los DNI de aprobados y las localidades por DNI— estuvieron
versionados en un repositorio público, viajaron a `main`, al GitLab de ECOM y, por el
`COPY . .` del `Dockerfile`, dentro de la imagen de producción. Sacarlos de `HEAD` no
alcanza: el patrón que los metió —«chore(becas): lista nueva de aprobados»— se repite.

Tres modos, los tres con la misma regla, para que no haya dos heurísticas distintas:

    python scripts/check_datos_personales.py --diff <base-sha>   # lo que agrega un PR
    python scripts/check_datos_personales.py --versionados       # todo `git ls-files`
    python scripts/check_datos_personales.py --arbol <dir>       # el árbol del release

Qué considera un volcado: un `INSERT INTO` que nombra una columna de persona (DNI,
CUIL, apellido, fecha de nacimiento, domicilio) **y** más de 100 filas de tuplas. Las
dos condiciones juntas, no cada una por su lado: `scripts/aprobados_materias_plantilla.sql`
tiene el INSERT pero tres filas de ejemplo, y es justamente el archivo que sí tiene que
quedar versionado. Lo que distingue a un volcado de una plantilla es el volumen.

En `--diff` se suma el techo de tamaño (512 KB) para los archivos nuevos o modificados:
un volcado en CSV, en JSON o en un formato que no reconozcamos igual pesa. El techo no
corre sobre el árbol completo porque hay archivos grandes legítimos que ya están
(`core/fixtures/`, `static/vendor/`, el CSS compilado).

Salida: una línea `::error file=...::` por hallazgo —GitHub la muestra sobre el archivo—
y código 1. **Nunca imprime el contenido del archivo.**
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

TECHO_BYTES = 512 * 1024
# Con qué mirar alcanza: un volcado muestra la cara en el primer par de megas, y leer
# 3 MB de datos personales a memoria para confirmarlo no suma nada.
LEER_BYTES = 2_000_000
FILAS_VOLCADO = 100

COLUMNAS_PERSONALES = re.compile(
    r"insert\s+into[^;]{0,400}?(dni|cuil|cuit|apellido|fecha_nac|domicilio)",
    re.IGNORECASE | re.DOTALL,
)
FILA_DE_TUPLA = re.compile(r"^\s*\(.*\)\s*[,;]?\s*$")

# Grandes a propósito y revisados: el catálogo geográfico que siembra la base, las
# librerías de terceros, el CSS compilado de Tailwind y la documentación interna
# (`requerimientos.md` solo crece y se toca en casi todos los PRs).
EXENTOS_TAMANO = (
    "core/fixtures/*.json",
    "docs/*",
    "package-lock.json",
    "static/custom/css/*",
    "static/vendor/*",
)
# Binarios: no tiene sentido buscarles un INSERT.
EXENTOS_LECTURA = (
    "*.eot",
    "*.gif",
    "*.ico",
    "*.jpeg",
    "*.jpg",
    "*.pdf",
    "*.png",
    "*.svg",
    "*.ttf",
    "*.webp",
    "*.woff",
    "*.woff2",
    "*.zip",
)


def _exento(relativa: str, patrones: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(relativa, patron) for patron in patrones)


def parece_volcado(ruta: Path) -> str | None:
    """Motivo por el que el archivo parece un volcado de personas, o ``None``."""
    try:
        texto = ruta.open("rb").read(LEER_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return None
    if not COLUMNAS_PERSONALES.search(texto):
        return None
    filas = sum(1 for linea in texto.splitlines() if FILA_DE_TUPLA.match(linea))
    if filas <= FILAS_VOLCADO:
        return None
    return f"parece un volcado con datos personales ({filas}+ filas de un INSERT con columnas de persona)"


def revisar(rutas, raiz: Path, con_techo_de_tamano: bool) -> list[str]:
    """Devuelve un error por archivo problemático, en formato de anotación de Actions."""
    errores = []
    for relativa in sorted(rutas):
        archivo = raiz / relativa
        if not archivo.is_file():
            continue
        if con_techo_de_tamano and not _exento(relativa, EXENTOS_TAMANO):
            tamano = archivo.stat().st_size
            if tamano > TECHO_BYTES:
                errores.append(f"::error file={relativa}::archivo de {tamano} bytes (techo {TECHO_BYTES})")
        if _exento(relativa, EXENTOS_LECTURA):
            continue
        motivo = parece_volcado(archivo)
        if motivo:
            errores.append(f"::error file={relativa}::{motivo}")
    return errores


def _git(raiz: Path, *args: str) -> list[str]:
    salida = subprocess.run(
        ["git", *args], cwd=raiz, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout
    return [linea for linea in salida.splitlines() if linea.strip()]


def archivos_versionados(raiz: Path) -> list[str]:
    return _git(raiz, "ls-files")


def archivos_del_diff(raiz: Path, base: str) -> list[str]:
    return _git(raiz, "diff", "--name-only", "--diff-filter=AM", base, "HEAD")


def archivos_del_arbol(raiz: Path) -> list[str]:
    return [str(p.relative_to(raiz)).replace("\\", "/") for p in raiz.rglob("*") if p.is_file()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--diff", metavar="BASE_SHA", help="Archivos agregados o modificados contra ese commit.")
    modo.add_argument("--versionados", action="store_true", help="Todos los archivos que versiona git.")
    modo.add_argument("--arbol", metavar="DIR", help="Todos los archivos de un directorio (el release).")
    args = parser.parse_args(argv)

    if args.arbol:
        raiz = Path(args.arbol).resolve()
        rutas, con_techo = archivos_del_arbol(raiz), False
        que = f"el árbol {raiz}"
    else:
        raiz = Path(__file__).resolve().parent.parent
        if args.versionados:
            rutas, con_techo = archivos_versionados(raiz), False
            que = "los archivos versionados"
        else:
            rutas, con_techo = archivos_del_diff(raiz, args.diff), True
            que = f"lo que agrega el PR sobre {args.diff}"

    errores = revisar(rutas, raiz, con_techo)
    for error in errores:
        print(error)
    if errores:
        print(f"\n{len(errores)} problema(s) en {que}. Ver scripts/README-datos-siis.md.", file=sys.stderr)
        return 1
    print(f"OK: {len(rutas)} archivo(s) revisados en {que}, ningún volcado de personas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
