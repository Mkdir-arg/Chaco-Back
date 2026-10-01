r"""Harness de mediciones de performance (verificación V4, pasada 2). NO es un test de regresión.

Auditoría integral DATAÑACH, oct-2026. Mide conteos exactos de sentencias (execute_wrapper),
SQL generado y costo en Python sobre SQLite en memoria con la forma de datos del banco:
seed_perf --scale 200 + scripts/perf_mysql/escalar_bench.py::main(N) (relevamiento público de N casos).
NO mide tiempos de MariaDB: para eso, el banco scripts/perf_mysql/ (contenedor 3308, base chaco_perf_ci).

CÓMO CORRERLO (PowerShell, raíz de un worktree descartable)
  New-Item -ItemType Directory -Force v4perf | Out-Null
  New-Item -ItemType File -Force v4perf\__init__.py | Out-Null
  Copy-Item <este archivo> v4perf\tests.py
  $env:DJANGO_SECRET_KEY="test-key"; $env:PYTEST_RUNNING="1"; $env:DJANGO_SYNCDB_PROJECT_APPS="True"
  $env:V4_CASOS="20000"            # tamaño del relevamiento (5000 para una corrida rápida)
  $env:V4_OUT="$PWD\v4_mediciones_nuevas.json"
  & C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe manage.py test v4perf -v 2

QUÉ ID MIDE CADA TEST
  test_a402_cupo                   -> PERF-02
  test_a403_xlsx / test_a403_perfil -> PERF-03
  test_a404_padron / _perfil       -> PERF-04 (antes)
  test_a404_despues                -> PERF-04 (prototipo validar_casos_pendientes_v4: 13.942 -> 676 sentencias)
  test_a407_payload / _perfil      -> PERF-01 (+ V4-NEW-02)
  test_a408_candidatos             -> PERF-07 (+ PERF-19)
  test_a413_link                   -> PERF-12
  test_v3new03_generar_alertas     -> PERF-20 (+ LEG-01)
Resultados de referencia (01-oct-2026): v4_mediciones.json en esta carpeta.
"""

import gzip
import io
import json
import sys
import time
import tracemalloc
import types
from collections import Counter
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

OUT = Path(__import__("os").environ.get("V4_OUT", str(Path(__file__).resolve().parent / "v4_mediciones_nuevas.json")))
RESULT = {}
N_CASOS = int(__import__("os").environ.get("V4_CASOS", "20000"))


