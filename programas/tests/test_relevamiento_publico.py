"""Tests del relevamiento de tipo Formulario público — Fase 1 (#290/#291/#292,
análisis #289): modelo, gateo RBAC del backoffice y ciclo de vida.
"""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import rbac
from programas.forms import RelevamientoForm
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_TERRITORIAL
from programas.models import (
    AsignacionTerritorial,
    Convocatoria,
    Relevamiento,
    Segmento,
)
from users.models import Capacidad

CAP_PUBLICO = "becas.relevamiento.publico"


def _dar_capacidad_publico(grupo):
    """Suma la capacidad del formulario público a un rol existente (mismo
    mecanismo que ``seed_becas``: Permission sobre el ancla Capacidad)."""
    ct = ContentType.objects.get_for_model(Capacidad)
    codename = rbac.codename_de(CAP_PUBLICO)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct, codename=codename, defaults={"name": "Formulario público"}
    )
    grupo.permissions.add(perm)


class _BasePublicoTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Segmento P", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv P",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.territorial = User.objects.create_user("terri_p", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.segmento, territorial=self.territorial)

        # Admin del programa SIN la capacidad de público (estado post-deploy).
        self.admin = User.objects.create_user("admin_p", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))

        # Admin de otro grupo CON la capacidad (encendido vía Roles).
        self.admin_publico = User.objects.create_user("admin_pub", password="x")
        grupo_admin = Group.objects.get(name=ROL_ADMIN)
        self.admin_publico.groups.add(grupo_admin)
        _dar_capacidad_publico(grupo_admin)
        # Ojo: al compartir el grupo, self.admin también ganaría la capacidad.
        # Para el "sin capacidad" se usa un rol clonado sin ella.
        grupo_sin = Group.objects.create(name="Becas — Admin sin público")
        grupo_sin.permissions.set(
            grupo_admin.permissions.exclude(codename=rbac.codename_de(CAP_PUBLICO))
        )
        from users.models import RolMeta

        RolMeta.objects.create(grupo=grupo_sin, activo=True)
        self.admin.groups.set([grupo_sin])

    def _crear_publico(self, **extra):
        defaults = {
            "convocatoria": self.convocatoria,
            "tipo": Relevamiento.Tipo.PUBLICO,
            "fecha_asignada": date(2026, 6, 1),
            "fecha_hasta": date(2026, 6, 30),
        }
        defaults.update(extra)
        return Relevamiento.objects.create(**defaults)

    def _form_data(self, **extra):
        data = {
            "tipo": Relevamiento.Tipo.PUBLICO,
            "convocatoria": self.convocatoria.pk,
            "fecha_asignada": "2026-06-01T08:00",
            "fecha_hasta": "2026-06-30T18:00",
            "cupo_maximo": 50,
        }
        data.update(extra)
        return data


class ModeloPublicoTests(_BasePublicoTest):
    def test_alta_publico_token_en_curso_sin_territorial(self):
        rel = self._crear_publico()
        self.assertTrue(rel.es_publico)
        self.assertIsNotNone(rel.token_publico)
        self.assertEqual(rel.estado, Relevamiento.Estado.EN_CURSO)
        self.assertIsNone(rel.territorial)
        self.assertIn(str(rel.token_publico), rel.url_publica)
        self.assertNotIn(str(rel.pk), rel.url_publica.replace(str(rel.token_publico), ""))

    def test_tokens_unicos_en_altas_sucesivas(self):
        rel1 = self._crear_publico()
        rel2 = self._crear_publico()
        self.assertNotEqual(rel1.token_publico, rel2.token_publico)
        self.assertEqual(rel2.numero, rel1.numero + 1)

    def test_clean_rechaza_publico_con_territorial(self):
        rel = Relevamiento(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )
        with self.assertRaises(ValidationError) as ctx:
            rel.clean()
        self.assertIn("territorial", ctx.exception.message_dict)

    def test_clean_rechaza_territorial_sin_territorial_o_zona(self):
        rel = Relevamiento(
            convocatoria=self.convocatoria,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )
        with self.assertRaises(ValidationError) as ctx:
            rel.clean()
        self.assertIn("territorial", ctx.exception.message_dict)
        rel.territorial = self.territorial
        with self.assertRaises(ValidationError) as ctx:
            rel.clean()
        self.assertIn("zona", ctx.exception.message_dict)

    def test_los_territoriales_existentes_no_cambian(self):
        rel = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona X",
        )
        self.assertEqual(rel.tipo, Relevamiento.Tipo.TERRITORIAL)
        self.assertIsNone(rel.token_publico)
        self.assertEqual(rel.estado, Relevamiento.Estado.ASIGNADO)


