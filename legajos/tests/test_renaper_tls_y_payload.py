"""SEC-27 y G1c-16 · El canal con RENAPER y lo que queda guardado de la respuesta.

SEC-27: la consulta iba con ``verify=False`` escrito en el código, y el módulo
apagaba el aviso de TLS **de todo el proceso** al importarse (también el de SIIS,
Personas y reCAPTCHA). Con el certificado sin validar, cualquiera en el camino de
red lee el documento consultado y devuelve la identidad que quiera, y eso es lo
que después marca a un ciudadano como «validado». **D-27 (default):** el
interruptor queda puesto y **apagado** —el default es el comportamiento de hoy—
hasta que ECOM confirme la cadena de certificados del organismo.

G1c-16: la respuesta cruda se guardaba entera en la sesión (24 h, Redis en prd) y
en la caché (10 min). La pantalla de confirmación dibuja nueve campos; lo demás
que mande el organismo no lo mira nadie.
"""

from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import rbac
from legajos.services import CiudadanosService
from legajos.services.consulta_renaper import (
    CAMPOS_DATOS_API,
    APIClient,
    datos_api_mostrables,
    verificacion_tls,
)
from users.models import Capacidad, RolMeta

#: Un payload con los campos que la pantalla muestra y tres que no.
PAYLOAD_CRUDO = {
    "apellido": "Pérez",
    "nombres": "Ana María",
    "fechaNacimiento": "1990-05-04",
    "calle": "San Martín",
    "numero": "123",
    "piso": "2",
    "departamento": "B",
    "ciudad": "Resistencia",
    "provincia": "Chaco",
    "cuil": "27123456783",
    "nroTramite": "00123456789",
    "mensaf": "OK",
}


class VerificacionTlsTests(SimpleTestCase):
    @override_settings(RENAPER_CA_BUNDLE="", RENAPER_VERIFY_TLS=False)
    def test_el_default_es_el_de_hoy(self):
        """D-27: nada cambia contra RENAPER hasta que ECOM confirme la cadena."""
        self.assertIs(verificacion_tls(), False)

    @override_settings(RENAPER_CA_BUNDLE="", RENAPER_VERIFY_TLS=True)
    def test_con_la_variable_encendida_se_verifica(self):
        self.assertIs(verificacion_tls(), True)

    @override_settings(RENAPER_CA_BUNDLE="/certs/renaper.pem", RENAPER_VERIFY_TLS=False)
    def test_el_bundle_implica_verificar(self):
        """Una CA privada del organismo, sin meterla en el almacén del sistema."""
        self.assertEqual(verificacion_tls(), "/certs/renaper.pem")


@override_settings(
    RENAPER_API_URL="https://renaper.example.test",
    RENAPER_API_KEY="una-clave",
    RENAPER_AUTH_MODE="api_key",
)
class VerifyLlegaAlPedidoTests(SimpleTestCase):
    """Lo que importa no es el helper sino el kwarg que sale por la red."""

    def _verify_del_pedido(self, metodo):
        cliente = APIClient()
        with patch.object(cliente.session, metodo) as llamada:
            llamada.return_value = None
            cliente._pedir({"Content-Type": "application/json"}, {"dni": "30111222"}, metodo)
        return llamada.call_args.kwargs["verify"]

    @override_settings(RENAPER_CA_BUNDLE="/certs/renaper.pem")
    def test_el_post_manda_el_bundle(self):
        self.assertEqual(self._verify_del_pedido("post"), "/certs/renaper.pem")

    @override_settings(RENAPER_CA_BUNDLE="/certs/renaper.pem")
    def test_el_get_manda_el_bundle(self):
        self.assertEqual(self._verify_del_pedido("get"), "/certs/renaper.pem")

    @override_settings(RENAPER_CA_BUNDLE="", RENAPER_VERIFY_TLS=True)
    def test_con_la_variable_encendida_el_pedido_verifica(self):
        self.assertIs(self._verify_del_pedido("post"), True)