def _save():
    previo = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    previo.update(RESULT)
    OUT.write_text(json.dumps(previo, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _tipo(sql):
    s = sql.lstrip().upper()
    for t in ("SELECT", "INSERT", "UPDATE", "DELETE", "SAVEPOINT", "RELEASE"):
        if s.startswith(t):
            return t
    return s[:10]


def _tabla(sql):
    import re

    m = re.search(r'(?:FROM|INTO|UPDATE)\s+"?([a-z_0-9]+)"?', sql, re.I)
    return m.group(1) if m else "?"


class V4Perf(TestCase):
    @classmethod
    def setUpTestData(cls):
        t0 = time.perf_counter()
        call_command("seed_perf", scale=200, stdout=StringIO())
        sys.modules["_bootstrap"] = types.ModuleType("_bootstrap")
        sys.modules["_bootstrap"].cargar_django = lambda: None
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "perf_mysql"))
        import escalar_bench

        with patch("builtins.print"):
            cls.rel = escalar_bench.main(N_CASOS)
        from programas.models import ProgramaSiis, Segmento

        cls.programa, _ = ProgramaSiis.objects.get_or_create(siis_programa_id=90, defaults={"nombre": "BENCH"})
        Segmento.objects.filter(pk=cls.rel.convocatoria.segmento_id).update(programa=cls.programa)
        cls.rel.refresh_from_db()
        cls.admin = User.objects.create_superuser("v4admin", "v4@x.invalid", "x")
        RESULT["seed_s"] = round(time.perf_counter() - t0, 1)

    def _client(self):
        self.client.force_login(self.admin)
        return self.client

    # ------------------------------------------------------------------ A4-02
    def test_a402_cupo(self):
        from programas.models import Formulario

        seg = self.rel.convocatoria.segmento
        c = self._client()
        url = reverse("becas:cupo_segmento", args=[seg.pk])
        res = {}
        for qs in ("", "?pendientes_page=50&beneficiarios_page=50"):
            with CaptureQueriesContext(connection) as ctx:
                t = time.perf_counter()
                r = c.get(url + qs)
                dt = time.perf_counter() - t
            paginas = [
                q["sql"] for q in ctx.captured_queries if "LIMIT" in q["sql"] and "programas_formulario" in q["sql"]
            ]
            res[qs or "p1"] = {
                "status": r.status_code,
                "queries": len(ctx.captured_queries),
                "ms": round(dt * 1000),
                "consultas_pagina_formulario": len(paginas),
                "pagina_trae_definicion": all('"definicion"' in s for s in paginas),
                "pagina_trae_respuestas": all('"respuestas"' in s for s in paginas),
                "pagina_trae_datos_siis": all('"datos_siis"' in s for s in paginas),
                "order_by": [s[s.find("ORDER BY") : s.find("ORDER BY") + 80] for s in paginas],
                "counts": [q["sql"][:200] for q in ctx.captured_queries if "COUNT(" in q["sql"]],
            }
            if paginas:
                res["sql_pagina_ejemplo"] = paginas[-1][:3000]
        res["volumen"] = {
            e: Formulario.objects.filter(relevamiento__convocatoria__segmento=seg, estado=e).count()
            for e in ("ENVIADO", "APROBADO", "RECHAZADO")
        }
        RESULT["A4-02"] = res
        _save()

    # ------------------------------------------------------------------ A4-03 / A4-15
    def test_a403_xlsx(self):
        from programas.services import dashboard_becas
        from programas.services.exportacion_reportes import respuesta_libro

        conv = self.rel.convocatoria
        res = {}
        t = time.perf_counter()
        reporte, alcance = dashboard_becas.respuestas_por_persona(conv)
        res["armar_reporte_s"] = round(time.perf_counter() - t, 2)
        res["filas"] = len(reporte.filas)
        res["columnas"] = len(reporte.encabezados)
        t = time.perf_counter()
        resp = respuesta_libro([("Respuestas", reporte)], "x", alcance=alcance)
        res["openpyxl_s"] = round(time.perf_counter() - t, 2)
        cuerpo = resp.content
        res["xlsx_mb"] = round(len(cuerpo) / 1e6, 2)
        t = time.perf_counter()
        comprimido = gzip.compress(cuerpo, compresslevel=6)
        res["gzip_s"] = round(time.perf_counter() - t, 3)
        res["gzip_ratio"] = round(len(comprimido) / len(cuerpo), 3)
        del reporte, resp, cuerpo, comprimido
        # Pico de memoria (tracemalloc: solo objetos Python; más lento)
        tracemalloc.start()
        reporte, alcance = dashboard_becas.respuestas_por_persona(conv)
        _, pico_reporte = tracemalloc.get_traced_memory()
        resp = respuesta_libro([("Respuestas", reporte)], "x", alcance=alcance)
        _, pico_total = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        res["pico_mb_armar_reporte"] = round(pico_reporte / 1e6, 1)
        res["pico_mb_total"] = round(pico_total / 1e6, 1)
        del reporte, resp
        # Request completo con Accept-Encoding: gzip (pasa por GZipMiddleware)
        c = self._client()
        url = reverse("becas:programa_dashboard_respuestas_xlsx", args=[conv.segmento.programa_id or 0, conv.pk])
        res["url"] = url
        t = time.perf_counter()
        r = c.get(url, HTTP_ACCEPT_ENCODING="gzip")
        res["request_s"] = round(time.perf_counter() - t, 2)
        res["request_status"] = r.status_code
        res["request_content_encoding"] = r.get("Content-Encoding")
        RESULT["A4-03"] = res
        _save()

    # ------------------------------------------------------------------ A4-04 / A4-18
    def test_a404_padron(self):
        from django.core.cache import cache

        from programas.models import Formulario
        from programas.services.padron import cargar_padron

        conv = self.rel.convocatoria
        pendientes = list(
            Formulario.objects.filter(relevamiento=self.rel, validado_renaper=False, identidad_forzada=False)
            .select_related("ciudadano")
            .only("pk", "ciudadano__dni", "ciudadano__genero")
        )
        entradas = [
            {
                "dni": f.ciudadano.dni,
                "sexo": f.ciudadano.genero,
                "nombre": "NOMBRE",
                "apellido": "APELLIDO",
                "fecha_nacimiento": __import__("datetime").date(2000, 1, 1),
                "localidad_texto": "",
            }
            for f in pendientes
        ]
        # completar hasta 50k filas de padrón (sin cruce)
        entradas += [
            {
                "dni": f"{40000000 + i}",
                "sexo": "F",
                "nombre": "N",
                "apellido": "A",
                "fecha_nacimiento": None,
                "localidad_texto": "",
            }
            for i in range(50000 - len(entradas))
        ]
        deletes = Counter()
        orig = cache.delete

        def contar(key, *a, **k):
            deletes["delete"] += 1
            return orig(key, *a, **k)

        with patch.object(cache, "delete", side_effect=contar), CaptureQueriesContext(connection) as ctx:
            t = time.perf_counter()
            resumen = cargar_padron(conv, None, entradas)
            dt = time.perf_counter() - t
        por = Counter(f"{_tipo(q['sql'])} {_tabla(q['sql'])}" for q in ctx.captured_queries)
        ins_padron = [
            q["sql"]
            for q in ctx.captured_queries
            if "programas_padronhabilitado" in q["sql"] and q["sql"].startswith("INSERT")
        ]
        RESULT["A4-04"] = {
            "pendientes_cruzados": resumen.casos_validados,
            "filas_padron": len(entradas),
            "queries": len(ctx.captured_queries),
            "segundos_sqlite": round(dt, 2),
            "por_tipo": dict(por.most_common(12)),
            "cache_delete": deletes["delete"],
            "inserts_padron_sqlite": len(ins_padron),
        }
        _save()

    # ------------------------------------------------------------------ A4-07 / A4-01 (costo por caso)
    def test_a407_payload(self):
        from programas.services import proceso_masivo as pm
        from programas.services import siis_envio
        from programas.services.siis_envio import Catalogos, armar_payload

        ids = list(pm.candidatos(programa=self.programa, filtrar_materias=False).values_list("pk", flat=True)[:200])
        casos = pm.hidratar(ids)
        orig = siis_envio.respuestas_por_destino

        def con_domicilio(f):
            r = orig(f)
            r.update(
                {
                    "prov_actual": "Chaco",
                    "loc_actual": "Resistencia",
                    "prov_nacim": "Chaco",
                    "loc_nacim": "Resistencia",
                    "est_civil": "Soltero",
                }
            )
            return r

        cat = Catalogos(cargar=lambda nombre: [{"id": 1, "nombre": "Soltero/a"}])
        res = {}
        with patch.object(siis_envio, "respuestas_por_destino", side_effect=con_domicilio):
            with CaptureQueriesContext(connection) as ctx:
                armar_payload(casos[0], catalogos=cat)
            res["queries_por_armar_payload"] = len(ctx.captured_queries)
            res["tablas"] = dict(Counter(_tabla(q["sql"]) for q in ctx.captured_queries))
            cuenta = pm.Cuenta()
            with CaptureQueriesContext(connection) as ctx:
                t = time.perf_counter()
                pm.elegir_completos(casos, cat, 5000, cuenta)
                dt = time.perf_counter() - t
            res["elegir_completos_200_queries"] = len(ctx.captured_queries)
            res["elegir_completos_200_ms_sqlite"] = round(dt * 1000)
        with CaptureQueriesContext(connection) as ctx:
            t = time.perf_counter()
            lista = list(pm.hidratar_por_lotes(ids))
            dt = time.perf_counter() - t
        res["hidratar_200_queries"] = len(ctx.captured_queries)
        res["hidratar_trae_definicion"] = '"definicion"' in ctx.captured_queries[0]["sql"]
        res["hidratar_trae_respuestas"] = '"respuestas"' in ctx.captured_queries[0]["sql"]
        res["bytes_json_por_caso"] = round(
            sum(
                len(json.dumps(c.definicion or {}))
                + len(json.dumps(c.respuestas or {}))
                + len(json.dumps(c.data or {}))
                for c in lista
            )
            / max(1, len(lista))
        )
        res["bytes_definicion_por_caso"] = round(
            sum(len(json.dumps(c.definicion or {})) for c in lista) / max(1, len(lista))
        )
        RESULT["A4-07"] = res
        _save()

    # ------------------------------------------------------------------ A4-08
    def test_a408_candidatos(self):
        from programas.models import Formulario
        from programas.services import proceso_masivo as pm

        dnis = [
            f.ciudadano.dni for f in Formulario.objects.filter(relevamiento=self.rel).select_related("ciudadano")[:7500]
        ]
        dnis += [f"{(i * 7919) % 9000000 + 41000000}" for i in range(15531 - len(dnis))]  # 8 dígitos como la lista real
        with connection.cursor() as cur:
            cur.execute("CREATE TABLE aprobados_materias (dni VARCHAR(20))")
            cur.executemany("INSERT INTO aprobados_materias (dni) VALUES (%s)", [(d,) for d in dnis])
        llamadas = Counter()
        orig = connection.introspection.table_names

        def contar(*a, **k):
            llamadas["table_names"] += 1
            return orig(*a, **k)

        res = {}
        with patch.object(connection.introspection, "table_names", side_effect=contar):
            s = pm.dnis_aprobados_materias()
            res["dnis_en_set"] = len(s)
            qs = pm.candidatos(programa=self.programa)
            try:
                with CaptureQueriesContext(connection) as ctx:
                    t = time.perf_counter()
                    n = qs.count()
                    dt = time.perf_counter() - t
                res["count"] = n
                res["count_ms_sqlite"] = round(dt * 1000)
                res["sql_bytes"] = len(ctx.captured_queries[-1]["sql"])
                sql = ctx.captured_queries[-1]["sql"]
                res["sql_sin_in"] = sql[:1500]
            except Exception as exc:  # noqa: BLE001
                res["count_error"] = repr(exc)[:300]
            llamadas.clear()
            c = self._client()
            url = reverse("becas:proceso_masivo", args=[self.programa.pk])
            try:
                with CaptureQueriesContext(connection) as ctx:
                    r = c.get(url)
                res["get_status"] = r.status_code
                res["get_queries"] = len(ctx.captured_queries)
                res["get_bytes_sql"] = sum(len(q["sql"]) for q in ctx.captured_queries)
            except Exception as exc:  # noqa: BLE001
                res["get_error"] = repr(exc)[:300]
            res["table_names_por_get"] = llamadas["table_names"]
        RESULT["A4-08"] = res
        _save()

    # ------------------------------------------------------------------ A4-13
    def test_a413_link(self):
        from portal.services.inscripcion import relevamiento_disponible

        rel = type(self.rel).objects.get(pk=self.rel.pk)
        with CaptureQueriesContext(connection) as ctx:
            relevamiento_disponible(rel)
        c = self.client
        url = (
            reverse("portal:inscripcion_paso1", args=[rel.token_publico])
            if getattr(rel, "token_publico", None)
            else None
        )
        res = {
            "queries_relevamiento_disponible": len(ctx.captured_queries),
            "sql": [q["sql"] for q in ctx.captured_queries],
        }
        if url:
            with CaptureQueriesContext(connection) as ctx:
                r = c.get(url)
            res.update(
                {
                    "paso1_get_status": r.status_code,
                    "paso1_get_queries": len(ctx.captured_queries),
                    "paso1_counts": [q["sql"][:160] for q in ctx.captured_queries if "COUNT(" in q["sql"]],
                }
            )
        RESULT["A4-13"] = res
        _save()


