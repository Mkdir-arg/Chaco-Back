from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse


class UrlNamespacesTests(SimpleTestCase):
    def test_users_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse('users:usuarios'), '/usuarios/')
        with self.assertRaises(NoReverseMatch):
            reverse('usuarios')
        self.assertEqual(reverse('users:logout'), '/logout')

    def test_core_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse('core:inicio'), '/inicio/')
        with self.assertRaises(NoReverseMatch):
            reverse('inicio')

    def test_healthcheck_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse('healthcheck:health_check'), '/health/')

    def test_conversaciones_tiene_namespace_estable(self):
        self.assertEqual(reverse('conversaciones:detalle', kwargs={'conversacion_id': 7}), '/conversaciones/7/')

    def test_legajos_alertas_tienen_names_unicos(self):
        self.assertEqual(reverse('legajos:cerrar_alerta_evento'), '/legajos/alertas/eventos/cerrar/')
        self.assertEqual(
            reverse('legajos:cerrar_alerta_ciudadano', kwargs={'alerta_id': 3}),
            '/legajos/alertas/3/cerrar/',
        )
