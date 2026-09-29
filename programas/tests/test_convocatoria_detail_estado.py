"""Detalle de convocatoria: el estado de la ficha «Datos» coincide con el del encabezado
y la solapa/tarjeta rotulan «Casos» (cuentan todos los casos, no solo beneficiarios)."""

from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.models import Convocatoria, Segmento


class ConvocatoriaDetailEstadoTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Seg Estado", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv Estado",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.client.force_login(User.objects.create_superuser("super_estado", password="x"))

    def _html(self):
        url = reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_pausada_no_dice_activa_en_ninguna_parte(self):
        self.convocatoria.pausado = True
        self.convocatoria.save()
        html = self._html()
        self.assertEqual(html.count('badge-warning badge-dot">Pausada</span>'), 2)  # encabezado + ficha
        self.assertNotIn('badge-dot">Activa</span>', html)

    def test_activa_dice_activa_en_encabezado_y_ficha(self):
        html = self._html()
        self.assertEqual(html.count('badge-success badge-dot">Activa</span>'), 2)
        self.assertNotIn(">Pausada</span>", html)

    def test_solapa_y_tarjeta_dicen_casos(self):
        html = self._html()
        self.assertIn('<i class="fas fa-users"></i> Casos', html)
        self.assertIn('font-medium">Casos</p>', html)
        self.assertNotIn('font-medium">Beneficiarios</p>', html)
        self.assertNotIn('<i class="fas fa-users"></i> Beneficiarios', html)