class V4Perfil(V4Perf):
    def test_a403_perfil(self):
        import cProfile
        import pstats

        from programas.services import dashboard_becas
        from programas.services.exportacion_reportes import respuesta_libro

        conv = self.rel.convocatoria
        reporte, alcance = dashboard_becas.respuestas_por_persona(conv)
        pr = cProfile.Profile()
        pr.enable()
        t = time.perf_counter()
        respuesta_libro([("Respuestas", reporte)], "x", alcance=alcance)
        dt = time.perf_counter() - t
        pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(12)
        from openpyxl import Workbook

        from programas.services.exportacion_reportes import celda_segura

        t = time.perf_counter()
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("R")
        for fila in reporte.filas:
            ws.append([celda_segura(v) for v in fila])
        b = io.BytesIO()
        wb.save(b)
        dt2 = time.perf_counter() - t
        RESULT["A4-03-perfil"] = {
            "respuesta_libro_s": round(dt, 2),
            "bytesio_s": round(dt2, 2),
            "top": s.getvalue()[:4000],
            "muestra_fila": [str(v)[:80] for v in reporte.filas[0]],
        }
        _save()


class V4Padron(V4Perf):
    def test_a404_perfil(self):
        import cProfile
        import datetime
        import pstats

        from programas.models import Formulario
        from programas.services.padron import cargar_padron

        conv = self.rel.convocatoria
        pendientes = list(
            Formulario.objects.filter(relevamiento=self.rel, validado_renaper=False, identidad_forzada=False)
            .select_related("ciudadano")
            .only("pk", "ciudadano__dni", "ciudadano__genero")
        )
        entradas = [
            {
                "dni": f.ciudadano.dni,
                "sexo": f.ciudadano.genero,
                "nombre": "NOMBRE",
                "apellido": "APELLIDO",
                "fecha_nacimiento": datetime.date(2000, 1, 1),
                "localidad_texto": "",
            }
            for f in pendientes
        ]
        entradas += [
            {
                "dni": f"{40000000 + i}",
                "sexo": "F",
                "nombre": "N",
                "apellido": "A",
                "fecha_nacimiento": None,
                "localidad_texto": "",
            }
            for i in range(50000 - len(entradas))
        ]
        cuenta = Counter()
        bytes_insert_padron = [0]

        def wrapper(execute, sql, params, many, context):
            cuenta[f"{_tipo(sql)} {_tabla(sql)}"] += 1
            if sql.startswith("INSERT") and "padronhabilitado" in sql:
                bytes_insert_padron[0] += len(sql) + sum(len(str(p)) + 3 for p in (params or ()))
            return execute(sql, params, many, context)

        pr = cProfile.Profile()
        with connection.execute_wrapper(wrapper):
            t = time.perf_counter()
            pr.enable()
            resumen = cargar_padron(conv, None, entradas)
            pr.disable()
            dt = time.perf_counter() - t
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(25)
        RESULT["A4-04-exacto"] = {
            "validados": resumen.casos_validados,
            "sentencias": dict(cuenta.most_common(15)),
            "total_sentencias": sum(cuenta.values()),
            "segundos_con_profiler": round(dt, 1),
            "bytes_insert_padron_aprox_mysql_un_insert": bytes_insert_padron[0],
            "perfil": s.getvalue()[:6000],
        }
        _save()


