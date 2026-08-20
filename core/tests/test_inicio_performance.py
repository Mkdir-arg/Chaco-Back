from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from core.views.public import inicio_view


class InicioPerformanceTests(TestCase):
    def test_reutiliza_el_conteo_de_seguimientos_en_el_contexto(self):
        request = RequestFactory().get("/inicio/")
        request.user = get_user_model().objects.create_user(username="inicio-performance")

        with (
            patch("core.views.public.contar_seguimientos_hoy", return_value=7) as contar_seguimientos,
            patch("core.views.public.render", return_value=HttpResponse()) as renderizar,
        ):
            inicio_view.__wrapped__(request)

        contexto = renderizar.call_args.args[2]
        contar_seguimientos.assert_called_once_with()
        self.assertEqual(contexto["actividad_hoy"], 7)
        self.assertEqual(contexto["seguimientos_hoy"], 7)

    def test_inicio_difiere_chartjs_hasta_que_el_grafico_este_cerca_del_viewport(self):
        user = get_user_model().objects.create_user(username="inicio-chart", password="secret")
        self.client.force_login(user)

        response = self.client.get("/inicio/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', html)
        self.assertIn("function cargarChartJs()", html)
        self.assertIn("IntersectionObserver", html)

    def test_sidebar_renderiza_las_opciones_una_sola_vez(self):
        sidebar = Path(settings.BASE_DIR, "templates", "includes", "sidebar", "base.html").read_text(
            encoding="utf-8"
        )

        self.assertEqual(sidebar.count("{% include 'includes/sidebar/opciones.html' %}"), 1)
        self.assertIn("Sidebar única", sidebar)
