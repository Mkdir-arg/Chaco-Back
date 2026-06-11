from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Localidad, Municipio, Provincia
from legajos.models import Ciudadano
from legajos.models_nachec import CasoNachec, EstadoCaso, HistorialEstadoCaso, TareaNachec
from legajos.models_programas import DerivacionPrograma, Programa
from legajos.services import DerivacionProgramaService


class DerivacionProgramaServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operador-programa',
            password='clave-segura-123',
            is_staff=True,
        )
        self.provincia = Provincia.objects.create(nombre='Chaco')
        self.municipio = Municipio.objects.create(
            nombre='Resistencia',
            provincia=self.provincia,
        )
        self.localidad = Localidad.objects.create(
            nombre='Centro',
            municipio=self.municipio,
        )
        self.ciudadano = Ciudadano.objects.create(
            dni='30999111',
            nombre='Ana',
            apellido='Paz',
            telefono='3624000000',
            municipio=self.municipio,
            localidad=self.localidad,
        )
        self.programa = Programa.objects.create(
            codigo='NAC-001',
            nombre='Programa Ñachec',
            tipo=Programa.TipoPrograma.NACHEC,
            descripcion='Programa de asistencia',
            estado=Programa.Estado.ACTIVO,
        )
        self.derivacion = DerivacionPrograma.objects.create(
            ciudadano=self.ciudadano,
            programa_destino=self.programa,
            motivo='Derivación por seguimiento',
            urgencia=DerivacionPrograma.Urgencia.MEDIA,
            derivado_por=self.user,
        )

    def test_build_nachec_acceptance_context_detects_validations_and_duplicates(self):
        CasoNachec.objects.create(
            ciudadano_titular=self.ciudadano,
            estado=EstadoCaso.EN_REVISION,
            municipio='Resistencia',
            localidad='Centro',
            direccion='Calle 123',
            fecha_derivacion='2026-03-13',
            motivo_derivacion='Ingreso previo',
        )

        context = DerivacionProgramaService.build_nachec_acceptance_context(self.derivacion)

        self.assertTrue(context['datos_completos'])
        self.assertEqual(context['duplicados'].count(), 1)
        self.assertTrue(context['validaciones']['tiene_contacto'])

    def test_accept_nachec_derivacion_creates_task_and_historial(self):
        # El CasoNachec lo crea automáticamente el signal al generar la derivación
        # (en setUp). El test debe operar sobre ese caso, no crear uno duplicado.
        caso = CasoNachec.objects.get(ciudadano_titular=self.ciudadano)

        result = DerivacionProgramaService.accept_nachec_derivacion(
            derivacion_id=self.derivacion.id,
            usuario=self.user,
            payload={
                'urgencia': 'ALTA',
                'tipo_atencion': 'Territorial',
                'comentario': 'Priorizar revisión',
            },
        )

        self.derivacion.refresh_from_db()
        caso.refresh_from_db()

        self.assertEqual(result.status, 'success')
        self.assertEqual(self.derivacion.estado, DerivacionPrograma.Estado.ACEPTADA)
        self.assertEqual(caso.prioridad, 'ALTA')
        self.assertEqual(TareaNachec.objects.filter(caso=caso, tipo='VALIDACION').count(), 1)
        self.assertEqual(HistorialEstadoCaso.objects.filter(caso=caso).count(), 1)

    def test_accept_nachec_derivacion_requires_duplicate_justification(self):
        with self.assertRaises(ValidationError):
            DerivacionProgramaService.accept_nachec_derivacion(
                derivacion_id=self.derivacion.id,
                usuario=self.user,
                payload={
                    'tiene_duplicado': 'true',
                    'resolucion_duplicado': 'justificar',
                    'justificacion_duplicado': '',
                },
            )

    def test_reject_derivacion_marks_derivacion_as_rejected(self):
        result = DerivacionProgramaService.reject_derivacion(
            derivacion_id=self.derivacion.id,
            usuario=self.user,
            motivo_rechazo='Rechazado desde bandeja de derivaciones',
        )

        self.derivacion.refresh_from_db()

        self.assertEqual(result.status, 'success')
        self.assertEqual(self.derivacion.estado, DerivacionPrograma.Estado.RECHAZADA)
