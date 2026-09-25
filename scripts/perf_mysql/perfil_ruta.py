"""Perfila una ruta con cProfile contra el banco: dónde se va el tiempo que no
es SQL (plantillas, RBAC, serialización). Uso: python perfil_ruta.py <url> [n]"""

import cProfile
import pstats
import sys

from _bootstrap import cargar_django  # noqa: E402

cargar_django()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

url = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
client = Client()
client.force_login(get_user_model().objects.get(username="perf_admin"))
client.get(url)  # calienta

with CaptureQueriesContext(connection) as cap:
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(n):
        client.get(url).content
    pr.disable()
sql_ms = sum(float(q["time"]) for q in cap.captured_queries) * 1000 / n
st = pstats.Stats(pr)
total = st.total_tt * 1000 / n
print(
    f"{url}: {total:.0f} ms por request, de los cuales SQL {sql_ms:.0f} ms ({len(cap.captured_queries) // n} consultas)"
)
print("\n-- por función (tiempo propio, top 18):")
st.sort_stats("tottime").print_stats(18)
print("\n-- acumulado en plantillas / rbac / middleware:")
st.sort_stats("cumulative").print_stats(r"template|rbac|middleware|sidebar|puede", 14)