class V4Alertas(V4Perf):
    def test_v3new03_generar_alertas(self):
        from legajos.models import AlertaCiudadano, Ciudadano
        from programas.models import InscripcionPrograma

        cuenta = Counter()

        def wrapper(execute, sql, params, many, context):
            cuenta[f"{_tipo(sql)} {_tabla(sql)}"] += 1
            return execute(sql, params, many, context)

        activos = Ciudadano.objects.filter(activo=True).count()
        con_legajo = (
            InscripcionPrograma.objects.filter(legajo_id__isnull=False).values("ciudadano_id").distinct().count()
        )
        alertas_antes = AlertaCiudadano.objects.count()
        with connection.execute_wrapper(wrapper):
            t = time.perf_counter()
            call_command("generar_alertas", stdout=StringIO())
            dt1 = time.perf_counter() - t
        primera = dict(cuenta)
        total1 = sum(cuenta.values())
        alertas_1 = AlertaCiudadano.objects.count()
        cuenta.clear()
        with connection.execute_wrapper(wrapper):
            call_command("generar_alertas", stdout=StringIO())
        total2 = sum(cuenta.values())
        alertas_2 = AlertaCiudadano.objects.count()
        RESULT["V3-NEW-03"] = {
            "ciudadanos_activos": activos,
            "ciudadanos_con_legajo": con_legajo,
            "sentencias_corrida_1": total1,
            "por_tabla_corrida_1": dict(Counter(primera).most_common(12)),
            "segundos_sqlite_corrida_1": round(dt1, 1),
            "sentencias_corrida_2": total2,
            "alertas_antes_1_2": [alertas_antes, alertas_1, alertas_2],
        }
        _save()


