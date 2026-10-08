"""Envío en segundo plano, prueba y transiciones (RF-007-10 a RF-007-15, RF-007-18, RN-007-01/11/14/16)."""

from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from notificaciones.models import Campana, Destinatario, PruebaEnviada
from notificaciones.services import envio
from notificaciones.services.campanas import TransicionInvalida
from notificaciones.tests import backends
from notificaciones.tests.utils import ConMediaTemporal, crear_campana, usuario_con

SIN_PAUSA = {"NOTIF_PAUSA_SEG": 0, "NOTIF_LOTE": 50}


def _enviando(campana, usuario=None):
    return envio.iniciar_envio(campana, usuario=usuario)


@override_settings(**SIN_PAUSA, EMAIL_ASUNTO_PREFIJO="[QA] ", DEFAULT_FROM_EMAIL="DATAÑACH <no-responder@x.gob.ar>")
class EnvioTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.usuario = usuario_con("notificacion.enviar", username="envia")

    def test_un_correo_individual_por_destinatario_con_prefijo_y_remitente(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com", "c@x.com"], asunto="Abrió la convocatoria")
        envio.correr(_enviando(campana, self.usuario))

        self.assertEqual(len(mail.outbox), 3)
        for mensaje in mail.outbox:
            self.assertEqual(len(mensaje.to), 1)
            self.assertEqual(mensaje.cc, [])
            self.assertEqual(mensaje.bcc, [])
            self.assertEqual(mensaje.subject, "[QA] Abrió la convocatoria")
            self.assertEqual(mensaje.from_email, "DATAÑACH <no-responder@x.gob.ar>")
            self.assertEqual(mensaje.alternatives[0][1], "text/html")
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["a@x.com", "b@x.com", "c@x.com"])

        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)
        self.assertEqual(campana.enviados, 3)
        self.assertIsNotNone(campana.finalizada_en)
        self.assertEqual(campana.enviada_por, self.usuario)
        self.assertFalse(campana.destinatarios.exclude(estado=Destinatario.Estado.ENVIADO).exists())

    def test_el_html_enviado_no_trae_el_script(self):
        campana = crear_campana(emails=["a@x.com"], html_texto="<p>Hola</p><script>alert(1)</script>")
        envio.correr(_enviando(campana))
        cuerpo_html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Hola", cuerpo_html)
        self.assertNotIn("<script", cuerpo_html)
        self.assertNotIn("alert", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="notificaciones.tests.backends.FallaParaAlgunos")
    def test_fallo_parcial_queda_enviada_con_errores(self):
        campana = crear_campana(emails=["a@x.com", "falla@x.com", "c@x.com"])
        envio.correr(_enviando(campana))

        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA_CON_ERRORES)
        self.assertEqual((campana.enviados, campana.fallidos), (2, 1))
        fallido = campana.destinatarios.get(email="falla@x.com")
        self.assertEqual(fallido.estado, Destinatario.Estado.FALLIDO)
        self.assertIn("SMTPRecipientsRefused", fallido.error)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(NOTIF_LOTE=2, NOTIF_PAUSA_SEG=3, EMAIL_BACKEND="notificaciones.tests.backends.Contador")
    def test_una_conexion_por_lote_y_pausa_entre_lotes(self):
        backends.Contador.aperturas = 0
        campana = crear_campana(emails=[f"p{i}@x.com" for i in range(5)])
        pausas = []
        envio.correr(_enviando(campana), dormir=pausas.append)
        self.assertEqual(backends.Contador.aperturas, 3)  # 2 + 2 + 1
        self.assertEqual(pausas, [3.0, 3.0])  # después del último lote no se espera
        self.assertEqual(len(mail.outbox), 5)

    def test_reanudar_solo_manda_a_los_pendientes(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com", "c@x.com"])
        campana = _enviando(campana)
        campana.destinatarios.filter(email="a@x.com").update(estado=Destinatario.Estado.ENVIADO)
        # El pod se recicló: el latido quedó viejo.
        Campana.objects.filter(pk=campana.pk).update(latido=timezone.now() - timedelta(minutes=6))
        campana.refresh_from_db()
        self.assertTrue(campana.interrumpida)

        envio.correr(envio.preparar_reanudacion(campana))

        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["b@x.com", "c@x.com"])
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)

    def test_no_se_reanuda_un_envio_vivo(self):
        campana = _enviando(crear_campana())
        with self.assertRaises(TransicionInvalida):
            envio.preparar_reanudacion(campana)

    @override_settings(EMAIL_BACKEND="notificaciones.tests.backends.DetenerTrasElPrimero")
    def test_detener_corta_al_terminar_el_correo_en_curso(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com", "c@x.com"])
        envio.correr(_enviando(campana))
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.CANCELADA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(campana.destinatarios.filter(estado=Destinatario.Estado.PENDIENTE).count(), 2)

    def test_pedir_detencion_marca_y_no_cierra_con_el_hilo_vivo(self):
        campana = _enviando(crear_campana())
        self.assertFalse(envio.pedir_detencion(campana))
        campana.refresh_from_db()
        self.assertTrue(campana.cancelacion_pedida)
        self.assertEqual(campana.estado, Campana.Estado.ENVIANDO)

    def test_detener_un_envio_interrumpido_lo_cancela_en_el_acto(self):
        campana = _enviando(crear_campana())
        Campana.objects.filter(pk=campana.pk).update(latido=timezone.now() - timedelta(minutes=10))
        self.assertTrue(envio.pedir_detencion(campana))
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.CANCELADA)

    @override_settings(EMAIL_BACKEND="notificaciones.tests.backends.ServidorCaido")
    def test_smtp_caido_al_empezar_deja_interrumpida_con_el_error(self):
        campana = crear_campana()
        with self.assertLogs("notificaciones.services.envio", "ERROR"):
            envio.correr(_enviando(campana))
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIANDO)
        self.assertTrue(campana.interrumpida)
        self.assertIn("No se pudo conectar", campana.mensaje)
        self.assertFalse(campana.destinatarios.exclude(estado=Destinatario.Estado.PENDIENTE).exists())

    @override_settings(EMAIL_BACKEND="notificaciones.tests.backends.ConexionCortada")
    def test_racha_de_fallos_del_servidor_frena_y_devuelve_a_pendientes(self):
        campana = crear_campana(emails=[f"p{i}@x.com" for i in range(12)])
        envio.correr(_enviando(campana))
        campana.refresh_from_db()
        self.assertTrue(campana.interrumpida)
        self.assertIn("fallos seguidos", campana.mensaje)
        self.assertEqual(campana.destinatarios.filter(estado=Destinatario.Estado.PENDIENTE).count(), 12)

    def test_nunca_reenvia_a_un_enviado(self):
        campana = _enviando(crear_campana(emails=["a@x.com"]))
        campana.destinatarios.update(estado=Destinatario.Estado.ENVIADO)
        envio.correr(campana)
        self.assertEqual(mail.outbox, [])
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)

    def test_lanzar_usa_el_ejecutor_inyectado(self):
        campana = _enviando(crear_campana())
        trabajos = []
        envio.lanzar(campana, ejecutor=trabajos.append)
        self.assertEqual(len(trabajos), 1)
        self.assertEqual(mail.outbox, [])


