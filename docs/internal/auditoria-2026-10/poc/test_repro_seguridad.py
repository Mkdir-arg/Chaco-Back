r"""Reproducciones de seguridad y autorización (verificación V1, pasada 2).

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
  Copy-Item <este archivo> core/tests/test_repro_seguridad.py
  & $env:PY manage.py test core.tests.test_repro_seguridad -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

  Corrida de referencia (01-oct-2026): «Ran 21 tests … OK (skipped=1)»; SEC-09 aparte con
  SERVE_MEDIA=True también OK. Con el fix de SEC-01 aplicado (patch_settings_sec01.py) los dos
  tests de SEC-01 pasan a 403: es lo buscado.

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  SEC01BasicAuthTests                            -> SEC-01 (+ SEC-29: registro anónimo sobre legajo existente)
  SEC02CiudadanoApiTests                         -> SEC-02
  SEC03TomaSuperusuarioTests                     -> SEC-03
  SEC04RenaperAnonimoTests                       -> SEC-04 (+ V1-NEW-04, oráculo de defunción)
  SEC05ActivateDeactivateTests                   -> SEC-05
  SEC06BecasCrossProgramTests                    -> SEC-06 (test_coordinador_sin_admin_no_exporta es el contraste que refuta la versión de A4)
  SEC07ProgramaConfigurarTests                   -> SEC-07
  SEC08XssRolTests                               -> SEC-08 (+ V1-NEW-01, apóstrofo)
  SEC09MediaTests                                -> SEC-09 (solo con $env:SERVE_MEDIA = 'True'; si no, se saltea)
  SEC10AdjuntosTests                             -> SEC-10
  SEC11LegajosJsonTests                          -> SEC-11 (+ SEC-18: alertas_dashboard con fallback CRÍTICA)
  SEC12DerivacionGetTests                        -> SEC-12
  SEC13GeoApiTests                               -> SEC-13
  SEC14DashboardApiTests                         -> SEC-14
  SEC15UploadsTests                              -> SEC-15
  SEC16UsersApiListTests                         -> SEC-16
  SEC17RenombrarCiudadanosTests                  -> SEC-17
  SEC18DebugXssTests                             -> SEC-19 (página de debug con XSS; el nombre de la clase quedó de la pasada 2)
"""

import base64
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core import rbac
from legajos.models import Adjunto, AlertaCiudadano, Ciudadano
from programas.models import (
    Convocatoria,
    DerivacionPrograma,
    Formulario,
    InscripcionPrograma,
    Programa,
    ProgramaSiis,
    Relevamiento,
    Segmento,
)
from users.models import Capacidad, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _basic(user, pwd):
    return "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()


def _rol(nombre, caps, programa=None, categoria=None):
    g = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=g,
        categoria=categoria or (rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_BACKOFFICE),
        programa=programa,
        activo=True,
    )
    for c in caps:
        g.permissions.add(_perm(c))
    return g


