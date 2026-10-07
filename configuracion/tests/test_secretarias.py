"""Borrado de secretarías y subsecretarías: la jerarquía no se puede romper (TST-02).

`configuracion/views/secretaria.py` borra filas de las que cuelga todo el árbol
organizacional (Secretaría → Subsecretaría → Programa) y no tenía ningún test. El
camino interesante es el `ProtectedError`: la FK es `PROTECT`, así que borrar una
secretaría con subsecretarías **no explota** sino que avisa… siempre que el `except`
siga ahí. Sin test, cambiarlo por un `delete()` pelado da 500 en producción y, si
alguien "arreglara" el 500 pasando la FK a `CASCADE`, un clic se llevaría puesta la
mitad del organigrama sin confirmación.

También se afirma el piso de capacidad (`config.administrar`) en las cuatro rutas de
borrado y listado, que es lo que SEC-07 va a mover.
"""

from django.test import TestCase
from django.urls import reverse

from configuracion.tests.test_configuracion_ola5 import usuario_con
from core.models import Secretaria, Subsecretaria
from programas.models import Programa


class BorradoDeSecretariaTests(TestCase):
    def setUp(self):
        self.operador = usuario_con("config.administrar", username="cfg-secretarias")
        self.client.force_login(self.operador)
        self.secretaria = Secretaria.objects.create(nombre="Secretaría de Desarrollo")

    def _mensajes(self, respuesta):
        return [str(m) for m in respuesta.context["messages"]]

    def test_una_secretaria_con_subsecretarias_no_se_borra_y_avisa(self):
        Subsecretaria.objects.create(nombre="Subsecretaría de Niñez", secretaria=self.secretaria)

        respuesta = self.client.post(
            reverse("configuracion:secretaria_eliminar", args=[self.secretaria.pk]), follow=True
        )

        self.assertTrue(Secretaria.objects.filter(pk=self.secretaria.pk).exists())
        self.assertIn(
            "No se puede eliminar esta secretaría porque tiene subsecretarías asociadas.",
            self._mensajes(respuesta),
        )

    def test_una_secretaria_sin_subsecretarias_si_se_borra(self):
        """Control: el freno de arriba es por la FK, no porque el borrado nunca ande."""
        respuesta = self.client.post(
            reverse("configuracion:secretaria_eliminar", args=[self.secretaria.pk]), follow=True
        )

        self.assertFalse(Secretaria.objects.filter(pk=self.secretaria.pk).exists())
        self.assertIn('Secretaría "Secretaría de Desarrollo" eliminada.', self._mensajes(respuesta))

    def test_una_subsecretaria_con_programas_no_se_borra_y_avisa(self):
        sub = Subsecretaria.objects.create(nombre="Subsecretaría de Niñez", secretaria=self.secretaria)
        Programa.objects.create(codigo="PROG-SUB", nombre="Programa colgado", subsecretaria=sub)

        respuesta = self.client.post(reverse("configuracion:subsecretaria_eliminar", args=[sub.pk]), follow=True)

        self.assertTrue(Subsecretaria.objects.filter(pk=sub.pk).exists())
        self.assertIn(
            "No se puede eliminar esta subsecretaría porque tiene programas asociados.",
            self._mensajes(respuesta),
        )

    def test_una_subsecretaria_sin_programas_si_se_borra(self):
        sub = Subsecretaria.objects.create(nombre="Subsecretaría vacía", secretaria=self.secretaria)

        self.client.post(reverse("configuracion:subsecretaria_eliminar", args=[sub.pk]), follow=True)

        self.assertFalse(Subsecretaria.objects.filter(pk=sub.pk).exists())

    def test_sin_config_administrar_no_se_borra_nada(self):
        sub = Subsecretaria.objects.create(nombre="Subsecretaría protegida", secretaria=self.secretaria)
        self.client.force_login(usuario_con(username="cfg-secretarias-sin-rol"))

        rutas = (
            ("configuracion:secretaria_eliminar", self.secretaria.pk),
            ("configuracion:subsecretaria_eliminar", sub.pk),
        )
        for nombre, pk in rutas:
            with self.subTest(ruta=nombre):
                respuesta = self.client.post(reverse(nombre, args=[pk]))

                self.assertEqual(respuesta.status_code, 302)

        self.assertTrue(Secretaria.objects.filter(pk=self.secretaria.pk).exists())
        self.assertTrue(Subsecretaria.objects.filter(pk=sub.pk).exists())

    def test_un_anonimo_no_borra_ni_lista(self):
        sub = Subsecretaria.objects.create(nombre="Subsecretaría anónima", secretaria=self.secretaria)
        self.client.logout()

        rutas = (
            ("configuracion:secretarias", ()),
            ("configuracion:subsecretarias", ()),
            ("configuracion:secretaria_eliminar", (self.secretaria.pk,)),
            ("configuracion:subsecretaria_eliminar", (sub.pk,)),
        )
        for nombre, args in rutas:
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.post(reverse(nombre, args=args)).status_code, 302)

        self.assertTrue(Secretaria.objects.filter(pk=self.secretaria.pk).exists())
        self.assertTrue(Subsecretaria.objects.filter(pk=sub.pk).exists())
