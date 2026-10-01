import json
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

USER_GROUPS_SCRIPT = re.compile(
    r'<script id="user-groups-data" type="application/json">(?P<contenido>.*?)</script>',
    re.DOTALL,
)


class NombreDeRolEnBaseTemplateTests(TestCase):
    """SEC-08 (auditoría oct-2026): el nombre de un rol no puede romper ni inyectar el <script> de base.html."""

    def _html_de_inicio_con_rol(self, nombre_rol):
        user = get_user_model().objects.create_user(username="usuario-rol-xss", password="secret")
        user.groups.add(Group.objects.create(name=nombre_rol))
        self.client.force_login(user)

        response = self.client.get("/inicio/")

        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_nombre_de_rol_no_rompe_script(self):
        nombre = "Op</script><script>alert(1)</script>"

        html = self._html_de_inicio_con_rol(nombre)

        self.assertNotIn("</script><script>alert(1)", html)
        datos = USER_GROUPS_SCRIPT.search(html)
        self.assertIsNotNone(datos, "base.html debe exponer los grupos con json_script")
        self.assertEqual(json.loads(datos.group("contenido")), [nombre])

    def test_apostrofe_en_nombre_de_rol(self):
        nombre = "Rol d'Ejemplo"

        html = self._html_de_inicio_con_rol(nombre)

        self.assertNotIn('"Rol d"Ejemplo"', html)
        datos = USER_GROUPS_SCRIPT.search(html)
        self.assertIsNotNone(datos, "base.html debe exponer los grupos con json_script")
        self.assertEqual(json.loads(datos.group("contenido")), [nombre])