class SEC01BasicAuthTests(TestCase):
    """A5-01: Basic auth en /api/ saltea PortalCiudadanoMiddleware (cadena desde registro anonimo)."""

    def setUp(self):
        cache.clear()
        Group.objects.get_or_create(name="Ciudadanos")
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Perez")
        User.objects.create_superuser("root", "r@x.com", "x")

    def test_registro_anonimo_y_basic_a_api_backoffice(self):
        # 1) Registro anonimo en el portal sobre un legajo existente (sin RENAPER).
        r = self.client.post(reverse("portal:ciudadano_registro_step1"), {"dni": "30111222", "genero": "F"})
        print("\n[SEC-01] registro step1:", r.status_code, r.get("Location"))
        r = self.client.post(
            reverse("portal:ciudadano_registro_step2"),
            {"email": "a@evil.test", "telefono": "", "password1": "Clave-Seg-2026x", "password2": "Clave-Seg-2026x"},
        )
        print("[SEC-01] registro step2:", r.status_code, r.get("Location"))
        u = User.objects.get(username="30111222")
        self.assertTrue(rbac.es_ciudadano_portal(u))
        # 2) Con sesion, el middleware lo corta.
        r = self.client.get("/api/users/users/")
        print("[SEC-01] sesion ciudadano /api/users/users/:", r.status_code)
        self.assertEqual(r.status_code, 302)
        # 3) Con Basic, pasa.
        c = APIClient()
        auth = _basic("30111222", "Clave-Seg-2026x")
        for url in ("/api/users/users/", "/api/legajos/ciudadanos/", "/api/buscar-ciudadanos/?q=301"):
            r = c.get(url, HTTP_AUTHORIZATION=auth)
            print(f"[SEC-01] basic ciudadano GET {url}:", r.status_code, r.content[:120])
            self.assertEqual(r.status_code, 200)
        r = c.post("/api/core/provincias/", {"nombre": "ProvPoC"}, HTTP_AUTHORIZATION=auth)
        print("[SEC-01] basic ciudadano POST provincia:", r.status_code)
        self.assertEqual(r.status_code, 201)

    def test_territorial_sin_login_web_usa_api_por_basic(self):
        rol = _rol("Territorial PoC", ["becas.campo"])
        t = User.objects.create_user("terr", password="Terr-2026-x")
        t.groups.add(rol)
        r = self.client.post(reverse("users:login"), {"username": "terr", "password": "Terr-2026-x"})
        print("\n[SEC-01] login web territorial:", r.status_code, "(200 = rechazado, form con error)")
        r = APIClient().get("/api/legajos/ciudadanos/", HTTP_AUTHORIZATION=_basic("terr", "Terr-2026-x"))
        print("[SEC-01] basic territorial /api/legajos/ciudadanos/:", r.status_code)
        self.assertEqual(r.status_code, 200)


class SEC02CiudadanoApiTests(TestCase):
    """A5-02 / A3-02: CiudadanoViewSet CRUD para cualquier autenticado."""

    def test_usuario_sin_capacidades_patch_y_delete(self):
        ciu = Ciudadano.objects.create(dni="22333444", nombre="Luis", apellido="Gomez")
        u = User.objects.create_user("plano", password="x")
        c = APIClient()
        c.force_authenticate(u)
        r = c.patch(f"/api/legajos/ciudadanos/{ciu.pk}/", {"dni": "99999999"}, format="json")
        print("\n[SEC-02] PATCH dni sin capacidades:", r.status_code)
        self.assertEqual(r.status_code, 200)
        ciu.refresh_from_db()
        self.assertEqual(ciu.dni, "99999999")
        r = c.delete(f"/api/legajos/ciudadanos/{ciu.pk}/")
        print("[SEC-02] DELETE sin capacidades:", r.status_code)
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Ciudadano.objects.filter(pk=ciu.pk).exists())


