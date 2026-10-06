#!/usr/bin/env python
"""Contrato de las migraciones nuevas: expand/contract y reversa declarada.

Tres reglas, las tres sobre el estado exacto en el que queda producción cuando algo
sale mal (auditoría oct-2026, `docs/internal/auditoria-2026-10/`):

* **EXPAND** (RED-14) — una columna nueva `NOT NULL` sin `DEFAULT` **en la base**. Un `default=`
  solo no cuenta: Django lo aplica durante el `ALTER` y después lo quita, así que vive en Python y
  lo pone el ORM al armar el `INSERT`. Con el esquema adelantado y el código viejo —lo que deja un
  rollback de release— ese ORM omite la columna y MariaDB con `STRICT_TRANS_TABLES` rechaza el alta
  entera. Se arregla con `null=True`, con `db_default=…` (el DEFAULT nativo de Django 5, que sí
  queda escrito en el esquema), con un `RunSQL(… SET DEFAULT …, state_operations=[])` o, si de
  verdad no hace falta, con la marca `# ROLLBACK-OK: <motivo>`.
* **CONTRACT** (RED-19) — `RemoveField`, `DeleteModel`, `RenameField` o `RenameModel`
  sin la marca `# CONTRACT: <la columna dejó de leerse en la release X>`. Durante un
  rolling los pods viejos siguen atendiendo: borrar lo que todavía se lee da 500
  intermitentes hasta que termina el rollout.
* **REVERSA** (RED-57) — un `RunPython`/`RunSQL` sin reversa declarada, o con reversa
  `noop` (incluida la función vacía) sin la marca `# REVERSA-NOOP: <qué dato queda
  inconsistente al revertir>`. Una reversa noop informa `OK` y deja los datos a medias.

Las marcas valen en el bloque de comentarios inmediatamente anterior a la operación o
adentro de la operación misma.

    python scripts/check_migraciones.py                  # migraciones nuevas vs origin/development
    python scripts/check_migraciones.py --base <ref>     # contra otra base (el CI pasa el SHA del PR)
    python scripts/check_migraciones.py <archivo>...     # archivos concretos
    python scripts/check_migraciones.py --todas          # todo el repo (diagnóstico: trae la deuda vieja)

Solo mira **archivos nuevos**: una migración ya aplicada en producción no se reescribe.
No importa Django ni toca la base: `ast` y `git`, nada más.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_POR_DEFECTO = "origin/development"

MARCAS = {
    "EXPAND": "# ROLLBACK-OK:",
    "CONTRACT": "# CONTRACT:",
    "REVERSA": "# REVERSA-NOOP:",
}

OPERACIONES_CONTRACT = ("RemoveField", "DeleteModel", "RenameField", "RenameModel")
SET_DEFAULT = re.compile(r"set\s+default", re.IGNORECASE)


@dataclass(frozen=True)
class Hallazgo:
    archivo: str
    linea: int
    regla: str
    mensaje: str

    def __str__(self) -> str:
        return f"{self.archivo}:{self.linea}: [{self.regla}] {self.mensaje}"


def _nombre_de_llamada(nodo: ast.Call) -> str:
    funcion = nodo.func
    if isinstance(funcion, ast.Attribute):
        return funcion.attr
    if isinstance(funcion, ast.Name):
        return funcion.id
    return ""


def _kw(llamada: ast.Call, nombre: str):
    for palabra in llamada.keywords:
        if palabra.arg == nombre:
            return palabra.value
    return None


def _argumento(llamada: ast.Call, posicion: int, nombre: str):
    """El argumento `nombre`, venga por posición o por palabra clave."""
    if len(llamada.args) > posicion:
        return llamada.args[posicion]
    return _kw(llamada, nombre)


def _texto_cercano(lineas: list[str], nodo: ast.AST) -> str:
    """Comentarios del bloque anterior a la operación, más los de adentro."""
    recogido: list[str] = []
    indice = nodo.lineno - 2
    while indice >= 0:
        linea = lineas[indice].strip()
        if linea.startswith("#"):
            recogido.append(linea)
        elif linea:
            break
        indice -= 1
    fin = getattr(nodo, "end_lineno", nodo.lineno)
    recogido.extend(lineas[nodo.lineno - 1 : fin])
    return "\n".join(recogido)


def _declarado(lineas: list[str], nodo: ast.AST, regla: str) -> bool:
    return MARCAS[regla] in _texto_cercano(lineas, nodo)


def _es_noop(nodo: ast.AST | None, vacias: set[str]) -> bool:
    """`RunPython.noop`, `RunSQL.noop` o una función del archivo que no hace nada."""
    if isinstance(nodo, ast.Attribute) and nodo.attr == "noop":
        return True
    return isinstance(nodo, ast.Name) and nodo.id in vacias


def _funciones_vacias(arbol: ast.Module) -> set[str]:
    """`def f(...): \"\"\"docstring\"\"\"` o `pass`: declara una reversa y no revierte nada."""
    vacias = set()
    for nodo in arbol.body:
        if not isinstance(nodo, ast.FunctionDef):
            continue
        cuerpo = [
            sentencia
            for sentencia in nodo.body
            if not (isinstance(sentencia, ast.Expr) and isinstance(sentencia.value, ast.Constant))
        ]
        if all(isinstance(sentencia, ast.Pass) for sentencia in cuerpo):
            vacias.add(nodo.name)
    return vacias


def _columna_es_not_null(llamada: ast.Call) -> bool:
    campo = _kw(llamada, "field") or _argumento(llamada, 2, "field")
    if not isinstance(campo, ast.Call):
        # Un `field=` que no es una llamada (una variable, por ejemplo) no se puede leer
        # acá: se deja pasar antes que inventar un hallazgo.
        return False
    if _nombre_de_llamada(campo) == "ManyToManyField":
        return False  # tabla intermedia: no agrega columna a la tabla del modelo
    nulo = _kw(campo, "null")
    return not (isinstance(nulo, ast.Constant) and nulo.value is True)


def _campo_trae_db_default(llamada: ast.Call) -> bool:
    """¿El `AddField` lleva `db_default=`, el DEFAULT nativo de Django 5?

    Es la forma corta de lo que esta regla pide: el `ADD COLUMN` sale con su
    `DEFAULT` escrito en el esquema, así que el INSERT del código viejo —el que
    no nombra la columna— entra igual. `default=` solo **no** alcanza: ese vive
    en Python y lo pone el ORM al armar el INSERT.
    """
    campo = _kw(llamada, "field") or _argumento(llamada, 2, "field")
    return isinstance(campo, ast.Call) and _kw(campo, "db_default") is not None


def _tiene_default_en_la_base(arbol: ast.Module, columna: str) -> bool:
    """Un `RunSQL` del mismo archivo que le pone `DEFAULT` a esa columna en la base."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if SET_DEFAULT.search(nodo.value) and columna in nodo.value:
                return True
    return False


