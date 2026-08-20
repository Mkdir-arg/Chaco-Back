#!/usr/bin/env python
"""Consulta el archivo vivo de requerimientos sin leerlo entero.

`docs/internal/requerimientos.md` crece con cada desarrollo, así que cargarlo
completo para buscar un dato es caro y en algún momento deja de entrar en
contexto. Este script lo indexa y devuelve solo lo pedido.

    python scripts/requerimientos.py                  # índice compacto
    python scripts/requerimientos.py --tag rbac       # filtrar por etiqueta
    python scripts/requerimientos.py --programa becas # filtrar por programa
    python scripts/requerimientos.py --buscar "cupo"  # texto dentro de las entradas
    python scripts/requerimientos.py --ver 24         # una entrada completa
    python scripts/requerimientos.py --check          # coherencia índice <-> entradas

No importa Django ni toca la base: lee el markdown y nada más.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "internal" / "requerimientos.md"

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


@dataclass
class Entrada:
    """Una entrada `# Cambio N` con su rango de líneas dentro del documento."""

    numero: str
    titulo: str
    linea_desde: int
    linea_hasta: int = 0
    estado: str = ""


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


def leer_documento() -> tuple[list[str], list[Fila], list[Entrada], set[str]]:
    if not DOC.exists():
        sys.exit(f"No se encontró {DOC}")

    lineas = DOC.read_text(encoding="utf-8").splitlines()

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

    return lineas, filas, entradas, vocabulario


def imprimir_indice(filas: list[Fila], entradas: list[Entrada], titulo: str) -> None:
    por_numero = {e.numero: e for e in entradas}
    print(titulo)
    print()
    for fila in sorted(filas, key=lambda f: _clave_orden(f.numero)):
        entrada = por_numero.get(fila.numero)
        ubicacion = f"L{entrada.linea_desde}" if entrada else "SIN ENTRADA"
        print(f"  {fila.numero:>4}  {fila.titulo}")
        print(f"        {fila.programa} · {' '.join(fila.etiquetas)} · {fila.estado}  [{ubicacion}]")
    print()
    print(f"  {len(filas)} requerimientos. Para leer uno: --ver <N>")


def comando_ver(numero: str, lineas: list[str], entradas: list[Entrada]) -> int:
    for entrada in entradas:
        if entrada.numero == numero:
            print(f"[{DOC.name} líneas {entrada.linea_desde}-{entrada.linea_hasta}]")
            print()
            print("\n".join(lineas[entrada.linea_desde - 1 : entrada.linea_hasta]).rstrip())
            return 0
    disponibles = ", ".join(e.numero for e in entradas)
    print(f"No existe el requerimiento {numero}. Hay: {disponibles}", file=sys.stderr)
    return 1


def comando_buscar(texto: str, lineas: list[str], entradas: list[Entrada]) -> int:
    aguja = _sin_tildes(texto)
    encontrados = 0
    for entrada in entradas:
        golpes = [
            (numero, linea.strip())
            for numero, linea in enumerate(
                lineas[entrada.linea_desde - 1 : entrada.linea_hasta], start=entrada.linea_desde
            )
            if aguja in _sin_tildes(linea)
        ]
        if not golpes:
            continue
        encontrados += 1
        print(f"  Cambio {entrada.numero} — {entrada.titulo}  [--ver {entrada.numero}]")
        for numero, linea in golpes[:3]:
            recorte = linea if len(linea) <= 150 else linea[:147] + "..."
            print(f"        L{numero}: {recorte}")
        if len(golpes) > 3:
            print(f"        … y {len(golpes) - 3} coincidencias más en esta entrada")
        print()
    if not encontrados:
        print(f'Sin coincidencias para "{texto}".')
        return 1
    print(f"  {encontrados} requerimiento(s) con coincidencias.")
    return 0


def comando_check(filas: list[Fila], entradas: list[Entrada], vocabulario: set[str]) -> int:
    problemas: list[str] = []

    numeros_indice = {f.numero for f in filas}
    numeros_entrada = {e.numero for e in entradas}

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
        for campo, valor in (("solicitante", fila.solicitante), ("fecha de pedido", fila.pedido)):
            if not valor:
                problemas.append(f"El Cambio {fila.numero} tiene el {campo} vacío.")

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consulta docs/internal/requerimientos.md por índice y etiquetas.",
    )
    parser.add_argument("--tag", "--etiqueta", dest="tag", help="filtrar por etiqueta (con o sin #)")
    parser.add_argument("--programa", help="filtrar por programa o módulo")
    parser.add_argument("--buscar", help="buscar texto dentro de las entradas")
    parser.add_argument("--ver", help="imprimir una entrada completa por su número")
    parser.add_argument("--check", action="store_true", help="verificar coherencia del archivo")
    args = parser.parse_args()

    lineas, filas, entradas, vocabulario = leer_documento()

    if args.check:
        return comando_check(filas, entradas, vocabulario)
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
