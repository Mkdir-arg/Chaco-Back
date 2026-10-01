r"""Reproducciones de datos y operación (verificación V6, pasada 2).

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
  Copy-Item <este archivo> programas/tests/test_repro_datos_operacion.py
  & $env:PY manage.py test programas.tests.test_repro_datos_operacion -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  A801CascadeTests                               -> DAT-01
  A804LoggingTests                               -> OPS-03
  A805HealthTests                                -> OPS-04
"""

import logging
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import resolve, reverse

from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    DisenoFormulario,
    EnvioSIIS,
    Formulario,
    ItemDiseno,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)


class A801CascadeTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.su = User.objects.create_superuser("su", "su@x.com", "x")
        self.client.force_login(self.su)
        self.seg = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.su,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.form = Formulario.objects.create(relevamiento=self.rel, celular="1", data={"globales": {}})

    def test_pregunta_eliminar_borra_adjuntos_e_items(self):
        preg = PreguntaGlobal.objects.create(texto="Certificado alumno regular", tipo=TipoCampo.ARCHIVO, activo=True)
        adj = AdjuntoFormulario.objects.create(
            formulario=self.form, pregunta_global=preg, archivo=SimpleUploadedFile("c.pdf", b"%PDF", "application/pdf")
        )
        diseno = DisenoFormulario.objects.create(convocatoria=self.conv)
        item = ItemDiseno.objects.create(
            diseno=diseno, tipo=ItemDiseno.Tipo.CAMPO, clave=f"pg-{preg.pk}", pregunta=preg
        )
        self.form.data = {"globales": {str(preg.pk): {"archivo_adjunto": True}}}
        self.form.save(update_fields=["data"])
        nombre = adj.archivo.name
        storage = adj.archivo.storage

        resp = self.client.post(reverse("becas:pregunta_eliminar", args=[preg.pk]))
        print("\n[A8-01 pregunta] status", resp.status_code)
        print("[A8-01 pregunta] adjunto existe:", AdjuntoFormulario.objects.filter(pk=adj.pk).exists())
        print("[A8-01 pregunta] item diseno existe:", ItemDiseno.objects.filter(pk=item.pk).exists())
        print("[A8-01 pregunta] archivo en storage:", storage.exists(nombre), nombre)
        self.form.refresh_from_db()
        print("[A8-01 pregunta] data residual:", self.form.data)
        self.assertFalse(AdjuntoFormulario.objects.filter(pk=adj.pk).exists())
        self.assertTrue(storage.exists(nombre))
        storage.delete(nombre)

    def test_requisito_eliminar_borra_adjuntos(self):
        req = RequisitoNativo.objects.create(texto="Constancia", tipo=TipoCampo.ARCHIVO, segmento=self.seg)
        adj = AdjuntoFormulario.objects.create(
            formulario=self.form, requisito_nativo=req, archivo=SimpleUploadedFile("k.pdf", b"%PDF", "application/pdf")
        )
        EnvioSIIS_count = EnvioSIIS.objects.count()
        resp = self.client.post(reverse("becas:requisito_eliminar", args=[req.pk]))
        print("\n[A8-01 requisito] status", resp.status_code, "EnvioSIIS", EnvioSIIS_count)
        print("[A8-01 requisito] adjunto existe:", AdjuntoFormulario.objects.filter(pk=adj.pk).exists())
        self.assertFalse(AdjuntoFormulario.objects.filter(pk=adj.pk).exists())
        adj.archivo.storage.delete(adj.archivo.name)

    def test_get_no_borra(self):
        preg = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.ARCHIVO, activo=True)
        self.client.get(reverse("becas:pregunta_eliminar", args=[preg.pk]))
        self.assertTrue(PreguntaGlobal.objects.filter(pk=preg.pk).exists())


class A804LoggingTests(TestCase):
    def test_config_django_request(self):
        cfg = settings.LOGGING["loggers"].get("django.request")
        print("\n[A8-04] django.request cfg:", cfg)
        print("[A8-04] root:", settings.LOGGING.get("root"))
        print("[A8-04] handlers:", {k: v.get("class") for k, v in settings.LOGGING["handlers"].items()})
        lg = logging.getLogger("django.request")
        print("[A8-04] runtime handlers:", lg.handlers, "propagate", lg.propagate)


class A805HealthTests(TestCase):
    def test_health_resuelve_a_basic(self):
        m = resolve("/health/")
        print("\n[A8-05] /health/ ->", m.func.__module__, m.func.__name__, m.url_name, m.namespace)
        from unittest.mock import patch

        from django.db import connection
        from django.db.utils import OperationalError

        with (
            patch.object(connection, "ensure_connection", side_effect=OperationalError("down")),
            patch.object(connection, "cursor", side_effect=OperationalError("down")),
        ):
            r = self.client.get("/health/")
        print("[A8-05] con DB caida ->", r.status_code, r.content[:40])
