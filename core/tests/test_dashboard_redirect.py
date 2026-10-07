from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse


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
    """`/` es el login, y lo es solo por el orden de `config/urls.py` (RED-78).

    `dashboard.views.home.DashboardView` es una copia vieja del inicio: montada en
    `/` por `dashboard/urls.py`, calcula contadores **globales** (usuarios,
    ciudadanos, legajos, alertas) y no tiene el gate por capacidad que SEC-14 le puso
    a `core.views.public.inicio_view`. Está muerta por un solo motivo: en
    `config/urls.py` el include de `users.urls` va antes que el de `dashboard.urls`,
    y gana el primero que matchea.

    El comentario «Root paths last» de ese archivo invita justamente a reordenar.
    Mover una línea deja `/` en manos de `DashboardView` y nadie se entera: la
    pantalla carga, con los números de todo el organismo a la vista de cualquiera
    que esté logueado.

    El borrado de `DashboardView` es de la Ola 7 (con OPS-14); hasta entonces, esto.
    """

    def test_la_raiz_es_el_login(self):
        self.assertEqual(resolve("/").view_name, "users:login")

    def test_dashboard_inicio_sigue_apuntando_a_la_raiz(self):
        """La otra mitad del hallazgo: la vista no está en una ruta propia, está
        tapada. Si alguna vez se la monta en `/dashboard-viejo/`, este test cae y
        hay que volver a mirar si sigue sin el gate de SEC-14."""
        self.assertEqual(reverse("dashboard:inicio"), "/")

    def test_la_vista_tapada_no_tiene_el_gate_de_capacidad(self):
        """Lo que vuelve grave al reordenamiento. `inicio_view` filtra su contexto
        por capacidad (SEC-14); `DashboardView` solo exige estar autenticado.

        Si alguna vez `DashboardView` **sí** tuviera el gate, este test se pone rojo:
        es la señal de que el riesgo de RED-78 se achicó y hay que actualizar la ficha.
        """
        from django.contrib.auth.mixins import LoginRequiredMixin

        from dashboard.views.home import DashboardView

        self.assertEqual(DashboardView.__mro__[1], LoginRequiredMixin)
        self.assertFalse(hasattr(DashboardView, "capacidad_requerida"))
