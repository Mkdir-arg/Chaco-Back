"""Render de los reportes de Becas con las piezas del sistema (Ola 3, W3-P-K)."""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN


class ReportesRenderOla3Tests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-render-reportes", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)

    def test_hub_con_encabezado_e_iconos_distintos(self):
        html = self.client.get(reverse("becas:reportes")).content.decode()
        self.assertIn("<h1", html)
        for icono in ("fa-chart-pie", "fa-bars-progress", "fa-map-location-dot", "fa-filter", "fa-users"):
            self.assertIn(icono, html)

    def test_detalle_usa_botones_y_filtros_del_sistema(self):
        html = self.client.get(reverse("becas:reporte_detalle", args=["avance"])).content.decode()
        self.assertIn("btn-nodo btn-brand btn-base", html)
        self.assertNotIn("btn-primary", html)
        self.assertIn('aria-label="Volver a reportes"', html)
        self.assertIn('class="nodo-field"', html)
        self.assertIn("nodo-thead-row", html)
        self.assertNotIn("bg-danger-subtle", html)

    def test_error_de_filtros_usa_alerta_danger(self):
        html = self.client.get(
            reverse("becas:reporte_detalle", args=["avance"]), {"desde": "2026-12-31", "hasta": "2026-01-01"}
        ).content.decode()
        self.assertIn("bg-danger-soft", html)
        self.assertIn('role="alert"', html)
        self.assertNotIn("bg-danger-subtle", html)
