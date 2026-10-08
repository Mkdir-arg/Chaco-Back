"""Envío de una campaña en segundo plano (RF-007-10 a RF-007-15, RNF-007-05 a RNF-007-09).

Patrón de ``programas.services.proceso_masivo`` + ``CorridaSiis``:

- el request **no** envía: pasa la campaña a «Enviando» —commiteado— y arranca un hilo
  del pod (``lanzar``), con el ejecutor inyectable para que los tests corran sincrónico;
- el hilo escribe un **latido** por correo; si el pod se recicla, el latido envejece y la
  pantalla muestra el envío como interrumpido y ofrece «Reanudar»;
- «Detener» no cambia el estado: marca ``cancelacion_pedida`` y el hilo corta al terminar
  el correo que tiene entre manos;
- cada destinatario se marca ENVIADO o FALLIDO con un ``UPDATE`` condicionado a que siga
  PENDIENTE, así que reanudar nunca le vuelve a mandar a quien ya recibió (RN-007-11).

Una sola conexión SMTP por lote (``get_connection()``), con el lote y la pausa leídos de
``settings.NOTIF_LOTE`` y ``settings.NOTIF_PAUSA_SEG`` en cada vuelta: se ajustan por
variable de entorno sin release. Cada correo lleva un solo destinatario en ``To``
(RNF-007-08), sale de ``DEFAULT_FROM_EMAIL`` (RN-007-17) y con ``EMAIL_ASUNTO_PREFIJO``
(RNF-007-09).
"""

from __future__ import annotations

import logging
import smtplib
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from notificaciones.models import Campana, Destinatario, PruebaEnviada
from notificaciones.services.campanas import TransicionInvalida
from notificaciones.services.html import documento

logger = logging.getLogger(__name__)

PREFIJO_PRUEBA = "[PRUEBA] "
#: Fallos **seguidos** que no son de un destinatario puntual (conexión cortada, rechazo
#: por volumen, timeout) y que frenan el envío. Los correos de esa racha vuelven a
#: pendientes: su falla fue del servidor, no de la dirección, y se reintentan al reanudar.
MAX_FALLOS_SEGUIDOS = 10
LARGO_ERROR = 500


def asunto_de(campana, *, prueba=False):
    """Asunto con el prefijo del ambiente (``[QA] `` en testing) y, en la prueba, ``[PRUEBA] ``.

    El orden es el del precedente ``diagnosticar_correo``: primero el ambiente.
    """
    return f"{settings.EMAIL_ASUNTO_PREFIJO}{PREFIJO_PRUEBA if prueba else ''}{campana.asunto}"


def armar_mensaje(campana, email, *, conexion=None, prueba=False):
    """Un correo de la campaña para **una** dirección: HTML saneado + texto plano."""
    mensaje = EmailMultiAlternatives(
        subject=asunto_de(campana, prueba=prueba),
        body=campana.texto_plano,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
        connection=conexion,
    )
    mensaje.attach_alternative(documento(campana.html_sanitizado), "text/html")
    return mensaje


def _error_corto(exc):
    texto = f"{type(exc).__name__}: {exc}".strip()
    return texto[:LARGO_ERROR]


# ---------------------------------------------------------------------------
# Prueba
# ---------------------------------------------------------------------------
def enviar_prueba(campana, email, *, usuario):
    """Manda la campaña **solo** a ``email`` con «[PRUEBA] » (RF-007-18). Nunca propaga.

    No cambia el estado de la campaña ni toca sus destinatarios; queda registrada en
    ``PruebaEnviada``. Devuelve ``(ok, error)``.
    """
    if not campana.editable:
        raise TransicionInvalida("La prueba se manda solo mientras la campaña está «A enviar».")
    ok, error = True, ""
    try:
        armar_mensaje(campana, email, prueba=True).send(fail_silently=False)
    except Exception as exc:  # SMTP caído, rechazo, mal configurado…
        logger.exception("No se pudo enviar la prueba de la campaña %s a %s", campana.pk, email)
        ok, error = False, _error_corto(exc)
    PruebaEnviada.objects.create(campana=campana, enviada_por=usuario, email=email, ok=ok, error=error)
    return ok, error


# ---------------------------------------------------------------------------
# Transiciones (con candado sobre la fila de la campaña)
# ---------------------------------------------------------------------------
def iniciar_envio(campana, *, usuario):
    """«A enviar» → «Enviando», registrando quién y cuándo. Commitea antes de devolver.

    El candado es la propia fila (``select_for_update``): si dos personas aprietan
    Enviar a la vez, la segunda espera, lee «Enviando» y recibe ``TransicionInvalida``
    (RNF-007-07). El candado dura dos consultas: no compromete el ``read_timeout`` de ECOM.
    """
    with transaction.atomic():
        actual = Campana.objects.select_for_update().get(pk=campana.pk)
        if actual.estado != Campana.Estado.A_ENVIAR:
            raise TransicionInvalida("La campaña ya no está «A enviar»: alguien la envió o la cambió.")
        ahora = timezone.now()
        actual.estado = Campana.Estado.ENVIANDO
        actual.enviada_por = usuario
        actual.enviada_en = ahora
        actual.latido = ahora
        actual.cancelacion_pedida = False
        actual.mensaje = ""
        actual.save(
            update_fields=[
                "estado",
                "enviada_por",
                "enviada_en",
                "latido",
                "cancelacion_pedida",
                "mensaje",
                "modificado",
            ]
        )
    return actual


