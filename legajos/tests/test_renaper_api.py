from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class RenaperApiTests(TestCase):
    def test_consulta_renaper_api_devuelve_datos_normalizados(self):
        with patch("legajos.api_views.consultar_datos_renaper") as consultar:
            consultar.return_value = {
                "success": True,
                "data": {
                    "dni": "30111222",
                    "apellido": "Perez",
                    "nombre": "Juan",
                    "fecha_nacimiento": "1990-01-15",
                    "genero": "M",
                },
                "datos_api": {"fuente": "mock"},
            }

            response = self.client.post(
                reverse("renaper_consultar"),
                {"dni": "30111222", "sexo": "M"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["dni"], "30111222")
        self.assertEqual(response.json()["data"]["sexo"], "M")
        consultar.assert_called_once_with("30111222", "M")

    def test_consulta_renaper_api_requiere_dni_y_sexo(self):
        response = self.client.post(
            reverse("renaper_consultar"),
            {"dni": "30111222"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
