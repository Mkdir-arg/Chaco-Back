from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_REFERENTE,
    ROL_TERRITORIAL,
)
from programas.models import (
    AsignacionCoordinador,
    AsignacionReferente,
    AsignacionTerritorial,
    Convocatoria,
    Segmento,
    Subsegmento,
)
from programas.services.autorizacion import segmentos_visibles
from users.selectors.usuarios import usuarios_visibles_para


class ReferenteTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Norte", cupo_maximo=100)
        self.otro_segmento = Segmento.objects.create(nombre="Sur", cupo_maximo=100)
        self.localidad = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Resistencia", cupo_maximo=50
        )
        self.otra_localidad = Subsegmento.objects.create(
            segmento=self.otro_segmento, nombre="Villa Ángela", cupo_maximo=50
        )
        self.admin = self._usuario("admin-r", ROL_ADMIN)
        self.coordinador = self._usuario("coord-r", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coordinador)
        self.referente = self._usuario("referente-r", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=self.referente, coordinador=self.coordinador)
        self.territorial = self._usuario("territorial-r", ROL_TERRITORIAL)
        AsignacionTerritorial.objects.create(territorial=self.territorial, segmento=self.segmento)
        self.territorial_ajeno = self._usuario("territorial-ajeno-r", ROL_TERRITORIAL)
        AsignacionTerritorial.objects.create(territorial=self.territorial_ajeno, segmento=self.otro_segmento)

    @staticmethod
    def _usuario(username, rol):
        user = User.objects.create_user(username, password="x")
        user.groups.add(Group.objects.get(name=rol))
        return user

    def test_referente_hereda_segmentos_y_solo_administra_territoriales_del_coordinador(self):
        self.assertEqual(list(segmentos_visibles(self.referente)), [self.segmento])
        self.assertEqual(list(usuarios_visibles_para(self.referente)), [self.territorial])
        self.assertFalse(rbac.puede(self.referente, "rol.administrar"))
        self.assertFalse(rbac.puede(self.referente, "becas.convocatoria.crear"))

    def test_referente_no_puede_pausar(self):
        convocatoria = Convocatoria.objects.create(
            nombre="Operativo",
            segmento=self.segmento,
            subsegmento=self.localidad,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.client.force_login(self.referente)
        response = self.client.post(
            reverse("becas:gestionar_pausa", args=["convocatoria", convocatoria.pk]),
            {"accion": "pausar", "motivo": "No permitido"},
        )
        self.assertEqual(response.status_code, 403)
        convocatoria.refresh_from_db()
        self.assertFalse(convocatoria.pausado)