def validar_casos_pendientes_v4(objetivo, usuario=None):
    """Prototipo del verificador (no va al repo): mismo resultado, escrituras en lote."""
    from django.core.cache import cache
    from django.db import transaction
    from django.utils import timezone

    from legajos.models import Ciudadano
    from programas.models import Formulario, PadronHabilitado, TracaFormulario
    from programas.services import padron as P

    filas = {
        (f.dni, f.sexo): f
        for f in P.padron_de(objetivo).exclude(nombre="").exclude(apellido="").select_related("localidad")
    }
    if not filas:
        return 0
    pendientes = (
        Formulario.objects.filter(validado_renaper=False, identidad_forzada=False)
        .defer("data", "respuestas", "definicion", "datos_siis")
        .select_related("ciudadano")
    )
    if P._es_relevamiento(objetivo):
        pendientes = pendientes.filter(relevamiento=objetivo)
    else:
        pendientes = pendientes.filter(relevamiento__convocatoria=objetivo).exclude(
            relevamiento__in=PadronHabilitado.objects.filter(relevamiento__convocatoria=objetivo).values(
                "relevamiento_id"
            )
        )
    ahora = timezone.now()
    trazas, ciudadanos_por_campos, solo_constantes, con_json = [], {}, [], []
    for formulario in pendientes.iterator(chunk_size=2000):
        dni, sexo = P._identidad_del_caso(formulario)
        fila = filas.get((P.normalizar_dni(dni), P.normalizar_sexo(sexo)))
        if fila is None:
            continue
        cambios = [("Validación de identidad", "Pendiente", "Validada por padrón")]
        ciudadano = formulario.ciudadano
        if ciudadano is not None:
            actualizados = []
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento),
                ("localidad", fila.localidad),
            ):
                if valor and not getattr(ciudadano, campo):
                    setattr(ciudadano, campo, valor)
                    actualizados.append(campo)
                    cambios.append((f"Ciudadano · {campo}", "", str(valor)))
            if actualizados:
                ciudadano.modificado = ahora
                ciudadanos_por_campos.setdefault(tuple(actualizados), []).append(ciudadano)
        elif isinstance(formulario.datos_identificacion, dict):
            datos = dict(formulario.datos_identificacion)
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento.isoformat() if fila.fecha_nacimiento else ""),
            ):
                if valor and not datos.get(campo):
                    datos[campo] = valor
            if fila.localidad_id and not datos.get("localidad_id"):
                datos["localidad_id"] = fila.localidad_id
            datos["origen"] = "padron"
            formulario.datos_identificacion = datos
        nuevo_dni = formulario._dni_titular_actual()
        if formulario.ciudadano_id is None or nuevo_dni != formulario.dni_titular:
            formulario.dni_titular = nuevo_dni
            con_json.append(formulario)
        else:
            solo_constantes.append(formulario.pk)
        trazas.extend(
            TracaFormulario(
                formulario_id=formulario.pk,
                editado_por=usuario,
                campo=c,
                valor_anterior="" if a in (None, "") else str(a),
                valor_nuevo="" if n in (None, "") else str(n),
            )
            for c, a, n in cambios
        )
    constantes = {
        "validado_renaper": True,
        "origen_validacion": Formulario.OrigenValidacion.PADRON,
        "modificado": ahora,
    }
    for i in range(0, len(solo_constantes), 1000):
        Formulario.objects.filter(pk__in=solo_constantes[i : i + 1000]).update(**constantes)
    for f in con_json:
        for k, v in constantes.items():
            setattr(f, k, v)
    Formulario.objects.bulk_update(con_json, [*constantes, "datos_identificacion", "dni_titular"], batch_size=200)
    for campos, lista in ciudadanos_por_campos.items():
        Ciudadano.objects.bulk_update(lista, [*campos, "modificado"], batch_size=500)
    TracaFormulario.objects.bulk_create(trazas, batch_size=1000)
    claves = {"contar_ciudadanos", "contar_usuarios"} | {
        f"ciudadano_{c.pk}" for lista in ciudadanos_por_campos.values() for c in lista
    }
    transaction.on_commit(lambda: cache.delete_many(list(claves)))
    return len(solo_constantes) + len(con_json)


