"""Los context processors degradan, pero dejan rastro (RED-55).

`core.context_processors.identidad_usuario` corre en el **100 % del tráfico
autenticado** del backoffice y envolvía su trabajo en un `except Exception` mudo. El
modo de falla medido por la auditoría no es hipotético: un `OperationalError` de MariaDB
por el `read_timeout` de 10 s se convertía en «usuario sin grupos» —el rol desaparece
del sidebar— sin una sola línea en ningún log. El usuario ve una pantalla rara, nadie ve
por qué.

Lo que estos tests fijan es lo mínimo que pedía la ficha y nada más: **el render sigue
dando 200 y el contexto sigue degradando igual**, pero el fallo aparece en el log con su
traceback. Ensanchar esto a «que explote» sería cambiar lo que ve el usuario en el 100 %
del tráfico por un error que hoy es tolerado a propósito.

Dos cambios respecto de cómo entró RED-55:

- el processor se llamaba `conversaciones.context_processors.user_groups` y se mudó a
  `core` con RED-13: cuatro de sus variables son del shell, no de esa app;
- la otra mitad de RED-55, `sidebar_badges`, contaba las conversaciones sin asignar.
  Con la app apagada (G1-01 fase 2) ya no cuenta nada y no consulta la base, así que no
  hay nada que degradar: queda el test que lo afirma.
"""

from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.db.utils import OperationalError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.context_processors import identidad_usuario, sidebar_badges


class SidebarBadgesTests(TestCase):
    """RED-55 (a) + G1-01 fase 2: el único badge era el de conversaciones."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser("su-badges", "su@x.com", "x")

    def _request(self):
        request = self.factory.get("/inicio/")
        request.user = self.user
        return request

    def test_no_queda_ningun_badge_ni_consulta(self):
        """Un superusuario ve todo lo que haya: no hay nada, y no se toca la base."""
        with self.assertNumQueries(0):
            badges = sidebar_badges(self._request())

        self.assertEqual(badges, {})

    def test_el_anonimo_tampoco(self):
        request = self.factory.get("/inicio/")
        request.user = None

        self.assertEqual(sidebar_badges(request), {})


class IdentidadUsuarioDegradacionTests(TestCase):
    """RED-55 (b): `core.context_processors.identidad_usuario`."""

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
            "core.context_processors.prefetch_related_objects",
            side_effect=OperationalError("read_timeout"),
        ):
            with self.assertLogs("core.context_processors", "ERROR") as registro:
                contexto = identidad_usuario(self._request())

        self.assertEqual(contexto["user_groups_list"], [], "sigue degradando a «sin grupos»")
        self.assertIsNone(contexto["user_primary_group"])
        self.assertIn("OperationalError", "\n".join(registro.output))

    def test_el_camino_feliz_no_loguea_nada(self):
        with self.assertNoLogs("core.context_processors", "ERROR"):
            contexto = identidad_usuario(self._request())

        self.assertEqual(contexto["user_groups_list"], [])

    def test_el_anonimo_recibe_las_mismas_claves(self):
        """El shell lee estas variables sin `{% if %}`: el anónimo no puede traer menos."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/portal/")
        request.user = AnonymousUser()

        contexto = identidad_usuario(request)

        self.assertEqual(
            set(contexto),
            {
                "user_groups_list",
                "user_primary_group",
                "user_is_superuser",
                "websockets_enabled",
                "puede_alertas_sensibles",
            },
        )
        self.assertFalse(contexto["user_is_superuser"])
        self.assertFalse(contexto["puede_alertas_sensibles"])


class RenderDegradadoTests(TestCase):
    """Lo que ve el usuario no cambia: la pantalla sigue respondiendo 200."""

    def setUp(self):
        self.user = User.objects.create_superuser("su-render", "su@x.com", "x")
        self.client.force_login(self.user)

    def test_la_pantalla_sigue_en_200_con_los_grupos_caidos(self):
        # Se pisa el `rbac` **que ve el processor**, no `core.rbac`: en un request de
        # verdad el middleware ya consultó los grupos (y dejó puesto el
        # `_group_names_cache`, así que el `prefetch` del processor ni se ejecuta).
        # Romper `core.rbac` entero mediría el middleware, no esto.
        rbac_roto = Mock()
        rbac_roto.nombres_de_grupos.side_effect = OperationalError("read_timeout")
        rbac_roto.puede.return_value = False

        with patch("core.context_processors.rbac", rbac_roto):
            with self.assertLogs("core.context_processors", "ERROR"):
                respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)
