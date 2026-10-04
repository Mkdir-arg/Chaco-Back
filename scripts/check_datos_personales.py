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

Qué considera un volcado. Tres reglas, y alcanza con que dispare una. Todas exigen
**volumen**: lo que distingue un volcado de una plantilla no es el nombre de la columna,
es la cantidad de personas. `scripts/aprobados_materias_plantilla.sql` tiene un
`INSERT INTO … (dni)` con tres filas de ejemplo y tiene que seguir versionado.

1. **`INSERT` con la lista de columnas** y alguna de persona (`dni`, `cuil`, `cuit`,
   `apellido`, `fecha_nac`, `domicilio`), más de 100 filas de tuplas. Es el formato en
   el que el organismo exportó los suyos.
2. **`INSERT` sin lista de columnas**, que es lo que emite `mysqldump` por defecto
   (``INSERT INTO `t` VALUES (…),(…)``): ahí no hay nombre de columna que mirar, así que
   se mira el contenido — más de 100 documentos distintos (7 u 8 dígitos) o más de 50
   CUIL/CUIT distintos, con más de 100 filas de tuplas.
3. **Tabular sin SQL** (`.csv`, `.tsv`, `.dump`, `.dat`, `.sql`): más de 100 documentos
   distintos en más de 100 líneas. Un padrón de 5.000 DNI en CSV pesa 60 KB y no lo
   atrapa ningún techo de tamaño.

La regla 2 puede dar un falso positivo sobre un seed legítimo de más de 100 filas cuyos
ids caigan en el rango de 7-8 dígitos. Es un gate de seguridad: el falso positivo se
resuelve revisando el archivo, no aflojando la regla.

A las tres se les suma el **techo de tamaño** (512 KB), que es la red para el volcado en
un formato que no reconocemos (JSON, Parquet, un export binario). Corre en los tres
modos, no solo en el diff del PR: un push directo a `development` saltea el PR, y los
archivos grandes legítimos que ya están versionados son seis y están enumerados abajo.

Las exenciones del techo son **rutas exactas, nunca globs**: un glob (`docs/*`,
`core/fixtures/*.json`) convierte a ese directorio en un escondite donde un volcado
nuevo entra sin que lo pesen.

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
DOCUMENTOS_VOLCADO = 100
CUILES_VOLCADO = 50

# Acotada a la lista de columnas --entre el nombre de la tabla y el VALUES--, no a lo
# que venga después: si no, un apellido «Apellido» dentro de los datos hacía pasar por
# regla 1 lo que en realidad es un mysqldump sin columnas, y el mensaje mentía.
COLUMNAS_PERSONALES = re.compile(
    r"insert\s+into\s+[`\"\[]?[\w.]+[`\"\]]?\s*\([^)]{0,400}?"
    r"(dni|cuil|cuit|apellido|fecha_nac|domicilio)[^)]{0,400}?\)\s*values",
    re.IGNORECASE | re.DOTALL,
)
INSERT = re.compile(r"insert\s+into", re.IGNORECASE)
FILA_DE_TUPLA = re.compile(r"^\s*\(.*\)\s*[,;]?\s*$")
# Un DNI argentino: 7 u 8 dígitos sueltos. El `\b` evita contar los 8 primeros dígitos
# de un CUIL, que no tiene borde adentro.
DOCUMENTO = re.compile(r"\b\d{7,8}\b")
CUIL = re.compile(r"\b(?:20|23|24|27|30|33|34)-?\d{8}-?\d\b")
# Donde no hay SQL que mirar, el formato igual delata que la fila es una persona.
EXTENSIONES_TABULARES = (".csv", ".dat", ".dump", ".sql", ".tsv")

# Rutas **exactas**, revisadas una por una: son los archivos grandes que ya estaban
# versionados antes del gate. Nunca un glob: un `docs/*` convierte ese directorio en el
# lugar obvio para dejar el próximo volcado sin que nadie lo pese. Si aparece otro
# archivo legítimo de más de 512 KB, se agrega acá a mano y se revisa en el PR; hay un
# test que no deja que la lista se desactualice.
EXENTOS_TAMANO = (
    "core/fixtures/localidad_municipio_provincia.json",
    "docs/design-kb/Programa Becas - Chaco NODO.html",
    "docs/internal/requerimientos.md",
    "package-lock.json",
    "static/vendor/adminlte/adminlte.min.css",
    "static/vendor/vis-network/vis-network.min.js",
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
    """Motivo por el que el archivo parece un volcado de personas, o ``None``.

    Las tres reglas están en el docstring del módulo. El orden importa solo para el
    mensaje: se devuelve el motivo de la primera que dispare.
    """
    try:
        texto = ruta.open("rb").read(LEER_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return None

    lineas = texto.splitlines()
    filas = sum(1 for linea in lineas if FILA_DE_TUPLA.match(linea))
    con_volumen = filas > FILAS_VOLCADO

    # 1 · El formato en el que el organismo exportó los suyos.
    if con_volumen and COLUMNAS_PERSONALES.search(texto):
        return f"parece un volcado con datos personales ({filas} filas de un INSERT con columnas de persona)"

    # 2 y 3 miran el contenido: contar es caro, así que recién acá.
    if not (con_volumen or (ruta.suffix.lower() in EXTENSIONES_TABULARES and len(lineas) > FILAS_VOLCADO)):
        return None
    cuiles = len(set(CUIL.findall(texto)))
    documentos = len(set(DOCUMENTO.findall(texto)))

    # 2 · `mysqldump` por defecto: INSERT INTO `t` VALUES (…), sin lista de columnas.
    if con_volumen and INSERT.search(texto) and (documentos > DOCUMENTOS_VOLCADO or cuiles > CUILES_VOLCADO):
        return (
            f"parece un volcado con datos personales en formato mysqldump "
            f"({filas} filas, {documentos} documentos y {cuiles} CUIL distintos)"
        )

    # 3 · Tabular sin SQL: un padrón en CSV pesa poco y no lo atrapa el techo.
    if ruta.suffix.lower() in EXTENSIONES_TABULARES and len(lineas) > FILAS_VOLCADO:
        if documentos > DOCUMENTOS_VOLCADO or cuiles > CUILES_VOLCADO:
            return (
                f"parece un padrón de personas ({len(lineas)} líneas, "
                f"{documentos} documentos y {cuiles} CUIL distintos)"
            )
    return None


def revisar(rutas, raiz: Path) -> list[str]:
    """Devuelve un error por archivo problemático, en formato de anotación de Actions."""
    errores = []
    for relativa in sorted(rutas):
        archivo = raiz / relativa
        if not archivo.is_file():
            continue
        if relativa not in EXENTOS_TAMANO:
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
        rutas = archivos_del_arbol(raiz)
        que = f"el árbol {raiz}"
    else:
        raiz = Path(__file__).resolve().parent.parent
        if args.versionados:
            rutas = archivos_versionados(raiz)
            que = "los archivos versionados"
        else:
            rutas = archivos_del_diff(raiz, args.diff)
            que = f"lo que agrega el PR sobre {args.diff}"

    errores = revisar(rutas, raiz)
    for error in errores:
        print(error)
    if errores:
        print(f"\n{len(errores)} problema(s) en {que}. Ver scripts/README-datos-siis.md.", file=sys.stderr)
        return 1
    print(f"OK: {len(rutas)} archivo(s) revisados en {que}, ningún volcado de personas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