class V4PadronDespues(V4Perf):
    def test_a404_despues(self):
        import datetime

        from programas.models import Formulario, TracaFormulario
        from programas.services import padron as P

        conv = self.rel.convocatoria
        pendientes = list(
            Formulario.objects.filter(relevamiento=self.rel, validado_renaper=False, identidad_forzada=False)
            .select_related("ciudadano")
            .only("pk", "ciudadano__dni", "ciudadano__genero")
        )
        entradas = [
            {
                "dni": f.ciudadano.dni,
                "sexo": f.ciudadano.genero,
                "nombre": "NOMBRE",
                "apellido": "APELLIDO",
                "fecha_nacimiento": datetime.date(2000, 1, 1),
                "localidad_texto": "",
            }
            for f in pendientes
        ]
        entradas += [
            {
                "dni": f"{40000000 + i}",
                "sexo": "F",
                "nombre": "N",
                "apellido": "A",
                "fecha_nacimiento": None,
                "localidad_texto": "",
            }
            for i in range(50000 - len(entradas))
        ]
        res = {}
        for nombre, funcion in (("antes", P.validar_casos_pendientes), ("despues", validar_casos_pendientes_v4)):
            sid = transaction_savepoint()
            cuenta = Counter()

            def wrapper(execute, sql, params, many, context):
                cuenta[f"{_tipo(sql)} {_tabla(sql)}"] += 1
                return execute(sql, params, many, context)

            with patch.object(P, "validar_casos_pendientes", side_effect=funcion), connection.execute_wrapper(wrapper):
                t = time.perf_counter()
                resumen = P.cargar_padron(conv, None, entradas)
                dt = time.perf_counter() - t
            res[nombre] = {
                "validados": resumen.casos_validados,
                "sentencias": sum(cuenta.values()),
                "detalle": dict(cuenta.most_common(8)),
                "segundos_sqlite": round(dt, 1),
                "trazas": TracaFormulario.objects.filter(formulario__relevamiento=self.rel).count(),
                "validados_en_base": Formulario.objects.filter(relevamiento=self.rel, validado_renaper=True).count(),
            }
            transaction_rollback(sid)
        RESULT["A4-04-antes-despues"] = res
        _save()


