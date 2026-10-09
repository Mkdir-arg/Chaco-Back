from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse


class UrlNamespacesTests(SimpleTestCase):
    def test_users_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse("users:usuarios"), "/usuarios/")
        with self.assertRaises(NoReverseMatch):
            reverse("usuarios")
        self.assertEqual(reverse("users:logout"), "/logout")

    def test_core_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse("core:inicio"), "/inicio/")
        with self.assertRaises(NoReverseMatch):
            reverse("inicio")

    def test_healthcheck_namespace_es_el_contrato_estable(self):
        self.assertEqual(reverse("healthcheck:health_check"), "/health/")

    # G1-01 fase 2: acá se fijaba el namespace de `conversaciones` (`conversaciones:detalle`
    # → `/conversaciones/7/`). La app se apagó y sus dos `include()` salieron de
    # `config/urls.py`; que ya no resuelvan lo mide `conversaciones/tests/test_apagado.py`.

    def test_legajos_alertas_tienen_names_unicos(self):
        self.assertEqual(
            reverse("legajos:cerrar_alerta_ciudadano", kwargs={"alerta_id": 3}),
            "/legajos/alertas/3/cerrar/",
        )