class SEC03TomaSuperusuarioTests(TestCase):
    """A5-03: admin de usuarios de un programa cambia clave/email de un superusuario."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        rol_admin = _rol("Admin Becas", ["programa.usuario.administrar"], programa=self.becas)
        self.admin = User.objects.create_user("adm-becas", password="x")
        self.admin.groups.add(rol_admin)
        self.rol_op = _rol("Operador Becas", [], programa=self.becas)
        self.su = User.objects.create_superuser("root", "root@example.com", "x")
        self.su.groups.add(self.rol_op)
        User.objects.create_superuser("root2", "root2@example.com", "x")

    def test_cambia_clave_y_desactiva_superusuario(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            reverse("users:usuario_editar", args=[self.su.pk]),
            {
                "username": "root",
                "email": "atacante@evil.test",
                "password": "Pwn3d-Clave-2026",
                "groups": [str(self.rol_op.pk)],
                "first_name": "",
                "last_name": "",
            },
        )
        self.su.refresh_from_db()
        print(
            "\n[SEC-03] POST editar superusuario:",
            r.status_code,
            self.su.email,
            self.su.check_password("Pwn3d-Clave-2026"),
        )
        self.assertTrue(self.su.check_password("Pwn3d-Clave-2026"))
        r = self.client.post(reverse("users:usuario_toggle", args=[self.su.pk]))
        self.su.refresh_from_db()
        print("[SEC-03] toggle activo superusuario:", r.status_code, "is_active=", self.su.is_active)
        self.assertFalse(self.su.is_active)


class SEC04RenaperAnonimoTests(TestCase):
    """A5-04 / A3-01 / A2-01: RENAPER anonimo, datos_api crudo y throttle evadible por XFF."""

    RES = {
        "success": True,
        "data": {"dni": "1", "nombre": "N", "apellido": "A", "fecha_nacimiento": "1990-01-01", "genero": "M"},
        "datos_api": {"calle": "San Martin", "numero": "123", "piso": "2", "provincia": "Chaco"},
    }

    def setUp(self):
        cache.clear()

    def test_anonimo_recibe_domicilio_y_throttle_se_esquiva(self):
        c = APIClient()
        with patch("legajos.api_views.consultar_datos_renaper", return_value=self.RES):
            r = c.post("/api/legajos/renaper/consultar/", {"dni": "30111222", "sexo": "M"}, format="json")
            print("\n[SEC-04] anonimo:", r.status_code, r.json().get("datos_api"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["datos_api"]["calle"], "San Martin")
            codigos = []
            for i in range(40):
                r = c.post(
                    "/api/legajos/renaper/consultar/",
                    {"dni": str(30000000 + i), "sexo": "M"},
                    format="json",
                    HTTP_X_FORWARDED_FOR=f"1.2.3.{i}, 10.0.0.1",
                )
                codigos.append(r.status_code)
            print("[SEC-04] 40 pedidos con XFF rotado:", {c_: codigos.count(c_) for c_ in set(codigos)})
            self.assertNotIn(429, codigos)
            # Control: sin rotar, el pedido 31 da 429.
            cache.clear()
            ctrl = [
                c.post("/api/legajos/renaper/consultar/", {"dni": "1", "sexo": "M"}, format="json").status_code
                for _ in range(31)
            ]
            print("[SEC-04] control sin XFF, pedido 31:", ctrl[-1])
            self.assertEqual(ctrl[-1], 429)


class SEC05ActivateDeactivateTests(TestCase):
    """A5-05: deactivate/activate por API sin usuario.administrar."""

    def test_usuario_sin_capacidades_desactiva_a_otro(self):
        User.objects.create_superuser("root", "r@x.com", "x")
        victima = User.objects.create_user("victima", password="x")
        u = User.objects.create_user("plano", password="x")
        c = APIClient()
        c.force_authenticate(u)
        r = c.post(f"/api/users/users/{victima.pk}/deactivate/")
        victima.refresh_from_db()
        print("\n[SEC-05] deactivate sin capacidad:", r.status_code, "is_active=", victima.is_active)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(victima.is_active)


class SEC06BecasCrossProgramTests(TestCase):
    """A5-06 (+A4 obs): admin de roles de Dispositivos se otorga becas.* y exporta DNI de Becas."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        rol = _rol(
            "Admin Dispositivos", ["programa.usuario.administrar", "programa.rol.administrar"], programa=self.disp
        )
        self.u = User.objects.create_user("adm-disp", password="x")
        self.u.groups.add(rol)
        User.objects.create_superuser("root", "r@x.com", "x")
        ps = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=ps)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        terr = User.objects.create_user("t", password="x")
        rel = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=terr, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        ciu = Ciudadano.objects.create(dni="27888999", nombre="Beneficiaria", apellido="Secreta")
        Formulario.objects.create(relevamiento=rel, ciudadano=ciu, estado=Formulario.Estado.APROBADO)
        self.ps = ps

    def test_se_otorga_becas_admin_y_exporta(self):
        self.client.force_login(self.u)
        r = self.client.get(reverse("users:rol_crear"))
        ofrece = "becas.programa.administrar" in r.content.decode()
        print("\n[SEC-06] ABM roles ofrece becas.programa.administrar al admin de Dispositivos:", ofrece)
        r = self.client.post(
            reverse("users:rol_crear"),
            {
                "name": "Escalada",
                "descripcion": "",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(self.disp.pk),
                "capacidades": ["becas.programa.administrar", "becas.programa.proceso_masivo"],
            },
        )
        g = Group.objects.get(name="Escalada")
        print("[SEC-06] rol creado:", r.status_code, rbac.capacidades_de_grupo(g), "programa=", g.meta.programa)
        self.assertIn("becas.programa.administrar", rbac.capacidades_de_grupo(g))
        self.u.groups.add(g)
        u = User.objects.get(pk=self.u.pk)
        self.client.force_login(u)
        from programas.services.autorizacion import es_admin_becas

        print(
            "[SEC-06] puede global:", rbac.puede(u, "becas.programa.administrar"), "es_admin_becas:", es_admin_becas(u)
        )
        r = self.client.get(reverse("becas:convocatoria_export_beneficiarios", args=[self.conv.pk]))
        body = r.content.decode("utf-8", "ignore")
        print("[SEC-06] export beneficiarios:", r.status_code, body.strip().splitlines()[-1] if body else "")
        self.assertEqual(r.status_code, 200)
        self.assertIn("27888999", body)
        r = self.client.get(reverse("becas:proceso_masivo", args=[self.ps.pk]))
        print("[SEC-06] pantalla proceso masivo:", r.status_code)
        self.assertEqual(r.status_code, 200)

    def test_coordinador_sin_admin_no_exporta(self):
        """Contraste para la observacion de A4: un Coordinador (sin becas.programa.administrar) NO baja el CSV."""
        rol = _rol("Coord Becas", ["becas.segmento.ver", "becas.relevamiento.ver"], programa=self.becas)
        c = User.objects.create_user("coord", password="x")
        c.groups.add(rol)
        self.client.force_login(c)
        r = self.client.get(reverse("becas:convocatoria_export_beneficiarios", args=[self.conv.pk]))
        print("\n[SEC-06] coordinador sin admin, export:", r.status_code, r.get("Location"))
        self.assertNotEqual(r.status_code, 200)