def preparar_reanudacion(campana):
    """Toma un envío interrumpido para seguirlo con los pendientes (RF-007-15).

    Renueva el latido con el candado tomado: un segundo «Reanudar» simultáneo ya no la ve
    interrumpida y recibe ``TransicionInvalida``, así no corren dos hilos sobre la misma.
    """
    with transaction.atomic():
        actual = Campana.objects.select_for_update().get(pk=campana.pk)
        if not actual.interrumpida:
            raise TransicionInvalida("Solo se reanuda un envío interrumpido.")
        actual.latido = timezone.now()
        actual.cancelacion_pedida = False
        actual.mensaje = ""
        actual.save(update_fields=["latido", "cancelacion_pedida", "mensaje", "modificado"])
    return actual


def pedir_detencion(campana):
    """«Detener envío» (RF-007-14). Devuelve ``True`` si quedó cancelada en el acto.

    Con el hilo vivo solo se marca el pedido: el estado final lo escribe quien está
    enviando, al terminar el correo en curso (si lo marcara este request, la pantalla
    diría «Cancelada» mientras sale un correo más). Con el envío interrumpido no hay
    hilo que lo lea, así que se cancela acá.
    """
    with transaction.atomic():
        actual = Campana.objects.select_for_update().get(pk=campana.pk)
        if actual.estado != Campana.Estado.ENVIANDO:
            raise TransicionInvalida("Solo se detiene una campaña que se está enviando.")
        if actual.interrumpida:
            _cerrar(actual, Campana.Estado.CANCELADA, "Se detuvo un envío interrumpido. Lo enviado quedó enviado.")
            return True
        Campana.objects.filter(pk=actual.pk).update(cancelacion_pedida=True)
    return False


# ---------------------------------------------------------------------------
# El hilo
# ---------------------------------------------------------------------------
def contar_por_estado(campana_id):
    """``{PENDIENTE: n, ENVIADO: n, FALLIDO: n}`` en una consulta."""
    conteos = {estado: 0 for estado in Destinatario.Estado.values}
    filas = (
        Destinatario.objects.filter(campana_id=campana_id)
        .values("estado")
        .order_by()
        .annotate(n=Count("pk"))
        .values_list("estado", "n")
    )
    conteos.update(dict(filas))
    return conteos


def _latir(campana_id):
    """Solo la señal de vida: no usa ``save()`` para no pisar ``cancelacion_pedida``."""
    Campana.objects.filter(pk=campana_id).update(latido=timezone.now())


def _volcar_contadores(campana_id):
    conteos = contar_por_estado(campana_id)
    Campana.objects.filter(pk=campana_id).update(
        enviados=conteos[Destinatario.Estado.ENVIADO],
        fallidos=conteos[Destinatario.Estado.FALLIDO],
        latido=timezone.now(),
    )
    return conteos


def _cerrar(campana, estado, mensaje=""):
    conteos = contar_por_estado(campana.pk)
    Campana.objects.filter(pk=campana.pk).update(
        estado=estado,
        finalizada_en=timezone.now(),
        mensaje=mensaje,
        enviados=conteos[Destinatario.Estado.ENVIADO],
        fallidos=conteos[Destinatario.Estado.FALLIDO],
        modificado=timezone.now(),
    )


def _dejar_interrumpida(campana_id, mensaje):
    """Deja el envío «interrumpido» **ya**, con el motivo, para que se ofrezca Reanudar.

    La interrupción se deduce del latido (``Campana.interrumpida``), así que se lo fecha
    más atrás que el umbral: esperar cinco minutos a que venza solo dejaría la pantalla
    diciendo «Enviando» sin que nadie envíe.
    """
    vencido = timezone.now() - Campana.LATIDO_VENCIDO - timedelta(seconds=1)
    Campana.objects.filter(pk=campana_id).update(latido=vencido, mensaje=mensaje[:LARGO_ERROR])
    _volcar_contadores_sin_latido(campana_id)


def _volcar_contadores_sin_latido(campana_id):
    conteos = contar_por_estado(campana_id)
    Campana.objects.filter(pk=campana_id).update(
        enviados=conteos[Destinatario.Estado.ENVIADO],
        fallidos=conteos[Destinatario.Estado.FALLIDO],
    )


def _sigue_a_cargo(campana):
    """Relee lo que otro request puede haber cambiado: estado y pedido de detención."""
    campana.refresh_from_db(fields=["estado", "cancelacion_pedida"])
    return campana.estado == Campana.Estado.ENVIANDO


