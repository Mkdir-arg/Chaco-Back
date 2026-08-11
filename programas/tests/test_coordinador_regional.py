"""Alcance del Coordinador Regional: opera su subsegmento y nada más.

El rol ve el segmento que contiene su subsegmento solo como contexto: no puede
configurarlo ni asomarse a los subsegmentos de sus pares.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from programas.forms import RelevamientoForm, SubsegmentoForm
from programas.management.commands.seed_becas import ROL_COORDINADOR_REGIONAL
from programas.models import Convocatoria, Segmento, Subsegmento
from programas.services.autorizacion import (
    convocatorias_visibles,
    es_coordinador_regional_becas,
    puede_gestionar_segmento,
    puede_operar_subsegmento,
    segmentos_para_gestion_territoriales,
    segmentos_visibles,
    subsegmentos_visibles,
    usuarios_coordinadores_becas,
    usuarios_coordinadores_regionales_becas,
)


class CoordinadorRegionalTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.rol = Group.objects.get(name=ROL_COORDINADOR_REGIONAL)

        self.segmento = Segmento.objects.create(nombre="Fuego y Barro", cupo_maximo=300)
        self.otro_segmento = Segmento.objects.create(nombre="Producción", cupo_maximo=300)

        self.ana = self._crear_coordinador_regional("ana")
        self.beto = self._crear_coordinador_regional("beto")

        self.sub_ana = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Ladrillo", cupo_maximo=100, referente=self.ana
        )
        self.sub_beto = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Carbón", cupo_maximo=100, referente=self.beto
        )
        self.sub_huerfano = Subsegmento.objects.create(segmento=self.segmento, nombre="Sin referente", cupo_maximo=50)
        self.sub_ajeno = Subsegmento.objects.create(
            segmento=self.otro_segmento, nombre="De otro segmento", cupo_maximo=50
        )

    def _crear_coordinador_regional(self, username):
        user = User.objects.create_user(username, password="x")
        user.groups.add(self.rol)
        return user

    # --- Identificación del rol ---------------------------------------------

    def test_el_rol_se_reconoce(self):
        self.assertTrue(es_coordinador_regional_becas(self.ana))

    def test_no_se_ofrece_como_coordinador_de_segmento(self):
        """El selector de coordinadores del segmento no debe listarlo."""
        self.assertNotIn(self.ana, usuarios_coordinadores_becas())
        self.assertIn(self.ana, usuarios_coordinadores_regionales_becas())

    # --- Alcance -------------------------------------------------------------

    def test_ve_el_segmento_que_contiene_su_subsegmento(self):
        self.assertIn(self.segmento, segmentos_visibles(self.ana))
        self.assertNotIn(self.otro_segmento, segmentos_visibles(self.ana))
        self.assertTrue(puede_gestionar_segmento(self.ana, self.segmento))
        self.assertFalse(puede_gestionar_segmento(self.ana, self.otro_segmento))

    def test_cada_uno_ve_solo_su_subsegmento(self):
        self.assertEqual(list(subsegmentos_visibles(self.ana)), [self.sub_ana])
        self.assertEqual(list(subsegmentos_visibles(self.beto)), [self.sub_beto])

    def test_no_puede_operar_el_subsegmento_de_un_par(self):
        """Comparten segmento: sin este corte, Ana entraría al de Beto."""
        self.assertTrue(puede_operar_subsegmento(self.ana, self.sub_ana))
        self.assertFalse(puede_operar_subsegmento(self.ana, self.sub_beto))
        self.assertFalse(puede_operar_subsegmento(self.ana, self.sub_huerfano))
        self.assertFalse(puede_operar_subsegmento(self.ana, self.sub_ajeno))

    def test_sin_subsegmento_asignado_no_ve_nada(self):
        sola = self._crear_coordinador_regional("sola")

        self.assertEqual(list(segmentos_visibles(sola)), [])
        self.assertEqual(list(subsegmentos_visibles(sola)), [])

    def test_puede_tener_subsegmentos_de_segmentos_distintos(self):
        self.sub_ajeno.referente = self.ana
        self.sub_ajeno.save(update_fields=["referente", "modificado"])

        self.assertCountEqual(segmentos_visibles(self.ana), [self.segmento, self.otro_segmento])
        self.assertCountEqual(subsegmentos_visibles(self.ana), [self.sub_ana, self.sub_ajeno])

    # --- Convocatorias y relevamientos ---------------------------------------

    def test_solo_ve_las_convocatorias_de_su_subsegmento(self):
        propia = Convocatoria.objects.create(
            nombre="Propia",
            segmento=self.segmento,
            subsegmento=self.sub_ana,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        del_par = Convocatoria.objects.create(
            nombre="Del par",
            segmento=self.segmento,
            subsegmento=self.sub_beto,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        del_segmento = Convocatoria.objects.create(
            nombre="Sin subsegmento",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

        visibles = convocatorias_visibles(self.ana)

        self.assertIn(propia, visibles)
        self.assertNotIn(del_par, visibles)
        # La convocatoria a nivel segmento excede su alcance.
        self.assertNotIn(del_segmento, visibles)

    def test_el_selector_de_relevamientos_respeta_su_alcance(self):
        propia = Convocatoria.objects.create(
            nombre="Propia",
            segmento=self.segmento,
            subsegmento=self.sub_ana,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        del_par = Convocatoria.objects.create(
            nombre="Del par",
            segmento=self.segmento,
            subsegmento=self.sub_beto,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

        form = RelevamientoForm(convocatorias_permitidas=convocatorias_visibles(self.ana))

        self.assertIn(propia, form.fields["convocatoria"].queryset)
        self.assertNotIn(del_par, form.fields["convocatoria"].queryset)

    def test_puede_gestionar_territoriales_de_su_segmento(self):
        self.assertIn(self.segmento, segmentos_para_gestion_territoriales(self.ana))
        self.assertNotIn(self.otro_segmento, segmentos_para_gestion_territoriales(self.ana))


class ReferenteDelSubsegmentoFormTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Fuego y Barro", cupo_maximo=300)
        self.regional = User.objects.create_user("regional", password="x")
        self.regional.groups.add(Group.objects.get(name=ROL_COORDINADOR_REGIONAL))
        self.ajeno = User.objects.create_user("ajeno", password="x")

    def test_el_selector_solo_ofrece_coordinadores_regionales(self):
        form = SubsegmentoForm(segmento=self.segmento)

        opciones = list(form.fields["referente"].queryset)
        self.assertIn(self.regional, opciones)
        self.assertNotIn(self.ajeno, opciones)

    def test_el_referente_es_opcional(self):
        form = SubsegmentoForm({"nombre": "Ladrillo", "cupo_maximo": 100}, segmento=self.segmento)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().referente)

    def test_asignar_otro_referente_reemplaza_al_anterior(self):
        otro = User.objects.create_user("otro-regional", password="x")
        otro.groups.add(Group.objects.get(name=ROL_COORDINADOR_REGIONAL))
        sub = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Ladrillo", cupo_maximo=100, referente=self.regional
        )

        form = SubsegmentoForm(
            {"nombre": "Ladrillo", "cupo_maximo": 100, "referente": otro.pk},
            instance=sub,
            segmento=self.segmento,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().referente, otro)
