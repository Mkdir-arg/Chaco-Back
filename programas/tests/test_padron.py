"""Tests del padrón de habilitados por Excel (#299, análisis #289)."""

from datetime import date
from io import BytesIO, StringIO

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.forms import RelevamientoForm
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, PadronHabilitado, Relevamiento, Segmento
from programas.services.padron import cargar_padron, esta_habilitado, parsear_padron
from programas.tests.test_relevamiento_publico import _dar_capacidad_publico

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(filas, nombre="padron.xlsx"):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    buffer = BytesIO()
    libro.save(buffer)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=XLSX_MIME)


class _BasePadronTest(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )


class ParserPadronTests(TestCase):
    def test_parsea_filas_validas_y_reporta_rechazadas(self):
        archivo = _xlsx(
            [
                ("documento", "sexo"),  # encabezado: se saltea
                ("30.123.456", "f"),
                (28111222, "MASCULINO"),
                ("", "F"),  # sin dni: rechazada
                ("27000111", "Z"),  # sexo inválido: rechazada
                ("30123456", "M"),  # dni duplicado: rechazada
            ]
        )
        entradas, rechazadas = parsear_padron(archivo)
        self.assertEqual(entradas, [("30123456", "F"), ("28111222", "M")])
        self.assertEqual(rechazadas, 3)

    def test_sin_encabezado_tambien_funciona(self):
        entradas, rechazadas = parsear_padron(_xlsx([("30123456", "F")]))
        self.assertEqual(entradas, [("30123456", "F")])
        self.assertEqual(rechazadas, 0)

    def test_extension_invalida(self):
        archivo = SimpleUploadedFile("padron.csv", b"30123456,F", content_type="text/csv")
        with self.assertRaises(ValidationError):
            parsear_padron(archivo)

    def test_contenido_no_excel(self):
        archivo = SimpleUploadedFile("padron.xlsx", b"esto no es un excel", content_type=XLSX_MIME)
        with self.assertRaises(ValidationError):
            parsear_padron(archivo)

    def test_sin_filas_validas(self):
        with self.assertRaises(ValidationError):
            parsear_padron(_xlsx([("documento", "sexo"), ("", "")]))


class EstaHabilitadoTests(_BasePadronTest):
    def test_sin_padron_el_link_es_abierto(self):
        self.assertTrue(esta_habilitado(self.relevamiento, "99999999", "F"))

    def test_matchea_con_normalizacion_en_ambos_sentidos(self):
        cargar_padron(self.relevamiento, None, [("30123456", "F")])
        self.assertTrue(esta_habilitado(self.relevamiento, "30.123.456", "femenino"))
        self.assertFalse(esta_habilitado(self.relevamiento, "30123456", "M"))
        self.assertFalse(esta_habilitado(self.relevamiento, "11111111", "F"))

    def test_reemplazo_total_con_efecto_inmediato(self):
        cargar_padron(self.relevamiento, None, [("30123456", "F")])
        cargar_padron(self.relevamiento, None, [("28111222", "M")])
        self.assertFalse(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertTrue(esta_habilitado(self.relevamiento, "28111222", "M"))
        self.assertEqual(self.relevamiento.padron.count(), 1)


class FormConPadronTests(_BasePadronTest):
    def _data(self):
        return {
            "tipo": Relevamiento.Tipo.PUBLICO,
            "convocatoria": self.convocatoria.pk,
            "fecha_asignada": "2026-07-01T08:00",
            "fecha_hasta": "2026-07-31T18:00",
        }

    def test_alta_con_padron_crea_entradas_y_resumen(self):
        form = RelevamientoForm(
            data=self._data(),
            files={"padron": _xlsx([("documento", "sexo"), ("30123456", "F"), ("bad", ""), ("28111222", "m")])},
            puede_publico=True,
        )
        self.assertTrue(form.is_valid(), form.errors)
        rel = form.save()
        self.assertEqual(rel.padron.count(), 2)
        self.assertEqual(form.padron_resumen, (2, 1))
        self.assertTrue(rel.padron_archivo)

    def test_alta_sin_padron_queda_abierta(self):
        form = RelevamientoForm(data=self._data(), puede_publico=True)
        self.assertTrue(form.is_valid(), form.errors)
        rel = form.save()
        self.assertEqual(rel.padron.count(), 0)
        self.assertTrue(esta_habilitado(rel, "1234567", "F"))

    def test_archivo_invalido_rechaza_el_alta(self):
        form = RelevamientoForm(
            data=self._data(),
            files={"padron": SimpleUploadedFile("p.xlsx", b"no excel", content_type=XLSX_MIME)},
            puede_publico=True,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("padron", form.errors)
        self.assertFalse(Relevamiento.objects.filter(pk__isnull=False, tipo="PUBLICO", padron__isnull=False).exists())


class ReemplazoPadronViewTests(_BasePadronTest):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        grupo_admin = Group.objects.get(name=ROL_ADMIN)
        self.admin_publico = User.objects.create_user("admin_pub", password="x")
        self.admin_publico.groups.add(grupo_admin)
        _dar_capacidad_publico(grupo_admin)
        self.admin_sin = User.objects.create_user("admin_sin", password="x")

    def _url(self):
        return reverse("becas:relevamiento_padron", args=[self.relevamiento.pk])

    def test_reemplazo_ok(self):
        self.client.force_login(self.admin_publico)
        resp = self.client.post(self._url(), {"padron": _xlsx([("30123456", "F")])})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(esta_habilitado(self.relevamiento, "30123456", "F"))

    def test_sin_capacidad_no_puede(self):
        self.client.force_login(self.admin_sin)
        resp = self.client.post(self._url(), {"padron": _xlsx([("30123456", "F")])})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.relevamiento.padron.count(), 0)

    def test_no_aplica_a_territoriales(self):
        terr_user = User.objects.create_user("terr")
        rel_terr = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=terr_user,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona",
        )
        self.client.force_login(self.admin_publico)
        self.client.post(reverse("becas:relevamiento_padron", args=[rel_terr.pk]), {"padron": _xlsx([("1234567", "F")])})
        self.assertEqual(PadronHabilitado.objects.filter(relevamiento=rel_terr).count(), 0)