class SEC07ProgramaConfigurarTests(TestCase):
    """A5-07: admin de roles de Becas se otorga programa.configurar y edita Dispositivos."""

    def test_escalada(self):
        becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        otro = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        rol = _rol("Admin Becas", ["programa.usuario.administrar", "programa.rol.administrar"], programa=becas)
        u = User.objects.create_user("adm", password="x")
        u.groups.add(rol)
        User.objects.create_superuser("root", "r@x.com", "x")
        self.client.force_login(u)
        self.client.post(
            reverse("users:rol_crear"),
            {
                "name": "Escalada",
                "descripcion": "",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(becas.pk),
                "capacidades": ["programa.configurar"],
            },
        )
        g = Group.objects.get(name="Escalada")
        u.groups.add(g)
        u = User.objects.get(pk=u.pk)
        self.client.force_login(u)
        r = self.client.get(reverse("configuracion:programa_editar_paso1", args=[otro.pk]))
        print("\n[SEC-07] caps rol:", rbac.capacidades_de_grupo(g), "editar Dispositivos:", r.status_code)
        self.assertEqual(r.status_code, 200)


class SEC08XssRolTests(TestCase):
    """A5-08: nombre de rol en <script> de base.html."""

    def test_nombre_de_rol_rompe_script(self):
        g = _rol("Op</script><script>alert(document.domain)</script>", ["dashboard.ver"])
        u = User.objects.create_user("victima", password="x")
        u.groups.add(g)
        self.client.force_login(u)
        html = self.client.get(reverse("core:inicio")).content.decode()
        i = html.find("window.userGroups")
        print("\n[SEC-08]", html[i : i + 90])
        self.assertIn("<script>alert(document.domain)</script>", html)

    def test_apostrofe_rompe_el_js_de_todas_las_paginas(self):
        g = _rol("Rol d'Ejemplo", ["dashboard.ver"])
        u = User.objects.create_user("v2", password="x")
        u.groups.add(g)
        self.client.force_login(u)
        html = self.client.get(reverse("core:inicio")).content.decode()
        i = html.find("window.userGroups")
        print("\n[SEC-08] apostrofe:", html[i : i + 60])
        self.assertIn('["Rol d"Ejemplo"]', html)


