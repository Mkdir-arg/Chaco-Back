"""La confirmación de baja del detalle de programa muestra el nombre como texto (Cambio 95).

El ``onclick`` ya pasa el nombre con ``escapejs`` (el literal JS es seguro), pero
``confirmarBaja`` lo metía crudo en el ``html`` de SweetAlert2, que sí se carga en
esta pantalla: el nombre del ciudadano se interpretaba como marcado.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.js_harness import correr_script, requiere_node, script_con
from programas.models import Programa

NOMBRE_CON_MARCADO = '<img src=x onerror="window.__inyectado=1">'


class ConfirmarBajaNombreTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-legajos-xss", password="x")
        self.programa = Programa.objects.create(codigo="XSS-1", nombre="Programa XSS", estado="ACTIVO")

    def _script(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("legajos:programa_detalle", args=[self.programa.pk]))
        self.assertEqual(response.status_code, 200)
        return script_con(response.content.decode(), "function confirmarBaja")

    def test_no_interpola_el_nombre_crudo_en_el_html(self):
        self.assertNotIn("<strong>${nombreCiudadano}</strong>", self._script())

    @requiere_node
    def test_el_html_de_la_baja_muestra_el_nombre_como_texto(self):
        log = correr_script(self._script(), f"confirmarBaja(7, {json.dumps(NOMBRE_CON_MARCADO)});")

        (popup,) = log["swal"]
        self.assertNotIn("<img", popup["html"])
        self.assertIn("<strong>&lt;img src=x onerror=&quot;window.__inyectado=1&quot;&gt;</strong>", popup["html"])
        self.assertIn('id="swal-motivo"', popup["html"])
        self.assertEqual(popup["title"], "¿Dar de baja?")
