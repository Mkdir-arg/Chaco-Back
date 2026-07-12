from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Localidad, Municipio, Provincia
from legajos.models import Ciudadano
from legajos.services import DerivacionProgramaService
from programas.models import DerivacionPrograma, Programa


class DerivacionProgramaServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operador-programa",
            password="clave-segura-123",
            is_staff=True,
        )
        self.provincia = Provincia.objects.create(nombre="Chaco")
        self.municipio = Municipio.objects.create(
            nombre="Resistencia",
            provincia=self.provincia,
        )
        self.localidad = Localidad.objects.create(
            nombre="Centro",
            municipio=self.municipio,
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="30999111",
            nombre="Ana",
            apellido="Paz",
            telefono="3624000000",
            municipio=self.municipio,
            localidad=self.localidad,
        )
        self.programa = Programa.objects.create(
            codigo="ACOMP-001",
            nombre="Programa de Acompañamiento",
            tipo=Programa.TipoPrograma.ACOMPANAMIENTO_SOCIAL,
            descripcion="Programa de asistencia",
            estado=Programa.Estado.ACTIVO,
        )
        self.derivacion = DerivacionPrograma.objects.create(
            ciudadano=self.ciudadano,
            programa_destino=self.programa,
            motivo="Derivación por seguimiento",
            urgencia=DerivacionPrograma.Urgencia.MEDIA,
            derivado_por=self.user,
        )

    def test_accept_derivacion_marks_derivacion_as_accepted(self):
        result = DerivacionProgramaService.accept_derivacion(
            derivacion_id=self.derivacion.id,
            usuario=self.user,
        )

        self.derivacion.refresh_from_db()

        self.assertEqual(result.status, "success")
        self.assertEqual(self.derivacion.estado, DerivacionPrograma.Estado.ACEPTADA)

    def test_reject_derivacion_marks_derivacion_as_rejected(self):
        result = DerivacionProgramaService.reject_derivacion(
            derivacion_id=self.derivacion.id,
            usuario=self.user,
            motivo_rechazo="Rechazado desde bandeja de derivaciones",
        )

        self.derivacion.refresh_from_db()

        self.assertEqual(result.status, "success")
        self.assertEqual(self.derivacion.estado, DerivacionPrograma.Estado.RECHAZADA)
