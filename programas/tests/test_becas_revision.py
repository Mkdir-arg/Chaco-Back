"""Tests de la revisión de formularios de Becas (#77)."""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    Relevamiento,
    Segmento,
    TracaFormulario,
)


class _BaseRevisionTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.seg_a = Segmento.objects.create(nombre="Seg A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Seg B", cupo_maximo=100)
        self.conv_a = Convocatoria.objects.create(
            nombre="Conv A", segmento=self.seg_a, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.conv_b = Convocatoria.objects.create(
            nombre="Conv B", segmento=self.seg_b, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.territorial = User.objects.create_user("terri", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        self.rel_a = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.rel_b = Relevamiento.objects.create(
            convocatoria=self.conv_b,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="B",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.form_a = Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624100100",
            email_contacto="a@b.com",
            data={"globales": {}, "requisitos": {}},
        )
        self.form_b = Formulario.objects.create(
            relevamiento=self.rel_b,
            celular="3624200200",
            email_contacto="b@b.com",
        )

        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.coord_a = User.objects.create_user("coord_a", password="x")
        self.coord_a.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord_a)


class AccesoRevisionTests(_BaseRevisionTest):
    def test_coordinador_accede_revision(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(reverse("becas:revision")).status_code, 200)

    def test_territorial_no_accede(self):
        self.client.force_login(self.territorial)
        self.assertEqual(self.client.get(reverse("becas:revision")).status_code, 302)

    def test_coordinador_formularios_fuera_de_alcance_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:revision_formularios", args=[self.rel_b.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_formulario_ajeno_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 403)


class EdicionTrazaTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord_a)

    def test_editar_genera_traza(self):
        resp = self.client.post(
            reverse("becas:formulario_detalle", args=[self.form_a.pk]),
            {
                "celular": "3624999999",  # cambia
                "email_contacto": "a@b.com",  # igual
                "apoderado_nombre": "",
                "apoderado_apellido": "",
                "apoderado_fecha_nacimiento": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.celular, "3624999999")
        traza = TracaFormulario.objects.filter(formulario=self.form_a, campo="Celular")
        self.assertEqual(traza.count(), 1)
        self.assertEqual(traza.first().valor_anterior, "3624100100")
        self.assertEqual(traza.first().valor_nuevo, "3624999999")

    def test_editar_sin_cambios_no_traza(self):
        self.client.post(
            reverse("becas:formulario_detalle", args=[self.form_a.pk]),
            {
                "celular": "3624100100",
                "email_contacto": "a@b.com",
                "apoderado_nombre": "",
                "apoderado_apellido": "",
                "apoderado_fecha_nacimiento": "",
            },
        )
        self.assertEqual(TracaFormulario.objects.filter(formulario=self.form_a).count(), 0)


class AprobarRechazarTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord_a)

    def test_aprobar(self):
        resp = self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)

    def test_rechazar_sin_motivo_falla(self):
        self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": ""})
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_rechazar_con_motivo(self):
        self.client.post(
            reverse("becas:formulario_rechazar", args=[self.form_a.pk]),
            {"motivo": "Documentación incompleta"},
        )
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.motivo_rechazo, "Documentación incompleta")


class TransicionesRelevamientoTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord_a)

    def test_iniciar_revision(self):
        self.client.post(reverse("becas:revision_iniciar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)

    def test_terminar_bloqueado_con_pendientes(self):
        self.rel_a.estado = Relevamiento.Estado.EN_REVISION
        self.rel_a.save()
        self.client.post(reverse("becas:revision_terminar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)  # sigue, hay pendiente

    def test_terminar_ok_sin_pendientes(self):
        self.rel_a.estado = Relevamiento.Estado.EN_REVISION
        self.rel_a.save()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save()
        self.client.post(reverse("becas:revision_terminar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.TERMINADO)


class BeneficiarioScopingTests(_BaseRevisionTest):
    """El Coordinador tiene becas.beneficiario.editar, pero solo puede
    gestionar beneficiarios de los segmentos que tiene asignados (#78)."""

    def setUp(self):
        super().setUp()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save()
        self.form_b.estado = Formulario.Estado.APROBADO
        self.form_b.save()

    def test_coordinador_da_de_baja_beneficiario_de_su_segmento(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.BAJA)

    def test_coordinador_no_da_de_baja_beneficiario_de_otro_segmento(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 403)
        self.form_b.refresh_from_db()
        self.assertEqual(self.form_b.estado, Formulario.Estado.APROBADO)

    def test_admin_da_de_baja_beneficiario_de_cualquier_segmento(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_b.refresh_from_db()
        self.assertEqual(self.form_b.estado, Formulario.Estado.BAJA)
