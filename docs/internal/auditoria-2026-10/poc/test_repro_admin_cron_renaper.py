r"""Reproducciones de admin, ws/alertas, alta RENAPER del backoffice y bootstrap (verificación G3, pasada 3).

Auditoría integral DATAÑACH, oct-2026 (ver el README.md de la carpeta de la auditoría).

CÓMO LEERLO (importante para TDD)
  Cada test AFIRMA EL COMPORTAMIENTO DEFECTUOSO ACTUAL: hoy PASA (verde = el bug existe en
  origin/development @ 917e583). Después del fix, el test correspondiente tiene que FALLAR.
  Para el ciclo TDD del ítem: copiá el test, INVERTÍ la aserción (o escribí el test de la
  sección «Tests a agregar» de la ficha), confirmá que el test invertido FALLA antes del fix
  y PASA después. Este archivo NO se commitea tal cual: se commitea el test invertido, con
  el nombre que pide la ficha.

CÓMO CORRERLO (PowerShell, raíz del repo, en el worktree de la ola)
  $env:PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"   # el venv vive en el checkout principal
  $env:DJANGO_SECRET_KEY = "test-key"; $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
  Copy-Item <este archivo> core/tests/test_repro_admin_cron_renaper.py
  & $env:PY manage.py test core.tests.test_repro_admin_cron_renaper -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

  Corrida de referencia (01-oct-2026): «Ran 9 tests … OK». Usa channels.testing (WebsocketCommunicator)
  y levanta un HTTPServer local para simular RENAPER.

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  G1c02SeedPisaCapacidadesTests                  -> OPS-06 (seeds de arranque pisan capacidades tildadas en el ABM)
  G1c04WsAlertasTests                            -> G1c-04 (/ws/alertas/ sin alcance, sin Origin y sin revalidar sesión)
  G1c08AltaRenaperTests                          -> G1c-08 (DNI con puntos, confirmación RENAPER alterable, edición de DNI)
  G1c09AdminNmas1Tests                           -> G1c-09 (fichas del admin que crecen con la tabla)
  RenaperClienteTests.test_503_*                 -> G1c-15 (Retry(total=0) convierte un 503 en «error de conexión»)
  RenaperClienteTests.test_401_*                 -> SIIS-14 (el token RENAPER no se descarta ante un 401; = G3-02)
"""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano
from programas.models import (
    Convocatoria,
    Formulario,
    InscripcionPrograma,
    Programa,
    ProgramaSiis,
    Relevamiento,
    Segmento,
)
from users.models import Capacidad, Profile, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    perm, _ = Permission.objects.get_or_create(codename=rbac.codename_de(codigo), content_type=ct)
    return perm


def _rol(nombre, caps):
    g = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=g, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    for c in caps:
        g.permissions.add(_perm(c))
    return g


# ---------------------------------------------------------------- G1c-02
class G1c02SeedPisaCapacidadesTests(TestCase):
    def test_seed_datos_base_revierte_tilde_manual(self):
        call_command("seed_datos_base", stdout=StringIO())
        ref = Group.objects.get(name="Becas — Referente")
        pub = _perm("becas.relevamiento.publico")
        ref.permissions.add(pub)  # lo que el Cambio 91 pide hacer «desde Roles, sin deploy»
        op = Group.objects.get(name="Operador de backoffice")
        extra = _perm("ciudadano.crear")
        op.permissions.add(extra)
        self.assertTrue(ref.permissions.filter(pk=pub.pk).exists())

        call_command("seed_datos_base", stdout=StringIO())  # = arranque del pod / contenedor
        ref_tiene = Group.objects.get(name="Becas — Referente").permissions.filter(pk=pub.pk).exists()
        op_tiene = Group.objects.get(name="Operador de backoffice").permissions.filter(pk=extra.pk).exists()
        print(
            f"\n[G1c-02] tras 2do seed_datos_base: Referente con relevamiento.publico={ref_tiene}; "
            f"Operador con ciudadano.crear={op_tiene}"
        )
        self.assertFalse(ref_tiene)
        self.assertFalse(op_tiene)


