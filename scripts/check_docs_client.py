#!/usr/bin/env python
"""Gate de `docs/client/`: nada se publica en internet sin que alguien lo mire (RED-64).

`docs/client/` se construye con MkDocs y se publica en
https://mkdir-arg.github.io/Chaco-Back/ —un sitio **público**, `"public": true` según la
API de Pages— en cada push a `development` que toque esa carpeta. Entre el commit y la
URL pública pasa menos de un minuto y no hay nadie en el medio: `/pm:reporte`,
`/pm:minuta` y `/analisis:publicar` escriben ahí.

La mitad humana de la ficha es el `environment:` del job con *required reviewers*, que lo
configura el dueño del repo. Esta es la mitad mecánica, y corre **dos veces**: como paso
del workflow que publica (antes de construir) y como test de la suite
(`core/tests/test_docs_client_publicacion.py`), para que el hallazgo aparezca en el PR y
no recién cuando el dato ya está en internet.

    python scripts/check_docs_client.py            # revisa docs/client/ entero
    python scripts/check_docs_client.py --json     # la misma salida, para un test

Tres reglas. Alcanza con que dispare una.

1. **Persona identificable.** Un documento (7 u 8 dígitos, con o sin puntos) en una línea
   que además nombra el documento —«DNI», «D.N.I.», «documento»—, o un CUIL/CUIT bien
   formado en cualquier lado. El CUIL no necesita palabra cerca: el prefijo `20/23/24/27`
   más 9 dígitos ya lo identifica solo. Es la regla que encontró el caso real que este PR
   despublica: una respuesta de RENAPER con nombre, DNI, CUIL y domicilio de una persona
   de verdad, pegada en `funcionalidades/programa-becas.md` «para mostrar al equipo
   Ministerio».

2. **Secreto con valor.** Una clave que se llama `password`/`contraseña`/`secret`/`token`/
   `api_key` seguida de `:` o `=` y de un valor que **no** es un marcador de posición. El
   `\\S` de la ficha marcaba las doce líneas de `versiones/version-001.md` que documentan
   el `.env` con `<password-db>` y `…`, que es justo lo que hay que escribir: lo que se
   mira es el valor, no la clave. Un marcador es `<…>`, `{{…}}`, `$VAR`, `…`, `***`, un
   backtick, o una de las palabras de `PALABRAS_DE_RELLENO`.

3. **Archivo fuera del nav.** MkDocs construye **todo** `docs_dir`, esté o no en el menú:
   un `.md` suelto queda publicado y accesible por URL sin aparecer en ningún índice, que
   es la peor forma de publicar algo sin querer. Lo declarado a propósito va en el
   `not_in_nav` de `mkdocs.yml`, donde se ve.

No hay archivo de excepciones, por el mismo motivo que `check_datos_personales.py` no
tiene globs: una lista de perdonados es un escondite. Un falso positivo se arregla
escribiendo el valor como marcador o declarando el archivo en `not_in_nav`.

Salida: una línea `::error file=…,line=…::` por hallazgo —GitHub la muestra sobre el
archivo en la pestaña del PR— y código 1. **Nunca imprime el valor que encontró**, solo
dice qué regla disparó: el log de Actions de un repo público también es público.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
MKDOCS = RAIZ / "mkdocs.yml"

#: Un documento argentino: 7 u 8 dígitos, con los puntos de miles opcionales. El
#: `(?!\.?\d)` del final corta los números más largos (un CUIL, un id de trámite) sin
#: comerse el punto que cierra la oración. No es una regla de validación —esa vive una
#: sola vez, en `core.dni` (RED-48)—: acá se buscan documentos **publicados**, igual que
#: en `check_datos_personales.py`, que está exento por lo mismo.
DOCUMENTO = re.compile(r"(?<![\d.])(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})(?!\.?\d)")  # regla-dni: ok
#: La palabra que convierte a ese número en un documento de alguien.
NOMBRA_DOCUMENTO = re.compile(r"(?i)\b(dni|d\.n\.i\.?|documento|nro\.?\s*doc)\b")
#: CUIL/CUIT: prefijo de persona o empresa + 8 dígitos + verificador. Se identifica solo.
CUIL = re.compile(r"(?<!\d)(?:20|23|24|27|30|33|34)[-\s]?\d{8}[-\s]?\d(?!\d)")

#: Clave que se llama como un secreto, su separador y el valor que le sigue.
SECRETO = re.compile(
    r"(?i)\b[\w.]*(?:password|passwd|contrase[nñ]a|secret|token|api[_-]?key)[\w.]*\s*[:=]\s*(?P<valor>\S+)"
)
#: Un valor que es un marcador de posición y no un secreto.
RELLENO = re.compile(r"^[<{$`*\[(\"']|^\.{3}|^…|^-+$|^_+$")
PALABRAS_DE_RELLENO = frozenset(
    {
        "none",
        "null",
        "n/a",
        "na",
        "placeholder",
        "ejemplo",
        "example",
        "valor",
        "value",
        "tu",
        "su",
        "xxx",
        "xxxx",
        "xxxxx",
        "cambiar",
        "change",
        "changeme",
        "opcional",
        "vacío",
        "vacio",
    }
)
#: Por debajo de esto no es un secreto, es prosa que quedó pegada al separador.
LARGO_MINIMO_DE_SECRETO = 6


def _cargar_mkdocs(ruta: Path = MKDOCS) -> dict:
    """`mkdocs.yml` trae `!!python/name:` (emoji, superfences): `safe_load` solo lo rechaza."""

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda *_: None)
    Loader.add_multi_constructor("!!python/name:", lambda *_: None)
    return yaml.load(ruta.read_text(encoding="utf-8"), Loader=Loader) or {}


def _paginas_del_nav(nav) -> set[str]:
    """Las rutas `.md` del `nav`, a cualquier profundidad."""
    encontradas: set[str] = set()
    if isinstance(nav, str):
        if nav.endswith(".md"):
            encontradas.add(nav.lstrip("/"))
    elif isinstance(nav, list):
        for entrada in nav:
            encontradas |= _paginas_del_nav(entrada)
    elif isinstance(nav, dict):
        for valor in nav.values():
            encontradas |= _paginas_del_nav(valor)
    return encontradas


def _patrones_fuera_del_nav(config: dict) -> list[str]:
    """`not_in_nav` es un bloque de patrones estilo `.gitignore`, uno por línea."""
    crudo = config.get("not_in_nav") or ""
    if isinstance(crudo, list):
        lineas = crudo
    else:
        lineas = str(crudo).splitlines()
    return [linea.strip().lstrip("/") for linea in lineas if linea.strip() and not linea.strip().startswith("#")]


def _declarado_fuera_del_nav(relativa: str, patrones: list[str]) -> bool:
    for patron in patrones:
        if patron.endswith("/"):
            if relativa.startswith(patron):
                return True
        elif relativa == patron or relativa.startswith(patron.rstrip("/") + "/"):
            return True
    return False


def _es_relleno(valor: str) -> bool:
    if RELLENO.search(valor):
        return True
    limpio = valor.strip("`'\"*,.;:()[]{}<>").lower()
    if len(limpio) < LARGO_MINIMO_DE_SECRETO:
        return True
    return limpio in PALABRAS_DE_RELLENO or limpio.startswith("<") or limpio.endswith(">")


def _revisar_contenido(relativa: str, texto: str) -> list[dict]:
    hallazgos = []
    # Las tres reglas miran **todas** las líneas, también las de adentro de un bloque de
    # código: el hallazgo real de esta ficha estaba justamente en un ```json.
    for numero, linea in enumerate(texto.splitlines(), 1):
        if NOMBRA_DOCUMENTO.search(linea) and DOCUMENTO.search(linea):
            hallazgos.append(
                {
                    "archivo": relativa,
                    "linea": numero,
                    "regla": "persona",
                    "mensaje": "un número de documento junto a la palabra que lo nombra",
                }
            )
        if CUIL.search(linea):
            hallazgos.append(
                {
                    "archivo": relativa,
                    "linea": numero,
                    "regla": "persona",
                    "mensaje": "algo con forma de CUIL/CUIT",
                }
            )
        secreto = SECRETO.search(linea)
        if secreto and not _es_relleno(secreto.group("valor")):
            hallazgos.append(
                {
                    "archivo": relativa,
                    "linea": numero,
                    "regla": "secreto",
                    "mensaje": "una clave de secreto con un valor que no es un marcador de posición",
                }
            )
    return hallazgos


def revisar(raiz: Path = RAIZ) -> list[dict]:
    """Todos los hallazgos de `docs/client/`, ordenados por archivo y línea."""
    config = _cargar_mkdocs(raiz / "mkdocs.yml")
    carpeta = raiz / (config.get("docs_dir") or "docs/client")
    if not carpeta.is_dir():
        return [{"archivo": str(carpeta), "linea": 1, "regla": "nav", "mensaje": "docs_dir no existe"}]

    del_nav = _paginas_del_nav(config.get("nav"))
    fuera_del_nav = _patrones_fuera_del_nav(config)

    hallazgos: list[dict] = []
    for ruta in sorted(carpeta.rglob("*.md")):
        relativa = ruta.relative_to(carpeta).as_posix()
        if relativa not in del_nav and not _declarado_fuera_del_nav(relativa, fuera_del_nav):
            hallazgos.append(
                {
                    "archivo": (ruta.relative_to(raiz)).as_posix(),
                    "linea": 1,
                    "regla": "nav",
                    "mensaje": "se publica pero no está en el nav de mkdocs.yml ni declarado en not_in_nav",
                }
            )
        hallazgos += _revisar_contenido(
            (ruta.relative_to(raiz)).as_posix(), ruta.read_text(encoding="utf-8", errors="replace")
        )
    return sorted(hallazgos, key=lambda h: (h["archivo"], h["linea"], h["regla"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gate de publicación de docs/client/ (RED-64).")
    parser.add_argument("--json", action="store_true", help="imprime los hallazgos como JSON")
    parser.add_argument("--raiz", default=str(RAIZ), help="raíz del repo (para los tests)")
    args = parser.parse_args(argv)

    hallazgos = revisar(Path(args.raiz))
    if args.json:
        print(json.dumps(hallazgos, ensure_ascii=False, indent=2))
    else:
        for hallazgo in hallazgos:
            print(
                f"::error file={hallazgo['archivo']},line={hallazgo['linea']}::"
                f"[{hallazgo['regla']}] {hallazgo['mensaje']}"
            )
        total = len(hallazgos)
        print(f"docs/client/: {total} hallazgo(s) que frenan la publicación")
        if total:
            print(
                "Cómo se arregla: sacá el dato de la persona, escribí el secreto como "
                "marcador (<valor>), o declará el archivo en el nav o en not_in_nav de mkdocs.yml."
            )
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
