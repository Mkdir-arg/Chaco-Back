#!/usr/bin/env python
"""Gate de `pip-audit`: ninguna excepción puede ser permanente de hecho (RED-63).

`pr-security.yml` llevaba `--ignore-vuln PYSEC-2026-3447` escrito a mano, con el
comentario «conserva la excepción preexistente aprobada para CI»: sin fecha, sin
ticket y sin nadie que la vuelva a mirar. Una excepción así se renueva sola para
siempre, y el día que la vulnerabilidad importe nadie se entera.

Acá las excepciones viven en `security/excepciones.toml`, cada una con las cuatro
claves obligatorias —`id`, `motivo`, `vence_el`, `ticket`— y el CI las verifica
antes de auditar:

    python scripts/check_excepciones_seguridad.py                 # valida y explica
    python scripts/check_excepciones_seguridad.py --ignore-args   # emite las banderas

El segundo modo es el que consume el workflow:

    read -r -a ignores <<< "$(python3 scripts/check_excepciones_seguridad.py --ignore-args)"
    pip-audit -r requirements.txt "${ignores[@]}"

así la lista de ignores sale del archivo versionado y no del YAML. Si una excepción
venció, los dos modos salen con 1 y el job se pone rojo: renovarla es editar
`vence_el` en un PR, que es exactamente la revisión que faltaba.

`vence_el` tiene que ser una **fecha TOML** (`vence_el = 2027-01-02`, sin comillas).
Escrita como texto parsearía como string y no vencería nunca: es el agujero obvio y
está cubierto por su propia regla.
"""

import argparse
import datetime
import sys
from pathlib import Path

import tomllib

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "security" / "excepciones.toml"
CLAVES = ("id", "motivo", "vence_el", "ticket")
TABLA = "pip_audit"


def cargar(ruta=ARCHIVO):
    """Las entradas declaradas en el TOML. Un archivo ausente o vacío son cero excepciones."""
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    return tomllib.loads(ruta.read_text(encoding="utf-8")).get(TABLA, [])


def revisar(entradas, hoy):
    """Los motivos por los que el gate tiene que ponerse rojo, en texto para el log."""
    errores = []
    for i, entrada in enumerate(entradas, start=1):
        etiqueta = entrada.get("id") or f"[[{TABLA}]] #{i}"

        faltantes = [clave for clave in CLAVES if clave not in entrada or entrada[clave] in (None, "")]
        if faltantes:
            errores.append(f"la excepción {etiqueta} no declara {', '.join(faltantes)}")
            continue

        vence_el = entrada["vence_el"]
        if isinstance(vence_el, datetime.datetime) or not isinstance(vence_el, datetime.date):
            errores.append(
                f"la excepción {etiqueta} tiene `vence_el` que no es una fecha TOML (sin comillas, 2027-01-02)"
            )
            continue

        if vence_el < hoy:
            errores.append(
                f"la excepción {etiqueta} venció el {vence_el.isoformat()}: renovala o resolvé la vulnerabilidad"
            )

    return errores


def banderas(entradas):
    """Las banderas de `pip-audit` que corresponden a las excepciones vigentes."""
    return [arg for entrada in entradas for arg in ("--ignore-vuln", entrada["id"])]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archivo", default=str(ARCHIVO), help="TOML de excepciones")
    parser.add_argument("--hoy", help="fecha de referencia ISO (para probar el vencimiento)")
    parser.add_argument(
        "--ignore-args",
        action="store_true",
        help="emitir por stdout las banderas --ignore-vuln en vez del informe",
    )
    args = parser.parse_args(argv)

    # noqa DTZ011 deliberado: es una herramienta de línea de comandos que no corre
    # bajo Django (no hay `TIME_ZONE` que consultar) y su default es el día de quien
    # la ejecuta; `--hoy` existe justamente para fijarlo.
    hoy = datetime.date.fromisoformat(args.hoy) if args.hoy else datetime.date.today()  # noqa: DTZ011
    entradas = cargar(args.archivo)
    errores = revisar(entradas, hoy)

    if errores:
        for error in errores:
            print(f"::error::{error}", file=sys.stderr)
        return 1

    if args.ignore_args:
        print(" ".join(banderas(entradas)))
        return 0

    if not entradas:
        print("Sin excepciones de seguridad vigentes.")
        return 0

    for entrada in entradas:
        print(f"{entrada['id']} vence el {entrada['vence_el'].isoformat()} ({entrada['ticket']}): {entrada['motivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
