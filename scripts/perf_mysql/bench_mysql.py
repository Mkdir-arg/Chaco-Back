"""Mide las rutas presupuestadas (scripts/perf_audit.py) más las pesadas del
dashboard y los reportes, contra el banco MySQL con las OPTIONS de producción.

Por ruta: ms en frío (primer request), ms en caliente (mediana de 3), cantidad
de consultas, duplicadas y las 3 consultas más lentas. Salida en JSON + tabla.

Uso: python bench_mysql.py [--solo clave,clave] [--salida archivo.json]
"""

import argparse
import json
import os
import statistics
import time

from _bootstrap import cargar_django  # noqa: E402

cargar_django()

from django.core.cache import cache  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.urls import reverse  # noqa: E402

from scripts.perf_audit import build_clients, build_targets, duplicate_query_groups  # noqa: E402


def _extra_targets():
    from programas.models import Convocatoria, Programa, Relevamiento

    programa = Programa.objects.order_by("pk").first()
    rel = Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).order_by("-pk").first()
    conv = rel.convocatoria if rel else Convocatoria.objects.order_by("pk").first()
    extras = []
    if programa:
        extras += [
            {
                "key": "dashboard_becas_datos",
                "actor": "backoffice",
                "url": reverse("becas:programa_dashboard_datos", args=[programa.pk]),
            },
            {
                "key": "dashboard_becas_export_xlsx",
                "actor": "backoffice",
                "url": reverse("becas:programa_dashboard_exportar", args=[programa.pk, "xlsx"]),
            },
        ]
        if conv:
            extras.append(
                {
                    "key": "dashboard_respuestas_xlsx",
                    "actor": "backoffice",
                    "url": reverse("becas:programa_dashboard_respuestas_xlsx", args=[programa.pk, conv.pk]),
                }
            )
    for reporte in ("cupos", "avance", "produccion", "embudo", "beneficiarios"):
        extras.append(
            {
                "key": f"reporte_{reporte}",
                "actor": "backoffice",
                "url": reverse("becas:reporte_detalle", args=[reporte]),
            }
        )
        extras.append(
            {
                "key": f"reporte_{reporte}_xlsx",
                "actor": "backoffice",
                "url": reverse("becas:reporte_exportar", args=[reporte, "xlsx"]),
            }
        )
    if rel:
        extras.append(
            {
                "key": "revision_publico",
                "actor": "backoffice",
                "url": reverse("becas:revision_formularios", args=[rel.pk]),
            }
        )
        extras.append(
            {
                "key": "revision_publico_pagina_50",
                "actor": "backoffice",
                "url": reverse("becas:revision_formularios", args=[rel.pk]) + "?page=50",
            }
        )
        extras.append(
            {
                "key": "relevamiento_publico_detalle",
                "actor": "backoffice",
                "url": reverse("becas:relevamiento_detalle", args=[rel.pk]),
            }
        )
        extras.append(
            {
                "key": "convocatoria_publica_detalle",
                "actor": "backoffice",
                "url": reverse("becas:convocatoria_detalle", args=[conv.pk]),
            }
        )
        extras.append(
            {
                "key": "portal_inscripcion_paso1",
                "actor": "anon",
                "url": reverse("portal:inscripcion_paso1", args=[rel.token_publico]),
            }
        )
    return extras


def _medir(client, target):
    url, req = target["url"], target.get("request")
    cache.clear()
    reset_queries()

    def _pedir():
        # En el manifiesto de perf_audit ``request`` es una función (client, url) → response.
        return req(client, url) if callable(req) else client.get(url)

    with CaptureQueriesContext(connection) as cap:
        t0 = time.perf_counter()
        resp = _pedir()
        _ = resp.content
        frio = (time.perf_counter() - t0) * 1000
    consultas = list(cap.captured_queries)
    lentas = sorted(((float(q["time"]) * 1000, q["sql"][:160]) for q in consultas), reverse=True)[:3]
    dup = duplicate_query_groups(consultas)
    calientes = []
    for _ in range(3):
        t0 = time.perf_counter()
        _ = _pedir().content
        calientes.append((time.perf_counter() - t0) * 1000)
    return {
        "status": resp.status_code,
        "frio_ms": round(frio, 1),
        "caliente_ms": round(statistics.median(calientes), 1),
        "consultas": len(consultas),
        "duplicadas": len(dup) if hasattr(dup, "__len__") else dup,
        "sql_ms": round(sum(float(q["time"]) for q in consultas) * 1000, 1),
        "lentas": [(round(ms, 1), sql) for ms, sql in lentas],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", default="")
    parser.add_argument("--salida", default=os.path.join(os.path.dirname(__file__), "resultado.json"))
    args = parser.parse_args()
    manifest = build_targets()
    clients = build_clients(manifest["actors"])
    clients["anon"] = Client()
    targets = manifest["targets"] + _extra_targets()
    solo = {s for s in args.solo.split(",") if s}
    resultados = {}
    print(f"{'ruta':36} {'st':>3} {'frío ms':>8} {'cal ms':>7} {'q':>4} {'dup':>4} {'sql ms':>7}")
    for t in targets:
        if solo and t["key"] not in solo:
            continue
        try:
            r = _medir(clients[t["actor"]], t)
        except Exception as e:  # noqa: BLE001
            r = {
                "status": "ERR",
                "error": f"{type(e).__name__}: {e}"[:200],
                "frio_ms": 0,
                "caliente_ms": 0,
                "consultas": 0,
                "duplicadas": 0,
                "sql_ms": 0,
                "lentas": [],
            }
        resultados[t["key"]] = {"url": t["url"], **r}
        print(
            f"{t['key']:36} {str(r['status']):>3} {r['frio_ms']:>8} {r['caliente_ms']:>7} {r['consultas']:>4} {r['duplicadas']:>4} {r['sql_ms']:>7}"
            + (f"  {r['error']}" if "error" in r else "")
        )
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(resultados, fh, ensure_ascii=False, indent=1)
    print(f"\nJSON: {args.salida}")


if __name__ == "__main__":
    main()
