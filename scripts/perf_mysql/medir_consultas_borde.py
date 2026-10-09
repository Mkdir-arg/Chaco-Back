"""Mide, consulta por consulta, las que las fichas PERF-12, PERF-13 y PERF-15 ponen
en duda: con el `EXPLAIN` que eligió MariaDB y con el tiempo promediado sobre muchas
corridas.

`bench_mysql.py` mide la ruta entera con `perf_counter`, que en Windows tiene una
granularidad de 15,6 ms: una consulta de 3 ms y una de 14 ms miden las dos «16,0». Acá
cada consulta se corre `--repeticiones` veces y se divide, así que el número deja de
depender del reloj.

El SQL **no se transcribe a mano**: se ejecuta el código real (la property del cupo, el
queryset de la bandeja, el aggregate del detalle) y se captura lo que salió hacia el
motor. Lo que se mide es exactamente lo que va a correr en producción.

Uso: python scripts/perf_mysql/medir_consultas_borde.py [--repeticiones 50]
"""

import argparse
import time

from _bootstrap import cargar_django  # noqa: E402

cargar_django()

from django.db import connection  # noqa: E402
from django.db.models import Count, Q  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from programas.models import Formulario, Relevamiento, q_con_identidad  # noqa: E402


def capturar(fn):
    """Corre ``fn`` y devuelve el SQL que ejecutó, ya con sus parámetros."""
    with CaptureQueriesContext(connection) as cap:
        fn()
    return [q["sql"] for q in cap.captured_queries]


def medir(titulo, sql, repeticiones):
    print(f"\n=== {titulo}")
    print(f"SQL: {sql[:260]}{' …' if len(sql) > 260 else ''}")
    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN {sql}")
        columnas = [c[0] for c in cur.description]
        for fila in cur.fetchall():
            print("  EXPLAIN " + " | ".join(f"{c}={v}" for c, v in zip(columnas, fila) if v not in (None, "")))
        cur.execute(sql)  # calienta el buffer pool; esta corrida no cuenta
        cur.fetchall()
        t0 = time.perf_counter()
        for _ in range(repeticiones):
            cur.execute(sql)
            cur.fetchall()
        total = (time.perf_counter() - t0) * 1000
    print(f"  --> {total / repeticiones:.2f} ms por corrida ({repeticiones} corridas, {total:.0f} ms en total)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeticiones", type=int, default=50)
    args = parser.parse_args()
    reps = args.repeticiones

    rel = Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).order_by("-pk").first()
    conv = rel.convocatoria
    casos = Formulario.objects.filter(relevamiento=rel).count()
    bajas = Formulario.objects.filter(estado=Formulario.Estado.BAJA).count()
    print(f"relevamiento {rel.pk} · convocatoria {conv.pk} · {casos} casos · {bajas} en BAJA")

    # ── PERF-12 · el COUNT del cupo del link público: la property que mira
    # `relevamiento_disponible` en el GET del paso 1 y que el envío repite bajo el lock.
    for sql in capturar(lambda: rel.cupo_utilizado):
        medir("PERF-12 · COUNT del cupo del link público", sql, reps)

    # ── PERF-13 · la bandeja de personas filtrada por un estado raro, página 10.
    # Mismo queryset que `RevisionPersonasListView.get_queryset`: los ids de
    # relevamiento resueltos aparte, `only("pk")` y el orden `-creado, -pk`.
    ids = list(Relevamiento.objects.values_list("pk", flat=True))
    bandeja = (
        Formulario.objects.filter(relevamiento_id__in=ids, estado=Formulario.Estado.BAJA)
        .only("pk")
        .order_by("-creado", "-pk")
    )
    for sql in capturar(lambda: list(bandeja[225:250])):
        medir(f"PERF-13 · bandeja estado=BAJA página 10 ({len(ids)} relevamientos)", sql, reps)
    for sql in capturar(bandeja.count):
        medir("PERF-13 · COUNT del paginador de esa bandeja", sql, reps)

    # El contraste que la ficha no pide pero que decide el índice: el mismo filtro
    # con un estado **común**. Si el motor elige el índice de `estado` ahí también,
    # ordena decenas de miles de filas y el índice combinado sí tendría trabajo.
    comun = (
        Formulario.objects.filter(relevamiento_id__in=ids, estado=Formulario.Estado.APROBADO)
        .only("pk")
        .order_by("-creado", "-pk")
    )
    aprobados = comun.count()
    for sql in capturar(lambda: list(comun[225:250])):
        medir(f"PERF-13 · bandeja estado=APROBADO página 10 ({aprobados} casos)", sql, reps)
    for sql in capturar(lambda: list(comun[9975:10000])):
        medir("PERF-13 · bandeja estado=APROBADO página 400 (la más profunda)", sql, reps)
    for sql in capturar(
        lambda: list(Formulario.objects.filter(relevamiento_id__in=ids).only("pk").order_by("-creado", "-pk")[225:250])
    ):
        medir("PERF-13 · bandeja sin filtro de estado, página 10", sql, reps)

    # ── PERF-15 · el aggregate del padrón del detalle de convocatoria
    # (`ConvocatoriaDetailView.get_context_data`), tal cual está escrito ahí.
    nivel = Q(relevamiento__isnull=True)

    def aggregate_del_detalle():
        return conv.padron.aggregate(
            total=Count("pk", filter=nivel),
            con_identidad=Count("pk", filter=nivel & q_con_identidad()),
            rels_propios=Count("relevamiento", distinct=True),
        )

    filas = conv.padron.count()
    for sql in capturar(aggregate_del_detalle):
        medir(f"PERF-15 · aggregate del padrón del detalle de convocatoria ({filas} filas)", sql, reps)

    # ── PERF-15 · los dos Count anotados en el queryset del detalle de relevamiento
    # (`RelevamientoDetailView.queryset`), que recorren el padrón de la convocatoria.
    from django.db.models import F

    def anotados_del_detalle():
        return list(
            Relevamiento.objects.filter(pk=rel.pk).annotate(
                n_padron_propio=Count("convocatoria__padron", filter=Q(convocatoria__padron__relevamiento_id=F("pk"))),
                n_padron_convocatoria=Count(
                    "convocatoria__padron", filter=Q(convocatoria__padron__relevamiento__isnull=True)
                ),
            )
        )

    for sql in capturar(anotados_del_detalle):
        medir("PERF-15 · Count del padrón anotado en el detalle de relevamiento", sql, reps)


if __name__ == "__main__":
    main()
