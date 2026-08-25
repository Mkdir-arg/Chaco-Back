"""Regresiones de la segunda revision del formulario publico de Becas (Fase 6)."""

from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from portal.services import inscripcion as servicio
from portal.tests.test_inscripcion import DATOS_GRAN_BASE, _BaseInscripcionTest, _tolerar_render_local
from portal.tests.test_inscripcion_envio import _BasePaso2Test, _identificacion
from programas.admin import RelevamientoAdmin
from programas.forms import RelevamientoForm
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services.inscripcion_publica import crear_formulario_publico
from programas.views import relevamientos as vistas_rel
from programas.views import revision as vistas_rev
from programas.views.relevamientos import ConvocatoriaDetailView
from programas.views.revision import RevisionPersonasListView


def _xlsx(filas):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(list(fila))
    buffer = BytesIO()
    libro.save(buffer)
    return SimpleUploadedFile("padron.xlsx", buffer.getvalue())


class RateLimitHeaderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()

    def test_x_real_ip_prevalece_sobre_x_forwarded_for(self):
        req1 = self.rf.post("/", HTTP_X_REAL_IP="10.0.0.1", HTTP_X_FORWARDED_FOR="1.1.1.1")
        req2 = self.rf.post("/", HTTP_X_REAL_IP="10.0.0.1", HTTP_X_FORWARDED_FOR="2.2.2.2")
        with patch.object(servicio, "MAX_INTENTOS_IP", 1):
            self.assertFalse(servicio.paso1_excedido(req1))
            self.assertTrue(servicio.paso1_excedido(req2))

    def test_x_forwarded_for_usa_el_ultimo_valor_si_no_hay_x_real_ip(self):
        req1 = self.rf.post("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 10.0.0.9")
        req2 = self.rf.post("/", HTTP_X_FORWARDED_FOR="2.2.2.2, 10.0.0.9")
        with patch.object(servicio, "MAX_INTENTOS_IP", 1):
            self.assertFalse(servicio.paso1_excedido(req1))
            self.assertTrue(servicio.paso1_excedido(req2))


class CaptchaConsumeTests(_BaseInscripcionTest):
    @patch("portal.views.inscripcion.consultar_persona", return_value=DATOS_GRAN_BASE)
    def test_captcha_correcto_se_consume_y_no_se_reutiliza(self, mock_consulta):
        primero = self._post_paso1()
        self.assertEqual(primero.status_code, 302)
        try:
            self.client.post(self._url(), {"dni": "28111222", "sexo": "F", "captcha": "7"})
        except AttributeError as exc:
            _tolerar_render_local(exc)
        mock_consulta.assert_called_once_with("30123456", "F")


class IdempotenciaUuidTextoTests(_BasePaso2Test):
    def _form_valido(self, ident):
        form = self._form(identificacion=ident)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_client_uuid_string_con_guiones_es_idempotente(self):
        client_uuid = str(uuid4())
        ident = _identificacion(client_uuid=client_uuid)
        primero, creado1 = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=client_uuid
        )
        segundo, creado2 = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=client_uuid
        )
        self.assertTrue(creado1)
        self.assertFalse(creado2)
        self.assertEqual(primero.pk, segundo.pk)