# ---------------------------------------------------------------- G1c-04 / G3 ws
class G1c04WsAlertasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operador", password="x")
        self.rol = _rol("Solo ver ciudadanos", ["ciudadano.ver"])
        self.user.groups.add(self.rol)
        self.client.force_login(self.user)
        self.cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        self.ciu = Ciudadano.objects.create(dni="20111222", nombre="Persona", apellido="Ajena")

    def _app(self):
        from config.asgi import application

        return application

    def test_difunde_fuera_de_alcance_sin_origin_check_y_sin_revalidar(self):
        from asgiref.sync import sync_to_async

        from legajos.services.alertas import AlertasService
        from legajos.services.filtros_usuario import FiltrosUsuarioService

        def crear_y_enviar(tipo, prioridad):
            alerta = AlertaCiudadano.objects.create(ciudadano=self.ciu, tipo=tipo, prioridad=prioridad, mensaje="m")
            visible = FiltrosUsuarioService.obtener_alertas_usuario(self.user).filter(pk=alerta.pk).exists()
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.id, visible

        def quitar_rol():
            self.user.groups.clear()
            cache.clear()
            return rbac.puede(User.objects.get(pk=self.user.pk), "ciudadano.ver")

        async def flujo():
            com = WebsocketCommunicator(
                self._app(),
                "/ws/alertas/",
                headers=[(b"cookie", self.cookie), (b"origin", b"https://evil.example"), (b"host", b"testserver")],
            )
            ok, _ = await com.connect()
            id1, visible = await sync_to_async(crear_y_enviar)("SIN_CONTACTO", "MEDIA")
            m1 = await com.receive_json_from(timeout=3)
            sigue = await sync_to_async(quitar_rol)()
            id2, _ = await sync_to_async(crear_y_enviar)("SIN_EVALUACION", "BAJA")
            m2 = await com.receive_json_from(timeout=3)
            await com.disconnect()
            return ok, visible, m1, sigue, id2, m2

        ok, visible, m1, sigue, id2, m2 = async_to_sync(flujo)()
        print(f"\n[G1c-04] connect con Origin evil.example: {ok}")
        print(f"[G1c-04] HTTP la muestra al usuario: {visible}; WS entrega: {m1}")
        print(
            f"[G1c-04] tras quitarle el rol (puede={sigue}) el socket abierto recibe la alerta {id2}: "
            f"{m2['alerta']['id'] == id2}"
        )
        self.assertTrue(ok)
        self.assertFalse(visible)
        self.assertEqual(m1["alerta"]["ciudadano"], "Persona Ajena")
        self.assertFalse(sigue)
        self.assertEqual(m2["alerta"]["id"], id2)

    def test_sesion_reemplazada_igual_abre_socket(self):
        # El login en otro navegador reemplaza la sesión: en HTTP esta cookie ya no sirve.
        Profile.objects.update_or_create(user=self.user, defaults={"backoffice_session_key": "otra-sesion"})
        r = self.client.get(reverse("legajos:ciudadanos"))
        print(f"\n[G1c-04] HTTP con la sesión reemplazada: {r.status_code} -> {r.get('Location')}")

        # El cliente de test hizo logout en la sesión: recreamos una sesión vieja válida.
        self.client.force_login(self.user)
        cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.filter(user=self.user).update(backoffice_session_key="otra-sesion")

        async def flujo():
            com = WebsocketCommunicator(self._app(), "/ws/alertas/", headers=[(b"cookie", cookie)])
            ok, _ = await com.connect()
            await com.disconnect()
            return ok

        ok = async_to_sync(flujo)()
        print(f"[G1c-04] WS con sesión reemplazada (backoffice_session_key distinto): conectado={ok}")
        self.assertTrue(ok)


