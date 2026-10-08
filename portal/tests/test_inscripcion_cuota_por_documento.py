"""SIIS-21 · Con el captcha aritmético, la cuota de un documento no se quema desde afuera.

La cubeta por documento del paso 1 (RN-P11, 15 intentos/h) es **global**: no
incluye la IP, justamente para que rotar de IP no sirva para enumerar un
documento ni para barrer el padrón (Cambio 71). Esa decisión se tomó dando por
sentado que delante hay un reCAPTCHA.

En un ambiente **sin claves de Google** el desafío es el aritmético propio, que
un script resuelve leyendo la pregunta del HTML. Ahí la cubeta global se da
vuelta: con quince POST se le quema la cuota al documento de un tercero y esa
persona no se puede inscribir en toda la hora.

Cambio 174 (SIIS-21): **solo en modo aritmético** la cubeta del documento pasa a
contar también por IP, así quemarla requiere tantas IP como ataques. Con
reCAPTCHA activo —lo que corresponde en producción, y lo que exige `core.E005`—
la cubeta sigue siendo global y la defensa contra enumeración queda intacta.
"""

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from portal.services.inscripcion import MAX_INTENTOS_DNI, documento_excedido

CON_RECAPTCHA = dict(RECAPTCHA_SITE_KEY="sitio", RECAPTCHA_SECRET_KEY="secreto")
SIN_RECAPTCHA = dict(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")


class CuotaPorDocumentoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.factory = RequestFactory()

    def _pedido(self, ip):
        return self.factory.post("/portal/inscripcion/x/", REMOTE_ADDR=ip)

    def _quemar(self, ip, dni, veces=None):
        for _ in range(veces if veces is not None else MAX_INTENTOS_DNI):
            documento_excedido(self._pedido(ip), dni)

    @override_settings(**SIN_RECAPTCHA)
    def test_con_captcha_aritmetico_otra_ip_no_hereda_la_cuota_quemada(self):
        self._quemar("203.0.113.9", "30111222")

        self.assertTrue(documento_excedido(self._pedido("203.0.113.9"), "30111222"))
        self.assertFalse(documento_excedido(self._pedido("198.51.100.4"), "30111222"))

    @override_settings(**CON_RECAPTCHA)
    def test_con_recaptcha_la_cubeta_sigue_siendo_global(self):
        """La defensa contra enumeración del Cambio 71 no se toca donde vale."""
        self._quemar("203.0.113.9", "30111222")

        self.assertTrue(documento_excedido(self._pedido("198.51.100.4"), "30111222"))

    @override_settings(**SIN_RECAPTCHA)
    def test_el_tope_por_documento_sigue_existiendo_en_cada_ip(self):
        self._quemar("203.0.113.9", "30111222")

        self.assertTrue(documento_excedido(self._pedido("203.0.113.9"), "30111222"))

    @override_settings(**SIN_RECAPTCHA)
    def test_dos_documentos_de_la_misma_ip_no_comparten_cubeta(self):
        self._quemar("203.0.113.9", "30111222")

        self.assertFalse(documento_excedido(self._pedido("203.0.113.9"), "28444555"))

    @override_settings(**SIN_RECAPTCHA)
    def test_un_documento_vacio_no_cuenta(self):
        self.assertFalse(documento_excedido(self._pedido("203.0.113.9"), ""))
