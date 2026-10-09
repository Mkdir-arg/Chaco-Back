#!/usr/bin/env python
"""Auditoría mecánica y reproducible de performance para superficies Django clave."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import statistics
import sys
import tempfile
import time
import traceback
import uuid
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from importlib import import_module
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = Path(tempfile.gettempdir()) / "chaco_perf_baseline.json"
WARM_SAMPLE_COUNT = 3

HEX_BLOB_RE = re.compile(r"\b(?:0x[0-9a-f]+|x'[0-9a-f]+')\b", re.IGNORECASE)
SQL_STRING_RE = re.compile(r"'(?:''|\\.|[^'])*'")
SQL_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:\.\d+)?(?![\w])")
WHITESPACE_RE = re.compile(r"\s+")


def bootstrap_django():
    """Carga Django únicamente contra la SQLite in-memory usada por tests."""
    os.environ["PYTEST_RUNNING"] = "1"
    os.environ["DJANGO_SYNCDB_PROJECT_APPS"] = "True"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ.setdefault("DJANGO_SECRET_KEY", "test-key")
    os.environ["DJANGO_DEBUG"] = "False"
    os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"
    os.environ["ENVIRONMENT"] = "dev"

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    import django

    django.setup()

    from django.conf import settings

    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.sqlite3" or database["NAME"] != ":memory:":
        raise RuntimeError("perf_audit se negó a iniciar: la base configurada no es SQLite in-memory")

    # RED-10: el destino del paso 2 del link público sube los cinco adjuntos
    # obligatorios del catálogo, así que medir **escribe archivos**. Van a un temporal:
    # una auditoría no tiene por qué dejar basura en el `media/` del repo.
    settings.MEDIA_ROOT = tempfile.mkdtemp(prefix="chaco_perf_media_")


def normalize_sql(sql: str) -> str:
    """Elimina valores variables para comparar la forma de dos queries."""
    normalized = HEX_BLOB_RE.sub("?", sql)
    normalized = SQL_STRING_RE.sub("?", normalized)
    normalized = SQL_NUMBER_RE.sub("?", normalized)
    return WHITESPACE_RE.sub(" ", normalized).strip()


def sql_fingerprint(sql: str) -> str:
    """Identificador irreversible de una forma de SQL normalizada."""
    return hashlib.sha256(normalize_sql(sql).encode("utf-8")).hexdigest()[:16]


def query_call_site():
    """Devuelve el primer punto de llamada del repositorio, sin rutas locales."""
    for frame in reversed(traceback.extract_stack()[:-1]):
        try:
            relative_path = Path(frame.filename).resolve().relative_to(REPO).as_posix()
        except ValueError:
            continue
        if relative_path != "scripts/perf_audit.py" and not relative_path.startswith(".venv/"):
            return f"{relative_path}:{frame.lineno}:{frame.name}"
    return "origen_no_clasificado"


class QueryDiagnosticCollector:
    """Conserva SQL sólo durante la request para emitir huellas y call-sites seguros."""

    def __init__(self):
        self.records = []

    def __call__(self, execute, sql, params, many, context):
        self.records.append({"sql": sql, "call_site": query_call_site()})
        return execute(sql, params, many, context)


def duplicate_query_groups(query_records):
    groups = defaultdict(lambda: {"occurrences": 0, "call_sites": Counter()})
    for query in query_records:
        fingerprint = sql_fingerprint(query.get("sql", ""))
        groups[fingerprint]["occurrences"] += 1
        groups[fingerprint]["call_sites"][query.get("call_site", "origen_no_clasificado")] += 1

    repeated = [
        {
            "fingerprint": fingerprint,
            "occurrences": group["occurrences"],
            "duplicates": group["occurrences"] - 1,
            "call_sites": [
                {"call_site": call_site, "occurrences": occurrences}
                for call_site, occurrences in sorted(group["call_sites"].items(), key=lambda item: (-item[1], item[0]))
            ],
        }
        for fingerprint, group in groups.items()
        if group["occurrences"] > 1
    ]
    repeated.sort(key=lambda item: (-item["occurrences"], item["fingerprint"]))
    return repeated


#: Un PNG con la firma real y nada más. SIIS-16 (Cambio 174) valida los bytes del
#: adjunto en el link público, así que un archivo de texto con extensión `.png` ya no
#: entra y el envío medido no sería el que ocurre en producción.
PNG_SINTETICO = b"\x89PNG\r\n\x1a\nPERF"

#: Qué contesta el manifiesto en cada campo protegido del catálogo (RED-10). La
#: identidad va por vínculo y no por posición: el texto de la etiqueta y el orden se
#: pueden editar desde el backoffice, el vínculo no.
RESPUESTAS_PROTEGIDAS = {
    "nombre": "Nombre PERF",
    "apellido": "Apellido PERF",
    "dni": "20111222",
    "genero": "F",
    "fecha_nacimiento": "1990-01-01",
    "telefono": "3624000000",
    "email": "paso2@perf.invalid",
}


def datos_paso2(definicion, indice):
    """``(data, files)`` de un envío válido del paso 2, armados desde el catálogo.

    El formulario público es **dinámico**: lo arma el diseño de la convocatoria sobre el
    catálogo de hoy (RN-1), así que una pregunta nueva obligatoria entra sola. Por eso el
    payload no se escribe a mano: se le pregunta al propio form qué campos tiene y se
    contesta por tipo. Si mañana el catálogo suma un adjunto obligatorio, este destino lo
    manda sin que nadie lo actualice —y si no lo mandara, el presupuesto mediría un 200
    con errores de validación en vez de la escritura, que es el modo de falla que importa.
    """
    from django import forms
    from django.core.files.uploadedfile import SimpleUploadedFile

    from portal.forms.inscripcion import InscripcionPaso2Form
    from programas.models import PreguntaGlobal
    from programas.services.diseno import clave_pregunta

    identificacion = {"dni": "70000000", "sexo": "F", "datos": None, "origen": "manual"}
    form = InscripcionPaso2Form(None, None, definicion=definicion, identificacion=identificacion)
    vinculos = {clave_pregunta(p): p.vinculo for p in PreguntaGlobal.objects.filter(protegido=True)}

    datos, archivos = {}, {}
    for nombre, campo in form.fields.items():
        vinculo = vinculos.get(nombre)
        if isinstance(campo, forms.FileField):
            archivos[nombre] = SimpleUploadedFile(
                f"perf-{indice}-{nombre}.png", PNG_SINTETICO, content_type="image/png"
            )
        elif vinculo in RESPUESTAS_PROTEGIDAS:
            datos[nombre] = RESPUESTAS_PROTEGIDAS[vinculo]
        elif isinstance(campo, forms.DateField):
            datos[nombre] = "1990-01-01"
        elif isinstance(campo, forms.EmailField):
            datos[nombre] = f"paso2-{indice}@perf.invalid"
        elif getattr(campo, "choices", None):
            opciones = [valor for valor, _ in campo.choices if valor not in ("", None)]
            if not opciones:
                continue
            datos[nombre] = [opciones[0]] if isinstance(campo, forms.MultipleChoiceField) else opciones[0]
        elif isinstance(campo, (forms.DecimalField, forms.FloatField, forms.IntegerField)):
            datos[nombre] = "1"
        else:
            datos[nombre] = f"PERF {indice}"
    return datos, archivos


def build_targets(worker_id=None):
    """Resuelve el manifiesto después del seed, fuera de la captura SQL."""
    from django.conf import settings
    from django.urls import reverse

    # `timezone` a secas es el del stdlib, que este módulo ya importa arriba.
    from django.utils import timezone as timezone_django
    from rest_framework.authtoken.models import Token

    from conversaciones.models import Conversacion
    from core.management.commands.seed_perf import (
        PERF_ADMIN_USERNAME,
        PERF_CITIZEN_USERNAME,
        PERF_CONVOCATORIA_ESCRITURAS,
        PERF_DNI_LINK_PUBLICO,
        PERF_FIRST_DNI,
        PERF_LOGIN_PASSWORD,
        PERF_LOGIN_USERNAME,
        PERF_SIIS_PROGRAMA_ID,
        PERF_TERRITORIAL_API_USERNAME,
    )
    from core.models import Localidad
    from legajos.models import Ciudadano
    from portal.services.inscripcion import clave_sesion
    from programas.models import Convocatoria, ProgramaSiis, Relevamiento
    from programas.services.becas import definicion_formulario

    ciudadano = Ciudadano.objects.get(dni=PERF_FIRST_DNI)
    programa_siis = ProgramaSiis.objects.get(siis_programa_id=PERF_SIIS_PROGRAMA_ID)
    if worker_id is None:
        conversacion = (
            Conversacion.objects.filter(ciudadano_usuario__username=PERF_CITIZEN_USERNAME)
            .order_by("fecha_inicio")
            .first()
        )
    else:
        worker_suffix = hashlib.sha256(worker_id.encode()).hexdigest()[:12]
        worker_started_at = datetime(2040, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(worker_suffix, 16))
        conversacion, _ = Conversacion.objects.get_or_create(
            ciudadano_usuario__username=PERF_CITIZEN_USERNAME,
            fecha_inicio=worker_started_at,
            defaults={
                "tipo": "personal",
                "estado": "pendiente",
                "prioridad": "normal",
                "dni_ciudadano": PERF_FIRST_DNI,
            },
        )
    relevamiento = Relevamiento.objects.get(zona="Zona PERF item 0000")
    # Cambio 58: el detalle de un caso arma las respuestas desde la foto de la
    # definición, así que entra al presupuesto como cualquier otra ruta pesada.
    formulario = relevamiento.formularios.order_by("numero").first()
    localidad = Localidad.objects.get(pk=ciudadano.localidad_id)
    login_username = (
        PERF_LOGIN_USERNAME
        if worker_id is None
        else f"perf_ci_login_{hashlib.sha256(worker_id.encode()).hexdigest()[:12]}"
    )

    if conversacion is None:
        raise RuntimeError("seed_perf no creó la conversación PERF requerida")

    write_index = itertools.count(1)

    def siguiente_escritura():
        return next(write_index)

    def alta_ciudadano(client, url):
        index = siguiente_escritura()
        worker_offset = int(hashlib.sha256((worker_id or "local").encode()).hexdigest()[:6], 16) % 9_000_000
        dni = str(90_000_000 + worker_offset + index)
        return client.post(
            url,
            {
                "dni": dni,
                "nombre": "Ciudadano",
                "apellido": f"PERF {index}",
                "fecha_nacimiento": "1990-05-05",
                "genero": "X",
                "telefono": "3624000000",
                "email": f"ciudadano-{index}@perf.invalid",
                "domicilio": "Calle PERF 123",
                "provincia": ciudadano.provincia_id,
                "municipio": ciudadano.municipio_id,
                "localidad": ciudadano.localidad_id,
            },
        )

    def carga_relevamiento(client, url):
        index = siguiente_escritura()
        return client.post(
            url,
            {
                "convocatoria": relevamiento.convocatoria_id,
                "territorial": relevamiento.territorial_id,
                "municipio": localidad.municipio_id,
                "zona": localidad.pk,
                "fecha_asignada": f"2026-09-{index:02d}T09:00",
                "fecha_hasta": f"2026-09-{index:02d}T18:00",
                "cupo_maximo": 10,
                "observaciones": f"Relevamiento sintético PERF {index}",
                "confirmar_solapamiento": "1",
            },
        )

    def edicion_convocatoria(client, url):
        index = siguiente_escritura()
        convocatoria = relevamiento.convocatoria
        return client.post(
            url,
            {
                "nombre": f"PERF Convocatoria 000 edición {index}",
                "segmento": convocatoria.segmento_id,
                "fecha_inicio": convocatoria.fecha_inicio.isoformat(),
                "fecha_fin": convocatoria.fecha_fin.isoformat(),
                "descripcion": "Edición sintética para auditoría de performance.",
                "activo": "on",
            },
        )

    def envio_conversacion(client, url):
        index = siguiente_escritura()
        return client.post(
            url,
            data=json.dumps({"mensaje": f"Mensaje sintético PERF {index}"}),
            content_type="application/json",
        )

    # --- RED-10 · las dos escrituras que trabajan bajo el lock del relevamiento ------
    #
    # Las dos ya rompieron o estuvieron al borde contra el `read_timeout` de 10 s
    # (Cambio 91: 165 × 500 en el link público; Cambio 93: el alta por API de 32 a 10
    # consultas) y ninguna tenía destino en el manifiesto: el trabajo que hacen adentro
    # del `select_for_update` no tenía ningún número que lo defendiera.

    convocatoria_escrituras = Convocatoria.objects.get(nombre=PERF_CONVOCATORIA_ESCRITURAS)
    relevamiento_publico = Relevamiento.objects.get(
        convocatoria=convocatoria_escrituras, tipo=Relevamiento.Tipo.PUBLICO
    )
    relevamiento_api = Relevamiento.objects.get(
        convocatoria=convocatoria_escrituras, tipo=Relevamiento.Tipo.TERRITORIAL
    )
    token_de_campo = Token.objects.get(user__username=PERF_TERRITORIAL_API_USERNAME).key
    desplazamiento_dni = int(hashlib.sha256((worker_id or "local").encode()).hexdigest()[:6], 16) % 9_000_000

    def _dni_sintetico(base, index):
        return str(base + desplazamiento_dni + index)

    # Las sesiones del paso 1 se crean **acá**, al armar el manifiesto, y no adentro de
    # la petición medida: sembrarlas cuesta un `INSERT` y un `SELECT` que no son de la
    # pantalla y ensuciarían el presupuesto. Cada una lleva su propio DNI porque el
    # control de duplicados por convocatoria (RN-P5) rechaza el segundo envío del mismo
    # documento, y la muestra en caliente de `perf_audit` repite la escritura.
    motor_de_sesiones = import_module(settings.SESSION_ENGINE)
    sesiones_paso2 = []
    for indice_sesion in range(WARM_SAMPLE_COUNT + 3):
        sesion = motor_de_sesiones.SessionStore()
        sesion[clave_sesion(relevamiento_publico)] = {
            "dni": _dni_sintetico(PERF_DNI_LINK_PUBLICO, indice_sesion),
            "sexo": "F",
            # `origen: manual` es el camino que **no** acredita identidad, así que el
            # formulario pide nombre, apellido y fecha de nacimiento: el envío más
            # pesado de los dos y el único que no depende de un servicio externo.
            "datos": None,
            "origen": "manual",
            "sellada": timezone_django.now().isoformat(),
        }
        sesion.save()
        sesiones_paso2.append(sesion.session_key)

    definicion_publica = definicion_formulario(relevamiento_publico)
    sesiones_disponibles = iter(sesiones_paso2)

    def inscripcion_publica_paso2(client, url):
        """El envío del paso 2: crea el formulario, el ciudadano y el legajo."""
        indice = siguiente_escritura()
        try:
            client.cookies[settings.SESSION_COOKIE_NAME] = next(sesiones_disponibles)
        except StopIteration:
            # Antes acá había un `next(..., sesiones_paso2[-1])`: al agotarse las sesiones
            # se reusaba en silencio la última, ya gastada. El síntoma era el rechazo por
            # DNI duplicado (RN-P5) y un 200 donde el manifiesto espera un 302, o sea un
            # mensaje que no dice qué pasó. Se siembran `WARM_SAMPLE_COUNT + 3` y se gastan
            # `WARM_SAMPLE_COUNT + 1` (una muestra fría más las calientes): el día que el
            # muestreo crezca, esto revienta nombrando el número que hay que mover.
            raise RuntimeError(
                f"inscripcion_publica_paso2 se quedó sin sesiones sembradas: hay {len(sesiones_paso2)} "
                f"(WARM_SAMPLE_COUNT={WARM_SAMPLE_COUNT} + 3) y el muestreo pidió una más. "
                "Subir el margen donde se arma `sesiones_paso2`; reusar una sesión gastada "
                "haría fallar el envío por DNI duplicado (RN-P5) sin decir por qué."
            ) from None
        datos, archivos = datos_paso2(definicion_publica, indice)
        return client.post(url, {**datos, **archivos})

    def becas_api_alta(client, url):
        """`POST …/formularios/`: el alta de un caso desde la app de campo."""
        indice = siguiente_escritura()
        return client.post(
            url,
            data=json.dumps(
                {
                    "client_uuid": str(uuid.uuid4()),
                    "celular": "3624111222",
                    "email_contacto": f"campo-{indice}@perf.invalid",
                    "datos_identificacion": {
                        "dni": _dni_sintetico(PERF_DNI_LINK_PUBLICO + 5_000_000, indice),
                        "nombre": "Juan",
                        "apellido": f"Campo PERF {indice}",
                        "fecha_nacimiento": "1990-01-02",
                    },
                    "data": {"globales": {}, "requisitos": {}},
                }
            ),
            content_type="application/json",
            headers={"authorization": f"Token {token_de_campo}"},
        )

    def login(client, url):
        client.logout()
        return client.post(url, {"username": login_username, "password": PERF_LOGIN_PASSWORD, "remember": "on"})

    return {
        "actors": {
            "backoffice": PERF_ADMIN_USERNAME,
            "citizen": PERF_CITIZEN_USERNAME,
            "login": PERF_LOGIN_USERNAME,
        },
        "targets": [
            {
                "key": "login",
                "route": "users:login",
                "url": reverse("users:login"),
                "actor": "login",
                "request": login,
                "expected_status": 302,
            },
            {"key": "inicio", "route": "core:inicio", "url": reverse("core:inicio"), "actor": "backoffice"},
            {
                "key": "dashboard_redirect",
                "route": "core:dashboard",
                "url": reverse("core:dashboard"),
                "actor": "backoffice",
                "expected_status": 302,
                "expected_redirect_view": "users:login",
            },
            {
                "key": "dashboard_metricas",
                "route": "dashboard:api_metricas",
                "url": reverse("dashboard:api_metricas"),
                "actor": "backoffice",
            },
            {
                "key": "legajos_lista",
                "route": "legajos:ciudadanos",
                "url": reverse("legajos:ciudadanos"),
                "actor": "backoffice",
            },
            {
                "key": "legajo_detalle",
                "route": "legajos:ciudadano_detalle",
                "url": reverse("legajos:ciudadano_detalle", kwargs={"pk": ciudadano.pk}),
                "actor": "backoffice",
            },
            {
                "key": "legajos_ciudadano_nuevo",
                "route": "legajos:ciudadano_nuevo",
                "url": reverse("legajos:ciudadano_nuevo"),
                "actor": "backoffice",
            },
            {
                "key": "conversaciones_lista",
                "route": "conversaciones:lista",
                "url": reverse("conversaciones:lista"),
                "actor": "backoffice",
            },
            {
                "key": "conversacion_detalle",
                "route": "conversaciones:detalle",
                "url": reverse("conversaciones:detalle", kwargs={"conversacion_id": conversacion.pk}),
                "actor": "backoffice",
            },
            {
                "key": "becas_formulario_detalle",
                "route": "becas:formulario_detalle",
                "url": reverse("becas:formulario_detalle", kwargs={"pk": formulario.pk}),
                "actor": "backoffice",
            },
            # SEC-29: las rutas del portal ciudadano (perfil, programas, consultas) ya no
            # existen; la única superficie del portal que queda presupuestada es su home.
            {"key": "portal_home", "route": "portal:home", "url": reverse("portal:home"), "actor": "anonymous"},
            {
                "key": "becas_segmentos",
                "route": "becas:segmentos",
                "url": reverse("becas:segmentos"),
                "actor": "backoffice",
            },
            {
                "key": "becas_convocatorias",
                "route": "becas:convocatorias",
                "url": reverse("becas:convocatorias"),
                "actor": "backoffice",
            },
            {
                "key": "becas_relevamientos",
                "route": "becas:relevamientos",
                "url": reverse("becas:relevamientos"),
                "actor": "backoffice",
            },
            {
                "key": "becas_relevamiento_detalle",
                "route": "becas:relevamiento_detalle",
                "url": reverse("becas:relevamiento_detalle", kwargs={"pk": relevamiento.pk}),
                "actor": "backoffice",
            },
            {
                # Bandeja de personas: llegó a dar 500 por timeout con 40.000 casos.
                "key": "becas_revision",
                "route": "becas:revision",
                "url": reverse("becas:revision"),
                "actor": "backoffice",
            },
            {
                # Revisión de un relevamiento: no paginaba y tardaba 206 s con 40.000 casos.
                "key": "becas_revision_formularios",
                "route": "becas:revision_formularios",
                "url": reverse("becas:revision_formularios", kwargs={"relevamiento_pk": relevamiento.pk}),
                "actor": "backoffice",
            },
            {
                # PERF-02: la pantalla de cupo traía las tres tablas con los cinco JSON
                # del caso y ordenaba por una columna sin índice. En el banco MariaDB de
                # 20.000 casos eran 8,9 s de SQL, con el `read_timeout` de ECOM en 10 s.
                "key": "becas_cupo_segmento",
                "route": "becas:cupo_segmento",
                "url": reverse("becas:cupo_segmento", kwargs={"pk": relevamiento.convocatoria.segmento_id}),
                "actor": "backoffice",
            },
            {
                # PERF-07: con una corrida en curso esta pantalla se relee sola cada 5 s
                # y el `count()` de candidatos viaja con la lista entera de DNI
                # habilitados como literales (188 KB de SQL con la planilla real).
                "key": "becas_proceso_masivo",
                "route": "becas:proceso_masivo",
                "url": reverse("becas:proceso_masivo", kwargs={"pk": programa_siis.pk}),
                "actor": "backoffice",
            },
            {
                "key": "becas_reportes",
                "route": "becas:reportes",
                "url": reverse("becas:reportes"),
                "actor": "backoffice",
            },
            {
                "key": "becas_programas",
                "route": "becas:programas",
                "url": reverse("becas:programas"),
                "actor": "backoffice",
            },
            {
                "key": "alta_ciudadano",
                "route": "legajos:ciudadano_manual",
                "url": reverse("legajos:ciudadano_manual"),
                "actor": "backoffice",
                "expected_status": 302,
                "request": alta_ciudadano,
                "include_in_timing": False,
            },
            {
                "key": "carga_relevamiento",
                "route": "becas:relevamiento_crear",
                "url": reverse("becas:relevamiento_crear"),
                "actor": "backoffice",
                "expected_status": 302,
                "request": carga_relevamiento,
                "include_in_timing": False,
            },
            {
                "key": "edicion_convocatoria",
                "route": "becas:convocatoria_editar",
                "url": reverse("becas:convocatoria_editar", kwargs={"pk": relevamiento.convocatoria_id}),
                "actor": "backoffice",
                "expected_status": 302,
                "request": edicion_convocatoria,
                "include_in_timing": False,
            },
            {
                # RED-10: el envío del paso 2 del link público. Escribe formulario,
                # ciudadano, legajo y adjuntos bajo el `select_for_update` del
                # relevamiento; el Cambio 91 lo vio dar 165 × 500 por `read_timeout`.
                "key": "inscripcion_publica_paso2",
                "route": "portal:inscripcion_paso2",
                "url": reverse("portal:inscripcion_paso2", kwargs={"token": relevamiento_publico.token_publico}),
                "actor": "anonymous",
                "expected_status": 302,
                "expected_redirect_view": "portal:inscripcion_confirmacion",
                "request": inscripcion_publica_paso2,
                "include_in_timing": False,
            },
            {
                # RED-10: el alta de un caso por la app de campo, la otra escritura bajo
                # el mismo lock (Cambio 93: de 32 a 10 consultas). El actor es anónimo
                # porque la autenticación va por `Token` en el encabezado, no por sesión.
                "key": "becas_api_alta",
                "route": "becas_api:relevamiento-formularios",
                "url": reverse("becas_api:relevamiento-formularios", kwargs={"pk": relevamiento_api.pk}),
                "actor": "anonymous",
                "expected_status": 201,
                "request": becas_api_alta,
                "include_in_timing": False,
            },
            {
                "key": "envio_conversacion",
                "route": "conversaciones:enviar_mensaje_operador",
                "url": reverse("conversaciones:enviar_mensaje_operador", kwargs={"conversacion_id": conversacion.pk}),
                "actor": "backoffice",
                "request": envio_conversacion,
                "expected_json_success": True,
                "include_in_timing": False,
            },
        ],
    }


def build_clients(actor_usernames):
    from django.contrib.auth import get_user_model
    from django.test import Client

    user_model = get_user_model()
    clients = {
        "anonymous": Client(raise_request_exception=False),
        "backoffice": Client(raise_request_exception=False),
        "citizen": Client(raise_request_exception=False),
        "login": Client(raise_request_exception=False),
    }
    clients["backoffice"].force_login(user_model.objects.get(username=actor_usernames["backoffice"]))
    clients["citizen"].force_login(user_model.objects.get(username=actor_usernames["citizen"]))
    return clients


def _resolved_view(url):
    from django.urls import Resolver404, resolve

    try:
        return resolve(urlparse(url).path).view_name
    except Resolver404:
        return None


def _capture_request(client, url, request=None):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    collector = QueryDiagnosticCollector()
    with connection.execute_wrapper(collector):
        with CaptureQueriesContext(connection) as captured:
            started = time.perf_counter_ns()
            response = request(client, url) if request else client.get(url, follow=False)
            body = response.content
            duration_ms = (time.perf_counter_ns() - started) / 1_000_000

    duplicate_groups = duplicate_query_groups(collector.records)
    return {
        "response": response,
        "body": body,
        "query_count": len(captured),
        "duplicate_query_count": sum(group["duplicates"] for group in duplicate_groups),
        "duration_ms": duration_ms,
        "duplicate_groups": duplicate_groups,
    }


def measure_target(target, client):
    from django.core.cache import cache

    cache.clear()
    cold = _capture_request(client, target["url"], target.get("request"))
    warm_samples = [_capture_request(client, target["url"], target.get("request")) for _ in range(WARM_SAMPLE_COUNT)]

    response = cold["response"]
    body = cold["body"]

    redirect_to = response.get("Location") if 300 <= response.status_code < 400 else None
    redirect_view = _resolved_view(urljoin(target["url"], redirect_to)) if redirect_to else None
    result = {
        "key": target["key"],
        "route": target["route"],
        "url": target["url"],
        "actor": target["actor"],
        "resolved_view": _resolved_view(target["url"]),
        "status_code": response.status_code,
        "redirect_to": redirect_to,
        "redirect_resolved_view": redirect_view,
        "query_count": cold["query_count"],
        "duplicate_query_count": cold["duplicate_query_count"],
        "duration_ms": round(cold["duration_ms"], 2),
        "warm_sample_count": WARM_SAMPLE_COUNT,
        "warm_query_count": int(statistics.median(sample["query_count"] for sample in warm_samples)),
        "warm_duplicate_query_count": int(
            statistics.median(sample["duplicate_query_count"] for sample in warm_samples)
        ),
        "warm_duration_ms": round(statistics.median(sample["duration_ms"] for sample in warm_samples), 2),
        "response_bytes": len(body),
        "content_type": response.get("Content-Type", ""),
        "duplicate_groups": cold["duplicate_groups"][:10],
    }
    expected_status = target.get("expected_status", 200)
    errors = []
    if response.status_code != expected_status:
        errors.append(f"status {response.status_code}, esperado {expected_status}")
    warm_statuses = {sample["response"].status_code for sample in warm_samples}
    if warm_statuses != {expected_status}:
        errors.append(f"status warm {sorted(warm_statuses)}, esperado solo {expected_status}")
    if result["resolved_view"] != target["route"]:
        errors.append(f"resuelve a {result['resolved_view']!r}, esperado {target['route']!r}")
    expected_redirect_view = target.get("expected_redirect_view")
    if expected_redirect_view and redirect_view != expected_redirect_view:
        errors.append(f"redirect resuelve a {redirect_view!r}, esperado {expected_redirect_view!r}")
    if target.get("expected_json_success"):
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            errors.append("no devolvió JSON válido")
        else:
            if not isinstance(payload, dict) or payload.get("success") is not True:
                errors.append("no confirmó success=true")
    return result, errors


def create_report(scale):
    manifest = build_targets()
    clients = build_clients(manifest["actors"])
    results = []
    failures = []
    for target in manifest["targets"]:
        result, errors = measure_target(target, clients[target["actor"]])
        results.append(result)
        if errors:
            failures.append(f"{target['key']}: {'; '.join(errors)}")

    report = {
        "schema_version": 1,
        "environment": {
            "database": "sqlite-memory",
            "scale": scale,
            "cache_state": "cold request plus median of 3 warm requests per URL; primary fields are cold",
            "duplicate_definition": "sum(occurrences - 1) for normalized SQL repeated in one request",
            "timing_scope": "Django test client + middleware + render; no network/application server",
        },
        "coverage_notes": [
            "dashboard_redirect documents that /dashboard/ redirects to the shadowed users login at /.",
            "SQLite timings and query plans are not representative of MySQL production.",
        ],
        "summary": {
            "url_count": len(results),
            "successful_2xx": sum(1 for result in results if 200 <= result["status_code"] < 300),
            "total_queries": sum(result["query_count"] for result in results),
            "total_duplicate_queries": sum(result["duplicate_query_count"] for result in results),
            "total_duration_ms": round(sum(result["duration_ms"] for result in results), 2),
            "total_warm_queries": sum(result["warm_query_count"] for result in results),
            "total_warm_duplicate_queries": sum(result["warm_duplicate_query_count"] for result in results),
            "total_warm_duration_ms": round(sum(result["warm_duration_ms"] for result in results), 2),
            "total_response_bytes": sum(result["response_bytes"] for result in results),
        },
        "results": results,
    }
    return report, failures


def write_report(report, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def print_report(report):
    print("\nPerformance baseline (cold + mediana de 3 warm por URL)")
    print(f"{'URL':30} {'St':>3} {'Qc':>5} {'Qw':>5} {'Dc':>4} {'Dw':>4} {'ms c':>8} {'ms w':>8} {'Bytes':>9}")
    print("-" * 88)
    for result in report["results"]:
        print(
            f"{result['key'][:30]:30} {result['status_code']:>3} "
            f"{result['query_count']:>5} {result['warm_query_count']:>5} "
            f"{result['duplicate_query_count']:>4} {result['warm_duplicate_query_count']:>4} "
            f"{result['duration_ms']:>8.2f} {result['warm_duration_ms']:>8.2f} {result['response_bytes']:>9}"
        )

    ranked = sorted(
        (result for result in report["results"] if 200 <= result["status_code"] < 300),
        key=lambda result: (-result["query_count"], -result["duplicate_query_count"], result["key"]),
    )[:10]
    print("\nTop 10 por queries cold (solo respuestas 2xx)")
    for position, result in enumerate(ranked, 1):
        print(
            f"{position:>2}. {result['key']}: {result['query_count']} queries, "
            f"{result['duplicate_query_count']} duplicadas, {result['duration_ms']:.2f} ms"
        )

    duplicated = sorted(
        (result for result in report["results"] if 200 <= result["status_code"] < 300),
        key=lambda result: (-result["duplicate_query_count"], -result["query_count"], result["key"]),
    )[:10]
    print("\nTop 10 por queries duplicadas cold (solo respuestas 2xx)")
    for position, result in enumerate(duplicated, 1):
        print(
            f"{position:>2}. {result['key']}: {result['duplicate_query_count']} duplicadas "
            f"sobre {result['query_count']} queries"
        )


def run(scale, output):
    bootstrap_django()

    from django.test.runner import DiscoverRunner

    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = None
    environment_ready = False
    try:
        runner.setup_test_environment()
        environment_ready = True
        old_config = runner.setup_databases()
        seed_output = StringIO()
        with redirect_stdout(seed_output), redirect_stderr(seed_output):
            from django.core.management import call_command

            call_command("seed_perf", scale=scale, verbosity=0)
        report, failures = create_report(scale)
        print_report(report)
        if failures:
            print("\nAudit abortado; no se escribió el baseline:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1
        write_report(report, output)
        try:
            display_output = output.relative_to(REPO)
        except ValueError:
            display_output = output
        print(f"\nBaseline escrito en {display_output}")
        return 0
    finally:
        if old_config is not None:
            runner.teardown_databases(old_config)
        if environment_ready:
            runner.teardown_test_environment()


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, default=200)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale debe ser mayor que cero")
    output = args.output if args.output.is_absolute() else REPO / args.output
    return run(args.scale, output)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