# ---------------------------------------------------------------- G1c-08
class G1c08AltaRenaperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("legajos", password="x")
        self.user.groups.add(_rol("Gestion", ["ciudadano.ver", "ciudadano.crear", "ciudadano.editar"]))
        self.client.force_login(self.user)

    def _post(self, name, data, **kw):
        return self.client.post(reverse(name, **kw), data)

    def test_dni_con_puntos_duplica_persona(self):
        Ciudadano.objects.create(dni="12345678", nombre="Ana", apellido="Perez")
        r = self._post("legajos:ciudadano_manual", {"dni": "12.345.678", "nombre": "Ana", "apellido": "Perez"})
        dnis = list(Ciudadano.objects.order_by("pk").values_list("dni", flat=True))
        print(f"\n[G1c-08] manual '12.345.678' -> {r.status_code}; DNIs en base: {dnis}")
        self.assertEqual(len(dnis), 2)
        # Y la consulta RENAPER no lo frena: el exists() compara contra el DNI normalizado.
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as m:
            m.return_value = {"success": False, "error": "x"}
            self._post("legajos:ciudadano_nuevo", {"dni": "87654321", "sexo": "F"})
        Ciudadano.objects.create(dni="87.654.321", nombre="B", apellido="C")
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as m:
            m.return_value = {"success": True, "data": {"dni": "87654321", "nombre": "B", "apellido": "C"}}
            r = self._post("legajos:ciudadano_nuevo", {"dni": "87654321", "sexo": "F"})
        print(f"[G1c-08] alta RENAPER de 87654321 existiendo '87.654.321': {r.status_code} -> {r.get('Location')}")
        self.assertEqual(r.status_code, 302)

    def test_confirmacion_renaper_acepta_datos_alterados_y_no_deja_procedencia(self):
        datos = {
            "dni": "30111222",
            "nombre": "Real",
            "apellido": "Persona",
            "genero": "F",
            "fecha_nacimiento": "1990-01-01",
            "domicilio": "",
            "provincia": None,
        }
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as m:
            m.return_value = {"success": True, "data": datos, "datos_api": {"apellido": "Persona"}}
            r = self._post("legajos:ciudadano_nuevo", {"dni": "30111222", "sexo": "F"})
        self.assertEqual(r.status_code, 302)
        r = self._post(
            "legajos:ciudadano_confirmar",
            {
                "dni": "99999999",
                "nombre": "Inventado",
                "apellido": "Otro",
                "genero": "M",
                "fecha_nacimiento": "2001-02-03",
            },
        )
        c = Ciudadano.objects.get()
        print(
            f"\n[G1c-08] confirmación alterada -> {r.status_code}; guardado dni={c.dni} nombre={c.nombre} "
            f"estado_renaper={c.estado_renaper!r}"
        )
        self.assertEqual(c.dni, "99999999")
        self.assertEqual(c.estado_renaper, "")

    def test_edicion_cambia_dni_de_un_titular_de_beca(self):
        ps = ProgramaSiis.objects.create(nombre="P", siis_programa_id=79)
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=ps)
        conv = Convocatoria.objects.create(
            nombre="C", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        rel = Relevamiento.objects.create(
            convocatoria=conv, territorial=self.user, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        ciu = Ciudadano.objects.create(dni="27888999", nombre="Bene", apellido="Ficiaria")
        Formulario.objects.create(relevamiento=rel, ciudadano=ciu, estado=Formulario.Estado.APROBADO)
        r = self._post(
            "legajos:ciudadano_editar",
            {"dni": "11111111", "nombre": "Bene", "apellido": "Ficiaria", "estado_renaper": "REGISTRADO"},
            args=[ciu.pk],
        )
        ciu.refresh_from_db()
        print(f"\n[G1c-08] edición -> {r.status_code}; dni={ciu.dni} estado_renaper={ciu.estado_renaper}")
        self.assertEqual(ciu.dni, "11111111")
        self.assertEqual(ciu.estado_renaper, "REGISTRADO")


# ---------------------------------------------------------------- G1c-09
class G1c09AdminNmas1Tests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser("root", "r@x.com", "x")
        self.client.force_login(self.root)
        ps = ProgramaSiis.objects.create(nombre="P", siis_programa_id=79)
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=ps)
        conv = Convocatoria.objects.create(
            nombre="C", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.rel = Relevamiento.objects.create(
            convocatoria=conv, territorial=self.root, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        self.prog = Programa.objects.create(codigo="DISP", nombre="Disp")
        self.n = 0

    def _sumar(self, k):
        for _ in range(k):
            self.n += 1
            ciu = Ciudadano.objects.create(dni=f"3{self.n:07d}", nombre="N", apellido="A")
            Formulario.objects.create(relevamiento=self.rel, ciudadano=ciu)
            InscripcionPrograma.objects.create(ciudadano=ciu, programa=self.prog)

    def _medir(self, url):
        from zeal import zeal_ignore

        with zeal_ignore(), CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return len(ctx.captured_queries)

    def test_ficha_formulario_y_alta_derivacion_crecen_con_la_tabla(self):
        self._sumar(5)
        f = Formulario.objects.first()
        url_f = reverse("admin:programas_formulario_change", args=[f.pk])
        url_d = reverse("admin:programas_derivacionprograma_add")
        a_f, a_d = self._medir(url_f), self._medir(url_d)
        self._sumar(30)
        b_f, b_d = self._medir(url_f), self._medir(url_d)
        print(f"\n[G1c-09] ficha Formulario: {a_f} consultas con 5 casos -> {b_f} con 35")
        print(f"[G1c-09] alta Derivación: {a_d} consultas con 5 inscripciones -> {b_d} con 35")
        self.assertGreaterEqual(b_f - a_f, 25)
        self.assertGreaterEqual(b_d - a_d, 30)


# ---------------------------------------------------------------- RENAPER cliente (G1c-15 y G3 nuevo)
class _Handler(BaseHTTPRequestHandler):
    logins = 0
    consulta_status = 503

    def log_message(self, *a):
        pass

    def do_POST(self):  # noqa: N802
        largo = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(largo)
        if self.path.endswith("/auth/login"):
            type(self).logins += 1
            cuerpo = json.dumps({"token": f"tok{type(self).logins}", "expiration": "2099-01-01T00:00:00Z"}).encode()
            self.send_response(200)
        else:
            cuerpo = json.dumps({"error": "x"}).encode()
            self.send_response(type(self).consulta_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


class RenaperClienteTests(TestCase):
    def setUp(self):
        self.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}/api"
        _Handler.logins = 0
        import legajos.services.consulta_renaper as mod

        mod._client = None
        cache.clear()
        self.mod = mod

    def tearDown(self):
        self.srv.shutdown()
        self.mod._client = None

    def _ajustes(self):
        return override_settings(
            RENAPER_TEST_MODE=False,
            RENAPER_API_URL=self.base,
            RENAPER_API_USERNAME="u",
            RENAPER_API_PASSWORD="p",
            RENAPER_API_KEY="",
            RENAPER_AUTH_MODE="credentials",
            RENAPER_HTTP_METHOD="post",
            RENAPER_LOGIN_URL="",
            RENAPER_CONSULTA_URL="",
        )

    def test_503_se_informa_como_error_de_conexion(self):
        _Handler.consulta_status = 503
        with self._ajustes():
            res = self.mod.consultar_datos_renaper("30111222", "F")
        print(f"\n[G1c-15] RENAPER 503 -> {res}")
        self.assertNotIn("Error HTTP 503", res.get("error", ""))

    def test_401_no_invalida_el_token(self):
        _Handler.consulta_status = 401
        with self._ajustes():
            self.mod.consultar_datos_renaper("30111222", "F")
            r2 = self.mod.consultar_datos_renaper("30111223", "F")
        print(f"\n[G3] tras dos 401: logins={_Handler.logins}; r2={r2.get('error')}")
        self.assertEqual(_Handler.logins, 1)
        self.assertIn("401", r2.get("error", ""))
