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