class FormPublicoTests(_BasePublicoTest):
    def test_alta_publica_valida_sin_territorial_ni_zona(self):
        form = RelevamientoForm(data=self._form_data(), puede_publico=True)
        self.assertTrue(form.is_valid(), form.errors)
        rel = form.save()
        self.assertTrue(rel.es_publico)
        self.assertEqual(rel.estado, Relevamiento.Estado.EN_CURSO)
        self.assertEqual(rel.zona, "")
        self.assertEqual(rel.cupo_maximo, 50)

    def test_post_publico_con_territorial_se_rechaza(self):
        form = RelevamientoForm(
            data=self._form_data(territorial=self.territorial.pk), puede_publico=True
        )
        self.assertFalse(form.is_valid())
        self.assertIn("territorial", form.errors)

    def test_post_publico_sin_capacidad_se_rechaza(self):
        form = RelevamientoForm(data=self._form_data(), puede_publico=False)
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_sin_capacidad_el_form_no_ofrece_tipo(self):
        form = RelevamientoForm(puede_publico=False)
        self.assertNotIn("tipo", form.fields)
        self.assertNotIn("confirmar_por_email", form.fields)

    def test_flujo_territorial_sigue_exigiendo_territorial(self):
        data = self._form_data(tipo=Relevamiento.Tipo.TERRITORIAL)
        form = RelevamientoForm(data=data, puede_publico=True)
        self.assertFalse(form.is_valid())
        self.assertIn("territorial", form.errors)


class VistasPublicoTests(_BasePublicoTest):
    def test_crear_publico_redirige_al_detalle(self):
        self.client.force_login(self.admin_publico)
        resp = self.client.post(reverse("becas:relevamiento_crear"), self._form_data())
        rel = Relevamiento.objects.get(tipo=Relevamiento.Tipo.PUBLICO)
        self.assertRedirects(resp, reverse("becas:relevamiento_detalle", args=[rel.pk]))

    def test_detalle_muestra_link_copiable(self):
        rel = self._crear_publico()
        self.client.force_login(self.admin_publico)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[rel.pk]))
        self.assertContains(resp, rel.url_publica)
        self.assertContains(resp, "data-copy-link")

    def test_sin_capacidad_no_ve_publicos_en_listado(self):
        rel = self._crear_publico()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertNotContains(resp, rel.nombre)
        self.client.force_login(self.admin_publico)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertContains(resp, rel.nombre)
        self.assertContains(resp, "Formulario público")

    def test_sin_capacidad_no_ve_selector_de_tipo(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertNotContains(resp, "Tipo de relevamiento")

    def test_sin_capacidad_detalle_de_publico_403(self):
        rel = self._crear_publico()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[rel.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_post_publico_sin_capacidad_no_crea(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("becas:relevamiento_crear"), self._form_data())
        self.assertFalse(Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).exists())

    def test_superusuario_puede_crear_publico(self):
        superuser = User.objects.create_superuser("root", "r@x.com", "x")
        self.client.force_login(superuser)
        resp = self.client.post(reverse("becas:relevamiento_crear"), self._form_data())
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).exists())

    def test_reasignar_sobre_publico_no_aplica(self):
        rel = self._crear_publico()
        self.client.force_login(self.admin_publico)
        self.client.post(
            reverse("becas:relevamiento_reasignar", args=[rel.pk]),
            {"territorial": self.territorial.pk},
        )
        rel.refresh_from_db()
        self.assertIsNone(rel.territorial)

    def test_export_relevamientos_no_rompe_con_publico(self):
        self._crear_publico()
        self.client.force_login(self.admin_publico)
        resp = self.client.get(
            reverse("becas:convocatoria_export_relevamientos", args=[self.convocatoria.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Formulario público", resp.content.decode("utf-8-sig"))


class ApiCampoPublicoTests(_BasePublicoTest):
    def test_api_de_campo_no_expone_publicos(self):
        rel_publico = self._crear_publico(
            fecha_asignada=timezone.now(), fecha_hasta=timezone.now() + timedelta(days=5)
        )
        self.client.force_login(self.territorial)
        listado = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertEqual(listado.status_code, 200)
        nombres = [r["nombre"] for r in listado.json()["results"]] if "results" in listado.json() else [
            r["nombre"] for r in listado.json()
        ]
        self.assertNotIn(rel_publico.nombre, nombres)
        detalle = self.client.get(reverse("becas_api:relevamiento-detail", args=[rel_publico.pk]))
        self.assertEqual(detalle.status_code, 404)


class VencimientoPublicoTests(_BasePublicoTest):
    def test_publico_vencido_pasa_a_revision(self):
        ayer = timezone.now() - timedelta(days=1)
        rel = self._crear_publico(fecha_asignada=ayer - timedelta(days=5), fecha_hasta=ayer)
        call_command("procesar_vencimientos", stdout=StringIO())
        rel.refresh_from_db()
        self.assertEqual(rel.estado, Relevamiento.Estado.EN_REVISION)
        self.assertIsNotNone(rel.fecha_finalizado)

    def test_publico_vigente_no_se_toca(self):
        rel = self._crear_publico(
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        call_command("procesar_vencimientos", stdout=StringIO())
        rel.refresh_from_db()
        self.assertEqual(rel.estado, Relevamiento.Estado.EN_CURSO)
