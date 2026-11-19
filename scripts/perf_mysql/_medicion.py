"""`medir`: `EXPLAIN`, filas leídas y tiempo de una consulta en el motor real del banco.

Compartido por los scripts de `scripts/perf_mysql/` (antes cada uno tenía su copia). Recibe el
SQL **capturado** del código real (nunca transcripto a mano) y lo corre contra la base del banco.
"""

import time

from django.db import connection


def _filas_leidas(cur):
    """Las lecturas del handler de la sesión: no dependen del reloj."""

    cur.execute("SHOW SESSION STATUS LIKE 'Handler_read%'")
    return sum(int(valor) for _nombre, valor in cur.fetchall())


def medir(titulo, sql, repeticiones, *, ancho=400, contar_lecturas=True):
    """Imprime el `EXPLAIN` tabular de `sql`, las filas devueltas y leídas, y el tiempo promedio.

    La primera corrida calienta el buffer pool y no cuenta. `ancho` recorta el SQL impreso;
    `contar_lecturas` agrega el delta de `Handler_read%` de una corrida.
    """

    print(f"\n=== {titulo}")
    print(f"SQL: {sql[:ancho]}{' …' if len(sql) > ancho else ''}")
    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN {sql}")
        columnas = [c[0] for c in cur.description]
        for fila in cur.fetchall():
            print("  EXPLAIN " + " | ".join(f"{c}={v}" for c, v in zip(columnas, fila) if v not in (None, "")))
        cur.execute(sql)
        devueltas = len(cur.fetchall())
        if contar_lecturas:
            antes = _filas_leidas(cur)
            cur.execute(sql)
            cur.fetchall()
            print(f"  --> {devueltas} filas devueltas · {_filas_leidas(cur) - antes} lecturas del handler por corrida")
        t0 = time.perf_counter()
        for _ in range(repeticiones):
            cur.execute(sql)
            cur.fetchall()
        total = (time.perf_counter() - t0) * 1000
    print(f"  --> {total / repeticiones:.2f} ms por corrida ({repeticiones} corridas, {total:.0f} ms en total)")
