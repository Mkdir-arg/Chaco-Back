"""SEC-19 (auditoría oct-2026): las rutas de debug/prueba de legajos no existen.

`/legajos/alertas/debug/` armaba el HTML con f-strings y devolvía sin escapar el
nombre del ciudadano, el mensaje de la alerta, el username y los nombres de grupo:
un ciudadano llamado `<img src=x onerror=alert(1)>` era XSS almacenado para
cualquier usuario logueado, incluso sin roles.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from legajos.models import AlertaCiudadano, Ciudadano

PAYLOAD_XSS = "<img src=x onerror=alert(1)>"

NOMBRES_DESMONTADOS = (
    "legajos:debug_alertas",
    "legajos:test_alertas",
    "legajos:test_contactos",
    "legajos:test_api",
)

RUTAS_DESMONTADAS = (
    "/legajos/alertas/debug/",
    "/legajos/alertas/test/",
    "/legajos/test-contactos/",
    "/legajos/test-api/",
)


class RutasDebugDesmontadasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="sin-roles", password="secret")
        self.client.force_login(self.usuario)

    def test_rutas_de_debug_no_existen(self):
        """Ninguno de los cuatro nombres de URL resuelve."""
        for nombre in NOMBRES_DESMONTADOS:
            with self.subTest(nombre=nombre), self.assertRaises(NoReverseMatch):
                reverse(nombre)

    def test_las_urls_de_debug_devuelven_404(self):
        for ruta in RUTAS_DESMONTADAS:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_el_nombre_del_ciudadano_no_vuelve_sin_escapar(self):
        """El sink de XSS almacenado se fue con la vista."""
        ciudadano = Ciudadano.objects.create(dni="20111333", nombre=PAYLOAD_XSS, apellido="Z")
        AlertaCiudadano.objects.create(
            ciudadano=ciudadano,
            tipo="RIESGO_SUICIDA",
            prioridad="CRITICA",
            mensaje="mensaje de la alerta",
        )

        response = self.client.get("/legajos/alertas/debug/")

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(PAYLOAD_XSS, response.content.decode())