class AvisoTlsTests(SimpleTestCase):
    def test_el_modulo_no_apaga_el_aviso_de_tls_del_proceso(self):
        """`urllib3.disable_warnings` silenciaba también a SIIS y a Personas.

        Se mide sobre el árbol del módulo a propósito: el efecto es global y
        ocurre una sola vez al importar, así que no hay forma de observarlo
        después —y el nombre sigue nombrado en los comentarios, que es por lo que
        esto mira llamadas y no texto—.
        """
        import ast
        from pathlib import Path

        import legajos.services.consulta_renaper as modulo

        arbol = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
        llamadas = [
            nodo.func.attr if isinstance(nodo.func, ast.Attribute) else getattr(nodo.func, "id", "")
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Call)
        ]

        self.assertNotIn("disable_warnings", llamadas)


class DatosApiMostrablesTests(SimpleTestCase):
    def test_solo_sobreviven_los_campos_de_la_pantalla(self):
        recortado = datos_api_mostrables(PAYLOAD_CRUDO)

        self.assertEqual(set(recortado), set(CAMPOS_DATOS_API))
        self.assertNotIn("cuil", recortado)
        self.assertNotIn("nroTramite", recortado)

    def test_los_valores_no_se_tocan(self):
        self.assertEqual(datos_api_mostrables(PAYLOAD_CRUDO)["calle"], "San Martín")

    def test_lo_que_no_es_un_diccionario_no_rompe(self):
        for valor in (None, "", [], "texto suelto"):
            with self.subTest(valor=valor):
                self.assertEqual(datos_api_mostrables(valor), {})

    def test_un_campo_que_falta_no_se_inventa(self):
        self.assertEqual(datos_api_mostrables({"apellido": "Pérez"}), {"apellido": "Pérez"})


class SesionDelAltaTests(TestCase):
    """Lo que queda en la sesión entre la consulta y la confirmación (G1c-16)."""

    def setUp(self):
        self.usuario = User.objects.create_user("alta-renaper", password="Clave-Seg-2026x")
        grupo = Group.objects.create(name="Alta de ciudadanos (test)")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        tipo = ContentType.objects.get_for_model(Capacidad)
        for codigo in ("ciudadano.ver", "ciudadano.crear"):
            grupo.permissions.add(Permission.objects.get(content_type=tipo, codename=rbac.codename_de(codigo)))
        self.usuario.groups.add(grupo)
        self.client.force_login(self.usuario)

    def _consultar(self):
        resultado = {
            "success": True,
            "data": {
                "dni": "30111222",
                "nombre": "Ana María",
                "apellido": "Pérez",
                "genero": "F",
                "fecha_nacimiento": "1990-05-04",
                "domicilio": "San Martín 123",
                "provincia": None,
            },
            "datos_api": PAYLOAD_CRUDO,
        }
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper", return_value=resultado):
            return self.client.post(reverse("legajos:ciudadano_nuevo"), {"dni": "30111222", "sexo": "F"})

    def test_en_la_sesion_no_queda_el_payload_entero(self):
        self.assertEqual(self._consultar().status_code, 302)

        guardado = self.client.session[CiudadanosService.RENAPER_RAW_SESSION_KEY]

        self.assertEqual(set(guardado), set(CAMPOS_DATOS_API))
        self.assertNotIn("cuil", guardado)

    def test_la_pantalla_de_confirmacion_sigue_mostrando_lo_suyo(self):
        self._consultar()

        html = self.client.get(reverse("legajos:ciudadano_confirmar")).content.decode()

        self.assertIn("San Martín", html)
        self.assertIn("Resistencia", html)

    def test_volver_al_alta_borra_la_consulta_anterior(self):
        """Quien consulta y se arrepiente ya no deja esos datos 24 h en la sesión."""
        self._consultar()
        self.assertIn(CiudadanosService.RENAPER_SESSION_KEY, self.client.session)

        self.client.get(reverse("legajos:ciudadano_nuevo"))

        self.assertNotIn(CiudadanosService.RENAPER_SESSION_KEY, self.client.session)
        self.assertNotIn(CiudadanosService.RENAPER_RAW_SESSION_KEY, self.client.session)