def revisar_texto(texto: str, archivo: str) -> list[Hallazgo]:
    """Los hallazgos de una migración, ordenados por línea."""
    try:
        arbol = ast.parse(texto)
    except SyntaxError as error:  # pragma: no cover - lo caza `ruff`/`compileall` antes
        return [Hallazgo(archivo, error.lineno or 0, "SINTAXIS", f"no se pudo leer: {error.msg}")]

    lineas = texto.splitlines()
    vacias = _funciones_vacias(arbol)
    hallazgos: list[Hallazgo] = []

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        operacion = _nombre_de_llamada(nodo)

        if operacion == "AddField" and _columna_es_not_null(nodo):
            nombre = _kw(nodo, "name") or _argumento(nodo, 1, "name")
            columna = nombre.value if isinstance(nombre, ast.Constant) else ""
            cubierta = (
                _campo_trae_db_default(nodo)
                or _tiene_default_en_la_base(arbol, columna)
                or _declarado(lineas, nodo, "EXPAND")
            )
            if not cubierta:
                hallazgos.append(
                    Hallazgo(
                        archivo,
                        nodo.lineno,
                        "EXPAND",
                        f"la columna «{columna}» nace NOT NULL sin DEFAULT en la base: el código viejo "
                        "no la manda y toda alta falla después de un rollback (RED-14). Poné `null=True`, "
                        "`db_default=…`, agregá un `RunSQL(… SET DEFAULT …, state_operations=[])` o justificá con "
                        f"«{MARCAS['EXPAND']} <motivo>».",
                    )
                )

        elif operacion in OPERACIONES_CONTRACT and not _declarado(lineas, nodo, "CONTRACT"):
            hallazgos.append(
                Hallazgo(
                    archivo,
                    nodo.lineno,
                    "CONTRACT",
                    f"`{operacion}` es *contract*: durante el rolling los pods viejos todavía leen esa "
                    f"columna (RED-19). Declaralo con «{MARCAS['CONTRACT']} dejó de leerse en la "
                    "release <X>».",
                )
            )

        elif operacion in ("RunPython", "RunSQL"):
            posicion, nombre = (1, "reverse_code") if operacion == "RunPython" else (1, "reverse_sql")
            reversa = _argumento(nodo, posicion, nombre)
            if reversa is None:
                hallazgos.append(
                    Hallazgo(
                        archivo,
                        nodo.lineno,
                        "REVERSA",
                        f"`{operacion}` sin reversa: escribila, o poné `None` explícito si la migración "
                        "es irreversible a propósito (RED-57).",
                    )
                )
            elif _es_noop(reversa, vacias) and not _declarado(lineas, nodo, "REVERSA"):
                hallazgos.append(
                    Hallazgo(
                        archivo,
                        nodo.lineno,
                        "REVERSA",
                        f"la reversa no hace nada, así que `migrate` informa OK y los datos quedan a "
                        f"medias (RED-57). Declará qué se pierde con «{MARCAS['REVERSA']} <qué dato "
                        "queda inconsistente>».",
                    )
                )

    return sorted(hallazgos, key=lambda h: (h.linea, h.regla))


