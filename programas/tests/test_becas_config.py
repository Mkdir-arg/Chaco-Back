"""Tests del backoffice de Configuración de Becas (#74)."""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR
from programas.models import (
    AsignacionCoordinador,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)


class _BaseConfigTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.coord = User.objects.create_user("coord_becas", password="x")
        self.coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))


class AccesoConfigTests(_BaseConfigTest):
    def test_admin_accede(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 200)

    def test_coordinador_no_accede(self):
        self.client.force_login(self.coord)
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 302)  # redirigido (sin becas.configurar)

    def test_anonimo_redirige_login(self):
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 302)


class SegmentoCrudTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_crear_segmento(self):
        resp = self.client.post(
            reverse("becas:segmento_crear"),
            {
                "nombre": "Producción",
                "descripcion": "Población objetivo del segmento productivo",
                "cupo_maximo": 200,
                "coordinador": self.coord.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Segmento.objects.filter(nombre="Producción", cupo_maximo=200).exists())

    def test_editar_segmento(self):
        seg = Segmento.objects.create(nombre="S1", cupo_maximo=100)
        resp = self.client.post(
            reverse("becas:segmento_editar", args=[seg.pk]),
            {"nombre": "S1 editado", "descripcion": "", "cupo_maximo": 150, "activo": "on"},
        )
        self.assertEqual(resp.status_code, 302)
        seg.refresh_from_db()
        self.assertEqual(seg.nombre, "S1 editado")
        self.assertEqual(seg.cupo_maximo, 150)

    def test_toggle_segmento(self):
        seg = Segmento.objects.create(nombre="S1", cupo_maximo=100, activo=True)
        self.client.post(reverse("becas:segmento_toggle", args=[seg.pk]))
        seg.refresh_from_db()
        self.assertFalse(seg.activo)


class SubsegmentoCupoTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=200)

    def test_crear_subsegmento_ok(self):
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[self.seg.pk]),
            {"nombre": "Ladrillo", "cupo_maximo": 120},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Subsegmento.objects.filter(segmento=self.seg, nombre="Ladrillo").exists())

    def test_subsegmento_excede_cupo_rn40(self):
        Subsegmento.objects.create(segmento=self.seg, nombre="Ladrillo", cupo_maximo=120)
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[self.seg.pk]),
            {"nombre": "Carbón", "cupo_maximo": 100},  # 120 + 100 > 200
        )
        self.assertEqual(resp.status_code, 200)  # re-render con error
        self.assertFalse(Subsegmento.objects.filter(nombre="Carbón").exists())
        self.assertContains(resp, "supera el cupo del segmento")


class CoordinadorTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=100)

    def test_asignar_coordinador(self):
        resp = self.client.post(
            reverse("becas:coordinador_asignar", args=[self.seg.pk]),
            {"coordinador": self.coord.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AsignacionCoordinador.objects.filter(segmento=self.seg, coordinador=self.coord).exists())

    def test_no_asignar_usuario_sin_rol_coordinador(self):
        otro = User.objects.create_user("otro", password="x")  # sin rol coordinador
        self.client.post(
            reverse("becas:coordinador_asignar", args=[self.seg.pk]),
            {"coordinador": otro.pk},
        )
        # El form rechaza el usuario (queryset acotado a rol coordinador)
        self.assertFalse(AsignacionCoordinador.objects.filter(coordinador=otro).exists())

    def test_desasignar_coordinador(self):
        asig = AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=self.coord)
        self.client.post(reverse("becas:coordinador_desasignar", args=[asig.pk]))
        self.assertFalse(AsignacionCoordinador.objects.filter(pk=asig.pk).exists())


class RequisitoTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub", cupo_maximo=40)

    def test_crear_requisito_segmento(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {"texto": "Actividad", "tipo": TipoCampo.STRING, "orden": 1, "obligatorio": "True"},
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Actividad")
        self.assertEqual(req.segmento, self.seg)
        self.assertIsNone(req.subsegmento)

    def test_crear_requisito_subsegmento(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]) + f"?subsegmento={self.sub.pk}",
            {
                "texto": "Tipo horno",
                "tipo": TipoCampo.STRING,
                "orden": 1,
                "obligatorio": "True",
                "subsegmento": self.sub.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Tipo horno")
        self.assertEqual(req.subsegmento, self.sub)

    def test_crear_requisito_selector_parsea_opciones(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {
                "texto": "Material",
                "tipo": TipoCampo.SELECTOR,
                "orden": 1,
                "obligatorio": "True",
                "opciones_texto": "Ladrillo\nCarbón\nOtro",
            },
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Material")
        self.assertEqual(req.opciones, ["Ladrillo", "Carbón", "Otro"])


class PreguntaGlobalTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_crear_pregunta_selector(self):
        resp = self.client.post(
            reverse("becas:pregunta_crear"),
            {
                "texto": "Tenencia de la vivienda",
                "tipo": TipoCampo.SELECTOR,
                "orden": 1,
                "obligatorio": "on",
                "activo": "on",
                "opciones_texto": "Propia\nAlquilada\nPrestada",
            },
        )
        self.assertEqual(resp.status_code, 302)
        p = PreguntaGlobal.objects.get(texto="Tenencia de la vivienda")
        self.assertEqual(p.opciones, ["Propia", "Alquilada", "Prestada"])

    def test_toggle_pregunta(self):
        p = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.STRING, activo=True)
        self.client.post(reverse("becas:pregunta_toggle", args=[p.pk]))
        p.refresh_from_db()
        self.assertFalse(p.activo)

    def test_eliminar_pregunta(self):
        p = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.STRING)
        self.client.post(reverse("becas:pregunta_eliminar", args=[p.pk]))
        self.assertFalse(PreguntaGlobal.objects.filter(pk=p.pk).exists())
