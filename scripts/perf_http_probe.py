#!/usr/bin/env python
"""Sonda HTTP acotada y reproducible para el relevamiento de performance #262.

La herramienta solo acepta stacks locales y no registra cuerpos, payloads,
credenciales ni URLs que contengan identificadores de fixtures.
"""

import argparse
import http.cookiejar
import json
import re
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Equivalente HTTP del manifiesto de scripts/perf_audit.py::build_targets.
# Los placeholders sólo se expanden desde fixtures sintéticas del stack efímero.
LECTURAS = (
    ("login", "users:login", "/", "anonymous", 200),
    ("inicio", "core:inicio", "/inicio/", "backoffice", 200),
    ("dashboard_redirect", "core:dashboard", "/dashboard/", "backoffice", 302),
    ("dashboard_metricas", "dashboard:api_metricas", "/api/metricas/", "backoffice", 200),
    ("legajos_lista", "legajos:ciudadanos", "/legajos/ciudadanos/", "backoffice", 200),
    ("legajo_detalle", "legajos:ciudadano_detalle", "/legajos/ciudadanos/{ciudadano_pk}/", "backoffice", 200),
    ("conversaciones_lista", "conversaciones:lista", "/conversaciones/", "backoffice", 200),
    ("conversacion_detalle", "conversaciones:detalle", "/conversaciones/{conversacion_pk}/", "backoffice", 200),
    ("portal_home", "portal:home", "/portal/", "anonymous", 200),
    ("portal_perfil", "portal:ciudadano_mi_perfil", "/portal/mi-perfil/", "citizen", 200),
    ("portal_programas", "portal:ciudadano_mis_programas", "/portal/mi-perfil/programas/", "citizen", 200),
    ("portal_consultas", "portal:ciudadano_mis_consultas", "/portal/mi-perfil/consultas/", "citizen", 200),
    ("becas_segmentos", "becas:segmentos", "/becas/config/segmentos/", "backoffice", 200),
    ("becas_convocatorias", "becas:convocatorias", "/becas/convocatorias/", "backoffice", 200),
    ("becas_relevamientos", "becas:relevamientos", "/becas/relevamientos/", "backoffice", 200),
    (
        "becas_relevamiento_detalle",
        "becas:relevamiento_detalle",
        "/becas/relevamientos/{relevamiento_pk}/",
        "backoffice",
        200,
    ),
)
CONCURRENT_READS = tuple(item for item in LECTURAS if item[3] == "backoffice" and item[4] == 200)
FASES_CON_ESCRITURAS = {"escrituras", "concurrencia", "todas"}
CSRF_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', re.IGNORECASE)
SENSITIVE_KEYS = ("password", "token", "secret", "credential", "username", "user", "payload", "param", "sql")


