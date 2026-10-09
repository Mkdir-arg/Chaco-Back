import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse


class DashboardRedirectTests(TestCase):
    """`/dashboard/` es un alias histórico y tiene que llevar al inicio real.

    Resolvía `dashboard:inicio`, que está montado en la raíz junto al login: el
    reverse daba `/`, así que el usuario autenticado rebotaba por la pantalla de
    login en lugar de aterrizar en `/inicio/`.
    """

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dashboard_redirect",
            password="clave-de-prueba",
        )

    def test_usuario_autenticado_termina_en_inicio(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:dashboard"))

        # `fetch_redirect_response=False`: acá se valida el destino del redirect,
        # no que `/inicio/` renderice.
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)

    def test_el_destino_no_es_el_login(self):
        """La regresión concreta: el destino no puede volver a ser `/`."""
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:dashboard"))

        self.assertNotEqual(respuesta["Location"], reverse("users:login"))

    def test_usuario_anonimo_sigue_protegido(self):
        destino = reverse("core:dashboard")

        respuesta = self.client.get(destino)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], f"{reverse('users:login')}?next={destino}")


class RuteoRaizTests(TestCase):
    """`/` es el login, y ya no depende del orden de `config/urls.py` (RED-78).

    `dashboard.views.home.DashboardView` era una copia vieja del inicio del
    backoffice: montada en `/` por `dashboard/urls.py`, calculaba contadores
    **globales** (usuarios, ciudadanos, legajos, alertas) y no tenía el gate por
    capacidad que SEC-14 le puso a `core.views.public.inicio_view`. Estaba muerta por
    un solo motivo: en `config/urls.py` el include de `users.urls` va antes que el de
    `dashboard.urls`, y gana el primero que matchea. El comentario «Root paths last»
    de ese archivo invitaba justamente a reordenar, y mover una línea dejaba `/` en
    manos de esa vista sin que nadie se enterara.

    La Ola 7 la borró, con su template y su `path`. Lo que queda acá es la mitad que
    sigue valiendo (`/` es el login) más los dos tests que impiden que vuelva: el
    nombre `dashboard:inicio` ya no resuelve y el paquete `dashboard.views` no existe.
    """

    def test_la_raiz_es_el_login(self):
        self.assertEqual(resolve("/").view_name, "users:login")

    def test_dashboard_inicio_ya_no_existe(self):
        """La vista tapada se borró: su nombre de ruta no tiene a quién apuntar.

        Antes `reverse("dashboard:inicio")` daba `/` —la misma URL que el login—,
        que era la forma de ver que la vista estaba tapada y no montada aparte.
        """
        with self.assertRaises(NoReverseMatch):
            reverse("dashboard:inicio")

    def test_el_paquete_de_vistas_del_dashboard_no_esta(self):
        """El módulo entero se fue, no solo su `path`.

        Dejar la clase en el árbol sin ruta es exactamente el estado del que salió
        esta ficha: código que nadie ejecuta y que una línea vuelve a servir.
        """
        with self.assertRaises(ImportError):
            importlib.import_module("dashboard.views")

    def test_las_apis_del_dashboard_siguen_ruteadas(self):
        """Lo que **no** se borró: las cinco APIs de `dashboard/api_views` quedan.

        El hallazgo era la pantalla, no la app. Si este test se pone rojo, el borrado
        se llevó algo que el front sí usa.
        """
        for nombre, ruta in (
            ("dashboard:api_metricas", "/api/metricas/"),
            ("dashboard:api_buscar_ciudadanos", "/api/buscar-ciudadanos/"),
            ("dashboard:api_alertas_criticas", "/api/alertas-criticas/"),
            ("dashboard:api_actividad_reciente", "/api/actividad-reciente/"),
            ("dashboard:api_tendencias", "/api/tendencias/"),
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(reverse(nombre), ruta)
