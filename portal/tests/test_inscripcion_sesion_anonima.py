"""PERF-10 · La visita que no pasa el paso 1 no deja una sesión de 24 h.

El GET del link público escribe el desafío anti-bot en la sesión, así que **toda**
visita —persona, buscador o bot— estrenaba una sesión con la vigencia completa de
`SESSION_COOKIE_AGE`. En producción esas sesiones viven en Redis, compartiendo los
350 MB con la caché y con `allkeys-lru`: la medición de la auditoría puso el llenado en
350-700 mil visitas únicas en 24 h, 10-20× el objetivo de 40k.

Lo que **no** se hace es acortar la sesión entera: el Cambio 91 ya probó que así se
pierde el paso 2 a medio completar, con los adjuntos ya elegidos. La vigencia corta vale
solo mientras la sesión no tiene nada más que el captcha, y el paso 1 la devuelve al
default apenas guarda la identificación.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.services import inscripcion as servicio
from programas.models import Convocatoria, Relevamiento, Segmento


@override_settings(PERSONAS_API_ACTIVA=False, RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
class SesionAnonimaDelLinkPublicoTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg PERF-10", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas PERF-10",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def _url(self):
        return reverse("portal:inscripcion_paso1", kwargs={"token": self.relevamiento.token_publico})

    def test_la_visita_que_solo_mira_deja_una_sesion_de_una_hora(self):
        self.client.get(self._url())

        sesion = self.client.session
        self.assertIn(servicio.SESSION_KEY_CAPTCHA, sesion)
        self.assertEqual(sesion.get_expiry_age(), servicio.sesion_anonima_segundos())
        self.assertLess(sesion.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    @patch("programas.services.identidad.consultar_persona", return_value=None)
    def test_pasar_el_paso_1_le_devuelve_la_vigencia_completa(self, _consulta):
        """Si no, la persona perdería el paso 2 —y sus adjuntos— al cumplirse la hora."""
        self.client.get(self._url())
        sesion = self.client.session
        respuesta = self.client.post(
            self._url(),
            {"dni": "30123456", "sexo": "F", "captcha": str(sesion[servicio.SESSION_KEY_CAPTCHA])},
        )

        self.assertEqual(respuesta.status_code, 302)
        sesion = self.client.session
        self.assertIn(servicio.clave_sesion(self.relevamiento), sesion)
        self.assertEqual(sesion.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    @patch("programas.services.identidad.consultar_persona", return_value=None)
    def test_un_captcha_nuevo_no_vuelve_a_acortar_una_sesion_con_identificacion(self, _consulta):
        """Quien ya pasó el paso 1 de un relevamiento y abre el link de otro conserva
        las 24 h: la sesión tiene algo que perder y la regla mira el contenido, no la
        pantalla."""
        self.client.get(self._url())
        sesion = self.client.session
        self.client.post(
            self._url(),
            {"dni": "30123456", "sexo": "F", "captcha": str(sesion[servicio.SESSION_KEY_CAPTCHA])},
        )
        otro = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

        self.client.get(reverse("portal:inscripcion_paso1", kwargs={"token": otro.token_publico}))

        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    @override_settings(INSCRIPCION_SESION_ANONIMA_SEGUNDOS=120)
    def test_la_vigencia_corta_se_lee_en_cada_llamada(self):
        """Seguimiento MINOR de #645: era un escalar congelado en el import.

        La variable de entorno funcionaba igual —se lee al arrancar el proceso—, pero
        `override_settings` no la movía y la perilla quedaba sin forma de probarse. El
        resto de las perillas del módulo (`timeout_recaptcha`) ya se leían por llamada.
        """
        self.client.get(self._url())

        self.assertEqual(self.client.session.get_expiry_age(), 120)

    def test_el_intento_fallido_sigue_siendo_una_visita_anonima(self):
        """Un captcha mal respondido renueva el desafío: la sesión sigue sin tener nada
        más que eso, así que conserva la vigencia corta."""
        self.client.get(self._url())
        self.client.post(self._url(), {"dni": "30123456", "sexo": "F", "captcha": "0"})

        sesion = self.client.session
        self.assertNotIn(servicio.clave_sesion(self.relevamiento), sesion)
        self.assertEqual(sesion.get_expiry_age(), servicio.sesion_anonima_segundos())