class ProbeError(RuntimeError):
    """Error de configuración o de una operación imprescindible de la sonda."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Conserva los 302 para distinguir una escritura de una sesión caída."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Session:
    """Sesión HTTP aislada, con cookies y medición hasta headers y hasta EOF."""

    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect())

    def request(self, path, data=None, referer=None, json_body=None, csrf_token=None):
        url = path if path.startswith(("http://", "https://")) else self.base_url + path
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
        elif data is not None:
            body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        else:
            body = None

        request = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET")
        request.add_header("User-Agent", "perf262-http-probe")
        if referer:
            request.add_header("Referer", referer)
        if json_body is not None:
            request.add_header("Content-Type", "application/json")
            request.add_header("X-Requested-With", "XMLHttpRequest")
            if csrf_token:
                request.add_header("X-CSRFToken", csrf_token)
        elif data is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")

        started = time.perf_counter_ns()
        try:
            response = self.opener.open(request, timeout=self.timeout)
            status = response.status
        except urllib.error.HTTPError as exc:
            response = exc
            status = exc.code
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed_ms = (time.perf_counter_ns() - started) / 1e6
            return {"status": None, "ttfb_ms": elapsed_ms, "total_ms": elapsed_ms, "location": None, "error": str(exc)}

        ttfb_ms = (time.perf_counter_ns() - started) / 1e6
        payload = response.read()
        total_ms = (time.perf_counter_ns() - started) / 1e6
        return {
            "status": status,
            "ttfb_ms": ttfb_ms,
            "total_ms": total_ms,
            "location": response.headers.get("Location"),
            "bytes": len(payload),
            "text": payload.decode("utf-8", "replace"),
        }

    def csrf(self, path):
        response = self.request(path)
        match = CSRF_RE.search(response.get("text", ""))
        if match:
            return match.group(1), response
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value, response
        return None, response

    def login(self, username, password):
        token, page = self.csrf("/")
        if token is None:
            raise ProbeError(f"no se obtuvo CSRF para iniciar sesión (status {page['status']})")
        response = self.request(
            "/",
            data={"csrfmiddlewaretoken": token, "username": username, "password": password},
            referer=self.base_url + "/",
        )
        if response["status"] != 302:
            raise ProbeError(f"login de {username!r} devolvió status {response['status']}")
        if is_login_redirect(response):
            raise ProbeError(f"login de {username!r} redirigió nuevamente al login")
        return response

    def portal_login(self, username, password):
        path = "/portal/mi-perfil/login/"
        token, page = self.csrf(path)
        if token is None:
            raise ProbeError(f"no se obtuvo CSRF del portal (status {page['status']})")
        response = self.request(
            path,
            data={"csrfmiddlewaretoken": token, "username": username, "password": password},
            referer=self.base_url + path,
        )
        if response["status"] != 302 or is_login_redirect(response):
            raise ProbeError("el login de ciudadano no completó una sesión válida")
        return response


def is_login_redirect(sample):
    """Un 302 a `/` indica sesión caída, no una escritura exitosa."""
    location = sample.get("location")
    if sample.get("status") != 302 or not location:
        return False
    parsed = urllib.parse.urlparse(location)
    return parsed.path.rstrip("/") == ""


def safe_location(location):
    """Conserva solo destinos inocuos; nunca vuelca URLs con IDs de fixtures."""
    if not location:
        return None
    parsed = urllib.parse.urlparse(location)
    if parsed.path.rstrip("/") == "":
        return "/"
    return "(destino no incluido)"


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def json_success(sample):
    """Valida el indicador funcional sin conservar el cuerpo de la respuesta."""
    try:
        payload = json.loads(sample.get("text", ""))
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("success") is True


def summarize(samples, require_json_success=False, expected_statuses=None):
    """Resume solo respuestas medibles y marca cualquier fallo de sesión."""
    expected_statuses = set(expected_statuses or ())

    def status_is_valid(sample):
        if expected_statuses:
            return sample.get("status") in expected_statuses
        return sample.get("status", 500) < 400

    valid = [
        sample
        for sample in samples
        if sample.get("status") is not None
        and status_is_valid(sample)
        and (not require_json_success or json_success(sample))
    ]
    failures = [
        sample
        for sample in samples
        if sample.get("status") is None
        or not status_is_valid(sample)
        or is_login_redirect(sample)
        or (require_json_success and not json_success(sample))
    ]
    ttfb = [sample["ttfb_ms"] for sample in valid if not is_login_redirect(sample)]
    total = [sample["total_ms"] for sample in valid if not is_login_redirect(sample)]
    statuses = sorted({sample.get("status") for sample in samples}, key=lambda value: (value is None, value))
    locations = sorted({safe_location(sample.get("location")) for sample in samples if sample.get("location")})
    return {
        "estado": "fallido" if failures else "ok",
        "muestras": len(samples),
        "muestras_validas": len(ttfb),
        "muestras_fallidas": len(failures),
        "status_observados": statuses,
        "destinos_observados": locations,
        "redirige_al_login": any(is_login_redirect(sample) for sample in samples),
        "errores": sorted({sample["error"] for sample in samples if sample.get("error")}),
        "ttfb_median_ms": rounded(statistics.median(ttfb) if ttfb else None),
        "ttfb_p95_ms": rounded(percentile(ttfb, 95)),
        "ttfb_max_ms": rounded(max(ttfb) if ttfb else None),
        "total_median_ms": rounded(statistics.median(total) if total else None),
    }


def rounded(value):
    return round(value, 2) if value is not None else None


def measure_flow(session, key, path, reps, request_factory=None, require_json_success=False, expected_statuses=None):
    samples = []
    for index in range(reps):
        if request_factory is None:
            sample = session.request(path)
        else:
            sample = request_factory(session, index)
        samples.append(sample)
    return {
        "flujo": key,
        **summarize(samples, require_json_success=require_json_success, expected_statuses=expected_statuses),
    }


def fase_lecturas(sessions, reps, fixtures):
    results = {}
    for key, route, path, actor, expected_status in LECTURAS:
        path = path.format(**fixtures)
        session = sessions[actor]
        session.request(path)  # Calentamiento descartado del informe.
        results[key] = {
            "ruta": route,
            **measure_flow(session, key, path, reps, expected_statuses={expected_status}),
        }
    return results


def fase_escrituras(session, reps, fixtures):
    stamp = int(time.time())
    results = {}

    def alta_ciudadano(current, index):
        token, _ = current.csrf("/legajos/ciudadanos/manual/")
        dni = str(90000000 + (stamp % 1000) * 10 + index)
        return current.request(
            "/legajos/ciudadanos/manual/",
            data={
                "csrfmiddlewaretoken": token,
                "dni": dni,
                "nombre": "Relev",
                "apellido": f"Escritura{index}",
                "genero": "X",
                "fecha_nacimiento": "1990-05-05",
                "telefono": "3624000000",
                "email": f"relev{dni}@perf.invalid",
                "domicilio": "Calle sintetica 123",
            },
            referer=current.base_url + "/legajos/ciudadanos/manual/",
        )

    results["alta_ciudadano"] = {
        "ruta": "alta de ciudadano manual",
        **measure_flow(session, "alta_ciudadano", "", reps, alta_ciudadano),
    }

    def carga_relevamiento(current, index):
        token, _ = current.csrf("/becas/relevamientos/nuevo/")
        day = (index % 9) + 1
        return current.request(
            "/becas/relevamientos/nuevo/",
            data={
                "csrfmiddlewaretoken": token,
                "convocatoria": fixtures["convocatoria_pk"],
                "territorial": fixtures["territorial_pk"],
                "municipio": fixtures["municipio_pk"],
                "zona": fixtures["localidad_pk"],
                "fecha_asignada": f"2026-09-{day:02d}T09:00",
                "fecha_hasta": f"2026-09-{day:02d}T18:00",
                "cupo_maximo": 10,
                "observaciones": f"Relevamiento sintetico {stamp}-{index}",
                "confirmar_solapamiento": "1",
            },
            referer=current.base_url + "/becas/relevamientos/nuevo/",
        )

    results["carga_relevamiento"] = {
        "ruta": "carga de relevamiento",
        **measure_flow(session, "carga_relevamiento", "", reps, carga_relevamiento),
    }

    edit_path = f"/becas/convocatorias/{fixtures['convocatoria_pk']}/editar/"

    def editar_convocatoria(current, index):
        token, _ = current.csrf(edit_path)
        return current.request(
            edit_path,
            data={
                "csrfmiddlewaretoken": token,
                "nombre": f"PERF Convocatoria 000 rev{index}",
                "segmento": fixtures["segmento_pk"],
                "fecha_inicio": "2025-01-01",
                "fecha_fin": "2030-12-31",
                "descripcion": "Editada por el relevamiento 262",
                "activo": "on",
            },
            referer=current.base_url + edit_path,
        )

    results["edicion_convocatoria"] = {
        "ruta": "edición de convocatoria",
        **measure_flow(session, "edicion_convocatoria", "", reps, editar_convocatoria),
    }

    conversation_path = f"/conversaciones/{fixtures['conversacion_pk']}"

    def responder(current, index):
        csrf_token, _ = current.csrf(conversation_path + "/")
        return current.request(
            conversation_path + "/responder/",
            json_body={"mensaje": f"Mensaje sintetico {stamp}-{index}"},
            csrf_token=csrf_token,
            referer=current.base_url + conversation_path + "/",
        )

    results["envio_conversacion"] = {
        "ruta": "envío de mensaje",
        **measure_flow(session, "envio_conversacion", "", reps, responder, require_json_success=True),
    }
    return results


def fase_concurrencia(base_url, timeout, password, prefix, workers, rounds, fixtures):
    results = {key: [] for key, *_rest in CONCURRENT_READS}
    errors = []
    lock = threading.Lock()

    def worker(index):
        try:
            session = Session(base_url, timeout)
            session.login(f"{prefix}{index}", password)
            for _ in range(rounds):
                for key, _route, path, _actor, _expected in CONCURRENT_READS:
                    path = path.format(**fixtures)
                    sample = session.request(path)
                    with lock:
                        results[key].append(sample)
        except (ProbeError, OSError, urllib.error.URLError) as exc:
            with lock:
                errors.append(f"worker {index}: {type(exc).__name__}: {exc}")

    started = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started
    total = sum(len(samples) for samples in results.values())
    return {
        "nivel_concurrencia": workers,
        "rondas_por_worker": rounds,
        "requests_totales": total,
        "wall_clock_s": rounded(elapsed),
        "throughput_rps": rounded(total / elapsed if elapsed else None),
        "errores": errors,
        "por_flujo": {key: summarize(samples, expected_statuses={200}) for key, samples in results.items()},
    }


def sanitize_snapshot(value, key=""):
    if any(fragment in key.lower() for fragment in SENSITIVE_KEYS):
        return None
    if isinstance(value, dict):
        return {
            name: sanitize_snapshot(item, name)
            for name, item in value.items()
            if not any(fragment in name.lower() for fragment in SENSITIVE_KEYS)
        }
    if isinstance(value, list):
        return [sanitize_snapshot(item, key) for item in value]
    return value


def api_snapshot(base_url, timeout, username, password, session=None):
    if session is None:
        session = Session(base_url, timeout)
    if not getattr(session, "logged_in", False):
        session.login(username, password)
        session.logged_in = True
    response = session.request("/performance-api/")
    if response.get("status") != 200:
        return {"http_status": response.get("status"), "estado": "fallido"}
    try:
        payload = json.loads(response.get("text", ""))
    except (TypeError, ValueError):
        return {"http_status": response.get("status"), "estado": "fallido", "error": "respuesta no JSON"}
    return {"http_status": response["status"], "estado": "ok", "snapshot": sanitize_snapshot(payload)}


def verify_manifest_metrics(api_metrics, reps):
    """Evita declarar cubierta una ruta HTTP si /performance-api/ no la agregó."""
    if api_metrics.get("estado") != "ok":
        raise ProbeError("/performance-api/ no entregó un corte válido para el manifiesto")
    snapshot = api_metrics.get("snapshot", {})
    if snapshot.get("metrics", {}).get("queries", {}).get("source") != "measured":
        raise ProbeError("/performance-api/ no declaró métricas medidas")
    routes = {item.get("route"): item for item in snapshot.get("routes", [])}
    missing = []
    fields = {
        "requests",
        "queries",
        "duplicate_queries",
        "max_queries",
        "max_duplicate_queries",
        "latency_histogram",
        "p95_upper_bound_ms",
        "dependencies",
    }
    for _key, route, _path, _actor, _expected in LECTURAS:
        item = routes.get(route, {})
        if item.get("requests", 0) < reps or not fields.issubset(item):
            missing.append(route)
    if missing:
        raise ProbeError("/performance-api/ no agregó todas las rutas del manifiesto: " + ", ".join(missing))


def parse_args():
    parser = argparse.ArgumentParser(description="Mide TTFB y tiempo total de flujos HTTP en un stack local dedicado.")
    parser.add_argument("--base-url", default="http://localhost:8001", help="URL base; solo localhost, 127.0.0.1 o ::1")
    parser.add_argument("--fase", choices=("lecturas", "escrituras", "concurrencia", "todas"), default="todas")
    parser.add_argument("--reps", type=int, default=5, help="Repeticiones por flujo (default: 5)")
    parser.add_argument("--concurrencia", type=int, default=8, help="Workers simultáneos (default: 8)")
    parser.add_argument("--rondas-concurrencia", type=int, default=5)
    parser.add_argument("--usuario-prefijo", default="perf262_conc_")
    parser.add_argument("--usuario", default="perf_admin")
    parser.add_argument("--usuario-api", default="perf262_api")
    parser.add_argument("--password", default="perf262pass")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--confirmo-entorno-dedicado", action="store_true")
    parser.add_argument("--output", required=True, help="Archivo JSON de salida")
    parser.add_argument("--convocatoria-pk", type=int, default=1)
    parser.add_argument("--territorial-pk", type=int, default=8)
    parser.add_argument("--municipio-pk", type=int, default=758)
    parser.add_argument("--localidad-pk", type=int, default=8047)
    parser.add_argument("--segmento-pk", type=int, default=1)
    parser.add_argument("--conversacion-pk", type=int, default=1)
    parser.add_argument("--ciudadano-pk", type=int, default=1)
    parser.add_argument("--relevamiento-pk", type=int, default=1)
    return parser.parse_args()


def validate_args(args):
    parsed = urllib.parse.urlparse(args.base_url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
    ):
        raise ProbeError("--base-url debe apuntar únicamente a localhost, 127.0.0.1 o ::1 y no contener credenciales")
    if not parsed.netloc or parsed.path not in ("", "/"):
        raise ProbeError("--base-url no debe incluir una ruta, solo esquema, host y puerto locales")
    if args.reps < 1 or args.concurrencia < 1 or args.rondas_concurrencia < 1 or args.timeout <= 0:
        raise ProbeError("reps, concurrencia y rondas deben ser mayores que cero; timeout debe ser positivo")
    if args.fase in FASES_CON_ESCRITURAS and not args.confirmo_entorno_dedicado:
        raise ProbeError("las fases de escrituras y concurrencia requieren --confirmo-entorno-dedicado")


def run(args):
    validate_args(args)
    fixtures = {
        "convocatoria_pk": args.convocatoria_pk,
        "territorial_pk": args.territorial_pk,
        "municipio_pk": args.municipio_pk,
        "localidad_pk": args.localidad_pk,
        "segmento_pk": args.segmento_pk,
        "conversacion_pk": args.conversacion_pk,
        "ciudadano_pk": args.ciudadano_pk,
        "relevamiento_pk": args.relevamiento_pk,
    }
    output = {"herramienta": "perf_http_probe", "fase_solicitada": args.fase, "fases": {}}
    admin = Session(args.base_url, args.timeout)
    admin.login(args.usuario, args.password)
    citizen = Session(args.base_url, args.timeout)
    citizen.portal_login("perf_ciudadano", args.password)
    anonymous = Session(args.base_url, args.timeout)
    sessions = {"anonymous": anonymous, "backoffice": admin, "citizen": citizen}
    api = Session(args.base_url, args.timeout)

    phases = ("lecturas", "escrituras", "concurrencia") if args.fase == "todas" else (args.fase,)
    for phase in phases:
        if phase == "lecturas":
            flows = fase_lecturas(sessions, args.reps, fixtures)
        elif phase == "escrituras":
            flows = fase_escrituras(admin, args.reps, fixtures)
        else:
            flows = fase_concurrencia(
                args.base_url,
                args.timeout,
                args.password,
                args.usuario_prefijo,
                args.concurrencia,
                args.rondas_concurrencia,
                fixtures,
            )
        metrics = api_snapshot(args.base_url, args.timeout, args.usuario_api, args.password, api)
        if phase == "lecturas":
            verify_manifest_metrics(metrics, args.reps)
        output["fases"][phase] = {
            "flujos": flows,
            "metricas": metrics,
        }
    with open(args.output, "w", encoding="utf-8", newline="") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main():
    args = parse_args()
    try:
        run(args)
    except (ProbeError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