class SEC10AdjuntosTests(TestCase):
    """A5-10 / A3-03: listar/borrar adjuntos sin capacidad ni pertenencia."""

    def test_borra_adjunto_ajeno(self):
        ct = ContentType.objects.get_for_model(Ciudadano)
        adj = Adjunto.objects.create(
            content_type=ct, object_id=uuid.uuid4(), archivo=SimpleUploadedFile("dni.pdf", b"%PDF-1"), etiqueta="DNI"
        )
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        r = self.client.delete(reverse("legajos:eliminar_archivo", args=[adj.pk]))
        print("\n[SEC-10] DELETE adjunto ajeno sin capacidades:", r.status_code, r.content)
        self.assertFalse(Adjunto.objects.filter(pk=adj.pk).exists())


class SEC11LegajosJsonTests(TestCase):
    """A5-11: APIs JSON de legajos sin capacidad."""

    def test_sin_capacidades(self):
        ciu = Ciudadano.objects.create(dni="20111222", nombre="X", apellido="Y")
        AlertaCiudadano.objects.create(ciudadano=ciu, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="riesgo")
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        for name in ("timeline_ciudadano", "alertas_ciudadano", "prediccion_riesgo", "actividades_ciudadano"):
            r = self.client.get(reverse(f"legajos:{name}", args=[ciu.pk]))
            print(f"\n[SEC-11] {name}:", r.status_code, r.content[:110])
            self.assertEqual(r.status_code, 200)
        r = self.client.get(reverse("legajos:alertas_dashboard"))
        print("[SEC-11] alertas_dashboard (fallback CRITICA):", r.status_code, "riesgo" in r.content.decode())


class SEC12DerivacionGetTests(TestCase):
    """A5-12 / A3-04: aceptar derivacion por GET y sin capacidad."""

    def test_get_acepta(self):
        prog = Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos")
        ciu = Ciudadano.objects.create(dni="20999111", nombre="D", apellido="E")
        d = DerivacionPrograma.objects.create(ciudadano=ciu, programa_destino=prog, motivo="m")
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        r = self.client.get(reverse("legajos:derivacion_ciudadano_aceptar", args=[d.pk]))
        d.refresh_from_db()
        existe = InscripcionPrograma.objects.filter(ciudadano=ciu, programa=prog).exists()
        print("\n[SEC-12] GET aceptar sin capacidad:", r.status_code, d.estado, "inscripcion creada:", existe)
        self.assertNotEqual(d.estado, "PENDIENTE")


class SEC14DashboardApiTests(TestCase):
    """A5-14: buscar-ciudadanos para usuario sin ciudadano.ver."""

    def test_enumeracion(self):
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Perez")
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        r = self.client.get("/api/buscar-ciudadanos/?q=301")
        print("\n[SEC-14]", r.status_code, r.content[:120])
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"30111222", r.content)


class SEC15UploadsTests(TestCase):
    """A3-08 / A5-29: documentacion de merendero acepta .html."""

    def test_merendero_acepta_html(self):
        from programas.forms import SolicitudMerenderoForm

        f = SolicitudMerenderoForm(
            data={"codigo": "", "nombre": "M"},
            files={"documentacion": SimpleUploadedFile("x.html", b"<script>alert(1)</script>", "text/html")},
            validar_completitud=False,
        )
        ok = f.is_valid()
        print("\n[SEC-15] SolicitudMerenderoForm con .html valido:", ok, f.errors.get("documentacion"))
        self.assertNotIn("documentacion", f.errors)


