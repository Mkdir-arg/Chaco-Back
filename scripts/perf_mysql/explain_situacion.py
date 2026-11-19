"""`EXPLAIN` de las lecturas de la foto de situación de Emergencia (E8, RNF-009-10).

Corre ``programas.selectors.emergencia_situacion.foto_de_situacion`` contra la base del banco,
captura **el SQL real** de cada una de sus consultas (casos de la ventana, red, personas
alojadas, ritmo de `Estadia`, derivaciones, entregas, líneas por ítem, última recepción y
localidades) y lo mide con ``_medicion.medir``: `EXPLAIN`, filas leídas y tiempo.

Los datos los siembran los otros scripts del banco (``explain_ventana_tablero.py --sembrar``
para los casos históricos). Los índices que el `EXPLAIN` pida van en una migración aparte.

    python scripts/perf_mysql/explain_situacion.py [--ventana 72h|7d] [--repeticiones 20]
"""

import argparse

from _bootstrap import cargar_django  # noqa: E402
from _medicion import medir  # noqa: E402

cargar_django()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402

from programas.selectors import emergencia_situacion as situacion  # noqa: E402
from programas.services.configuracion_emergencia import sla_vigente  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ventana", default=situacion.VENTANA_POR_DEFECTO)
    parser.add_argument("--repeticiones", type=int, default=20)
    args = parser.parse_args()

    sla = sla_vigente()
    with CaptureQueriesContext(connection) as capturadas:
        foto = situacion.foto_de_situacion(sla, timezone.now(), situacion.FiltrosSituacion(ventana=args.ventana))
    print(f"\n{connection.vendor} {'MariaDB' if connection.mysql_is_mariadb else 'MySQL'} {connection.mysql_version}")
    print(f"{len(capturadas)} consultas · {len(foto.casos)} casos · {len(foto.alojados)} personas alojadas")
    for numero, consulta in enumerate(capturadas.captured_queries, start=1):
        medir(f"Consulta {numero} de la foto", consulta["sql"], args.repeticiones)


if __name__ == "__main__":
    main()
