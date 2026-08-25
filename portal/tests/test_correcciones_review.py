"""Tests de las correcciones de la revisión de código del formulario público
(Fase 5, Historial del Cambio 40). Cada test reproduce el bug que se corrigió."""

from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from portal.forms.inscripcion import InscripcionPaso2Form
from portal.tests.test_inscripcion import _BaseInscripcionTest, _tolerar_render_local
from portal.tests.test_inscripcion_envio import _BasePaso2Test, _identificacion
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services import reportes_becas
from programas.services.inscripcion_publica import InscripcionNoHabilitada, crear_formulario_publico
from programas.services.padron import cargar_padron, parsear_padron
from programas.services.personas import fecha_iso, normalizar_persona
from programas.views import relevamientos as vistas_rel
from programas.views.revision import RenaperPendientesListView


def _xlsx(filas):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(list(fila))
    buffer = BytesIO()
    libro.save(buffer)
    return SimpleUploadedFile("padron.xlsx", buffer.getvalue())


class ReporteProduccionConPublicosTests(TestCase):
    def test_un_publico_no_rompe_el_reporte_ni_aparece(self):
        admin = User.objects.create_superuser("root", "r@r.com", "x")
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        terri = User.objects.create_user("terri", password="x", first_name="Tere", last_name="Campo")
        Relevamiento.objects.create(convocatoria=conv, territorial=terri, fecha_asignada=timezone.now(), zona="Z")
        Relevamiento.objects.create(
            convocatoria=conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        reporte = reportes_becas.reporte_produccion(admin)  # antes: AttributeError → 500
        territoriales = [fila[0] for fila in reporte.filas]
        self.assertEqual(territoriales, ["Tere Campo"])


class RateLimitDevuelveMensajeTests(_BaseInscripcionTest):
    @patch("portal.views.inscripcion.consultar_persona")
    def test_rate_limit_no_es_un_500(self, mock_consulta):
        with patch("portal.views.inscripcion.paso1_excedido", return_value=True):
            try:
                resp = self._post_paso1()
            except AttributeError as exc:
                _tolerar_render_local(exc)  # antes: 'cleaned_data' → 500
                return
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "demasiados intentos")
        mock_consulta.assert_not_called()


class PendientesRenaperConPublicosTests(TestCase):
    def setUp(self):
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        publico = Relevamiento.objects.create(
            convocatoria=conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        Formulario.objects.create(
            relevamiento=publico, celular="1", email_contacto="a@a.com", datos_identificacion={"dni": "1"}
        )

    def test_el_selector_no_ofrece_territorial_none(self):
        base = Formulario.objects.filter(validado_renaper=False)
        opciones = list(RenaperPendientesListView.territoriales_pendientes(base))
        self.assertEqual(opciones, [])

    def test_filtro_territorial_invalido_no_rompe(self):
        vista = RenaperPendientesListView()
        vista.request = RequestFactory().get("/?territorial=None&segmento=abc")
        vista.request.user = User.objects.create_user("admin_publicos")
        with patch("programas.views.revision.puede", return_value=True):
            self.assertEqual(vista.get_queryset().count(), 1)


class FechaNoIsoTests(_BasePaso2Test):
    def test_fecha_iso_normaliza_formatos_de_proveedor(self):
        self.assertEqual(fecha_iso("15/03/2010"), "2010-03-15")
        self.assertEqual(fecha_iso("2010-03-15"), "2010-03-15")
        self.assertEqual(fecha_iso("2010-03-15T00:00:00"), "2010-03-15")
        self.assertEqual(fecha_iso("20100315"), "2010-03-15")
        self.assertEqual(fecha_iso(date(2010, 3, 15)), "2010-03-15")
        self.assertEqual(fecha_iso("sin fecha"), "")
        self.assertEqual(normalizar_persona({"data": {"fechaNacimiento": "15/03/2010"}}, "1")["fecha_nacimiento"], "2010-03-15")

    def test_menor_con_fecha_dd_mm_aaaa_exige_apoderado(self):
        hoy = timezone.localdate()
        nacimiento = hoy - timedelta(days=16 * 365)
        ident = _identificacion()
        ident["datos"]["fecha_nacimiento"] = nacimiento.strftime("%d/%m/%Y")
        form = InscripcionPaso2Form(
            self._data(), self._files(), definicion=self.definicion, identificacion=ident
        )
        self.assertFalse(form.is_valid())  # antes: parse_date → None → RN-22 salteada
        self.assertIn("apoderado_dni", form.errors)


class GateEnScopesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sin_publico", password="x")
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.publico = Relevamiento.objects.create(
            convocatoria=conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        self.territorial = Relevamiento.objects.create(
            convocatoria=conv, territorial=self.user, fecha_asignada=timezone.now(), zona="Z"
        )
        self.request = RequestFactory().post("/")
        self.request.user = self.user

    def test_assert_scope_bloquea_publicos_sin_capacidad(self):
        # Con alcance sobre el segmento pero sin la capacidad de público.
        with patch.object(vistas_rel, "puede_gestionar_segmento", return_value=True), patch.object(
            vistas_rel, "convocatorias_visibles"
        ) as visibles, patch.object(vistas_rel, "_puede_publico", return_value=False):
            visibles.return_value.filter.return_value.exists.return_value = True
            vistas_rel._assert_scope(self.request, self.territorial)  # pasa
            with self.assertRaises(PermissionDenied):
                vistas_rel._assert_scope(self.request, self.publico)  # antes: pasaba y mutaba


class PadronFloatsTests(TestCase):
    def test_dni_float_y_largo_invalido(self):
        entradas, rechazadas = parsear_padron(_xlsx([("documento", "sexo"), (30123456.0, "M"), (301234560, "F"), ("28.111.222", "f")]))
        self.assertEqual(entradas, [("30123456", "M"), ("28111222", "F")])
        self.assertEqual(rechazadas, 1)  # el de 9 dígitos


class PadronSeRechequeaAlEnviarTests(_BasePaso2Test):
    def test_reemplazo_entre_pasos_bloquea_el_envio(self):
        ident = _identificacion()
        form = InscripcionPaso2Form(self._data(), self._files(), definicion=self.definicion, identificacion=ident)
        self.assertTrue(form.is_valid(), form.errors)
        cargar_padron(self.relevamiento, None, [("11111111", "M")])  # María ya no figura
        with self.assertRaises(InscripcionNoHabilitada):
            crear_formulario_publico(self.relevamiento, identificacion=ident, form=form, client_uuid=str(uuid4()))
        self.assertEqual(self.relevamiento.formularios.count(), 0)


class TokenAlCambiarTipoTests(TestCase):
    def test_territorial_convertido_a_publico_recibe_token(self):
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        terri = User.objects.create_user("terri", password="x")
        rel = Relevamiento.objects.create(convocatoria=conv, territorial=terri, fecha_asignada=timezone.now(), zona="Z")
        self.assertIsNone(rel.token_publico)
        rel.tipo = Relevamiento.Tipo.PUBLICO
        rel.territorial = None
        rel.zona = ""
        rel.save()
        rel.refresh_from_db()
        self.assertIsNotNone(rel.token_publico)  # antes: link vacío
        self.assertTrue(rel.url_publica)
