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

Qué cuenta como justificación: una entrada **nueva** de `_meta.adjustments` —clave que
no existía en la base— que **nombre** el presupuesto que subió, como palabra entera en su
texto o como clave exacta de la entrada. La ficha pedía «una clave nueva en
`adjustments`»; se exige además que la nombre, porque una sola entrada nueva alcanzaba
para tapar cualquier cantidad de subidas en el mismo PR y porque la convención del
archivo ya escribe el nombre de la ruta («legajos_lista 14→12», «edicion_convocatoria
13→14»).

Las dos precisiones las trajo la revisión del PR #648:

* **nueva, no «nueva o modificada»**. Con «modificada» alcanzaba con tocar un carácter de
  una entrada vieja que ya nombra varios presupuestos —`perf_core_legajos_conversaciones`
  nombra `login`, `portal_perfil` y `conversaciones_lista`— para habilitar subirles el
  techo a todos sin escribir una línea de justificación.
* **palabra entera, no substring**. `h.presupuesto in texto` daba por nombrada una clave
  corta como `login` porque aparecía adentro de otra palabra de una entrada ajena. Para
  los nombres con punto (`_meta.timing`) vale también el último segmento (`timing`), que
  es como se los nombra en prosa.

Bajar un presupuesto nunca necesita nada: es la dirección buena.

Contra qué se compara: contra el **merge-base** con la ref que se pase, no contra su tip.
Con el tip, un worktree cuyo `origin/development` avanzó más allá de una *bajada* de
presupuesto sale rojo sin que el PR toque el JSON (medido en la revisión de #648). En el
CI da lo mismo —el SHA base del PR ya es antepasado del merge commit—, pero la corrida
local es la que se usa antes de abrir el PR.

    python scripts/check_perf_budgets.py                 # contra origin/development
    python scripts/check_perf_budgets.py --base <ref>    # el CI pasa el SHA base del PR
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


def resolver_base(ref: str) -> str:
    """El punto de bifurcación con `ref`, no su tip.

    Comparar contra el tip es lo que rompe la corrida local: si `origin/development`
    avanzó con una **bajada** de presupuesto que este PR no tiene, el diff contra el tip
    la lee como una subida y el gate sale rojo sin que el PR haya tocado el JSON. El
    merge-base es el archivo tal como estaba cuando la rama se separó, que es contra lo
    que el PR propone el cambio.

    Si `git merge-base` no resuelve —ref suelta, repo sin historia común— se devuelve la
    ref tal cual y el comportamiento es el de antes.
    """
    resultado = _git("merge-base", "HEAD", ref)
    if resultado.returncode != 0:
        return ref
    return resultado.stdout.strip() or ref


def leer_de_la_base(base: str):
    """El `perf_budgets.json` del árbol base, o `None` si ahí no existía."""
    resultado = _git("show", f"{base}:{RUTA_PRESUPUESTOS}")
    if resultado.returncode != 0:
        return None
    return json.loads(resultado.stdout)


def _ajustes(config) -> dict:
    return (config.get("_meta") or {}).get("adjustments") or {}


def justificaciones_nuevas(base, ahora) -> list[tuple[str, str]]:
    """Las entradas de `adjustments` que este PR **agregó**, como `(clave, texto)`.

    Modificar una entrada vieja no cuenta: las entradas históricas nombran varios
    presupuestos cada una y tocarles un carácter habilitaría subirles el techo a todos.
    """
    ajustes_base, ajustes_ahora = _ajustes(base), _ajustes(ahora)
    return [(clave, texto) for clave, texto in ajustes_ahora.items() if clave not in ajustes_base]


def _nombra(texto: str, presupuesto: str) -> bool:
    """`presupuesto` aparece en `texto` como palabra entera.

    `login` no queda nombrado por `perf_core_legajos_conversaciones` ni por
    `portal_perfil_login`. Para los nombres con punto vale también el último segmento:
    `_meta.timing` se nombra en prosa como «timing».
    """
    formas = {presupuesto}
    if "." in presupuesto:
        formas.add(presupuesto.rsplit(".", 1)[1])
    return any(re.search(rf"(?<![0-9A-Za-z_]){re.escape(forma)}(?![0-9A-Za-z_])", texto) for forma in formas)


def justifica(entradas: list[tuple[str, str]], presupuesto: str) -> bool:
    """Alguna entrada nueva nombra ese presupuesto, en su clave o en su texto."""
    return any(
        clave == presupuesto or _nombra(clave, presupuesto) or _nombra(texto, presupuesto) for clave, texto in entradas
    )


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
    entradas = justificaciones_nuevas(base, ahora)
    return [h for h in subidas(base, ahora) if not justifica(entradas, h.presupuesto)]


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

    # Contra el merge-base y no contra el tip de la ref: ver `resolver_base`.
    ref_base = resolver_base(argumentos.base)

    try:
        base = leer_de_la_base(ref_base)
    except json.JSONDecodeError as error:
        print(f"El {RUTA_PRESUPUESTOS} de {ref_base} no es JSON válido: {error}", file=sys.stderr)
        return 2

    if base is None:
        print(f"{RUTA_PRESUPUESTOS} no existe en {ref_base}: no hay contra qué comparar.")
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
        f"\nAgregá en `_meta.adjustments` de {RUTA_PRESUPUESTOS} una entrada **nueva** (clave que no existía)\n"
        "que **nombre** cada uno de esos presupuestos —como palabra entera o como clave de la entrada— y\n"
        "explique qué consulta se suma y por qué conviene. Editar una entrada vieja no alcanza. Subir el\n"
        "techo para que el job pase es tapar un N+1 (RED-62).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
