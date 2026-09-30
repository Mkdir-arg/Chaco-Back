"""Piezas comunes de diseño (Ola 3, P-F) en las pantallas de Relevamientos.

TIT-8 (encabezado en dos columnas con bajada y Pausar/Reanudar), ALR-11/ALR-14
(alertas con borde y ``role="alert"``), el modal de alta con ``x-becas-modal``
y los parciales canónicos, la tabla ``.nodo-*``/``.nodo-icon-btn`` y el
``?next=`` al caso.
"""

from datetime import date, datetime
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Localidad, Municipio, Provincia
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AsignacionCoordinador,
    AsignacionTerritorial,
    Convocatoria,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
)


class _Base(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(nombre="Becas de Educación Superior", siis_programa_id=38)
        self.segmento = Segmento.objects.create(
            nombre="Estudiantes universitarios", cupo_maximo=100, programa=self.programa
        )
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas Terciarias 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))

        self.coord = User.objects.create_user("coord_a", password="x")
        self.coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coord)

        self.territorial = User.objects.create_user("mgomez", password="x", first_name="Marcela", last_name="Gómez")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.segmento, territorial=self.territorial)

        self.provincia, _ = Provincia.objects.get_or_create(nombre="Chaco")
        self.municipio, _ = Municipio.objects.get_or_create(nombre="Resistencia", provincia=self.provincia)
        self.localidad, _ = Localidad.objects.get_or_create(nombre="Barranqueras", municipio=self.municipio)

        # Mediodía local: evita que la conversión de huso horario del filtro
        # ``date`` corra la fecha mostrada al día anterior (TIME_ZONE UTC-3).
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.make_aware(datetime(2026, 6, 1, 12, 0)),
            fecha_hasta=timezone.make_aware(datetime(2026, 6, 10, 12, 0)),
            zona="Barrio Güiraldes · Resistencia",
        )


class EncabezadoRelevamientoDetalleTests(_Base):
    """TIT-8: page_header en dos columnas con bajada, badges y Pausar/Reanudar."""

    def test_bajada_muestra_convocatoria_territorial_y_fechas(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, "Convocatoria")
        self.assertContains(
            resp,
            f'<a href="{reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])}"'
            ' class="text-fg-brand hover:underline font-medium">Becas Terciarias 2026</a>',
            html=False,
        )
        self.assertContains(resp, "Territorial: Marcela Gómez")
        self.assertContains(resp, "Del 01/06 al 10/06/2026")

    def test_migas_de_pan_con_cuatro_niveles(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, 'aria-label="Migas"')
        self.assertContains(resp, self.programa.nombre)
        self.assertContains(resp, self.segmento.nombre)

    def test_boton_pausar_sin_icono(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, "Pausar")
        self.assertNotContains(resp, "fa-play")

    def test_boton_reanudar_con_fa_play(self):
        self.relevamiento.pausado = True
        self.relevamiento.save(update_fields=["pausado"])
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, '<i class="fas fa-play" aria-hidden="true"></i> Reanudar')

    def test_tabs_admiten_flex_wrap(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, 'class="border-b border-base flex gap-1 px-2 flex-wrap"')


class TablaCasosRelevamientoDetalleTests(_Base):
    """Tabla .nodo-*, acciones .nodo-icon-btn con aria-label y ?next= al caso."""

    def setUp(self):
        super().setUp()
        self.formulario = Formulario.objects.create(relevamiento=self.relevamiento, celular="3624100100")

    def test_tabla_usa_clases_nodo(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]), {"tab": "formularios"}
        )
        self.assertContains(resp, "nodo-thead-row")
        self.assertContains(resp, "nodo-th")
        self.assertContains(resp, "nodo-td")

    def test_link_al_caso_lleva_next_e_icono_con_aria_label(self):
        self.client.force_login(self.admin)
        url = reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk])
        resp = self.client.get(url, {"tab": "formularios"})
        esperado_next = f"?next=/becas/relevamientos/{self.relevamiento.pk}/%3Ftab%3Dformularios"
        self.assertContains(resp, esperado_next)
        self.assertContains(resp, 'class="nodo-icon-btn" aria-label="Ver caso de persona sin identificar"')


class AlertasRelevamientoFormTests(_Base):
    """ALR-11 (non_field_errors con borde y role=alert) y ALR-14 (solapamiento, variante A)."""

    def test_solapamiento_usa_variante_a(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "convocatoria": self.convocatoria.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-06-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            'class="mb-4 rounded-lg bg-warning-soft border border-warning-subtle p-4 text-sm text-fg-warning" role="alert"',
        )

    def test_non_field_errors_con_borde_y_rol_alert(self):
        self.client.force_login(self.coord)
        resp = self.client.post(
            reverse("becas:relevamiento_crear"),
            {
                "tipo": "PUBLICO",
                "convocatoria": self.convocatoria.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            'class="mb-4 rounded-lg bg-danger-soft border border-danger-subtle p-4 text-sm text-fg-danger" role="alert"',
        )
        self.assertContains(resp, "No tenés permiso para crear relevamientos de formulario público.")


class ModalAltaRelevamientoListTests(_Base):
    """El modal de alta (no AJAX) con x-becas-modal y los parciales canónicos."""

    def test_modal_usa_x_becas_modal_y_parciales_accesibles(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertContains(resp, 'x-becas-modal="modalRel"')
        self.assertContains(resp, 'role="dialog" aria-modal="true" aria-labelledby="modal-rel-titulo"')
        self.assertContains(resp, 'id="modal-rel-titulo"')
        self.assertContains(resp, "custom/js/becas-modal.js")

    def test_tabla_de_relevamientos_usa_nodo_icon_btn(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:relevamientos"))
        self.assertContains(resp, f'class="nodo-icon-btn" aria-label="Ver {self.relevamiento.nombre}"')
        self.assertContains(resp, "nodo-thead-row")
