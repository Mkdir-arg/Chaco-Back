from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from programas.models import Merendero, Programa, SolicitudMerendero
from programas.services.merenderos import aprobar_solicitud, guardar_prestacion


class MerenderosServiceTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="operador-merenderos")

    def solicitud(self, *, documentacion="respaldo.pdf"):
        return SolicitudMerendero.objects.create(
            codigo="MER-ACEPT-01",
            nombre="Merendero Horizonte",
            domicilio="Calle 10 123",
            zona="Norte",
            barrio="San Martín",
            dias_horarios="Lunes a viernes, 16 a 19",
            responsable_nombre="María Pérez",
            documentacion=documentacion,
            estado=SolicitudMerendero.Estado.EN_REVISION,
        )

    def test_aprobar_solicitud_documentada_crea_un_unico_merendero_activo(self):
        solicitud = self.solicitud()

        merendero = aprobar_solicitud(solicitud, self.usuario)

        solicitud.refresh_from_db()
        self.assertEqual(merendero.estado, Merendero.Estado.ACTIVO)
        self.assertEqual(merendero.codigo, "MER-ACEPT-01")
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.APROBADA)
        self.assertEqual(solicitud.merendero, merendero)
        self.assertEqual(solicitud.validada_por, self.usuario)
        self.assertIsNotNone(solicitud.validada_en)
        self.assertEqual(Merendero.objects.count(), 1)

    def test_no_aprueba_solicitud_sin_documentacion(self):
        solicitud = self.solicitud(documentacion="")

        with self.assertRaisesMessage(ValidationError, "documentación respaldatoria"):
            aprobar_solicitud(solicitud, self.usuario)

        self.assertEqual(Merendero.objects.count(), 0)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)

    def test_f02_febrero_bisiesto_genera_dias_reales_y_firma(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-02",
            nombre="Rayito de Sol",
            domicilio="Av. Siempre Viva 742",
            responsable_nombre="Juan Gómez",
        )

        prestacion = guardar_prestacion(
            merendero,
            anio=2024,
            mes=2,
            raciones={29: {"DESAYUNO": 20, "ALMUERZO": 30}},
            observaciones={29: "Jornada especial"},
            usuario=self.usuario,
        )

        self.assertEqual(prestacion.lineas_diarias.count(), 29 * 4)
        self.assertEqual(prestacion.total_del_dia(29), 50)
        self.assertEqual(prestacion.lineas_diarias.filter(dia=29, firmado_por=self.usuario).count(), 4)
        self.assertEqual(prestacion.observacion_del_dia(29), "Jornada especial")

    def test_f02_reabre_el_mismo_mes_sin_duplicar_lineas(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-03",
            nombre="Manos Unidas",
            domicilio="Mitre 321",
            responsable_nombre="Ana Díaz",
        )

        primera = guardar_prestacion(merendero, anio=2026, mes=4, raciones={1: {"CENA": 4}}, usuario=self.usuario)
        segunda = guardar_prestacion(merendero, anio=2026, mes=4, raciones={1: {"CENA": 7}}, usuario=self.usuario)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.lineas_diarias.count(), 30 * 4)
        self.assertEqual(segunda.total_del_dia(1), 7)


class MerenderosViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(username="admin-merenderos", password="test")
        Programa.objects.create(
            codigo="MERENDEROS",
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.client.force_login(self.usuario)

    def solicitud_sin_documentacion(self):
        return SolicitudMerendero.objects.create(
            codigo="MER-SIN-DOC",
            nombre="Sin respaldo",
            domicilio="Calle 1",
            zona="Centro",
            barrio="Centro",
            dias_horarios="Lunes",
            responsable_nombre="Responsable",
            estado=SolicitudMerendero.Estado.EN_REVISION,
        )

    def test_post_directo_no_aprueba_solicitud_sin_documentacion(self):
        solicitud = self.solicitud_sin_documentacion()

        response = self.client.post(reverse("merenderos:solicitud_resolver", args=[solicitud.pk, "aprobar"]))

        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)
        self.assertFalse(Merendero.objects.filter(codigo="MER-SIN-DOC").exists())

    def test_post_prestacion_calcula_lineas_del_mes_y_no_acepta_total_manipulado(self):
        merendero = Merendero.objects.create(
            codigo="MER-F02-01", nombre="F02", domicilio="Calle 2", responsable_nombre="Responsable"
        )

        response = self.client.post(
            reverse("merenderos:prestacion", args=[merendero.pk]),
            {
                "anio": "2025",
                "mes": "2",
                "raciones-1-DESAYUNO": "20",
                "raciones-1-ALMUERZO": "30",
                "total-1": "9999",
            },
        )

        self.assertEqual(response.status_code, 302)
        prestacion = merendero.prestaciones_mensuales.get(anio=2025, mes=2)
        self.assertEqual(prestacion.lineas_diarias.count(), 28 * 4)
        self.assertEqual(prestacion.total_del_dia(1), 50)
