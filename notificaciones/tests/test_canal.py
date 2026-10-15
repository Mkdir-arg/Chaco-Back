"""Canal de correo de las campañas: SMTP propio (Amazon SES) o el común (Cambio 311, RNF-007-15).

Ningún test de este módulo abre un socket: la selección se mira con ``get_connection``
parcheado o con un backend en memoria que anota los parámetros que recibió. Las credenciales
son de mentira y el host es de un dominio reservado para pruebas.
"""

import smtplib
import socket
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from core.integraciones import costo_de_cadena
from notificaciones.models import Campana
from notificaciones.services import canal, envio
from notificaciones.tests import backends
from notificaciones.tests.utils import ConMediaTemporal, crear_campana, usuario_con

HOST = "email-smtp.ejemplo.test"
SMTP = "django.core.mail.backends.smtp.EmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
REGISTRA = "notificaciones.tests.backends.Registra"
COMUN_FROM = "DATAÑACH <no-responder@sistema.test>"
MASIVO_FROM = "DATAÑACH <campanas@masivo.test>"

#: El canal masivo configurado, con credenciales ficticias.
MASIVO = {
    "NOTIF_EMAIL_HOST": HOST,
    "NOTIF_EMAIL_PORT": 587,
    "NOTIF_EMAIL_HOST_USER": "usuario-ficticio",
    "NOTIF_EMAIL_HOST_PASSWORD": "clave-ficticia",
    "NOTIF_EMAIL_USE_TLS": True,
    "NOTIF_EMAIL_TIMEOUT": 20,
    "NOTIF_DEFAULT_FROM_EMAIL": MASIVO_FROM,
    "DEFAULT_FROM_EMAIL": COMUN_FROM,
}
SIN_MASIVO = {**MASIVO, "NOTIF_EMAIL_HOST": ""}


def _sin_red():
    """Cualquier intento de abrir un socket o un SMTP real hace fallar el test."""
    prohibido = AssertionError("un test intentó salir a la red")
    return (
        patch.object(smtplib, "SMTP", side_effect=prohibido),
        patch.object(socket, "create_connection", side_effect=prohibido),
    )


