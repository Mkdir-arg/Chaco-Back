"""Alcance del Coordinador Regional: opera su subsegmento y nada más.

El rol ve el segmento que contiene su subsegmento solo como contexto: no puede
configurarlo ni asomarse a los subsegmentos de sus pares.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from programas.forms import ConvocatoriaForm, RelevamientoForm, SubsegmentoForm
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR_REGIONAL
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
from programas.views.configuracion import segmento_subsegmentos_json


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

    # --- El subsegmento es obligatorio para este rol --------------------------

    def _datos_convocatoria(self, **cambios):
        datos = {
            "nombre": "Convocatoria de Ana",
            "segmento": self.segmento.pk,
            "subsegmento": self.sub_ana.pk,
            "fecha_inicio": "2026-09-01",
            "fecha_fin": "2026-09-30",
            "descripcion": "",
            "activo": "on",
        }
        datos.update(cambios)
        return datos

    def test_el_regional_no_puede_crear_una_convocatoria_sin_subsegmento(self):
        """Sin subsegmento la convocatoria queda fuera de su propio alcance: se
        guardaba bien y desaparecía del listado de quien acababa de crearla."""
        form = ConvocatoriaForm(
            self._datos_convocatoria(subsegmento=""),
            subsegmentos_permitidos=subsegmentos_visibles(self.ana),
            operador=self.ana,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("fuera de tu alcance", form.errors["subsegmento"][0])

    def test_el_regional_crea_con_su_subsegmento(self):
        form = ConvocatoriaForm(
            self._datos_convocatoria(),
            subsegmentos_permitidos=subsegmentos_visibles(self.ana),
            operador=self.ana,
        )

        self.assertTrue(form.is_valid(), form.errors)
        convocatoria = form.save()
        self.assertIn(convocatoria, convocatorias_visibles(self.ana))

    def test_el_regional_no_puede_usar_el_subsegmento_de_un_par(self):
        form = ConvocatoriaForm(
            self._datos_convocatoria(subsegmento=self.sub_beto.pk),
            subsegmentos_permitidos=subsegmentos_visibles(self.ana),
            operador=self.ana,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("subsegmento", form.errors)

    def test_para_otros_roles_el_subsegmento_sigue_siendo_opcional(self):
        """Una convocatoria a nivel segmento sigue siendo válida para el Admin:
        su alcance es el segmento, así que la ve igual."""
        admin = User.objects.create_user("admin_becas_conv", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))

        form = ConvocatoriaForm(self._datos_convocatoria(subsegmento=""), operador=admin)

        self.assertTrue(form.is_valid(), form.errors)

    def test_el_asterisco_aparece_solo_para_el_regional(self):
        """El template lo dibuja según ``field.required``."""
        del_regional = ConvocatoriaForm(subsegmentos_permitidos=subsegmentos_visibles(self.ana), operador=self.ana)
        sin_operador = ConvocatoriaForm()

        self.assertTrue(del_regional.fields["subsegmento"].required)
        self.assertFalse(sin_operador.fields["subsegmento"].required)

    # --- Select de subsegmentos del form de convocatoria ----------------------

    def test_el_endpoint_de_subsegmentos_solo_ofrece_los_suyos(self):
        """El select "Subsegmento" se puebla por AJAX, no por el queryset del
        form: sin scoping en el endpoint, Ana veía ahí el subsegmento de Beto."""
        self.client.force_login(self.ana)

        response = self.client.get(reverse("becas:segmento_subsegmentos_json", args=[self.segmento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nombre"] for item in response.json()], [self.sub_ana.nombre])

    def test_el_endpoint_de_subsegmentos_rechaza_un_segmento_fuera_de_alcance(self):
        """Sobre la vista y no por el test client: el 404 pasa por el handler de
        error, que renderiza un template (ver el piso de Py3.14 del suite)."""
        request = RequestFactory().get("/")
        request.user = self.ana

        with self.assertRaises(Http404):
            segmento_subsegmentos_json(request, self.otro_segmento.pk)


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
