"""La baja del detalle de programa se retiró entera (LEG-06, Ola 7).

**Historia.** El Cambio 95 arregló acá un XSS: `confirmarBaja` metía el nombre del
ciudadano crudo en el `html` de SweetAlert2, que esta pantalla sí carga, así que el
nombre se interpretaba como marcado. El arreglo quedó y este módulo lo vigilaba.

**Lo que midió la Ola 7.** Ese botón nunca sirvió para nada: posteaba a
`/legajos/acompanamiento/<id>/dar-de-baja/`, una ruta que **jamás estuvo en el
URLconf** (RED-42 lo encontró y lo dejó anotado en su allowlist), y además no llegaba
a dibujarse, porque `acompanamientos` es una lista vacía fija desde que se retiró
`models_institucional` (FE-16). O sea: la vulnerabilidad del Cambio 95 tampoco era
alcanzable. LEG-06 borró el botón, la función, el form oculto y la vista sin ruta
`dar_de_baja_inscripcion`.

El módulo sigue existiendo como **candado**: el día que alguien estrene la baja de
verdad —decisión del PM, no limpieza de deuda— estos tests se ponen rojos y obligan a
volver a mirar el escape antes de publicar la pantalla. `BajaProgramaService` sigue en
`legajos/services/programas.py`, con su test permanente de BEC-18.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from programas.models import Programa


class BajaRetiradaDelDetalleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-legajos-xss", password="x")
        self.programa = Programa.objects.create(codigo="XSS-1", nombre="Programa XSS", estado="ACTIVO")

    def _html(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("legajos:programa_detalle", args=[self.programa.pk]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_la_pantalla_ya_no_trae_el_boton_ni_su_handler(self):
        html = self._html()

        for marca in ("confirmarBaja", "form-dar-baja", "Dar de Baja"):
            with self.subTest(marca=marca):
                self.assertNotIn(marca, html)

    def test_la_pantalla_ya_no_postea_a_la_ruta_que_no_existe(self):
        """La URL a la que apuntaba el form sigue sin resolver, y nadie la escribe."""
        self.assertNotIn("dar-de-baja", self._html())

        with self.assertRaises(Resolver404):
            resolve("/legajos/acompanamiento/1/dar-de-baja/")

    def test_la_vista_sin_ruta_ya_no_esta_en_el_modulo(self):
        """Dejarla escrita es dejar la trampa armada para el próximo que rutee algo."""
        from legajos.views import programas as vistas

        self.assertFalse(hasattr(vistas, "dar_de_baja_inscripcion"))

    def test_la_confirmacion_que_si_vive_sigue_escapando_el_nombre(self):
        """Control del andamio: el patrón del Cambio 95 sigue puesto donde hace falta.

        El rechazo de derivación (SEC-12) usa el mismo `Swal.fire({html: ...})` con el
        nombre del ciudadano. Si este test se cayera, el módulo estaría verde por no
        mirar nada.
        """
        html = self._html()

        self.assertIn("js-rechazar-derivacion", html)
        self.assertIn("'&': '&amp;', '<': '&lt;', '>': '&gt;'", html)
