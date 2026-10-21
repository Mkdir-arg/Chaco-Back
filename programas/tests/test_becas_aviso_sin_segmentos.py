"""Aviso de «sin segmentos asignados» en los listados de Becas.

Coordinador, referente y coordinador regional ven Becas a través de ``segmentos_visibles``.
Con el rol pero sin asignación vigente los listados salen vacíos; el estado vacío tiene que
decir por qué. El aviso no cambia ningún alcance: solo explica.
"""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.urls import reverse

from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_REFERENTE,
)
from programas.models import AsignacionCoordinador, AsignacionReferente, Segmento
from programas.services.autorizacion import aviso_sin_segmentos_becas
from programas.tests.base_becas import BecasPantallaTestCase

TITULO = "Tu usuario no tiene segmentos asignados en Becas"
URLS = ("becas:convocatorias", "becas:relevamientos", "becas:revision")


class AvisoSinSegmentosTests(BecasPantallaTestCase):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Seg A", cupo_maximo=100)

    def _usuario(self, nombre, rol):
        user = User.objects.create_user(nombre, password="x")
        user.groups.add(Group.objects.get(name=rol))
        return user

    def _assert_en_listados(self, user, con_aviso):
        self.client.force_login(user)
        for nombre in URLS:
            resp = self.client.get(reverse(nombre))
            self.assertEqual(resp.status_code, 200, nombre)
            if con_aviso:
                self.assertContains(resp, TITULO, msg_prefix=nombre)
            else:
                self.assertNotContains(resp, TITULO, msg_prefix=nombre)

    def test_coordinador_sin_asignacion_ve_el_aviso(self):
        self._assert_en_listados(self._usuario("coord", ROL_COORDINADOR), con_aviso=True)

    def test_coordinador_con_asignacion_inactiva_ve_el_aviso(self):
        user = self._usuario("coord", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=user, activo=False)
        self._assert_en_listados(user, con_aviso=True)

    def test_coordinador_con_asignacion_no_ve_el_aviso(self):
        user = self._usuario("coord", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=user)
        self._assert_en_listados(user, con_aviso=False)

    def test_admin_no_ve_el_aviso(self):
        self._assert_en_listados(self._usuario("adm", ROL_ADMIN), con_aviso=False)

    def test_superusuario_no_ve_el_aviso(self):
        sup = User.objects.create_superuser("sup", password="x")
        self.assertEqual(aviso_sin_segmentos_becas(sup), "")

    def test_regional_sin_subsegmento_a_cargo_dice_el_motivo(self):
        user = self._usuario("reg", ROL_COORDINADOR_REGIONAL)
        aviso = aviso_sin_segmentos_becas(user)
        self.assertIn("subsegmento a tu cargo", aviso)
        self.assertIn("te designe referente de un subsegmento", aviso)
        self.assertIn("Referente asignado", aviso)
        self.assertNotIn("Usuarios", aviso)
        self.client.force_login(user)
        for nombre in URLS:
            self.assertContains(self.client.get(reverse(nombre)), "Referente asignado")

    def test_referente_sin_coordinador_dice_el_motivo(self):
        user = self._usuario("ref", ROL_REFERENTE)
        aviso = aviso_sin_segmentos_becas(user)
        self.assertIn("no tenés un coordinador asignado", aviso)
        self.assertIn("Usuarios → tu usuario → Coordinador del Referente", aviso)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("becas:revision")), "Coordinador del Referente")

    def test_referente_con_coordinador_sin_segmentos_dice_que_se_los_asignen_al_coordinador(self):
        coord = self._usuario("coord", ROL_COORDINADOR)
        ref = self._usuario("ref", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=ref, coordinador=coord)
        aviso = aviso_sin_segmentos_becas(ref)
        self.assertIn("que asigne segmentos a tu coordinador", aviso)
        self.assertNotIn("Usuarios", aviso)

    def test_coordinador_sin_segmento_dice_donde_se_asigna(self):
        aviso = aviso_sin_segmentos_becas(self._usuario("coord", ROL_COORDINADOR))
        self.assertIn("te asigne como coordinador de un segmento", aviso)
        self.assertIn("Asignar coordinador", aviso)
        self.assertNotIn("Usuarios", aviso)

    def test_referente_con_coordinador_con_segmentos_no_ve_aviso(self):
        coord = self._usuario("coord", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=coord)
        ref = self._usuario("ref", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=ref, coordinador=coord)
        self.assertEqual(aviso_sin_segmentos_becas(ref), "")

    def test_el_acceso_a_un_segmento_ajeno_sigue_en_403(self):
        user = self._usuario("coord", ROL_COORDINADOR)
        resp = self.client.get(reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        self.assertEqual(resp.status_code, 302)  # anónimo: login
        self.client.force_login(user)
        resp = self.client.get(reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        self.assertEqual(resp.status_code, 403)