class SEC09MediaTests(TestCase):
    """A5-09 (camino Django, SERVE_MEDIA=True): ciudadano del portal baja /media/."""

    def test_ciudadano_portal_descarga_media(self):
        from django.conf import settings

        if not settings.SERVE_MEDIA:
            self.skipTest("correr con SERVE_MEDIA=True")
        import os

        os.makedirs(os.path.join(settings.MEDIA_ROOT, "adjuntos"), exist_ok=True)
        with open(os.path.join(settings.MEDIA_ROOT, "adjuntos", "poc_dni.pdf"), "wb") as fh:
            fh.write(b"%PDF-secreto")
        g, _ = Group.objects.get_or_create(name="Ciudadanos")
        c = User.objects.create_user("ciud", password="x")
        c.groups.add(g)
        r = self.client.get("/media/adjuntos/poc_dni.pdf")
        print("\n[SEC-09] anonimo:", r.status_code)
        self.client.force_login(c)
        r = self.client.get("/media/adjuntos/poc_dni.pdf")
        body = b"".join(r.streaming_content) if r.streaming else r.content
        print("[SEC-09] ciudadano portal:", r.status_code, body[:20])
        self.assertEqual(r.status_code, 200)


class SEC13GeoApiTests(TestCase):
    def test_borra_provincia(self):
        from core.models import Provincia

        p = Provincia.objects.create(nombre="Borrable")
        u = User.objects.create_user("plano", password="x")
        c = APIClient()
        c.force_authenticate(u)
        r = c.delete(f"/api/core/provincias/{p.pk}/")
        print("\n[SEC-13] DELETE provincia sin capacidad:", r.status_code)
        self.assertEqual(r.status_code, 204)


class SEC16UsersApiListTests(TestCase):
    def test_lista_personal(self):
        User.objects.create_superuser("root", "r@x.com", "x")
        u = User.objects.create_user("plano", password="x")
        c = APIClient()
        c.force_authenticate(u)
        r = c.get("/api/users/users/?is_staff=true")
        print("\n[SEC-16] lista usuarios staff:", r.status_code, r.content[:150])
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"is_superuser", r.content)


class SEC17RenombrarCiudadanosTests(TestCase):
    """A5-17: rol.administrar renombra el grupo Ciudadanos por API -> el ciudadano entra al backoffice."""

    def test_renombrar_ciudadanos(self):
        g, _ = Group.objects.get_or_create(name="Ciudadanos")
        RolMeta.objects.create(grupo=g, categoria=rbac.CATEGORIA_PORTAL, activo=True, protegido=True)
        admin = User.objects.create_user("adm-roles", password="x")
        admin.groups.add(_rol("Admin Roles", ["rol.administrar"]))
        c = APIClient()
        c.force_authenticate(admin)
        r = c.patch(f"/api/users/groups/{g.pk}/", {"name": "Ciudadanos2"}, format="json")
        g.refresh_from_db()
        print("\n[SEC-17] PATCH rol protegido Ciudadanos:", r.status_code, g.name)
        self.assertEqual(g.name, "Ciudadanos2")


class SEC18DebugXssTests(TestCase):
    """A5-19 / A3-14: /legajos/alertas/debug/ arma HTML sin escapar."""

    def test_debug_alertas(self):
        ciu = Ciudadano.objects.create(dni="20111333", nombre="<img src=x onerror=alert(1)>", apellido="Z")
        AlertaCiudadano.objects.create(ciudadano=ciu, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="m")
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        r = self.client.get(reverse("legajos:debug_alertas"))
        print("\n[SEC-18] debug_alertas:", r.status_code, "<img src=x onerror" in r.content.decode())
        self.assertIn("<img src=x onerror=alert(1)>", r.content.decode())
