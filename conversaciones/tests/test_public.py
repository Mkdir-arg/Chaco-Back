"""Las rutas públicas del chat de conversaciones quedan desmontadas.

G1-01 y G1-02 de la auditoría oct-2026: sin login, cualquiera creaba el legajo
de cualquier DNI con el nombre que quisiera (`iniciar/`) y leía nombre,
apellido, nacimiento y domicilio de cualquier DNI (`consultar-renaper/`).
R0-01 cierra la última que quedaba: `<id>/evaluar/`, que dejaba a un anónimo
pisar la evaluación de cualquier conversación por id.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from conversaciones.models import Conversacion
from legajos.models import Ciudadano

DNI_AJENO = "45123456"


class RutasPublicasDesmontadasTests(TestCase):
    def test_iniciar_publico_desmontado(self):
        """G1-01: `iniciar/` no existe y no puede nacer un legajo desde ahí."""
        response = self.client.post(
            "/conversaciones/iniciar/",
            data=(
                '{"tipo":"personal","dni":"' + DNI_AJENO + '","sexo":"F",'
                '"datos_renaper":{"nombre":"Nombre Falso","apellido":"Apellido Falso"}}'
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Ciudadano.objects.filter(dni=DNI_AJENO).exists())
        self.assertFalse(Conversacion.objects.exists())

    @patch("legajos.services.consulta_renaper.consultar_datos_renaper")
    def test_consultar_renaper_publico_desmontado(self, mock_consultar_datos_renaper):
        """G1-02: el segundo oráculo RENAPER anónimo no existe ni llega al servicio."""
        response = self.client.post(
            "/conversaciones/consultar-renaper/",
            data='{"dni":"' + DNI_AJENO + '","sexo":"F"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        mock_consultar_datos_renaper.assert_not_called()

    def test_chat_y_endpoints_de_mensajes_publicos_desmontados(self):
        """El resto de la superficie pública del chat tampoco responde."""
        conversacion = Conversacion.objects.create(tipo="anonima", prioridad="normal", estado="activa")

        self.assertEqual(self.client.get("/conversaciones/chat/").status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/conversaciones/{conversacion.id}/enviar/",
                data='{"mensaje":"hola"}',
                content_type="application/json",
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(f"/conversaciones/{conversacion.id}/mensajes/").status_code, 404)

    def test_evaluar_publico_desmontado(self):
        """R0-01: la última escritura anónima de la app tampoco existe."""
        conversacion = Conversacion.objects.create(
            tipo="anonima",
            prioridad="normal",
            estado="cerrada",
            satisfaccion=2,
        )

        response = self.client.post(
            f"/conversaciones/{conversacion.id}/evaluar/",
            data='{"satisfaccion":5}',
            content_type="application/json",
        )

        conversacion.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(conversacion.satisfaccion, 2)

    def test_el_nombre_de_url_evaluar_no_resuelve(self):
        with self.assertRaises(NoReverseMatch):
            reverse("conversaciones:evaluar", args=[1])
