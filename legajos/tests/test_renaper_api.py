"""La consulta RENAPER anónima de Legajos ya no existe (SEC-04, auditoría oct-2026).

`POST /api/legajos/renaper/consultar/` era `AllowAny` y devolvía el payload crudo
de RENAPER (`datos_api`: calle, número, piso, provincia), más un oráculo de
defunción en la rama de error. Su throttle por IP se evadía rotando
`X-Forwarded-For`. No tenía consumidores: la app de campo usa
`/api/becas/renaper/consultar/`, que es autenticado y queda intacto.
"""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class RenaperLegacyRetiradoTests(TestCase):
    def test_renaper_legacy_no_existe(self):
        with self.assertRaises(NoReverseMatch):
            reverse("renaper_consultar")

        respuesta = self.client.post(
            "/api/legajos/renaper/consultar/",
            {"dni": "30111222", "sexo": "M"},
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 404)
