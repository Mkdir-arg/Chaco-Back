#!/usr/bin/env python
"""Consulta el archivo vivo de requerimientos sin leerlo entero.

El registro de requerimientos crece con cada desarrollo, así que cargarlo completo
para buscar un dato es caro y en algún momento deja de entrar en contexto. Este script
lo indexa y devuelve solo lo pedido.

Vive en dos lugares y el script lee los dos juntos: `docs/internal/requerimientos.md`
(la regla, el vocabulario, la plantilla y el historial hasta `ULTIMO_CAMBIO_HISTORICO`,
congelado) y la carpeta `docs/internal/requerimientos/`, con un archivo `N.md` por cada
Cambio nuevo. El índice de esos archivos no se escribe: se arma desde su ficha.

    python scripts/requerimientos.py                  # índice compacto
    python scripts/requerimientos.py --tag rbac       # filtrar por etiqueta
    python scripts/requerimientos.py --programa becas # filtrar por programa
    python scripts/requerimientos.py --buscar "cupo"  # texto dentro de las entradas
    python scripts/requerimientos.py --ver 24         # una entrada completa
    python scripts/requerimientos.py --check          # coherencia índice <-> entradas
    python scripts/requerimientos.py --siguiente      # número libre para el Cambio nuevo

No importa Django ni toca la base: lee el markdown y nada más.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "internal" / "requerimientos.md"
CARPETA = DOC.parent / "requerimientos"
RAIZ = DOC.parents[2]

# Un archivo por Cambio nuevo: `549.md`, o `96.37.md` para un sub-pedido. Sin slug: dos PR con
# el mismo número crean la misma ruta y git los frena con un conflicto add/add.
NOMBRE_RE = re.compile(r"^(\d+(?:\.\d+)?)\.md$")
CAMPO_FICHA_RE = re.compile(r"^\|\s*\*\*(?P<campo>[^*]+)\*\*\s*\|(?P<valor>.*)\|\s*$")
# El historial de `requerimientos.md` está congelado en este Cambio: lo que sigue va a la carpeta.
ULTIMO_CAMBIO_HISTORICO = 548

ENTRADA_RE = re.compile(r"^# Cambio ([\d.]+) — (.+)$")
# Los sub-pedidos de un requerimiento se escriben como "## 6.1 Título" dentro de su
# entrada madre, y cuentan como entrada propia para el índice y para --ver. Se los
# distingue de una subsección numerada cualquiera (por ejemplo "## 15.1 Usuarios y
# roles", que es una parte del Cambio 15 y no un pedido aparte) porque el sub-pedido
# lleva su propio semáforo de estado justo debajo del título.
SUBENTRADA_RE = re.compile(r"^## (\d+\.\d+) (?:—\s*)?(.+)$")
SEMAFOROS = ("🟢", "🟡", "🔴", "⚪")
FILA_RE = re.compile(r"^\|\s*([\d.]+)\s*\|")
ETIQUETA_RE = re.compile(r"`(#[a-z-]+)`")
VOCABULARIO_INICIO = "### Etiquetas"

# RED-84 · Una entrada con migración tiene que decir cómo se vuelve.
# El piso evita reescribir el histórico: la regla rige desde el Cambio 135, el primero
# que se escribió con el check puesto. Las entradas anteriores quedan como están.
PRIMER_CAMBIO_CON_REVERSION = 135
SIN_MIGRACION_RE = re.compile(r"no\s+(requiere|aplica)|^no$|sin\s+migraci", re.IGNORECASE)
# Las migraciones se nombran `app.NNNN` o `app.NNNN_con_el_nombre_completo`. El `\b` del
# final no sirve: después de los cuatro dígitos viene un `_`, que es carácter de palabra,
# así que `programas.0075_enviosiis_vigente` no coincidía y la regla no corría nunca.
MIGRACION_RE = re.compile(r"\b([a-z][a-z_]*)\.(\d{4})(?:_\w+)?")
CAMPO_MIGRACION_RE = re.compile(r"^\|\s*\*\*Migración\*\*\s*\|(?P<valor>.*)\|\s*$")


@dataclass
class Entrada:
    """Una entrada `# Cambio N` con su rango de líneas dentro del documento."""

    numero: str
    titulo: str
    linea_desde: int
    linea_hasta: int = 0
    estado: str = ""
    # Solo para las entradas de la carpeta: el archivo y la línea 0 del archivo dentro de la
    # lista concatenada de líneas (para informar la línea relativa al archivo).
    archivo: Path | None = None
    offset: int = 0


@dataclass
class Fila:
    """Una fila del índice."""

    numero: str
    titulo: str
    programa: str
    etiquetas: list[str] = field(default_factory=list)
    solicitante: str = ""
    pedido: str = ""
    estado: str = ""
    migracion: str = ""


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if not unicodedata.combining(c))


def _limpiar(celda: str) -> str:
    """Quita el ruido de markdown de una celda para poder imprimirla en columna."""
    celda = celda.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", celda)


def _clave_orden(numero: str) -> tuple[int, int]:
    mayor, _, menor = numero.partition(".")
    return int(mayor), int(menor or 0)


def _nombre_archivo(entrada: Entrada) -> str:
    """`requerimientos/549.md`: el archivo de una entrada de la carpeta."""
    return f"{entrada.archivo.parent.name}/{entrada.archivo.name}"


def _ficha(lineas: list[str]) -> dict[str, str]:
    """Los campos `| **Campo** | valor |` de la ficha, que va antes de la primera sección."""
    campos: dict[str, str] = {}
    for linea in lineas[1:]:
        if linea.startswith("## "):
            break
        coincidencia = CAMPO_FICHA_RE.match(linea)
        if coincidencia:
            campos.setdefault(coincidencia.group("campo").strip(), coincidencia.group("valor").strip())
    return campos


def _archivos_de_la_carpeta(carpeta: Path) -> list[Path]:
    """Los `.md` de la carpeta: primero los de nombre válido por número, después los inválidos."""

    def clave(ruta: Path) -> tuple[int, tuple[int, int], str]:
        coincidencia = NOMBRE_RE.match(ruta.name)
        if coincidencia:
            return 0, _clave_orden(coincidencia.group(1)), ruta.name
        return 1, (0, 0), ruta.name

    return sorted(carpeta.glob("*.md"), key=clave)


def _leer_carpeta(carpeta: Path, lineas: list[str], filas: list[Fila], entradas: list[Entrada]) -> None:
    """Suma a las listas las entradas y las filas de los archivos de la carpeta."""
    for archivo in _archivos_de_la_carpeta(carpeta):
        propias = archivo.read_text(encoding="utf-8").splitlines()
        desde = len(lineas) + 1
        lineas.extend(propias)
        hasta = len(lineas)
        coincidencia_nombre = NOMBRE_RE.match(archivo.name)
        coincidencia = ENTRADA_RE.match(propias[0]) if propias else None
        if not coincidencia_nombre or not coincidencia:
            motivo = (
                "el nombre no es `N.md` (sin slug)"
                if not coincidencia_nombre
                else "la primera línea no es `# Cambio N — Título`"
            )
            entradas.append(
                Entrada(
                    numero="", titulo=motivo, linea_desde=desde, linea_hasta=hasta, archivo=archivo, offset=desde - 1
                )
            )
            continue

        entrada = Entrada(
            numero=coincidencia.group(1),
            titulo=coincidencia.group(2).strip(),
            linea_desde=desde,
            linea_hasta=hasta,
            archivo=archivo,
            offset=desde - 1,
        )
        for linea in propias[1:5]:
            if any(s in linea for s in SEMAFOROS):
                entrada.estado = _limpiar(linea)
                break
        entradas.append(entrada)

        ficha = _ficha(propias)
        filas.append(
            Fila(
                numero=entrada.numero,
                titulo=_limpiar(entrada.titulo),
                programa=_limpiar(ficha.get("Programa / módulo", "")),
                etiquetas=ETIQUETA_RE.findall(ficha.get("Etiquetas", "")),
                solicitante=_limpiar(ficha.get("Solicitante", "")),
                pedido=_limpiar(ficha.get("Fecha del pedido", "")),
                estado=entrada.estado,
                migracion=_limpiar(ficha.get("Migración", "")),
            )
        )


def leer_documento(
    ruta: Path | None = None, carpeta: Path | None = None
) -> tuple[list[str], list[Fila], list[Entrada], set[str]]:
    """Lee el historial y, si hay carpeta, los archivos por Cambio.

    Sin `ruta` se usa el registro real (`DOC` y `CARPETA`). Con una `ruta` explícita solo se
    lee la carpeta si también se la pasa.
    """
    if ruta is None:
        ruta = DOC
        carpeta = CARPETA
    if not ruta.exists():
        sys.exit(f"No se encontró {ruta}")

    lineas = ruta.read_text(encoding="utf-8").splitlines()

    # El vocabulario de etiquetas es la tabla que sigue a "### Etiquetas".
    vocabulario: set[str] = set()
    en_vocabulario = False
    for linea in lineas:
        if linea.startswith(VOCABULARIO_INICIO):
            en_vocabulario = True
            continue
        if en_vocabulario:
            if linea.startswith("## "):
                break
            vocabulario.update(ETIQUETA_RE.findall(linea))

    # El índice es la tabla que sigue a "## Índice"; sus filas empiezan con el número.
    filas: list[Fila] = []
    en_indice = False
    for linea in lineas:
        if linea.startswith("## Índice"):
            en_indice = True
            continue
        if en_indice:
            if linea.startswith("## ") or linea.startswith("**Notas"):
                break
            if not FILA_RE.match(linea):
                continue
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            if len(celdas) < 8:
                continue
            filas.append(
                Fila(
                    numero=_limpiar(celdas[0]),
                    titulo=_limpiar(celdas[1]),
                    programa=_limpiar(celdas[2]),
                    etiquetas=ETIQUETA_RE.findall(celdas[3]),
                    solicitante=_limpiar(celdas[4]),
                    pedido=_limpiar(celdas[5]),
                    estado=_limpiar(celdas[6]),
                    migracion=_limpiar(celdas[7]),
                )
            )

    # Las entradas reales. La plantilla usa "# Cambio N — Título…" como ejemplo
    # dentro de un bloque ```markdown: se saltea para no contarla como entrada.
    entradas: list[Entrada] = []
    en_bloque = False
    for numero_linea, linea in enumerate(lineas, start=1):
        if linea.startswith("```"):
            en_bloque = not en_bloque
            continue
        if en_bloque:
            continue
        coincidencia = ENTRADA_RE.match(linea)
        if not coincidencia:
            subentrada = SUBENTRADA_RE.match(linea)
            siguientes = lineas[numero_linea : numero_linea + 3]
            if subentrada and any(
                semaforo in linea_siguiente for linea_siguiente in siguientes for semaforo in SEMAFOROS
            ):
                coincidencia = subentrada
        if coincidencia:
            if entradas:
                entradas[-1].linea_hasta = numero_linea - 1
            entradas.append(
                Entrada(
                    numero=coincidencia.group(1),
                    titulo=coincidencia.group(2).strip(),
                    linea_desde=numero_linea,
                )
            )
        elif linea.startswith("# ") and entradas and not entradas[-1].linea_hasta:
            # Un h1 que no es una entrada (por ejemplo "# Verificaciones generales")
            # cierra la última.
            entradas[-1].linea_hasta = numero_linea - 1
    if entradas and not entradas[-1].linea_hasta:
        entradas[-1].linea_hasta = len(lineas)

    # El estado de cada entrada es su primera línea con semáforo.
    for entrada in entradas:
        for linea in lineas[entrada.linea_desde : min(entrada.linea_desde + 4, len(lineas))]:
            if any(s in linea for s in ("🟢", "🟡", "🔴", "⚪")):
                entrada.estado = _limpiar(linea)
                break

    if carpeta is not None and carpeta.is_dir():
        _leer_carpeta(carpeta, lineas, filas, entradas)

    return lineas, filas, entradas, vocabulario


def imprimir_indice(filas: list[Fila], entradas: list[Entrada], titulo: str) -> None:
    por_numero = {e.numero: e for e in entradas}
    print(titulo)
    print()
    for fila in sorted(filas, key=lambda f: _clave_orden(f.numero)):
        entrada = por_numero.get(fila.numero)
        if not entrada:
            ubicacion = "SIN ENTRADA"
        elif entrada.archivo:
            ubicacion = _nombre_archivo(entrada)
        else:
            ubicacion = f"L{entrada.linea_desde}"
        print(f"  {fila.numero:>4}  {fila.titulo}")
        print(f"        {fila.programa} · {' '.join(fila.etiquetas)} · {fila.estado}  [{ubicacion}]")
    print()
    print(f"  {len(filas)} requerimientos. Para leer uno: --ver <N>")


def comando_ver(numero: str, lineas: list[str], entradas: list[Entrada]) -> int:
    for entrada in entradas:
        if entrada.numero == numero:
            if entrada.archivo:
                print(f"[{_nombre_archivo(entrada)}]")
            else:
                print(f"[{DOC.name} líneas {entrada.linea_desde}-{entrada.linea_hasta}]")
            print()
            print("\n".join(lineas[entrada.linea_desde - 1 : entrada.linea_hasta]).rstrip())
            return 0
    disponibles = ", ".join(e.numero for e in entradas if e.numero)
    print(f"No existe el requerimiento {numero}. Hay: {disponibles}", file=sys.stderr)
    return 1


def comando_buscar(texto: str, lineas: list[str], entradas: list[Entrada]) -> int:
    aguja = _sin_tildes(texto)
    encontrados = 0
    for entrada in entradas:
        if not entrada.numero:
            continue
        golpes = [
            (numero, linea.strip())
            for numero, linea in enumerate(
                lineas[entrada.linea_desde - 1 : entrada.linea_hasta], start=entrada.linea_desde - entrada.offset
            )
            if aguja in _sin_tildes(linea)
        ]
        if not golpes:
            continue
        encontrados += 1
        print(f"  Cambio {entrada.numero} — {entrada.titulo}  [--ver {entrada.numero}]")
        prefijo = f"{entrada.archivo.name} " if entrada.archivo else ""
        for numero, linea in golpes[:3]:
            recorte = linea if len(linea) <= 150 else linea[:147] + "..."
            print(f"        {prefijo}L{numero}: {recorte}")
        if len(golpes) > 3:
            print(f"        … y {len(golpes) - 3} coincidencias más en esta entrada")
        print()
    if not encontrados:
        print(f'Sin coincidencias para "{texto}".')
        return 1
    print(f"  {encontrados} requerimiento(s) con coincidencias.")
    return 0


def _secciones(lineas: list[str], entrada: Entrada) -> dict[str, list[str]]:
    """Las secciones `## Título` de una entrada, con sus líneas con contenido."""
    secciones: dict[str, list[str]] = {}
    actual: str | None = None
    en_bloque = False
    for linea in lineas[entrada.linea_desde - 1 : entrada.linea_hasta]:
        if linea.startswith("```"):
            en_bloque = not en_bloque
        if not en_bloque and linea.startswith("## "):
            actual = linea[3:].strip()
            secciones[actual] = []
            continue
        if actual and linea.strip():
            secciones[actual].append(linea.strip())
    return secciones


def _migracion_declarada(lineas: list[str], entrada: Entrada) -> str | None:
    """El valor de la fila `| **Migración** | … |` de la ficha de la entrada."""
    for linea in lineas[entrada.linea_desde - 1 : entrada.linea_hasta]:
        coincidencia = CAMPO_MIGRACION_RE.match(linea)
        if coincidencia:
            return coincidencia.group("valor").strip()
    return None


def problemas_de_reversion(lineas: list[str], entradas: list[Entrada]) -> list[str]:
    """RED-84: una entrada con migración dice qué migración y cómo se vuelve.

    Solo para las entradas desde `PRIMER_CAMBIO_CON_REVERSION`: el histórico se deja
    como está. Una `## Reversión` de una sola línea («No aplica») no cuenta: es
    justamente lo que el operador no puede leer la noche del rollback.
    """
    problemas: list[str] = []

    for entrada in entradas:
        if not entrada.numero or _clave_orden(entrada.numero)[0] < PRIMER_CAMBIO_CON_REVERSION:
            continue

        declarada = _migracion_declarada(lineas, entrada)
        if declarada is None:
            problemas.append(f"El Cambio {entrada.numero} no tiene la fila «**Migración**» de la plantilla.")
            continue

        # Primero se mira si la celda **nombra** una migración: «`programas.0076_x` (el
        # backfill no aplica a Dispositivos)» tiene migración y además dice «no aplica»,
        # y un `search` suelto del «no aplica» eximía la entrada entera.
        migraciones = [f"{app}.{numero}" for app, numero in MIGRACION_RE.findall(declarada)]
        if not migraciones:
            if SIN_MIGRACION_RE.search(_limpiar(declarada)):
                continue
            problemas.append(
                f"El Cambio {entrada.numero}: la fila «**Migración**» no nombra ninguna migración "
                "(`app.NNNN`) ni dice «No requiere»."
            )
            continue

        secciones = _secciones(lineas, entrada)

        base = secciones.get("Base de datos")
        if base is None:
            problemas.append(f"El Cambio {entrada.numero} declara migración y no tiene la sección «## Base de datos».")
        elif not any(m in " ".join(base) for m in migraciones):
            problemas.append(
                f"El Cambio {entrada.numero}: «## Base de datos» no nombra la migración ({', '.join(migraciones)})."
            )

        reversion = secciones.get("Reversión")
        if reversion is None:
            problemas.append(f"El Cambio {entrada.numero} declara migración y no tiene la sección «## Reversión».")
        elif len(reversion) < 2:
            problemas.append(
                f"El Cambio {entrada.numero}: «## Reversión» tiene {len(reversion)} línea(s). "
                "Con migración de por medio hay que escribir los pasos en orden y qué datos se pierden "
                "(runbook D.4 de processes.md)."
            )

    return problemas


def _duplicados(numeros: list[str]) -> list[str]:
    vistos: set[str] = set()
    repetidos: set[str] = set()
    for numero in numeros:
        (repetidos if numero in vistos else vistos).add(numero)
    return sorted(repetidos, key=_clave_orden)


def _subpedidos_dentro(lineas: list[str], entrada: Entrada) -> list[str]:
    """Los `## N.M` con semáforo dentro de una entrada: un sub-pedido tiene su propio archivo."""
    encontrados: list[str] = []
    en_bloque = False
    rango = lineas[entrada.linea_desde - 1 : entrada.linea_hasta]
    for posicion, linea in enumerate(rango):
        if linea.startswith("```"):
            en_bloque = not en_bloque
            continue
        coincidencia = SUBENTRADA_RE.match(linea)
        if en_bloque or not coincidencia:
            continue
        if any(s in siguiente for siguiente in rango[posicion + 1 : posicion + 4] for s in SEMAFOROS):
            encontrados.append(coincidencia.group(1))
    return encontrados


def problemas_de_estructura(
    filas: list[Fila],
    entradas: list[Entrada],
    lineas: list[str],
    ultimo: int = ULTIMO_CAMBIO_HISTORICO,
) -> list[str]:
    """Reglas del registro partido: historial congelado + un archivo por Cambio nuevo."""
    problemas: list[str] = []

    validas = [e for e in entradas if e.numero]
    for numero in _duplicados([e.numero for e in validas]):
        problemas.append(f"El Cambio {numero} tiene más de una entrada.")
    for numero in _duplicados([f.numero for f in filas]):
        problemas.append(f"El Cambio {numero} figura más de una vez en el índice.")

    numeros_existentes = {e.numero for e in validas}

    for entrada in entradas:
        if not entrada.archivo:
            # El historial está congelado: un Cambio nuevo no se escribe ahí.
            if entrada.numero and _clave_orden(entrada.numero)[0] > ultimo:
                problemas.append(
                    f"El Cambio {entrada.numero} está en {DOC.name}, que está congelado en el {ultimo}: "
                    f"el Cambio {entrada.numero} va en docs/internal/requerimientos/{entrada.numero}.md."
                )
            continue

        nombre = _nombre_archivo(entrada)
        if not entrada.numero:
            # Nombre inválido o archivo sin encabezado `# Cambio N — Título`.
            problemas.append(f"{nombre}: {entrada.titulo}.")
            continue

        # El número del archivo es el del H1.
        if entrada.archivo.stem != entrada.numero:
            problemas.append(
                f"{nombre} dice `# Cambio {entrada.numero}`: el número del archivo y el del título tienen que coincidir."
            )
        # Un número entero es posterior al historial; un N.M cuelga de un N que existe.
        mayor = _clave_orden(entrada.numero)[0]
        if "." not in entrada.numero:
            if mayor <= ultimo:
                problemas.append(
                    f"{nombre}: el Cambio {mayor} pertenece al historial (hasta el {ultimo}); "
                    "un Cambio nuevo lleva el número siguiente (`--siguiente`)."
                )
        elif str(mayor) not in numeros_existentes:
            problemas.append(f"{nombre}: el sub-pedido {entrada.numero} cuelga del Cambio {mayor}, que no existe.")
        # Un sub-pedido va en su propio archivo.
        for sub in _subpedidos_dentro(lineas, entrada):
            problemas.append(f"{nombre} contiene el sub-pedido {sub}: va en su propio archivo `{sub}.md`.")

    return problemas


def comando_check(
    filas: list[Fila], entradas: list[Entrada], vocabulario: set[str], lineas: list[str] | None = None
) -> int:
    problemas: list[str] = []

    numeros_indice = {f.numero for f in filas}
    numeros_entrada = {e.numero for e in entradas if e.numero}

    for numero in sorted(numeros_entrada - numeros_indice, key=_clave_orden):
        problemas.append(f"El Cambio {numero} tiene entrada pero no figura en el índice.")
    for numero in sorted(numeros_indice - numeros_entrada, key=_clave_orden):
        problemas.append(f"El Cambio {numero} está en el índice pero no tiene entrada.")

    for fila in filas:
        if not fila.etiquetas:
            problemas.append(f"El Cambio {fila.numero} no tiene etiquetas en el índice.")
        for etiqueta in fila.etiquetas:
            if etiqueta not in vocabulario:
                problemas.append(
                    f"El Cambio {fila.numero} usa la etiqueta {etiqueta}, "
                    "que no está en el vocabulario de la sección Etiquetas."
                )
        for campo, valor in (
            ("programa", fila.programa),
            ("solicitante", fila.solicitante),
            ("fecha de pedido", fila.pedido),
        ):
            if not valor:
                problemas.append(f"El Cambio {fila.numero} tiene el {campo} vacío.")

    if lineas is not None:
        problemas.extend(problemas_de_estructura(filas, entradas, lineas))
        problemas.extend(problemas_de_reversion(lineas, entradas))

    if problemas:
        print(f"{len(problemas)} problema(s):")
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    sin_registrar = [f.numero for f in filas if "sin registrar" in f.solicitante.lower()]
    print(f"OK: {len(filas)} requerimientos, índice y entradas coinciden.")
    print(f"    Vocabulario: {len(vocabulario)} etiquetas.")
    if sin_registrar:
        print(f"    Con solicitante «sin registrar» (deuda conocida): {', '.join(sin_registrar)}")
    return 0


def _git(*argumentos: str) -> list[str]:
    """Salida de `git`, por líneas; vacía si git no está o falla (el número local alcanza)."""
    try:
        resultado = subprocess.run(
            ["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return resultado.stdout.splitlines() if resultado.returncode == 0 else []


def siguiente_numero(entradas: list[Entrada], con_remotas: bool = True) -> int:
    """Máximo + 1 entre el historial, la carpeta local y la carpeta de cada rama remota."""
    mayores = [ULTIMO_CAMBIO_HISTORICO]
    mayores.extend(_clave_orden(e.numero)[0] for e in entradas if e.numero)
    if con_remotas:
        carpeta = CARPETA.relative_to(RAIZ).as_posix() + "/"
        for ref in _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin"):
            for ruta in _git("ls-tree", "--name-only", "-r", ref, carpeta):
                coincidencia = NOMBRE_RE.match(ruta.rsplit("/", 1)[-1])
                if coincidencia:
                    mayores.append(_clave_orden(coincidencia.group(1))[0])
    return max(mayores) + 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consulta el registro de requerimientos (docs/internal/requerimientos.md y la carpeta "
        "docs/internal/requerimientos/) por índice y etiquetas.",
    )
    parser.add_argument("--tag", "--etiqueta", dest="tag", help="filtrar por etiqueta (con o sin #)")
    parser.add_argument("--programa", help="filtrar por programa o módulo")
    parser.add_argument("--buscar", help="buscar texto dentro de las entradas")
    parser.add_argument("--ver", help="imprimir una entrada completa por su número")
    parser.add_argument("--check", action="store_true", help="verificar coherencia del archivo")
    parser.add_argument(
        "--siguiente",
        action="store_true",
        help="imprimir el número libre para el Cambio nuevo (mira el historial, la carpeta y las ramas remotas)",
    )
    parser.add_argument("--fetch", action="store_true", help="con --siguiente: `git fetch origin` antes de mirar")
    args = parser.parse_args()

    lineas, filas, entradas, vocabulario = leer_documento()

    if args.siguiente:
        if args.fetch:
            _git("fetch", "origin")
        print(siguiente_numero(entradas))
        return 0

    if args.check:
        return comando_check(filas, entradas, vocabulario, lineas)
    if args.ver:
        return comando_ver(args.ver.strip(), lineas, entradas)
    if args.buscar:
        return comando_buscar(args.buscar, lineas, entradas)

    titulo = f"Requerimientos ({DOC.relative_to(DOC.parents[2])})"
    if args.tag:
        etiqueta = args.tag if args.tag.startswith("#") else f"#{args.tag}"
        if etiqueta not in vocabulario:
            print(
                f"La etiqueta {etiqueta} no está en el vocabulario. Hay: {' '.join(sorted(vocabulario))}",
                file=sys.stderr,
            )
            return 1
        filas = [f for f in filas if etiqueta in f.etiquetas]
        titulo = f"Requerimientos con {etiqueta}"
    if args.programa:
        aguja = _sin_tildes(args.programa)
        filas = [f for f in filas if aguja in _sin_tildes(f.programa)]
        titulo += f" · programa ~ {args.programa}"

    if not filas:
        print("Sin requerimientos para ese filtro.")
        return 1

    imprimir_indice(filas, entradas, titulo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
