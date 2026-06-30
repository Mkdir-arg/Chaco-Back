"""Tests del ABM de Relevamientos de Becas (#76)."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_TERRITORIAL,
)
from programas.models import AsignacionCoordinador, Convocatoria, Relevamiento, Segmento


class _BaseRelevTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)
        self.conv_a = Convocatoria.objects.create(
            nombre="Conv A", segmento=self.seg_a, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.conv_b = Convocatoria.objects.create(
            nombre="Conv B", segmento=self.seg_b, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )

        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))

        self.coord_a = User.objects.create_user("coord_a", password="x")
        self.coord_a.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord_a)

        self.territorial = User.objects.create_user("terri", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        self.rel_a = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona A",
        )
        self.rel_b = Relevamiento.objects.create(
            convocatoria=self.conv_b,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona B",
        )


class AccesoTests(_BaseRelevTest):
    def test_admin_accede(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("becas:relevamientos")).status_code, 200)

    def test_coordinador_accede(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(reverse("becas:relevamientos")).status_code, 200)

    def test_territorial_no_accede(self):
        self.client.force_login(self.territorial)
        self.assertEqual(self.client.get(reverse("becas:relevamientos")).status_code, 302)


class ScopingTests(_BaseRelevTest):
    def test_admin_ve_todos(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertContains(resp, self.rel_a.nombre)
        self.assertContains(resp, self.rel_b.nombre)

    def test_coordinador_ve_solo_su_segmento(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertContains(resp, self.rel_a.nombre)
        self.assertNotContains(resp, self.rel_b.nombre)

    def test_coordinador_detalle_fuera_de_alcance_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel_b.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_detalle_propio_ok(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel_a.pk]))
        self.assertEqual(resp.status_code, 200)


class CrearReasignarReprogramarTests(_BaseRelevTest):
    def test_crear_relevamiento_nombre_auto(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "zona": "Nueva zona",
            },
        )
        self.assertEqual(resp.status_code, 302)
        nuevo = Relevamiento.objects.get(zona="Nueva zona")
        self.assertTrue(nuevo.nombre.startswith("Relevamiento "))
        self.assertEqual(nuevo.estado, Relevamiento.Estado.ASIGNADO)

    def test_coordinador_no_crea_en_segmento_ajeno(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_b.pk,  # segmento B, fuera de alcance
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "zona": "X",
            },
        )
        # La convocatoria B no está en el queryset permitido → form inválido.
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Relevamiento.objects.filter(zona="X").exists())

    def test_reasignar_territorial(self):
        otro = User.objects.create_user("terri2", password="x")
        otro.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_reasignar", args=[self.rel_a.pk]),
            {"territorial": otro.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.territorial, otro)

    def test_reprogramar(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_reprogramar", args=[self.rel_a.pk]),
            {"fecha_asignada": "2026-09-15"},
        )
        self.assertEqual(resp.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.fecha_asignada, date(2026, 9, 15))


class VencidoTests(_BaseRelevTest):
    def test_esta_vencido(self):
        ayer = timezone.localdate() - timedelta(days=1)
        rel = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=ayer,
            zona="Vieja",
            estado=Relevamiento.Estado.ASIGNADO,
        )
        self.assertTrue(rel.esta_vencido)

    def test_no_vencido_si_terminado(self):
        ayer = timezone.localdate() - timedelta(days=1)
        rel = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=ayer,
            zona="Vieja",
            estado=Relevamiento.Estado.TERMINADO,
        )
        self.assertFalse(rel.esta_vencido)


class ConvocatoriaTests(_BaseRelevTest):
    def test_crear_convocatoria(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:convocatoria_crear"),
            {
                "nombre": "Conv nueva",
                "segmento": self.seg_a.pk,
                "fecha_inicio": "2026-01-01",
                "fecha_fin": "2026-12-31",
                "descripcion": "",
                "activo": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Convocatoria.objects.filter(nombre="Conv nueva").exists())
