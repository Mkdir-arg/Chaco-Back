"""`EXPLAIN` de las lecturas de la solapa «Abastecimiento» de E8 (E-7b, RNF-009-10 y 11).

Lee la foto de situación (sin medirla: la mide ``explain_situacion.py``) y corre
``programas.selectors.emergencia_abastecimiento.lecturas_de_abastecimiento`` contra la base del
banco, captura **el SQL real** de A1-A5 (catálogo, recibido por dispositivo e ítem, en camino y
preparadas, personas alojadas y A5 si hace falta) y lo mide con ``_medicion.medir``: `EXPLAIN`,
filas leídas y tiempo.

Necesita ``SLAEmergencia.inicio_evento`` cargado y, para que la medición diga algo, un evento
anterior en la base (entregas recibidas y egresados antes del inicio). Los índices que el `EXPLAIN`
pida van en una migración aparte.

    python scripts/perf_mysql/explain_abastecimiento.py [--repeticiones 20]
"""

import argparse

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402
from _medicion import medir  # noqa: E402

cargar_django()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402

from programas.selectors import emergencia_situacion as situacion  # noqa: E402
from programas.selectors.emergencia_abastecimiento import lecturas_de_abastecimiento  # noqa: E402
from programas.services.configuracion_emergencia import sla_vigente  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeticiones", type=int, default=20)
    args = parser.parse_args()

    exigir_base_descartable()  # sla_vigente() puede escribir el SLA de fábrica
    sla = sla_vigente()
    if sla.inicio_evento is None:
        raise SystemExit("Sin SLAEmergencia.inicio_evento la solapa no calcula: cargalo en el banco antes de medir.")
    foto = situacion.foto_de_situacion(sla, timezone.now())
    with CaptureQueriesContext(connection) as capturadas:
        lecturas = lecturas_de_abastecimiento(foto, sla.inicio_evento)
    consultas = [consulta["sql"] for consulta in capturadas.captured_queries]
    print(f"\n{connection.vendor} {'MariaDB' if connection.mysql_is_mariadb else 'MySQL'} {connection.mysql_version}")
    print(
        f"{len(consultas)} consultas · {len(lecturas.items)} ítems · {len(lecturas.recibido)} pares recibidos · "
        f"{len(lecturas.personas)} personas leídas · inicio del evento {sla.inicio_evento:%d/%m %H:%M}"
    )
    for numero, sql in enumerate(consultas, start=1):
        medir(f"A{numero} de la solapa", sql, args.repeticiones)


if __name__ == "__main__":
    main()