def revisar_archivo(ruta: Path) -> list[Hallazgo]:
    ruta = Path(ruta)
    try:
        relativa = ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        relativa = ruta.as_posix()
    return revisar_texto(ruta.read_text(encoding="utf-8"), relativa)


def migraciones_nuevas(base: str) -> list[Path]:
    """Las migraciones **agregadas** respecto de `base` (`git diff --diff-filter=A`)."""
    comando = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=A",
        f"{base}...HEAD",
        "--",
        "*/migrations/*.py",
    ]
    corrida = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    if corrida.returncode != 0:
        print(f"no se pudo comparar contra {base}: {corrida.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    rutas = [RAIZ / linea for linea in corrida.stdout.split() if not linea.endswith("__init__.py")]
    return [ruta for ruta in rutas if ruta.exists()]


def todas_las_migraciones() -> list[Path]:
    return [
        ruta
        for ruta in sorted(RAIZ.glob("*/migrations/*.py"))
        if ruta.name != "__init__.py" and ".venv" not in ruta.parts
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contrato de las migraciones nuevas (RED-14, RED-19, RED-57).")
    parser.add_argument("archivos", nargs="*", type=Path, help="archivos concretos a revisar")
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help=f"rama base de la comparación ({BASE_POR_DEFECTO})")
    parser.add_argument("--todas", action="store_true", help="revisar todas las migraciones del repo")
    args = parser.parse_args(argv)

    if args.archivos:
        rutas = args.archivos
    elif args.todas:
        rutas = todas_las_migraciones()
    else:
        rutas = migraciones_nuevas(args.base)

    if not rutas:
        print("check_migraciones: ninguna migración nueva que revisar.")
        return 0

    hallazgos = [hallazgo for ruta in rutas for hallazgo in revisar_archivo(ruta)]
    for hallazgo in hallazgos:
        print(hallazgo)

    print(f"check_migraciones: {len(rutas)} migración(es) revisada(s), {len(hallazgos)} problema(s).")
    if hallazgos:
        print("Checklist completo: docs/internal/auditoria-2026-10/hallazgos/08-red-de-seguridad.md (Anexos A y C).")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    raise SystemExit(main())
