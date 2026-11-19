"""`EXPLAIN` de la ventana de RN-5.1 del tablero de Emergencia (E1, y la que E8 amplía).

La foto del tablero lee los casos de la operación del día con
``programas.selectors.emergencia_tablero._casos_de_la_ventana``:

    ~estado=CERRADO  OR  alojado_en >= ahora - 24 h  OR  cerrado_en >= ahora - 24 h

más dos subconsultas correlacionadas (la última traza y el contacto posterior al
alojamiento). ``CasoEmergencia`` solo tiene los índices ``(estado, prioridad)`` y
``(tomado_por, estado)``: la sospecha del Cambio 472 (pendiente 10) es que el ``OR``
recorre la tabla entera, que en una emergencia larga es casi todo histórico cerrado.

Este script lo mide en un motor real, con un histórico sembrado que no entra en la ventana:

* El SQL **no se transcribe a mano**: corre el selector real y captura lo que salió hacia
  el motor (mismo criterio que ``medir_consultas_borde.py``).
* Imprime el ``EXPLAIN`` (el tabular, que entienden MySQL 8 y MariaDB), las filas que el
  motor leyó (delta de ``Handler_read%`` de la sesión, que no depende del reloj) y el
  tiempo promedio de ``--repeticiones`` corridas.
* ``--probar-indices`` crea **en la base del banco** los índices candidatos, vuelve a medir
  y los borra. Es para decidir con evidencia; no reemplaza la migración, que si hace falta
  va en un PR aparte (análisis 009, §8.2).

Uso (la base descartable del README, con ``DATABASE_*`` exportadas):

    python scripts/perf_mysql/explain_ventana_tablero.py --sembrar 50000
    python scripts/perf_mysql/explain_ventana_tablero.py --probar-indices

``--sembrar N`` escribe N casos cerrados hace más de 24 h (con su traza), 500 abiertos y
200 cerrados o alojados dentro de la ventana. Solo corre sobre ``chaco_perf_ci``. Las
personas que siembra tienen un DNI que no es un número (``BENCH-E1-…``): nada que se
pueda confundir con un documento real.
"""

import argparse
from datetime import timedelta

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402
from _medicion import medir  # noqa: E402

cargar_django()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402

from legajos.models import Ciudadano  # noqa: E402
from programas.models import CasoEmergencia, GrupoFamiliar, TrazaCaso  # noqa: E402
from programas.selectors import emergencia_tablero as tablero  # noqa: E402

Estado = CasoEmergencia.Estado
PREFIJO = "BENCH-E1-"
LOTE = 2000

#: Los índices que la ventana podría pedir. Se prueban en la base del banco y se borran.
INDICES_CANDIDATOS = (
    ("bench_e1_alojado", "(alojado_en)"),
    ("bench_e1_cerrado", "(cerrado_en)"),
)


def _tabla():
    return CasoEmergencia._meta.db_table


def sembrar(historicos):
    """Casos sintéticos: ``historicos`` cerrados fuera de la ventana, y la operación del día."""

    exigir_base_descartable()
    ahora = timezone.now()
    usuario, _creado = get_user_model().objects.get_or_create(username="bench_e1")
    ya = CasoEmergencia.objects.filter(numero__startswith="B").count()
    print(f"Casos del banco ya sembrados: {ya}")

    planes = (
        [(Estado.CERRADO, ahora - timedelta(days=2 + n % 60), None) for n in range(historicos)]
        + [(Estado.NUEVO, None, None) for _ in range(250)]
        + [(Estado.EN_GESTION, None, None) for _ in range(150)]
        + [(Estado.ALOJADO, None, ahora - timedelta(hours=n % 20)) for n in range(100)]
        + [(Estado.CERRADO, ahora - timedelta(hours=1 + n % 20), None) for n in range(200)]
    )
    for inicio in range(0, len(planes), LOTE):
        tramo = planes[inicio : inicio + LOTE]
        base = ya + inicio
        personas = Ciudadano.objects.bulk_create(
            [
                Ciudadano(dni=f"{PREFIJO}{base + n:07d}", nombre="Banco", apellido=f"E1 {base + n}")
                for n in range(len(tramo))
            ]
        )
        grupos = GrupoFamiliar.objects.bulk_create(
            [
                GrupoFamiliar(
                    responsable=persona, traslado=GrupoFamiliar.Traslado.BOMBEROS, adultos_f=2, total_declarado=2
                )
                for persona in personas
            ]
        )
        casos = CasoEmergencia.objects.bulk_create(
            [
                CasoEmergencia(
                    numero=f"B{base + n:09d}",
                    grupo=grupo,
                    origen=CasoEmergencia.Origen.TERRITORIO,
                    estado=estado,
                    prioridad=CasoEmergencia.Prioridad.MEDIA,
                    direccion="Banco E1",
                    relevado_por=usuario,
                    relevado_en=ahora - timedelta(days=3),
                    alojado_en=alojado_en,
                    total_alojado=2 if alojado_en else None,
                    cerrado_en=cerrado_en,
                )
                for n, (grupo, (estado, cerrado_en, alojado_en)) in enumerate(zip(grupos, tramo))
            ]
        )
        TrazaCaso.objects.bulk_create(
            [TrazaCaso(caso=caso, usuario=usuario, accion=TrazaCaso.Accion.CONTACTO, detalle="Banco") for caso in casos]
        )
        print(f"  {inicio + len(tramo)} / {len(planes)}")
    with connection.cursor() as cur:
        cur.execute(f"ANALYZE TABLE {_tabla()}")  # nosec B608 - nombre de tabla del modelo
        cur.fetchall()


def sql_de_la_ventana(ahora):
    with CaptureQueriesContext(connection) as cap:
        tablero._casos_de_la_ventana(ahora)
    (consulta,) = cap.captured_queries
    return consulta["sql"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sembrar", type=int, default=0, help="casos cerrados fuera de la ventana a sembrar")
    parser.add_argument("--repeticiones", type=int, default=20)
    parser.add_argument("--probar-indices", action="store_true", help="medir con los índices candidatos y borrarlos")
    args = parser.parse_args()

    if args.sembrar:
        sembrar(args.sembrar)

    ahora = timezone.now()
    total = CasoEmergencia.objects.count()
    en_la_ventana = len(tablero._casos_de_la_ventana(ahora))
    print(f"\n{connection.vendor} {'MariaDB' if connection.mysql_is_mariadb else 'MySQL'} {connection.mysql_version}")
    print(f"{total} casos en la tabla · {en_la_ventana} en la ventana de RN-5.1")

    sql = sql_de_la_ventana(ahora)
    medir("Ventana de RN-5.1 (índices de hoy)", sql, args.repeticiones)

    if args.probar_indices:
        exigir_base_descartable()
        with connection.cursor() as cur:
            for nombre, columnas in INDICES_CANDIDATOS:
                cur.execute(f"CREATE INDEX {nombre} ON {_tabla()} {columnas}")  # nosec B608
            cur.execute(f"ANALYZE TABLE {_tabla()}")  # nosec B608
            cur.fetchall()
        try:
            medir("Ventana de RN-5.1 con " + ", ".join(c for _n, c in INDICES_CANDIDATOS), sql, args.repeticiones)
        finally:
            with connection.cursor() as cur:
                for nombre, _columnas in INDICES_CANDIDATOS:
                    cur.execute(f"DROP INDEX {nombre} ON {_tabla()}")  # nosec B608


if __name__ == "__main__":
    main()
