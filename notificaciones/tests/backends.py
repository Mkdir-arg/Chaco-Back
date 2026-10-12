"""Backends de correo para los tests del envío: fallan a propósito, como un SMTP de verdad."""

import smtplib

from django.core.mail.backends import locmem

from notificaciones.models import Campana


class Contador(locmem.EmailBackend):
    """Cuenta cuántas conexiones se abren (una por lote)."""

    aperturas = 0

    def open(self):
        type(self).aperturas += 1
        return super().open()


class FallaParaAlgunos(locmem.EmailBackend):
    """Rechaza las direcciones que contienen «falla», como un 550 del servidor."""

    def send_messages(self, messages):
        for mensaje in messages:
            if any("falla" in destino for destino in mensaje.to):
                raise smtplib.SMTPRecipientsRefused({mensaje.to[0]: (550, b"No such user")})
        return super().send_messages(messages)


class ServidorCaido(locmem.EmailBackend):
    def open(self):
        raise ConnectionRefusedError("Connection refused")


class ConexionCortada(locmem.EmailBackend):
    def send_messages(self, messages):
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")


class DetenerTrasElPrimero(locmem.EmailBackend):
    """Simula que alguien aprieta «Detener» mientras sale el primer correo."""

    def send_messages(self, messages):
        enviados = super().send_messages(messages)
        Campana.objects.update(cancelacion_pedida=True)
        return enviados


class CortaElSegundo(Contador):
    """La conexión se cae al mandar el segundo correo, una sola vez; el resto sale bien."""

    cortes = 0

    def send_messages(self, messages):
        if type(self).cortes == 0 and len(self.outbox_actual()) == 1:
            type(self).cortes += 1
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        return super().send_messages(messages)

    @staticmethod
    def outbox_actual():
        from django.core import mail

        return mail.outbox


class OtraCorridaEnElMedio(locmem.EmailBackend):
    """Mientras sale el primer correo, otra corrida (``al_primero``) corre sobre la misma campaña."""

    al_primero = None

    def send_messages(self, messages):
        accion, type(self).al_primero = type(self).al_primero, None
        if accion is not None:
            accion()
        return super().send_messages(messages)
