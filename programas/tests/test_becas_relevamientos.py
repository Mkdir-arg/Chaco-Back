"""Tests del ABM de Relevamientos de Becas (#76)."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Localidad, Municipio, Provincia
from programas.forms import RelevamientoForm, ReprogramarForm
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_TERRITORIAL,
)
from programas.models import (
    AsignacionCoordinador,
    AsignacionTerritorial,
    Convocatoria,
    Formulario,
    Relevamiento,
    Segmento,
)


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
        AsignacionTerritorial.objects.create(segmento=self.seg_a, territorial=self.territorial)

        # La zona se elige del catálogo de localidades: el alta necesita un
        # municipio y una localidad de la provincia operativa.
        self.provincia, _ = Provincia.objects.get_or_create(nombre="Chaco")
        self.municipio, _ = Municipio.objects.get_or_create(nombre="Resistencia", provincia=self.provincia)
        self.localidad, _ = Localidad.objects.get_or_create(nombre="Barranqueras", municipio=self.municipio)

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
        self.assertContains(resp, self.rel_a.zona)
        self.assertNotContains(resp, self.rel_b.zona)

    def test_coordinador_detalle_fuera_de_alcance_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel_b.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_detalle_propio_ok(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel_a.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_filtros_combinados(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("becas:relevamientos"),
            {
                "q": "Zona A",
                "estado": Relevamiento.Estado.ASIGNADO,
                "segmento": self.seg_a.pk,
                "territorial": self.territorial.pk,
                "fecha_desde": "2026-06-01",
                "fecha_hasta": "2026-06-01",
            },
        )
        self.assertContains(resp, self.rel_a.zona)
        self.assertNotContains(resp, self.rel_b.zona)

    def test_paginacion_muestra_25_y_permite_segunda_pagina(self):
        for numero in range(24):
            Relevamiento.objects.create(
                convocatoria=self.conv_a,
                territorial=self.territorial,
                fecha_asignada=date(2026, 7, 1) + timedelta(days=numero),
                zona=f"Zona paginada {numero}",
            )
        self.client.force_login(self.admin)

        primera = self.client.get(reverse("becas:relevamientos"))
        segunda = self.client.get(reverse("becas:relevamientos"), {"page": 2})

        self.assertEqual(len(primera.context["relevamientos"]), 25)
        self.assertEqual(len(segunda.context["relevamientos"]), 1)
        self.assertContains(primera, "Siguiente")


class CrearReasignarReprogramarTests(_BaseRelevTest):
    def test_crear_relevamiento_nombre_auto(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        nuevo = Relevamiento.objects.get(zona=self.localidad.nombre)
        self.assertEqual(nuevo.nombre, "Relevamiento 002 · Conv A")
        self.assertEqual(nuevo.estado, Relevamiento.Estado.ASIGNADO)

    def test_fecha_debe_estar_dentro_del_periodo_de_convocatoria(self):
        for fecha in ("2025-12-31", "2027-01-01"):
            with self.subTest(fecha=fecha):
                form = RelevamientoForm(
                    {
                        "convocatoria": self.conv_a.pk,
                        "territorial": self.territorial.pk,
                        "fecha_asignada": fecha,
                        "municipio": self.municipio.pk,
                        "zona": self.localidad.pk,
                    }
                )
                self.assertFalse(form.is_valid())
                self.assertIn("período de la convocatoria", form.errors["fecha_asignada"][0])

    def test_fecha_acepta_limites_inclusivos_de_convocatoria(self):
        for fecha in ("2026-01-01", "2026-12-31"):
            with self.subTest(fecha=fecha):
                form = RelevamientoForm(
                    {
                        "convocatoria": self.conv_a.pk,
                        "territorial": self.territorial.pk,
                        "fecha_asignada": fecha,
                        "municipio": self.municipio.pk,
                        "zona": self.localidad.pk,
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)

    def test_fecha_hasta_debe_estar_dentro_del_periodo_de_convocatoria(self):
        form = RelevamientoForm(
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-12-31T08:00",
                "fecha_hasta": "2027-01-01T08:00",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("período de la convocatoria", form.errors["fecha_hasta"][0])

    def test_opciones_de_convocatoria_exponen_limites_para_el_datepicker(self):
        html = str(RelevamientoForm()["convocatoria"])

        self.assertIn('data-fecha-inicio="2026-01-01"', html)
        self.assertIn('data-fecha-fin="2026-12-31"', html)

    def test_crear_solapado_advierte_sin_guardar(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-06-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.json()["confirm_required"])
        self.assertIn("terri", resp.json()["message"])
        self.assertIn("01/06/2026", resp.json()["message"])
        self.assertIn("Zona A", resp.json()["message"])
        self.assertFalse(Relevamiento.objects.filter(zona=self.localidad.nombre).exists())

    def test_crear_solapado_confirmado_guarda(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-06-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
                "confirmar_solapamiento": "1",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Relevamiento.objects.filter(zona=self.localidad.nombre).exists())

    def test_crear_en_fecha_libre_no_advierte(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-06-02",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Relevamiento.objects.filter(zona=self.localidad.nombre).exists())

    def test_coordinador_no_crea_en_segmento_ajeno(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_b.pk,  # segmento B, fuera de alcance
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
        )
        # La convocatoria B no está en el queryset permitido → form inválido.
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Relevamiento.objects.filter(zona=self.localidad.nombre).exists())

    def test_crear_con_territorial_de_otro_segmento_falla(self):
        """RN nueva: el territorial debe pertenecer al segmento de la convocatoria."""
        from programas.forms import RelevamientoForm

        terri_b = User.objects.create_user("terri_b", password="x")
        terri_b.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.seg_b, territorial=terri_b)
        form = RelevamientoForm(
            {
                "convocatoria": self.conv_a.pk,  # segmento A
                "territorial": terri_b.pk,  # asignado al segmento B
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("territorial", form.errors)

    def test_crear_con_territorial_sin_segmento_falla(self):
        from programas.forms import RelevamientoForm

        suelto = User.objects.create_user("terri_suelto", password="x")
        suelto.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        form = RelevamientoForm(
            {
                "convocatoria": self.conv_a.pk,
                "territorial": suelto.pk,
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("territorial", form.errors)

    def test_widgets_llevan_data_segmento(self):
        """El filtro dependiente del template depende de data-segmento por opción."""
        from programas.forms import RelevamientoForm

        html = str(RelevamientoForm()["territorial"])
        self.assertIn(f'data-segmento="{self.seg_a.pk}"', html)
        html_conv = str(RelevamientoForm()["convocatoria"])
        self.assertIn(f'data-segmento="{self.seg_a.pk}"', html_conv)
        self.assertIn(f'data-segmento="{self.seg_b.pk}"', html_conv)

    def test_reasignar_territorial(self):
        otro = User.objects.create_user("terri2", password="x")
        otro.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.seg_a, territorial=otro)
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_reasignar", args=[self.rel_a.pk]),
            {"territorial": otro.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.territorial, otro)

    def test_reasignar_a_territorial_de_otro_segmento_falla(self):
        """El combo de reasignación solo acepta territoriales del segmento del relevamiento."""
        terri_b = User.objects.create_user("terri_b2", password="x")
        terri_b.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.seg_b, territorial=terri_b)
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_reasignar", args=[self.rel_a.pk]),
            {"territorial": terri_b.pk},
        )
        self.assertEqual(resp.status_code, 302)  # redirige con mensaje de error
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.territorial, self.territorial)  # sin cambios

    def test_crear_con_next_vuelve_a_la_pantalla_de_origen(self):
        """El modal del detalle de convocatoria manda next para volver ahí tras crear."""
        self.client.force_login(self.admin)
        next_url = reverse("becas:convocatoria_detalle", args=[self.conv_a.pk])
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-20",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
                "next": next_url,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, next_url)
        self.assertTrue(Relevamiento.objects.filter(zona=self.localidad.nombre).exists())

    def test_next_externo_se_ignora(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.conv_a.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-20",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
                "next": "https://evil.example/phishing",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("becas:relevamientos"))

    def test_reprogramar(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("becas:relevamiento_reprogramar", args=[self.rel_a.pk]),
            {"fecha_asignada": "2026-09-15T14:00", "fecha_hasta": "2026-09-15T18:00"},
        )
        self.assertEqual(resp.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(timezone.localtime(self.rel_a.fecha_asignada).strftime("%Y-%m-%dT%H:%M"), "2026-09-15T14:00")
        self.assertEqual(timezone.localtime(self.rel_a.fecha_hasta).strftime("%Y-%m-%dT%H:%M"), "2026-09-15T18:00")

    def test_reprogramar_rechaza_horas_invertidas(self):
        form = ReprogramarForm(
            {"fecha_asignada": "2026-09-15T18:00", "fecha_hasta": "2026-09-15T14:00"},
            convocatoria=self.conv_a,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("anterior", form.errors["fecha_hasta"][0])

    def test_reprogramar_rechaza_fecha_fuera_de_convocatoria(self):
        form = ReprogramarForm(
            {"fecha_asignada": "2027-01-01"},
            convocatoria=self.conv_a,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("período de la convocatoria", form.errors["fecha_asignada"][0])
        self.assertEqual(form.fields["fecha_asignada"].widget.attrs["min"], "2026-01-01T00:00")
        self.assertEqual(form.fields["fecha_asignada"].widget.attrs["max"], "2026-12-31T23:59")

    def test_cupo_se_puede_aumentar(self):
        self.client.force_login(self.coord_a)

        respuesta = self.client.post(
            reverse("becas:relevamiento_modificar_cupo", args=[self.rel_a.pk]),
            {"cupo_maximo": 150},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.cupo_maximo, 150)

    def test_cupo_no_se_puede_reducir_por_debajo_de_personas_relevadas(self):
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624000000",
            email_contacto="persona@example.com",
        )
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624000001",
            email_contacto="otra@example.com",
        )
        self.rel_a.cupo_maximo = 5
        self.rel_a.save(update_fields=["cupo_maximo", "modificado"])
        self.client.force_login(self.coord_a)

        respuesta = self.client.post(
            reverse("becas:relevamiento_modificar_cupo", args=[self.rel_a.pk]),
            {"cupo_maximo": 1},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.cupo_maximo, 5)


class FinalizarReabrirTests(_BaseRelevTest):
    def test_finalizar_relevamiento_en_curso(self):
        self.rel_a.estado = Relevamiento.Estado.EN_CURSO
        self.rel_a.save(update_fields=["estado"])
        self.client.force_login(self.coord_a)

        response = self.client.post(reverse("becas:relevamiento_finalizar", args=[self.rel_a.pk]))

        self.assertRedirects(response, reverse("becas:relevamiento_detalle", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.FINALIZADO)
        self.assertIsNotNone(self.rel_a.fecha_finalizado)

    def test_finalizar_rechaza_estado_invalido(self):
        self.client.force_login(self.coord_a)

        self.client.post(reverse("becas:relevamiento_finalizar", args=[self.rel_a.pk]))

        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.ASIGNADO)
        self.assertIsNone(self.rel_a.fecha_finalizado)

    def _cerrar_relevamiento(self, estado, *, fecha_hasta=None):
        """Deja rel_a cerrado, con el período vigente salvo que se pida otro."""
        self.rel_a.estado = estado
        self.rel_a.fecha_finalizado = timezone.now()
        self.rel_a.fecha_hasta = fecha_hasta if fecha_hasta is not None else timezone.now() + timedelta(days=5)
        self.rel_a.save(update_fields=["estado", "fecha_finalizado", "fecha_hasta"])

    def test_volver_a_campo_desde_finalizado_con_periodo_vigente(self):
        self._cerrar_relevamiento(Relevamiento.Estado.FINALIZADO)
        self.client.force_login(self.coord_a)

        response = self.client.post(reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]))

        self.assertRedirects(response, reverse("becas:relevamiento_detalle", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_CURSO)
        self.assertIsNone(self.rel_a.fecha_finalizado)

    def test_volver_a_campo_desde_en_revision(self):
        """El caso que pidió el PM: a EN_REVISION se llega por fecha y hay vuelta."""
        self._cerrar_relevamiento(Relevamiento.Estado.EN_REVISION, fecha_hasta=timezone.now() - timedelta(days=1))
        self.client.force_login(self.coord_a)
        nueva = timezone.localtime(timezone.now() + timedelta(days=10))

        response = self.client.post(
            reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]),
            {"fecha_hasta": nueva.strftime("%Y-%m-%dT%H:%M")},
        )

        self.assertRedirects(response, reverse("becas:relevamiento_detalle", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_CURSO)
        self.assertIsNone(self.rel_a.fecha_finalizado)
        self.assertEqual(timezone.localtime(self.rel_a.fecha_hasta).date(), nueva.date())

    def test_volver_a_campo_vencido_sin_fecha_nueva_se_rechaza(self):
        """Sin fecha futura el cron lo devolvería a EN_REVISION esa noche."""
        self._cerrar_relevamiento(Relevamiento.Estado.EN_REVISION, fecha_hasta=timezone.now() - timedelta(days=1))
        self.client.force_login(self.coord_a)

        self.client.post(reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]))

        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)

    def test_volver_a_campo_rechaza_fecha_pasada(self):
        self._cerrar_relevamiento(Relevamiento.Estado.EN_REVISION, fecha_hasta=timezone.now() - timedelta(days=1))
        self.client.force_login(self.coord_a)
        pasada = timezone.localtime(timezone.now() - timedelta(days=2))

        self.client.post(
            reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]),
            {"fecha_hasta": pasada.strftime("%Y-%m-%dT%H:%M")},
        )

        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)

    def test_volver_a_campo_rechaza_convocatoria_cerrada(self):
        """Con la convocatoria cerrada el cron lo revierte igual: se bloquea."""
        self._cerrar_relevamiento(Relevamiento.Estado.EN_REVISION)
        self.conv_a.activo = False
        self.conv_a.save(update_fields=["activo"])
        self.client.force_login(self.coord_a)

        self.client.post(reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]))

        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)

    def test_volver_a_campo_rechaza_terminado(self):
        self._cerrar_relevamiento(Relevamiento.Estado.TERMINADO)
        self.client.force_login(self.coord_a)

        self.client.post(reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]))

        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.TERMINADO)

    def test_lo_que_vuelve_a_campo_no_lo_revierte_el_cron(self):
        """La razón de exigir fecha futura: la regla de vencimiento no lo agarra."""
        from programas.services.vencimientos import relevamientos_de_convocatoria_vencida

        self._cerrar_relevamiento(Relevamiento.Estado.EN_REVISION, fecha_hasta=timezone.now() - timedelta(days=1))
        self.client.force_login(self.coord_a)
        nueva = timezone.localtime(timezone.now() + timedelta(days=10))

        self.client.post(
            reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk]),
            {"fecha_hasta": nueva.strftime("%Y-%m-%dT%H:%M")},
        )

        self.assertNotIn(self.rel_a.pk, relevamientos_de_convocatoria_vencida().values_list("pk", flat=True))

    def test_acciones_solo_aceptan_post(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(
            self.client.get(reverse("becas:relevamiento_finalizar", args=[self.rel_a.pk])).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(reverse("becas:relevamiento_reabrir", args=[self.rel_a.pk])).status_code,
            405,
        )

    def test_coordinador_no_modifica_segmento_ajeno(self):
        self.rel_b.estado = Relevamiento.Estado.EN_CURSO
        self.rel_b.save(update_fields=["estado"])
        self.client.force_login(self.coord_a)

        response = self.client.post(reverse("becas:relevamiento_finalizar", args=[self.rel_b.pk]))

        self.assertEqual(response.status_code, 403)
        self.rel_b.refresh_from_db()
        self.assertEqual(self.rel_b.estado, Relevamiento.Estado.EN_CURSO)


class VencidoTests(_BaseRelevTest):
    def test_vence_por_hora(self):
        ahora = timezone.now()
        rel = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=ahora - timedelta(hours=2),
            fecha_hasta=ahora - timedelta(minutes=1),
            zona="Turno mañana",
            estado=Relevamiento.Estado.ASIGNADO,
        )

        self.assertTrue(rel.esta_vencido)

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


class ZonaDesdeCatalogoTests(_BaseRelevTest):
    """La zona sale del catálogo de localidades, acotada a la provincia operativa.

    El municipio solo filtra: no se guarda. Lo que queda en ``zona`` es el nombre
    de la localidad elegida.
    """

    def setUp(self):
        super().setUp()
        # Segundo municipio de Chaco: sirve para probar el cruce localidad/municipio.
        self.otro_municipio = Municipio.objects.create(nombre="Villa Ángela", provincia=self.provincia)
        self.localidad_otro_municipio = Localidad.objects.create(
            nombre="Coronel Du Graty", municipio=self.otro_municipio
        )
        # Provincia ajena: no tiene que aparecer en ningún selector.
        self.provincia_ajena = Provincia.objects.create(nombre="Corrientes")
        self.municipio_ajeno = Municipio.objects.create(nombre="Goya", provincia=self.provincia_ajena)
        self.localidad_ajena = Localidad.objects.create(nombre="Colonia Carolina", municipio=self.municipio_ajeno)

    def _datos(self, **cambios):
        datos = {
            "convocatoria": self.conv_a.pk,
            "territorial": self.territorial.pk,
            "fecha_asignada": "2026-07-05",
            "municipio": self.municipio.pk,
            "zona": self.localidad.pk,
        }
        datos.update(cambios)
        return datos

    def test_el_selector_de_municipios_es_solo_de_la_provincia_operativa(self):
        municipios = list(RelevamientoForm().fields["municipio"].queryset)

        self.assertIn(self.municipio, municipios)
        self.assertIn(self.otro_municipio, municipios)
        self.assertNotIn(self.municipio_ajeno, municipios)

    def test_guarda_el_nombre_de_la_localidad_elegida(self):
        self.client.force_login(self.admin)

        resp = self.client.post(reverse("becas:relevamiento_crear"), self._datos())

        self.assertEqual(resp.status_code, 302)
        nuevo = Relevamiento.objects.get(fecha_asignada=date(2026, 7, 5))
        self.assertEqual(nuevo.zona, self.localidad.nombre)

    def test_rechaza_una_localidad_que_no_es_del_municipio_elegido(self):
        """La cascada la ofrece bien, pero el POST se puede armar a mano."""
        form = RelevamientoForm(self._datos(zona=self.localidad_otro_municipio.pk))

        self.assertFalse(form.is_valid())
        self.assertIn("no pertenece al municipio elegido", form.errors["zona"][0])

    def test_rechaza_una_localidad_de_otra_provincia(self):
        form = RelevamientoForm(self._datos(municipio=self.municipio_ajeno.pk, zona=self.localidad_ajena.pk))

        self.assertFalse(form.is_valid())
        self.assertIn("municipio", form.errors)
        self.assertIn("zona", form.errors)

    def test_la_zona_es_obligatoria(self):
        form = RelevamientoForm(self._datos(zona=""))

        self.assertFalse(form.is_valid())
        self.assertIn("zona", form.errors)

    def test_el_select_de_localidad_llega_vacio_y_se_repuebla_al_volver_con_error(self):
        """Vacío en la carga (son cientos por provincia) y con las del municipio
        elegido cuando el form vuelve con errores, para no perder la selección."""
        vacio = str(RelevamientoForm()["zona"])
        self.assertIn("Elegí primero el municipio", vacio)
        self.assertNotIn(self.localidad.nombre, vacio)

        con_municipio = str(RelevamientoForm(self._datos(fecha_asignada=""))["zona"])
        self.assertIn(self.localidad.nombre, con_municipio)
        self.assertNotIn(self.localidad_otro_municipio.nombre, con_municipio)
