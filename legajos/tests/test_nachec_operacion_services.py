from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Municipio, Provincia
from legajos.models import Ciudadano
from legajos.models.nachec import CasoNachec, EstadoCaso, EstadoTarea, HistorialEstadoCaso, TareaNachec
from legajos.services import ServicioOperacionNachec


class ServicioOperacionNachecTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.operador = user_model.objects.create_user(username="operador", password="x")
        self.territorial = user_model.objects.create_user(username="territorial", password="x")
        self.provincia = Provincia.objects.create(nombre="Buenos Aires")
        self.municipio = Municipio.objects.create(nombre="La Plata", provincia=self.provincia)
        self.ciudadano = Ciudadano.objects.create(
            dni="12345678",
            nombre="Ana",
            apellido="Perez",
            municipio=self.municipio,
        )
        self.caso = CasoNachec.objects.create(
            ciudadano_titular=self.ciudadano,
            estado=EstadoCaso.EN_REVISION,
            prioridad="MEDIA",
            municipio="La Plata",
            localidad="Centro",
            direccion="Calle 1",
            fecha_derivacion=date.today(),
            motivo_derivacion="Derivacion inicial",
        )

    def test_completar_validacion_crea_tarea_completada(self):
        tarea = ServicioOperacionNachec.completar_validacion(self.caso, self.operador)

        self.assertEqual(tarea.tipo, "VALIDACION")
        self.assertEqual(tarea.estado, EstadoTarea.COMPLETADA)
        self.assertEqual(tarea.asignado_a, self.operador)

    def test_build_envio_asignacion_context_refleja_validaciones(self):
        ServicioOperacionNachec.completar_validacion(self.caso, self.operador)

        context = ServicioOperacionNachec.build_envio_asignacion_context(self.caso)

        self.assertTrue(context["validaciones"]["tarea_completada"])
        self.assertTrue(context["validaciones"]["tiene_dni"])
        self.assertTrue(context["validaciones"]["tiene_municipio"])
        self.assertTrue(context["puede_confirmar"])

    def test_enviar_a_asignacion_actualiza_estado_y_crea_tarea(self):
        ServicioOperacionNachec.completar_validacion(self.caso, self.operador)

        result = ServicioOperacionNachec.enviar_a_asignacion(
            caso=self.caso,
            usuario=self.operador,
            municipio="La Plata",
            localidad="Tolosa",
            observaciones="Observaciones suficientes para coordinación",
        )

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, EstadoCaso.A_ASIGNAR)
        self.assertEqual(result["tarea"].tipo, "OTRO")
        self.assertIn("Asignar territorial", result["tarea"].titulo)
        self.assertTrue(
            HistorialEstadoCaso.objects.filter(
                caso=self.caso,
                estado_anterior=EstadoCaso.EN_REVISION,
                estado_nuevo=EstadoCaso.A_ASIGNAR,
            ).exists()
        )

    def test_asignar_territorial_completa_tarea_de_asignacion_y_crea_relevamiento(self):
        ServicioOperacionNachec.completar_validacion(self.caso, self.operador)
        ServicioOperacionNachec.enviar_a_asignacion(
            caso=self.caso,
            usuario=self.operador,
            municipio="La Plata",
            localidad="Tolosa",
            observaciones="Observaciones suficientes para coordinación",
        )

        ServicioOperacionNachec.asignar_territorial(
            caso=self.caso,
            coordinador=self.operador,
            territorial=self.territorial,
            fecha_limite_obj=date.today() + timedelta(days=2),
            instrucciones="Contactar a la familia y relevar la situación completa.",
        )

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, EstadoCaso.ASIGNADO)
        self.assertEqual(self.caso.territorial, self.territorial)
        self.assertTrue(
            TareaNachec.objects.filter(
                caso=self.caso,
                tipo="OTRO",
                titulo__icontains="Asignar territorial",
                estado=EstadoTarea.COMPLETADA,
            ).exists()
        )
        self.assertTrue(
            TareaNachec.objects.filter(
                caso=self.caso,
                tipo="RELEVAMIENTO",
                asignado_a=self.territorial,
            ).exists()
        )

    def test_reasignar_territorial_actualiza_responsable_y_tareas_pendientes(self):
        otra_territorial = get_user_model().objects.create_user(username="territorial-2", password="x")
        self.caso.estado = EstadoCaso.ASIGNADO
        self.caso.territorial = self.territorial
        self.caso.save()
        tarea = TareaNachec.objects.create(
            caso=self.caso,
            tipo="RELEVAMIENTO",
            titulo="Tarea abierta",
            descripcion="Pendiente de tomar",
            asignado_a=self.territorial,
            creado_por=self.operador,
            estado=EstadoTarea.PENDIENTE,
            prioridad=self.caso.prioridad,
            fecha_vencimiento=date.today() + timedelta(days=1),
        )

        ServicioOperacionNachec.reasignar_territorial(
            caso=self.caso,
            usuario=self.operador,
            territorial=otra_territorial,
            motivo="Cambio por redistribucion de carga territorial",
        )

        self.caso.refresh_from_db()
        tarea.refresh_from_db()
        self.assertEqual(self.caso.territorial, otra_territorial)
        self.assertEqual(tarea.asignado_a, otra_territorial)
        self.assertTrue(
            HistorialEstadoCaso.objects.filter(
                caso=self.caso,
                observacion__icontains="redistribucion de carga",
            ).exists()
        )

    def test_iniciar_relevamiento_pasa_caso_y_tarea_a_en_proceso(self):
        self.caso.estado = EstadoCaso.ASIGNADO
        self.caso.territorial = self.territorial
        self.caso.sla_relevamiento = date.today() - timedelta(days=1)
        self.caso.save()
        tarea = TareaNachec.objects.create(
            caso=self.caso,
            tipo="RELEVAMIENTO",
            titulo="Relevamiento inicial",
            descripcion="Tomar contacto y completar ficha",
            asignado_a=self.territorial,
            creado_por=self.operador,
            estado=EstadoTarea.PENDIENTE,
            prioridad=self.caso.prioridad,
            fecha_vencimiento=date.today(),
        )

        result = ServicioOperacionNachec.iniciar_relevamiento(
            caso=self.caso,
            territorial=self.territorial,
        )

        self.caso.refresh_from_db()
        tarea.refresh_from_db()
        self.assertEqual(self.caso.estado, EstadoCaso.EN_RELEVAMIENTO)
        self.assertEqual(tarea.estado, EstadoTarea.EN_PROCESO)
        self.assertTrue(result["sla_vencido"])
        self.assertTrue(
            HistorialEstadoCaso.objects.filter(
                caso=self.caso,
                estado_anterior=EstadoCaso.ASIGNADO,
                estado_nuevo=EstadoCaso.EN_RELEVAMIENTO,
            ).exists()
        )