def transaction_savepoint():
    from django.db import transaction

    return transaction.savepoint()


def transaction_rollback(sid):
    from django.db import transaction

    transaction.savepoint_rollback(sid)


class V4Payload(V4Perf):
    def test_a407_perfil(self):
        import cProfile
        import pstats

        from programas.services import proceso_masivo as pm
        from programas.services import siis_envio
        from programas.services.siis_envio import Catalogos

        ids = list(pm.candidatos(programa=self.programa, filtrar_materias=False).values_list("pk", flat=True)[:500])
        casos = pm.hidratar(ids)
        orig = siis_envio.respuestas_por_destino

        def con_domicilio(f):
            r = orig(f)
            r.update(
                {
                    "prov_actual": "Chaco",
                    "loc_actual": "Resistencia",
                    "prov_nacim": "Chaco",
                    "loc_nacim": "Resistencia",
                    "est_civil": "Soltero",
                }
            )
            return r

        cat = Catalogos(cargar=lambda nombre: [{"id": 1, "nombre": "Soltero/a"}])
        pr = cProfile.Profile()
        with patch.object(siis_envio, "respuestas_por_destino", side_effect=con_domicilio):
            t = time.perf_counter()
            pm.elegir_completos(casos, cat, 5000, pm.Cuenta())
            dt = time.perf_counter() - t
            pr.enable()
            pm.elegir_completos(casos, cat, 5000, pm.Cuenta())
            pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(12)
        RESULT["A4-07-perfil"] = {
            "ms_por_caso_sin_profiler": round(dt * 1000 / len(casos), 2),
            "top": s.getvalue()[:3500],
        }
        _save()
