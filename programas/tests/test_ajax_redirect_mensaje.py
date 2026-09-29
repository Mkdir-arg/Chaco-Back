"""ALR-5: el mensaje de «Guardar y configurar» llega a la pantalla destino.

``ajax_redirect`` responde ``{ok, redirect, message}`` y ``_ajax_js.html`` navega
a ``redirect`` sin mostrar ``message``: el aviso se perdía. Ahora el mensaje se
encola en el framework de messages de Django antes de responder, así que la
página destino lo muestra (``base.html`` → ``nodo-toast``) una sola vez y con
su nivel.
"""

import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AsignacionTerritorial,
    Convocatoria,
    PadronHabilitado,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    Subsegmento,
)
from programas.tests.test_relevamiento_publico import _dar_capacidad_publico
from programas.views.ajax_utils import ajax_redirect

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class _AjaxRedirectMensajeBase(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_alr5", password="x")
        grupo_admin = Group.objects.get(name=ROL_ADMIN)
        _dar_capacidad_publico(grupo_admin)
        self.admin.groups.add(grupo_admin)
        self.client.force_login(self.admin)

    def _post_ajax(self, url, data):
        resp = self.client.post(url, data, **AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        self.assertTrue(payload["ok"])
        # Contrato JSON intacto: el front sigue recibiendo redirect + message.
        self.assertIn("redirect", payload)
        self.assertIn("message", payload)
        return payload

    def _assert_llega_una_vez(self, payload, texto, nivel):
        """GET al destino: el mensaje está encolado una sola vez, con su nivel,
        y se imprime una sola vez en el contenedor que lee nodo-toast."""
        self.assertEqual(payload["message"], texto)
        resp = self.client.get(payload["redirect"])
        self.assertEqual(resp.status_code, 200)
        recibidos = [(m.level, str(m)) for m in resp.context["messages"]]
        self.assertEqual(recibidos, [(nivel, texto)])
        self.assertContains(resp, 'class="dj-message"', count=1)
        self.assertContains(resp, texto, count=1)
        # Consumido: no reaparece en la navegación siguiente.
        resp = self.client.get(payload["redirect"])
        self.assertEqual(list(resp.context["messages"]), [])


class ConfiguracionAjaxRedirectTests(_AjaxRedirectMensajeBase):
    def setUp(self):
        super().setUp()
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)

    def _coordinador(self):
        coord = User.objects.create_user("coord_alr5", password="x")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        return coord

    def test_crear_segmento_guardar_y_configurar(self):
        coord = self._coordinador()
        payload = self._post_ajax(
            reverse("becas:segmento_crear"),
            {
                "programa": self.programa.pk,
                "nombre": "Segmento ALR5",
                "descripcion": "Población objetivo",
                "cupo_maximo": 100,
                "coordinador": coord.pk,
            },
        )
        seg = Segmento.objects.get(nombre="Segmento ALR5")
        self.assertEqual(payload["redirect"], reverse("becas:segmento_detalle", args=[seg.pk]))
        self._assert_llega_una_vez(payload, "Segmento creado — agregá sus subsegmentos.", messages.SUCCESS)

    def test_crear_segmento_sin_ajax_sigue_igual(self):
        coord = self._coordinador()
        resp = self.client.post(
            reverse("becas:segmento_crear"),
            {
                "programa": self.programa.pk,
                "nombre": "Segmento ALR5",
                "descripcion": "Población objetivo",
                "cupo_maximo": 100,
                "coordinador": coord.pk,
            },
            follow=True,
        )
        recibidos = [(m.level, str(m)) for m in resp.context["messages"]]
        self.assertEqual(recibidos, [(messages.SUCCESS, "Segmento creado.")])

    def test_vincular_programa_guardar_y_configurar(self):
        with patch(
            "programas.forms.listar_programas",
            return_value=[{"id": 41, "nombre": "Turismo", "estado": "ACTIVO"}],
        ):
            payload = self._post_ajax(reverse("becas:programa_crear"), {"siis_programa_id": 41})
        programa = ProgramaSiis.objects.get(siis_programa_id=41)
        self.assertEqual(payload["redirect"], reverse("becas:programa_detalle", args=[programa.pk]))
        self._assert_llega_una_vez(payload, "Programa vinculado — agregá sus segmentos.", messages.SUCCESS)

    def test_editar_subsegmento_fuera_del_panel(self):
        seg = Segmento.objects.create(programa=self.programa, nombre="S", cupo_maximo=200)
        sub = Subsegmento.objects.create(segmento=seg, nombre="Ladrillo", cupo_maximo=50)
        payload = self._post_ajax(
            reverse("becas:subsegmento_editar", args=[sub.pk]),
            {"nombre": "Ladrillo hueco", "cupo_maximo": 60},
        )
        self.assertEqual(payload["redirect"], reverse("becas:subsegmento_detalle", args=[sub.pk]))
        self._assert_llega_una_vez(payload, "Subsegmento actualizado.", messages.SUCCESS)


class RelevamientoPublicoAjaxRedirectTests(_AjaxRedirectMensajeBase):
    def setUp(self):
        super().setUp()
        self.segmento = Segmento.objects.create(nombre="Segmento P", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv P",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        territorial = User.objects.create_user("terri_alr5", password="x")
        territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.segmento, territorial=territorial)

    def _form_publico(self):
        return {
            "tipo": Relevamiento.Tipo.PUBLICO,
            "convocatoria": self.convocatoria.pk,
            "fecha_asignada": "2026-06-01T08:00",
            "fecha_hasta": "2026-06-30T18:00",
            "cupo_maximo": 50,
        }

    def test_publico_sin_padron_viaja_como_advertencia(self):
        payload = self._post_ajax(reverse("becas:relevamiento_crear"), self._form_publico())
        rel = Relevamiento.objects.get(tipo=Relevamiento.Tipo.PUBLICO)
        self.assertEqual(payload["redirect"], reverse("becas:relevamiento_detalle", kwargs={"pk": rel.pk}))
        self._assert_llega_una_vez(
            payload,
            "Relevamiento público creado. Compartí el link de inscripción. "
            "La convocatoria no tiene padrón: el link queda abierto.",
            messages.WARNING,
        )

    def test_publico_con_padron_viaja_como_exito(self):
        PadronHabilitado.objects.create(convocatoria=self.convocatoria, dni="30111222", sexo="F")
        payload = self._post_ajax(reverse("becas:relevamiento_crear"), self._form_publico())
        self._assert_llega_una_vez(
            payload,
            "Relevamiento público creado. Compartí el link de inscripción.",
            messages.SUCCESS,
        )


class AjaxRedirectHelperTests(TestCase):
    def test_nivel_por_defecto_es_exito_y_json_sin_cambios(self):
        request = RequestFactory().post("/x/")
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        resp = ajax_redirect(request, "/destino/", "Listo.")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), {"ok": True, "redirect": "/destino/", "message": "Listo."})
        self.assertEqual([(m.level, str(m)) for m in request._messages], [(messages.SUCCESS, "Listo.")])