def _marcar(destinatario_id, estado, *, error=""):
    """Escribe el resultado solo si el destinatario sigue PENDIENTE (RN-007-11)."""
    campos = {"estado": estado, "error": error}
    if estado == Destinatario.Estado.ENVIADO:
        campos["enviado_en"] = timezone.now()
    return Destinatario.objects.filter(pk=destinatario_id, estado=Destinatario.Estado.PENDIENTE).update(**campos)


def correr(campana, *, dormir=time.sleep):
    """Envía los pendientes de la campaña y escribe el desenlace. **Nunca lanza.**

    Corre en un hilo: una excepción que se escapara no la vería nadie y la campaña
    quedaría «Enviando» para siempre. Todo desenlace queda escrito en la campaña.
    """
    try:
        _latir(campana.pk)
        racha = []  # ids de la racha actual de fallos del servidor
        while True:
            if not _sigue_a_cargo(campana):
                return campana  # otro request la cerró: el hilo se retira sin escribir
            if campana.cancelacion_pedida:
                _cerrar(campana, Campana.Estado.CANCELADA, "Se detuvo el envío. Lo enviado quedó enviado.")
                return campana

            lote = max(1, int(getattr(settings, "NOTIF_LOTE", 50)))
            pendientes = list(
                Destinatario.objects.filter(campana_id=campana.pk, estado=Destinatario.Estado.PENDIENTE)
                .order_by("fila_excel", "pk")
                .values_list("pk", "email")[:lote]
            )
            if not pendientes:
                break

            conexion = get_connection(fail_silently=False)
            try:
                conexion.open()
            except Exception as exc:
                logger.exception("Campaña %s: no se pudo abrir la conexión SMTP", campana.pk)
                _dejar_interrumpida(
                    campana.pk,
                    f"No se pudo conectar con el servidor de correo ({_error_corto(exc)}). "
                    "Cuando se normalice, reanudá: sigue con los pendientes.",
                )
                return campana
            try:
                for destinatario_id, email in pendientes:
                    try:
                        conexion.send_messages([armar_mensaje(campana, email, conexion=conexion)])
                    except smtplib.SMTPRecipientsRefused as exc:
                        # Rechazo de esta dirección: es del destinatario, no del servidor.
                        _marcar(destinatario_id, Destinatario.Estado.FALLIDO, error=_error_corto(exc))
                        racha = []
                    except Exception as exc:  # conexión cortada, cuota, timeout…
                        _marcar(destinatario_id, Destinatario.Estado.FALLIDO, error=_error_corto(exc))
                        racha.append(destinatario_id)
                        if len(racha) >= MAX_FALLOS_SEGUIDOS:
                            Destinatario.objects.filter(pk__in=racha, estado=Destinatario.Estado.FALLIDO).update(
                                estado=Destinatario.Estado.PENDIENTE, error=""
                            )
                            _dejar_interrumpida(
                                campana.pk,
                                f"Se frenó tras {MAX_FALLOS_SEGUIDOS} fallos seguidos del servidor de correo "
                                f"(último: {_error_corto(exc)}). Esos correos quedaron pendientes: "
                                "reanudá cuando se normalice.",
                            )
                            return campana
                    else:
                        _marcar(destinatario_id, Destinatario.Estado.ENVIADO)
                        racha = []
                    _latir(campana.pk)
                    if not _sigue_a_cargo(campana):
                        return campana
                    if campana.cancelacion_pedida:
                        _cerrar(campana, Campana.Estado.CANCELADA, "Se detuvo el envío. Lo enviado quedó enviado.")
                        return campana
            finally:
                try:
                    conexion.close()
                except Exception:
                    logger.exception("Campaña %s: no se pudo cerrar la conexión SMTP", campana.pk)

            conteos = _volcar_contadores(campana.pk)
            if conteos[Destinatario.Estado.PENDIENTE]:
                pausa = max(0.0, float(getattr(settings, "NOTIF_PAUSA_SEG", 10)))
                if pausa:
                    dormir(pausa)
                    _latir(campana.pk)

        conteos = contar_por_estado(campana.pk)
        if conteos[Destinatario.Estado.FALLIDO]:
            _cerrar(campana, Campana.Estado.ENVIADA_CON_ERRORES)
        else:
            _cerrar(campana, Campana.Estado.ENVIADA)
        return campana
    except Exception as exc:  # noqa: BLE001 - la campaña es el único lugar donde se puede informar
        logger.exception("Campaña %s: error no previsto en el envío", campana.pk)
        try:
            _dejar_interrumpida(campana.pk, f"Error no previsto: {_error_corto(exc)}")
        except Exception:
            logger.exception("Campaña %s: tampoco se pudo registrar el error", campana.pk)
        return campana


def _en_un_hilo(funcion):
    threading.Thread(target=funcion, daemon=True).start()


def lanzar(campana, *, ejecutor=None):
    """Arranca el envío sin hacer esperar al request.

    ``ejecutor`` se inyecta para correr sincrónico en los tests: con el hilo de verdad,
    las pruebas serían una carrera.
    """

    def trabajo():
        try:
            correr(Campana.objects.get(pk=campana.pk))
        finally:
            # Django abre una conexión por hilo; sin esto queda colgada.
            connection.close()

    (ejecutor or _en_un_hilo)(trabajo)