class ScopeRevalidarRenaperTests(TestCase):
    def test_revalidar_renaper_bloquea_formulario_publico_sin_capacidad(self):
        user = User.objects.create_user("operador")
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        rel = Relevamiento.objects.create(
            convocatoria=conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        formulario = Formulario.objects.create(relevamiento=rel, celular="1", email_contacto="a@a.com")
        request = RequestFactory().post("/")
        request.user = user
        with patch.object(vistas_rev, "puede", return_value=False):
            with self.assertRaises(PermissionDenied):
                vistas_rev.formulario_revalidar_renaper.__wrapped__.__wrapped__(request, formulario.pk)


class FechaProveedorYApoderadoTests(_BasePaso2Test):
    def test_personas_sin_fecha_normalizada_exige_fecha_y_apoderado_si_es_menor(self):
        hoy = timezone.localdate()
        ident = _identificacion()
        ident["datos"]["fecha_nacimiento"] = "texto raro"
        data = self._data(fecha_nacimiento=(hoy - timedelta(days=16 * 365)).isoformat())
        form = self._form(identificacion=ident, data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_nacimiento", form.fields)
        self.assertIn("apoderado_dni", form.errors)

    def test_personas_sin_fecha_guarda_la_fecha_del_form(self):
        ident = _identificacion()
        ident["datos"]["fecha_nacimiento"] = "texto raro"
        data = self._data(
            fecha_nacimiento="1990-01-01",
            apoderado_dni="30.123.456",
        )
        form = self._form(identificacion=ident, data=data)
        self.assertTrue(form.is_valid(), form.errors)
        formulario, _ = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=form, client_uuid=ident["client_uuid"]
        )
        self.assertEqual(formulario.ciudadano.fecha_nacimiento.isoformat(), "1990-01-01")

    def test_apoderado_dni_se_normaliza_tambien_en_adultos(self):
        form = self._form(data=self._data(apoderado_dni="30.123.456"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["apoderado_dni"], "30123456")
        invalido = self._form(data=self._data(apoderado_dni="abc"))
        self.assertFalse(invalido.is_valid())
        self.assertIn("apoderado_dni", invalido.errors)


class PadronAtomicidadTests(TestCase):
    def test_si_falla_carga_de_padron_no_queda_relevamiento_publico(self):
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        data = {
            "tipo": Relevamiento.Tipo.PUBLICO,
            "convocatoria": conv.pk,
            "fecha_asignada": "2026-06-01T10:00",
            "fecha_hasta": "2026-06-30T18:00",
            "cupo_maximo": "10",
            "confirmar_por_email": "on",
        }
        form = RelevamientoForm(data, {"padron": _xlsx([("documento", "sexo"), ("30123456", "F")])}, puede_publico=True)
        self.assertTrue(form.is_valid(), form.errors)
        inicial = Relevamiento.objects.count()
        with patch("programas.services.padron.PadronHabilitado.objects.bulk_create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                form.save()
        self.assertEqual(Relevamiento.objects.count(), inicial)


class ListadosPublicosScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operador")
        self.seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        terr = User.objects.create_user("terr")
        self.rel_territorial = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=terr, fecha_asignada=timezone.now(), zona="Z"
        )
        self.rel_publico = Relevamiento.objects.create(
            convocatoria=self.conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
            fecha_hasta=timezone.now() + timedelta(days=5),
        )
        self.form_territorial = Formulario.objects.create(
            relevamiento=self.rel_territorial, celular="1", email_contacto="t@a.com", validado_renaper=False
        )
        self.form_publico = Formulario.objects.create(
            relevamiento=self.rel_publico, celular="1", email_contacto="p@a.com", validado_renaper=False
        )

    def test_revision_personas_excluye_publicos_sin_capacidad(self):
        view = RevisionPersonasListView()
        view.request = RequestFactory().get("/")
        view.request.user = self.user
        with (
            patch.object(vistas_rev, "convocatorias_visibles", return_value=Convocatoria.objects.all()),
            patch.object(vistas_rev, "puede", return_value=False),
        ):
            self.assertEqual(list(view.get_queryset()), [self.form_territorial])

    def test_beneficiarios_y_export_excluyen_publicos_sin_capacidad(self):
        self.form_territorial.estado = Formulario.Estado.APROBADO
        self.form_territorial.save(update_fields=["estado"])
        self.form_publico.estado = Formulario.Estado.APROBADO
        self.form_publico.save(update_fields=["estado"])
        request = RequestFactory().get("/")
        request.user = self.user

        view = ConvocatoriaDetailView()
        view.request = request
        view.object = self.conv
        with (
            patch.object(vistas_rel, "_puede_publico", return_value=False),
            patch.object(vistas_rel, "segmentos_visibles", return_value=Segmento.objects.all()),
            patch.object(vistas_rel, "convocatorias_visibles", return_value=Convocatoria.objects.all()),
            patch.object(vistas_rel, "subsegmentos_visibles", return_value=[]),
            patch.object(vistas_rel, "usuarios_territoriales_becas", return_value=User.objects.none()),
        ):
            ctx = view.get_context_data()
            self.assertEqual(ctx["n_beneficiarios"], 1)
            response = vistas_rel.convocatoria_export_beneficiarios.__wrapped__.__wrapped__(request, self.conv.pk)
        filas = response.content.decode("utf-8").splitlines()
        self.assertEqual(len(filas), 2)


class RelevamientoAdminTests(TestCase):
    def test_tipo_es_readonly_solo_al_editar(self):
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        conv = Convocatoria.objects.create(
            nombre="Conv", segmento=seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        terr = User.objects.create_user("terr_admin")
        rel = Relevamiento.objects.create(convocatoria=conv, territorial=terr, fecha_asignada=timezone.now(), zona="Z")
        admin = RelevamientoAdmin(Relevamiento, AdminSite())
        request = RequestFactory().get("/")
        self.assertNotIn("tipo", admin.get_readonly_fields(request, obj=None))
        self.assertIn("tipo", admin.get_readonly_fields(request, obj=rel))
