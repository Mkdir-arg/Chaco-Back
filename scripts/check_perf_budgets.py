#!/usr/bin/env python
"""RED-62 · Un presupuesto de performance que sube tiene que venir justificado.

Hasta acá los números de `scripts/perf_budgets.json` eran **autodeclarados**: la regla
«subir un `max_queries` requiere justificación» era prosa adentro del propio JSON. Un N+1
en `becas_revision` deja el job en rojo con «16 → 61»; subir el presupuesto a 61 en el
mismo PR lo deja en verde, y el N+1 entra sin que nadie se entere. Que hasta hoy siempre
se haya justificado (11 entradas en `_meta.adjustments`) no es un mecanismo.

Este script compara el archivo del PR contra el de **la base del PR** y falla si algo
sube sin una justificación escrita:

* `budgets.<ruta>.max_queries` y `.max_duplicate_queries` que crecen;
* `servicios.<servicio>.consultas_fijas` que crece, o `casos_por_consulta` que baja
  (las dos cosas son «el servicio puede consultar más»);
* `_meta.timing.reference_total_ms` que sube más de un 5 %, y los dos multiplicadores
  (`warning_multiplier`, `failure_multiplier`), que son la forma barata de aflojar esa
  misma alarma sin tocar la referencia.

Qué cuenta como justificación: una entrada **nueva o modificada** en
`_meta.adjustments` cuyo texto **nombre** el presupuesto que subió. La ficha pedía
«una clave nueva en `adjustments`»; se exige además que la nombre, porque una sola
entrada nueva alcanzaba para tapar cualquier cantidad de subidas en el mismo PR y
porque la convención del archivo ya escribe el nombre de la ruta («legajos_lista 14→12»,
«edicion_convocatoria 13→14»).

Bajar un presupuesto nunca necesita nada: es la dirección buena.

    python scripts/check_perf_budgets.py                 # contra origin/development
    python scripts/check_perf_budgets.py --base <ref>    # el CI pasa el SHA base del PR
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_PRESUPUESTOS = "scripts/perf_budgets.json"
BASE_POR_DEFECTO = "origin/development"

#: Cuánto puede moverse la alarma gruesa de tiempo sin explicación. Es una medición de
#: reloj de pared en GitHub Actions y tiene ruido propio; lo que no puede es derivar.
MARGEN_TIEMPO = 0.05


@dataclass(frozen=True)
class Hallazgo:
    presupuesto: str
    campo: str
    antes: float
    ahora: float
    motivo: str

    def __str__(self) -> str:
        return f"{self.presupuesto}.{self.campo}: {self.antes} → {self.ahora} — {self.motivo}"


def _git(*argumentos):
    return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, check=False, encoding="utf-8")


def leer_de_la_base(base: str):
    """El `perf_budgets.json` del árbol base, o `None` si ahí no existía."""
    resultado = _git("show", f"{base}:{RUTA_PRESUPUESTOS}")
    if resultado.returncode != 0:
        return None
    return json.loads(resultado.stdout)


def _ajustes(config) -> dict:
    return (config.get("_meta") or {}).get("adjustments") or {}


def justificaciones_nuevas(base, ahora) -> str:
    """El texto de las entradas de `adjustments` que este PR agregó o cambió."""
    ajustes_base, ajustes_ahora = _ajustes(base), _ajustes(ahora)
    nuevas = [f"{clave}: {texto}" for clave, texto in ajustes_ahora.items() if ajustes_base.get(clave) != texto]
    return "\n".join(nuevas)


def _numero(contenedor, clave):
    valor = contenedor.get(clave)
    return valor if isinstance(valor, (int, float)) else None


def _comparar(nombre, campo, antes, ahora, sube: bool, motivo: str):
    if antes is None or ahora is None:
        return None
    empeora = ahora > antes if sube else ahora < antes
    return Hallazgo(nombre, campo, antes, ahora, motivo) if empeora else None


def subidas(base, ahora) -> list[Hallazgo]:
    """Todo lo que afloja una guarda, con o sin justificación."""
    hallazgos = []

    presupuestos_base = base.get("budgets") or {}
    for nombre, presupuesto in (ahora.get("budgets") or {}).items():
        anterior = presupuestos_base.get(nombre)
        if not anterior:  # ruta nueva: no hay techo que aflojar
            continue
        for campo in ("max_queries", "max_duplicate_queries"):
            hallazgo = _comparar(
                nombre,
                campo,
                _numero(anterior, campo),
                _numero(presupuesto, campo),
                sube=True,
                motivo="la ruta puede hacer más consultas que antes",
            )
            if hallazgo:
                hallazgos.append(hallazgo)

    servicios_base = base.get("servicios") or {}
    for nombre, servicio in (ahora.get("servicios") or {}).items():
        anterior = servicios_base.get(nombre)
        if not isinstance(servicio, dict) or not isinstance(anterior, dict):
            continue
        hallazgo = _comparar(
            nombre,
            "consultas_fijas",
            _numero(anterior, "consultas_fijas"),
            _numero(servicio, "consultas_fijas"),
            sube=True,
            motivo="el servicio arranca con más consultas que antes",
        )
        if hallazgo:
            hallazgos.append(hallazgo)
        hallazgo = _comparar(
            nombre,
            "casos_por_consulta",
            _numero(anterior, "casos_por_consulta"),
            _numero(servicio, "casos_por_consulta"),
            sube=False,
            motivo="el servicio consulta más seguido (menos casos por consulta)",
        )
        if hallazgo:
            hallazgos.append(hallazgo)

    timing_base = (base.get("_meta") or {}).get("timing") or {}
    timing_ahora = (ahora.get("_meta") or {}).get("timing") or {}
    tiempo_base = _numero(timing_base, "reference_total_ms")
    tiempo_ahora = _numero(timing_ahora, "reference_total_ms")
    if tiempo_base and tiempo_ahora and tiempo_ahora > tiempo_base * (1 + MARGEN_TIEMPO):
        hallazgos.append(
            Hallazgo(
                "_meta.timing",
                "reference_total_ms",
                tiempo_base,
                tiempo_ahora,
                f"la alarma de tiempo se corre más de un {MARGEN_TIEMPO:.0%}",
            )
        )
    # Los multiplicadores son la otra forma de aflojar la misma alarma, y la más barata:
    # dejar `reference_total_ms` quieto y subir `failure_multiplier` corre el techo sin
    # que se note. El de esta ficha baja de 3.0 a 2.0, así que la puerta queda cerrada
    # en la dirección en que acaba de moverse.
    for campo in ("warning_multiplier", "failure_multiplier"):
        hallazgo = _comparar(
            "_meta.timing",
            campo,
            _numero(timing_base, campo),
            _numero(timing_ahora, campo),
            sube=True,
            motivo="la alarma de tiempo tolera más que antes",
        )
        if hallazgo:
            hallazgos.append(hallazgo)

    return hallazgos


def sin_justificar(base, ahora) -> list[Hallazgo]:
    """Las subidas que ninguna justificación nueva nombra."""
    texto = justificaciones_nuevas(base, ahora)
    return [h for h in subidas(base, ahora) if h.presupuesto not in texto]


def _anotar(mensaje):
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error title=Presupuesto de performance sin justificar::{mensaje}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help="Ref del árbol base (el CI pasa el SHA del PR).")
    parser.add_argument("--archivo", type=Path, default=RAIZ / RUTA_PRESUPUESTOS)
    argumentos = parser.parse_args(argv)

    try:
        ahora = json.loads(argumentos.archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"No se pudo leer {argumentos.archivo}: {error}", file=sys.stderr)
        return 2

    try:
        base = leer_de_la_base(argumentos.base)
    except json.JSONDecodeError as error:
        print(f"El {RUTA_PRESUPUESTOS} de {argumentos.base} no es JSON válido: {error}", file=sys.stderr)
        return 2

    if base is None:
        print(f"{RUTA_PRESUPUESTOS} no existe en {argumentos.base}: no hay contra qué comparar.")
        return 0

    todas = subidas(base, ahora)
    pendientes = sin_justificar(base, ahora)

    if not todas:
        print("Ningún presupuesto de performance sube en este PR.")
        return 0

    justificadas = [h for h in todas if h not in pendientes]
    for hallazgo in justificadas:
        print(f"OK (justificado): {hallazgo}")

    if not pendientes:
        return 0

    print("\nPresupuestos que suben sin justificación escrita:", file=sys.stderr)
    for hallazgo in pendientes:
        print(f"  {hallazgo}", file=sys.stderr)
        _anotar(str(hallazgo))
    print(
        f"\nAgregá en `_meta.adjustments` de {RUTA_PRESUPUESTOS} una entrada que **nombre** cada uno de esos\n"
        "presupuestos y explique qué consulta se suma y por qué conviene. Subir el techo para que el job\n"
        "pase es tapar un N+1 (RED-62).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