class SeleccionDeCanalTests(SimpleTestCase):
    @override_settings(**SIN_MASIVO)
    def test_sin_host_propio_las_campanas_salen_por_el_canal_comun(self):
        self.assertEqual(canal.canal(), canal.COMUN)
        with patch("notificaciones.services.canal.get_connection") as get_connection:
            canal.conexion_masiva()
        get_connection.assert_called_once_with(fail_silently=False)

    @override_settings(**MASIVO, EMAIL_BACKEND=SMTP)
    def test_con_host_propio_conecta_al_smtp_masivo_con_sus_parametros(self):
        self.assertEqual(canal.canal(), canal.MASIVO)
        with patch("notificaciones.services.canal.get_connection") as get_connection:
            canal.conexion_masiva()
        get_connection.assert_called_once_with(
            SMTP,
            fail_silently=False,
            host=HOST,
            port=587,
            username="usuario-ficticio",
            password="clave-ficticia",
            use_tls=True,
            use_ssl=False,
            timeout=20,
        )

    @override_settings(**MASIVO, EMAIL_BACKEND=SMTP)
    def test_el_backend_smtp_recibe_host_puerto_usuario_y_tls_sin_conectar(self):
        """La conexión se crea sin abrir: se ven sus atributos y no sale nada a la red."""
        red, sock = _sin_red()
        with red, sock:
            conexion = canal.conexion_masiva()
        self.assertEqual(type(conexion).__module__, "django.core.mail.backends.smtp")
        self.assertEqual(
            (conexion.host, conexion.port, conexion.username, conexion.use_tls, conexion.use_ssl, conexion.timeout),
            (HOST, 587, "usuario-ficticio", True, False, 20),
        )
        self.assertIsNone(conexion.connection)

    @override_settings(**MASIVO, EMAIL_BACKEND=LOCMEM)
    def test_con_el_backend_en_memoria_de_los_tests_nunca_usa_el_smtp(self):
        self.assertTrue(canal.en_memoria())
        self.assertEqual(canal.backend_masivo(), LOCMEM)
        self.assertEqual(type(canal.conexion_masiva()).__module__, "django.core.mail.backends.locmem")

    @override_settings(**MASIVO, EMAIL_BACKEND="notificaciones.tests.backends.Contador")
    def test_un_backend_de_prueba_derivado_de_locmem_tambien_se_respeta(self):
        self.assertEqual(canal.backend_masivo(), "notificaciones.tests.backends.Contador")

    @override_settings(**MASIVO, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_la_consola_del_dev_no_es_en_memoria(self):
        """En dev, cargar NOTIF_EMAIL_HOST a mano es pedir el SMTP real del masivo."""
        self.assertFalse(canal.en_memoria())
        self.assertEqual(canal.backend_masivo(), SMTP)

    @override_settings(**MASIVO)
    def test_remitente_del_canal_masivo(self):
        self.assertEqual(canal.remitente_masivo(), MASIVO_FROM)

    @override_settings(**{**MASIVO, "NOTIF_DEFAULT_FROM_EMAIL": ""})
    def test_sin_remitente_propio_usa_el_comun(self):
        self.assertEqual(canal.remitente_masivo(), COMUN_FROM)

    @override_settings(**SIN_MASIVO)
    def test_sin_canal_masivo_un_remitente_propio_suelto_no_se_usa(self):
        """El SMTP común rechaza un From distinto del que autentica."""
        self.assertEqual(canal.remitente_masivo(), COMUN_FROM)

    @override_settings(**MASIVO)
    def test_descripcion_con_canal_masivo(self):
        self.assertEqual(canal.descripcion(), "Se envía por el servicio de correo masivo (campanas@masivo.test).")

    @override_settings(**SIN_MASIVO)
    def test_descripcion_con_canal_comun(self):
        self.assertEqual(canal.descripcion(), "Se envía por el correo del sistema (no-responder@sistema.test).")

    def test_la_prueba_entra_en_el_presupuesto_de_llamadas_externas(self):
        cadena = "notificaciones · enviar la prueba de una campaña"
        with override_settings(**MASIVO, EMAIL_TIMEOUT=5):
            self.assertEqual(costo_de_cadena(cadena), 20)
        with override_settings(**SIN_MASIVO, EMAIL_TIMEOUT=5):
            self.assertEqual(costo_de_cadena(cadena), 5)


@override_settings(NOTIF_PAUSA_SEG=0, EMAIL_BACKEND=REGISTRA, EMAIL_ASUNTO_PREFIJO="")
class CanalEnElEnvioTests(ConMediaTemporal):
    """El masivo y la prueba salen por el canal de las campañas; el resto del sistema, no."""

    def setUp(self):
        super().setUp()
        backends.Registra.parametros = []

    def _hosts(self):
        return [parametros.get("host") for parametros in backends.Registra.parametros]

    @override_settings(**MASIVO)
    def test_el_envio_masivo_sale_por_el_canal_masivo_con_su_remitente(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com"])
        red, sock = _sin_red()
        with red, sock:
            envio.correr(envio.iniciar_envio(campana, usuario=None))

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({m.from_email for m in mail.outbox}, {MASIVO_FROM})
        self.assertEqual(self._hosts(), [HOST])
        self.assertEqual(backends.Registra.parametros[0]["username"], "usuario-ficticio")
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)

    @override_settings(**MASIVO)
    def test_la_prueba_sale_por_el_mismo_canal_que_el_masivo(self):
        campana = crear_campana()
        red, sock = _sin_red()
        with red, sock:
            ok, error, _aviso = envio.enviar_prueba(campana, "yo@x.com", usuario=None)

        self.assertEqual((ok, error), (True, ""))
        self.assertEqual(mail.outbox[0].from_email, MASIVO_FROM)
        self.assertEqual(self._hosts(), [HOST])

    @override_settings(**SIN_MASIVO)
    def test_sin_canal_masivo_la_campana_sale_por_el_comun_como_antes(self):
        campana = crear_campana(emails=["a@x.com"])
        envio.correr(envio.iniciar_envio(campana, usuario=None))
        envio_prueba = crear_campana()
        envio.enviar_prueba(envio_prueba, "yo@x.com", usuario=None)

        self.assertEqual({m.from_email for m in mail.outbox}, {COMUN_FROM})
        self.assertEqual(self._hosts(), [None, None])

    @override_settings(**MASIVO)
    def test_un_correo_del_sistema_sigue_saliendo_por_el_canal_comun(self):
        from users.services.correo import enviar_credenciales_usuario

        usuario = usuario_con(username="nuevo", email="nuevo@x.com")
        enviar_credenciales_usuario(usuario, "Clave-de-mentira1", domain="sistema.test")

        self.assertEqual(mail.outbox[0].from_email, COMUN_FROM)
        self.assertEqual(self._hosts(), [None])

    @override_settings(**MASIVO)
    def test_el_detalle_dice_por_que_canal_sale(self):
        self.client.force_login(usuario_con("notificacion.ver", username="ve"))
        campana = crear_campana()
        contenido = self.client.get(reverse("notificaciones:campana_detalle", args=[campana.pk])).content.decode()
        self.assertIn("Se envía por el servicio de correo masivo (campanas@masivo.test).", contenido)
        # El «De» de la vista previa es el remitente del canal masivo, no el común.
        self.assertIn("DATAÑACH &lt;campanas@masivo.test&gt;", contenido)
        self.assertNotIn("no-responder@sistema.test", contenido)

    @override_settings(**SIN_MASIVO)
    def test_el_detalle_sin_canal_masivo_dice_correo_del_sistema(self):
        self.client.force_login(usuario_con("notificacion.ver", username="ve"))
        campana = crear_campana()
        contenido = self.client.get(reverse("notificaciones:campana_detalle", args=[campana.pk])).content.decode()
        self.assertIn("Se envía por el correo del sistema (no-responder@sistema.test).", contenido)


@override_settings(**MASIVO, EMAIL_BACKEND=LOCMEM, NOTIF_LOTE=50, NOTIF_PAUSA_SEG=10)
class DiagnosticoCanalMasivoTests(SimpleTestCase):
    """``diagnosticar_correo --canal masivo``: los mismos pasos, contra NOTIF_EMAIL_*."""

    def _correr(self, *args):
        salida = StringIO()
        codigo = 0
        with patch("users.management.commands.diagnosticar_correo.socket.gethostbyname", return_value="192.0.2.10"):
            try:
                call_command("diagnosticar_correo", "--canal", "masivo", *args, stdout=salida)
            except SystemExit as exc:
                codigo = exc.code
        return codigo, salida.getvalue()

    def test_revisa_la_configuracion_y_la_conexion_del_canal_masivo_sin_mostrar_la_clave(self):
        codigo, salida = self._correr()
        self.assertEqual(codigo, 0, salida)
        self.assertIn(f"NOTIF_EMAIL_HOST: {HOST}", salida)
        self.assertIn("NOTIF_EMAIL_HOST_USER: usuario-ficticio", salida)
        self.assertIn(f"NOTIF_EMAIL_HOST_PASSWORD: presente ({len('clave-ficticia')} caracteres)", salida)
        self.assertNotIn("clave-ficticia", salida)
        self.assertIn("~5.0 correos/s", salida)
        self.assertIn("Conexión abierta y autenticada.", salida)
        self.assertIn("Sin --destino no se manda nada", salida)
        self.assertEqual(mail.outbox, [])

    def test_con_destino_manda_un_correo_por_el_canal_masivo(self):
        codigo, salida = self._correr("--destino", "yo@x.com")
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["yo@x.com"])
        self.assertEqual(mail.outbox[0].from_email, MASIVO_FROM)

    @override_settings(EMAIL_BACKEND=SMTP)
    def test_la_conexion_usa_el_smtp_masivo_y_reporta_credenciales_rechazadas(self):
        conexion = MagicMock()
        conexion.open.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication Credentials Invalid")
        with patch("notificaciones.services.canal.get_connection", return_value=conexion) as get_connection:
            codigo, salida = self._correr("--destino", "yo@x.com")

        self.assertEqual(codigo, 1)
        self.assertEqual(get_connection.call_args.args, (SMTP,))
        self.assertEqual(get_connection.call_args.kwargs["host"], HOST)
        self.assertIn("rechazó las credenciales: 535", salida)
        self.assertNotIn("clave-ficticia", salida)

    @override_settings(NOTIF_EMAIL_HOST="")
    def test_sin_canal_masivo_configurado_falla_y_lo_dice(self):
        codigo, salida = self._correr()
        self.assertEqual(codigo, 1)
        self.assertIn("NOTIF_EMAIL_HOST vacía", salida)
