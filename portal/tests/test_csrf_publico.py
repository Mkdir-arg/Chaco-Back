"""El 403 de CSRF del portal público tiene que ser recuperable.

Causa real (27/08/2026, producción): el backoffice y el portal comparten dominio
y `django.contrib.auth.login` rota la cookie CSRF de todo el navegador, así que
un formulario público abierto en otra pestaña se quedaba con un token viejo y el
envío moría en el 403 crudo de Django.
"""

import json
import uuid

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from config.views import _destino_seguro


class CsrfTokenVigenteTests(TestCase):
    def test_devuelve_un_token_y_no_se_cachea(self):
        respuesta = self.client.get(reverse("portal:csrf_token"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertTrue(json.loads(respuesta.content)["token"])

    def test_solo_responde_a_get(self):
        self.assertEqual(self.client.post(reverse("portal:csrf_token")).status_code, 405)

    def test_el_token_sirve_para_enviar_el_formulario(self):
        """Es el escenario de la pestaña que vuelve al frente: token nuevo, envío que pasa."""
        cliente = Client(enforce_csrf_checks=True)
        token = json.loads(cliente.get(reverse("portal:csrf_token")).content)["token"]
        url = reverse("portal:inscripcion_paso1", args=[uuid.uuid4()])

        respuesta = cliente.post(url, {"csrfmiddlewaretoken": token, "dni": "1", "sexo": "M"})

        # 404 = pasó CSRF y murió en el relevamiento inexistente, que es lo que se busca.
        self.assertEqual(respuesta.status_code, 404)


class CsrfFailurePortalTests(TestCase):
    def test_el_portal_muestra_la_pantalla_recuperable(self):
        cliente = Client(enforce_csrf_checks=True)
        url = reverse("portal:inscripcion_paso1", args=[uuid.uuid4()])

        respuesta = cliente.post(url, {"csrfmiddlewaretoken": "viejo", "dni": "1", "sexo": "M"})

        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, "portal/sesion_vencida.html")
        self.assertContains(respuesta, "Volver a cargar el formulario", status_code=403)
        self.assertContains(respuesta, url, status_code=403)

    def test_fuera_del_portal_se_conserva_la_pantalla_de_django(self):
        Usuario = get_user_model()
        Usuario.objects.create_user(username="csrf-test", password="x" * 12)
        cliente = Client(enforce_csrf_checks=True)

        respuesta = cliente.post("/login/", {"username": "csrf-test", "password": "x" * 12})

        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateNotUsed(respuesta, "portal/sesion_vencida.html")


class DestinoSeguroTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_conserva_la_ruta_propia(self):
        peticion = self.factory.post("/portal/inscripcion/x/?a=1")
        self.assertEqual(_destino_seguro(peticion), "/portal/inscripcion/x/?a=1")

    def test_una_ruta_que_es_una_url_absoluta_no_viaja_al_href(self):
        peticion = self.factory.post("//otro-dominio.example/portal/")
        self.assertEqual(_destino_seguro(peticion), "/portal/")
