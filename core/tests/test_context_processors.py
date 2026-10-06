"""Los context processors degradan, pero dejan rastro (RED-55).

`core.context_processors.sidebar_badges` y `conversaciones.context_processors.user_groups`
corren en el **100 % del tráfico autenticado** del backoffice y los dos envolvían su
trabajo en un `except Exception` mudo. El modo de falla medido por la auditoría no es
hipotético: un `OperationalError` de MariaDB por el `read_timeout` de 10 s se convierte
hoy en «badge 0» y en «usuario sin grupos» —el rol desaparece del sidebar— sin una sola
línea en ningún log. El usuario ve una pantalla rara, nadie ve por qué.

Lo que estos tests fijan es lo mínimo que pedía la ficha y nada más: **el render sigue
dando 200 y el contexto sigue degradando igual**, pero el fallo aparece en el log con su
traceback. Ensanchar esto a «que explote» sería cambiar lo que ve el usuario en el 100 %
del tráfico por un error que hoy es tolerado a propósito.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.utils import OperationalError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from conversaciones.context_processors import user_groups
from core.context_processors import sidebar_badges


class SidebarBadgesDegradacionTests(TestCase):
    """RED-55 (a): `core.context_processors.sidebar_badges`."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser("su-badges", "su@x.com", "x")

    def _request(self):
        request = self.factory.get("/inicio/")
        request.user = self.user
        return request

    def test_el_fallo_se_loguea(self):
        """El `OperationalError` que hoy se traga entero tiene que quedar escrito."""
        with patch(
            "conversaciones.selectors.get_conversaciones_pendientes_count",
            side_effect=OperationalError("read_timeout"),
        ):
            with self.assertLogs("core.context_processors", "ERROR") as registro:
                badges = sidebar_badges(self._request())

        self.assertEqual(badges, {"badge_conversaciones": 0}, "el badge sigue degradando a 0")
        self.assertIn("OperationalError", "\n".join(registro.output), "el traceback tiene que estar")

    def test_el_camino_feliz_no_loguea_nada(self):
        """Un log por request en el 100 % del tráfico sería el bug de al lado."""
        with patch("conversaciones.selectors.get_conversaciones_pendientes_count", return_value=7):
            with self.assertNoLogs("core.context_processors", "ERROR"):
                badges = sidebar_badges(self._request())

        self.assertEqual(badges["badge_conversaciones"], 7)

    def test_el_anonimo_no_toca_la_base(self):
        request = self.factory.get("/inicio/")
        request.user = None

        self.assertEqual(sidebar_badges(request), {})


class UserGroupsDegradacionTests(TestCase):
    """RED-55 (b): `conversaciones.context_processors.user_groups`."""

    def setUp(self):
        self.factory = RequestFactory()
        User.objects.create_superuser("su-grupos", "su@x.com", "x")

    def _request(self):
        request = self.factory.get("/inicio/")
        # Recién traído de la base: sin `_group_names_cache`, que es lo que hace que el
        # processor entre al `prefetch` en vez de responder con lo ya cacheado.
        request.user = User.objects.get(username="su-grupos")
        return request

    def test_el_fallo_se_loguea(self):
        with patch(
            "conversaciones.context_processors.prefetch_related_objects",
            side_effect=OperationalError("read_timeout"),
        ):
            with self.assertLogs("conversaciones.context_processors", "ERROR") as registro:
                contexto = user_groups(self._request())

        self.assertEqual(contexto["user_groups_list"], [], "sigue degradando a «sin grupos»")
        self.assertIsNone(contexto["user_primary_group"])
        self.assertIn("OperationalError", "\n".join(registro.output))

    def test_el_camino_feliz_no_loguea_nada(self):
        with self.assertNoLogs("conversaciones.context_processors", "ERROR"):
            contexto = user_groups(self._request())

        self.assertEqual(contexto["user_groups_list"], [])


class RenderDegradadoTests(TestCase):
    """Lo que ve el usuario no cambia: la pantalla sigue respondiendo 200."""

    def setUp(self):
        self.user = User.objects.create_superuser("su-render", "su@x.com", "x")
        self.client.force_login(self.user)

    def test_la_pantalla_sigue_en_200_con_el_contador_caido(self):
        with patch(
            "conversaciones.selectors.get_conversaciones_pendientes_count",
            side_effect=OperationalError("read_timeout"),
        ):
            with self.assertLogs("core.context_processors", "ERROR"):
                respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)
