"""El botón «Copiar DNI» no interpola el DNI en un onclick (Cambio 95).

El modelo no restringe el DNI a dígitos y la API de campo lo acepta tal cual llega
en ``datos_identificacion``: dentro de ``onclick="copiarDni('...')"`` una comilla en
el valor cerraba el literal JS. El DNI viaja en ``data-copiar-dni``.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de
from legajos.models import Ciudadano

DNI_QUE_CIERRA_EL_LITERAL = "1',window.__x=1,'"


class CopiarDniHandlerInlineTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-dni-xss", password="x")
        self.ciudadano = Ciudadano.objects.create(
            dni=DNI_QUE_CIERRA_EL_LITERAL, nombre="Ana", apellido="Paz", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )

    def test_el_dni_viaja_en_data_y_no_en_un_handler_on(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.ciudadano.pk]))
        self.assertEqual(response.status_code, 200)

        elementos = atributos_de(response.content.decode())
        for tag, attrs in elementos:
            for nombre_attr, valor in attrs.items():
                if nombre_attr.startswith("on"):
                    self.assertNotIn(DNI_QUE_CIERRA_EL_LITERAL, valor, f"<{tag} {nombre_attr}> interpola el DNI")
        self.assertIn(DNI_QUE_CIERRA_EL_LITERAL, [attrs.get("data-copiar-dni") for _, attrs in elementos])