@override_settings(**SIN_PAUSA)
class TransicionesTests(ConMediaTemporal):
    def test_no_se_envia_dos_veces(self):
        campana = crear_campana()
        envio.iniciar_envio(campana, usuario=None)
        with self.assertRaises(TransicionInvalida):
            envio.iniciar_envio(campana, usuario=None)

    def test_no_se_envia_una_terminada(self):
        campana = crear_campana()
        Campana.objects.filter(pk=campana.pk).update(estado=Campana.Estado.ENVIADA)
        with self.assertRaises(TransicionInvalida):
            envio.iniciar_envio(campana, usuario=None)

    def test_no_se_detiene_lo_que_no_se_envia(self):
        with self.assertRaises(TransicionInvalida):
            envio.pedir_detencion(crear_campana())


@override_settings(EMAIL_ASUNTO_PREFIJO="[QA] ")
class PruebaTests(ConMediaTemporal):
    def test_prueba_va_a_una_sola_direccion_con_prefijo_y_no_cambia_el_estado(self):
        usuario = usuario_con("notificacion.gestionar", username="gestiona")
        campana = crear_campana(asunto="Ya podés inscribirte")
        ok, error = envio.enviar_prueba(campana, "prueba@gmail.com", usuario=usuario)

        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prueba@gmail.com"])
        self.assertEqual(mail.outbox[0].subject, "[QA] [PRUEBA] Ya podés inscribirte")
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.A_ENVIAR)
        self.assertFalse(campana.destinatarios.exclude(estado=Destinatario.Estado.PENDIENTE).exists())
        prueba = PruebaEnviada.objects.get()
        self.assertEqual((prueba.email, prueba.ok, prueba.enviada_por), ("prueba@gmail.com", True, usuario))

    @override_settings(EMAIL_BACKEND="notificaciones.tests.backends.FallaParaAlgunos")
    def test_prueba_que_falla_se_registra_y_no_propaga(self):
        campana = crear_campana()
        with self.assertLogs("notificaciones.services.envio", "ERROR"):
            ok, error = envio.enviar_prueba(campana, "falla@gmail.com", usuario=None)
        self.assertFalse(ok)
        self.assertIn("SMTPRecipientsRefused", error)
        self.assertFalse(PruebaEnviada.objects.get().ok)

    def test_prueba_solo_en_a_enviar(self):
        campana = crear_campana()
        Campana.objects.filter(pk=campana.pk).update(estado=Campana.Estado.ENVIADA)
        campana.refresh_from_db()
        with self.assertRaises(TransicionInvalida):
            envio.enviar_prueba(campana, "prueba@gmail.com", usuario=None)
