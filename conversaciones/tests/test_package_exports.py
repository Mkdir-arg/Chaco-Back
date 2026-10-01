from django.test import SimpleTestCase


class ConversacionesPackageExportsTests(SimpleTestCase):
    def test_views_package_exports_public_symbols(self):
        from conversaciones.views import detalle_conversacion, evaluar_conversacion, lista_conversaciones

        self.assertTrue(callable(lista_conversaciones))
        self.assertTrue(callable(detalle_conversacion))
        self.assertTrue(callable(evaluar_conversacion))

    def test_forms_services_selectors_and_signals_export_public_symbols(self):
        from conversaciones.api_views import alertas_conversaciones_count
        from conversaciones.api_views.extra import conversacion_detalle
        from conversaciones.forms import MensajeConversacionForm
        from conversaciones.selectors import get_alertas_conversaciones_count
        from conversaciones.services import AsignadorAutomatico, crear_mensaje_operador
        from conversaciones.signals.alertas import alerta_nueva_conversacion

        self.assertTrue(callable(alertas_conversaciones_count))
        self.assertTrue(callable(conversacion_detalle))
        self.assertIsNotNone(MensajeConversacionForm)
        self.assertIsNotNone(AsignadorAutomatico)
        self.assertTrue(callable(crear_mensaje_operador))
        self.assertTrue(callable(get_alertas_conversaciones_count))
        self.assertTrue(callable(alerta_nueva_conversacion))
