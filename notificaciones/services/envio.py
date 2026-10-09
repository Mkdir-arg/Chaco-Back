"""Envío de una campaña en segundo plano (RF-007-10 a RF-007-15, RNF-007-05 a RNF-007-09).

Patrón de ``programas.services.proceso_masivo`` + ``CorridaSiis``:

- el request **no** envía: pasa la campaña a «Enviando» —commiteado— y arranca un hilo
  del pod (``lanzar``), con el ejecutor inyectable para que los tests corran sincrónico;
- el hilo escribe un **latido** por correo; si el pod se recicla, el latido envejece y la
  pantalla muestra el envío como interrumpido y ofrece «Reanudar»;
- «Detener» no cambia el estado: marca ``cancelacion_pedida`` y el hilo corta al terminar
  el correo que tiene entre manos;
- cada «Enviar» o «Reanudar» abre una **corrida** con token propio; el hilo lo compara antes
  de cada correo y se retira si cambió, así un hilo que se creyó muerto no sigue a la par
  del que lo reemplazó;
- antes de mandar, el destinatario se **reclama** (PENDIENTE → EN_CURSO con un ``UPDATE``
  condicional) y solo se manda si el reclamo salió; después queda ENVIADO o FALLIDO, y
  nunca se le vuelve a mandar a un ENVIADO (RN-007-11). La garantía es **al menos una vez**:
  ver ``preparar_reanudacion``.

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
import uuid
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
#: La pausa entre lotes se duerme en tramos de este largo, latiendo en cada uno.
TRAMO_PAUSA = 30
#: Techo de ``NOTIF_PAUSA_SEG``: por debajo de la mitad del umbral de latido vencido, con
#: un tramo de margen. Una pausa mayor se recorta acá, sin depender del entorno.
PAUSA_MAXIMA = Campana.LATIDO_VENCIDO.total_seconds() / 2 - TRAMO_PAUSA


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
def _token_nuevo():
    return uuid.uuid4().hex


def iniciar_envio(campana, *, usuario):
    """«A enviar» → «Enviando», registrando quién y cuándo. Commitea antes de devolver.

    El candado es la propia fila (``select_for_update``): si dos personas aprietan
    Enviar a la vez, la segunda espera, lee «Enviando» y recibe ``TransicionInvalida``
    (RNF-007-07). El candado dura dos consultas: no compromete el ``read_timeout`` de ECOM.
    La campaña devuelta trae el token de la corrida nueva, que es el que recibe ``lanzar``.
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
        actual.corrida = _token_nuevo()
        actual.save(
            update_fields=[
                "estado",
                "enviada_por",
                "enviada_en",
                "latido",
                "cancelacion_pedida",
                "mensaje",
                "corrida",
                "modificado",
            ]
        )
    return actual


def preparar_reanudacion(campana):
    """Toma un envío interrumpido para seguirlo con los pendientes (RF-007-15).

    Con el candado tomado: renueva el latido (un segundo «Reanudar» simultáneo ya no la ve
    interrumpida y recibe ``TransicionInvalida``), pone un **token de corrida nuevo** —si el
    hilo viejo en realidad seguía vivo, lo compara antes del próximo correo y se retira— y
    devuelve a PENDIENTE los EN_CURSO que quedaron reclamados por la corrida anterior.

    Semántica **al menos una vez**: un correo que la corrida vieja estaba mandando justo en
    el momento de reanudar puede salir dos veces (el SMTP lo aceptó, pero el hilo murió antes
    de anotarlo, o lo anota después de que la corrida nueva lo volvió a reclamar). Es a lo
    sumo un correo por corrida reemplazada; nunca se reenvía a un ENVIADO ya anotado.
    """
    with transaction.atomic():
        actual = Campana.objects.select_for_update().get(pk=campana.pk)
        if not actual.interrumpida:
            raise TransicionInvalida("Solo se reanuda un envío interrumpido.")
        actual.latido = timezone.now()
        actual.cancelacion_pedida = False
        actual.mensaje = ""
        actual.corrida = _token_nuevo()
        actual.save(update_fields=["latido", "cancelacion_pedida", "mensaje", "corrida", "modificado"])
        Destinatario.objects.filter(campana_id=actual.pk, estado=Destinatario.Estado.EN_CURSO).update(
            estado=Destinatario.Estado.PENDIENTE
        )
    return actual


def pedir_detencion(campana):
    """«Detener envío» (RF-007-14). Devuelve ``True`` si quedó cancelada en el acto.

    Con el hilo vivo solo se marca el pedido: el estado final lo escribe quien está
    enviando, al terminar el correo en curso (si lo marcara este request, la pantalla
    diría «Cancelada» mientras sale un correo más). Con el envío interrumpido no hay
    hilo que lo lea, así que se cancela acá, y se le saca el token a la corrida por si el
    hilo seguía vivo: al compararlo, se retira.
    """
    with transaction.atomic():
        actual = Campana.objects.select_for_update().get(pk=campana.pk)
        if actual.estado != Campana.Estado.ENVIANDO:
            raise TransicionInvalida("Solo se detiene una campaña que se está enviando.")
        if actual.interrumpida:
            Destinatario.objects.filter(campana_id=actual.pk, estado=Destinatario.Estado.EN_CURSO).update(
                estado=Destinatario.Estado.PENDIENTE
            )
            _cerrar(
                actual, None, Campana.Estado.CANCELADA, "Se detuvo un envío interrumpido. Lo enviado quedó enviado."
            )
            Campana.objects.filter(pk=actual.pk).update(corrida=None)
            return True
        Campana.objects.filter(pk=actual.pk).update(cancelacion_pedida=True)
    return False


# ---------------------------------------------------------------------------
# El hilo
# ---------------------------------------------------------------------------
def contar_por_estado(campana_id):
    """``{PENDIENTE: n, EN_CURSO: n, ENVIADO: n, FALLIDO: n}`` en una consulta."""
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


def _de_la_corrida(campana_id, token):
    """La fila de la campaña, solo si la corrida ``token`` sigue a cargo.

    Todo lo que escribe el hilo pasa por acá: un hilo reemplazado no late (no mantiene
    «viva» una campaña que ya no maneja), no cierra y no deja mensajes. ``token=None`` es la
    escritura de un request (detener una interrumpida), que no compite con ningún hilo.
    """
    filas = Campana.objects.filter(pk=campana_id)
    return filas if token is None else filas.filter(corrida=token)


def _latir(campana_id, token=None):
    """Solo la señal de vida: no usa ``save()`` para no pisar ``cancelacion_pedida``."""
    _de_la_corrida(campana_id, token).update(latido=timezone.now())


def _contadores(campana_id):
    conteos = contar_por_estado(campana_id)
    return conteos, {"enviados": conteos[Destinatario.Estado.ENVIADO], "fallidos": conteos[Destinatario.Estado.FALLIDO]}


def _volcar_contadores(campana_id, token):
    conteos, campos = _contadores(campana_id)
    _de_la_corrida(campana_id, token).update(latido=timezone.now(), **campos)
    return conteos


def _cerrar(campana, token, estado, mensaje=""):
    _conteos, campos = _contadores(campana.pk)
    ahora = timezone.now()
    _de_la_corrida(campana.pk, token).update(
        estado=estado, finalizada_en=ahora, mensaje=mensaje, modificado=ahora, **campos
    )


def _dejar_interrumpida(campana_id, token, mensaje):
    """Deja el envío «interrumpido» **ya**, con el motivo, para que se ofrezca Reanudar.

    La interrupción se deduce del latido (``Campana.interrumpida``), así que se lo fecha
    más atrás que el umbral: esperar cinco minutos a que venza solo dejaría la pantalla
    diciendo «Enviando» sin que nadie envíe.
    """
    vencido = timezone.now() - Campana.LATIDO_VENCIDO - timedelta(seconds=1)
    _conteos, campos = _contadores(campana_id)
    _de_la_corrida(campana_id, token).update(latido=vencido, mensaje=mensaje[:LARGO_ERROR], **campos)


def _sigue_a_cargo(campana, token):
    """¿La corrida ``token`` sigue a cargo? Relee estado, pedido de detención y token.

    Dos columnas y el token, no un ``refresh_from_db``: se lee antes de cada correo.
    """
    fila = Campana.objects.filter(pk=campana.pk).values_list("estado", "cancelacion_pedida", "corrida").first()
    if fila is None:
        return False
    campana.estado, campana.cancelacion_pedida, corrida = fila
    return campana.estado == Campana.Estado.ENVIANDO and corrida == token


def _reclamar(destinatario_id):
    """PENDIENTE → EN_CURSO con un ``UPDATE`` condicional. Solo se manda si devolvió 1.

    Dos corridas sobre la misma campaña (la vieja que se creyó muerta y la que la
    reemplazó) nunca mandan al mismo destinatario: la base deja pasar una sola.
    """
    return (
        Destinatario.objects.filter(pk=destinatario_id, estado=Destinatario.Estado.PENDIENTE).update(
            estado=Destinatario.Estado.EN_CURSO
        )
        == 1
    )


def _anotar(destinatario_id, estado, *, error=""):
    """Escribe el resultado de un correo que **salió del servidor** (o que este rechazó).

    Vale desde EN_CURSO y también desde PENDIENTE: si una reanudación devolvió el reclamo a
    pendientes mientras el correo salía, anotarlo igual evita que la corrida nueva lo
    reenvíe. Nunca pisa un ENVIADO ni un FALLIDO (RN-007-11).
    """
    campos = {"estado": estado, "error": error}
    if estado == Destinatario.Estado.ENVIADO:
        campos["enviado_en"] = timezone.now()
    return Destinatario.objects.filter(
        pk=destinatario_id, estado__in=(Destinatario.Estado.EN_CURSO, Destinatario.Estado.PENDIENTE)
    ).update(**campos)


def _devolver(destinatario_id):
    """EN_CURSO → PENDIENTE: el correo no salió por un problema del servidor, no de la dirección."""
    Destinatario.objects.filter(pk=destinatario_id, estado=Destinatario.Estado.EN_CURSO).update(
        estado=Destinatario.Estado.PENDIENTE
    )


def pausa_entre_lotes():
    """``NOTIF_PAUSA_SEG`` acotada: nunca llega a la mitad del umbral de latido vencido."""
    pedida = max(0.0, float(getattr(settings, "NOTIF_PAUSA_SEG", 10)))
    return min(pedida, PAUSA_MAXIMA)


def _dormir_latiendo(campana, token, segundos, dormir):
    """Duerme en tramos de hasta ``TRAMO_PAUSA`` segundos y late en cada uno.

    Una pausa larga sin latido hacía que la campaña se viera interrumpida con el hilo vivo,
    y entonces «Reanudar» lanzaba un segundo hilo. Devuelve ``False`` si en el medio la
    corrida dejó de estar a cargo.
    """
    restante = segundos
    while restante > 0:
        tramo = min(TRAMO_PAUSA, restante)
        dormir(tramo)
        restante -= tramo
        _latir(campana.pk, token)
        if not _sigue_a_cargo(campana, token):
            return False
    return True


def _es_rechazo_del_destinatario(exc):
    """El servidor rechazó **esta dirección** (RCPT TO 5xx): falla del destinatario.

    Cualquier otra excepción —conexión cortada, timeout, rechazo por volumen, error de
    datos— es del servidor: el destinatario vuelve a pendientes y se reintenta.
    """
    return isinstance(exc, smtplib.SMTPRecipientsRefused)


def correr(campana, *, token=None, dormir=time.sleep):
    """Envía los pendientes de la campaña y escribe el desenlace. **Nunca lanza.**

    Corre en un hilo: una excepción que se escapara no la vería nadie y la campaña
    quedaría «Enviando» para siempre. Todo desenlace queda escrito en la campaña.

    ``token`` es la corrida que lanzó este hilo (por defecto, la que trae la campaña).
    Antes de cada correo se verifica que siga siendo la corrida a cargo; si no, el hilo se
    retira sin escribir nada más.
    """
    token = token or campana.corrida
    try:
        _latir(campana.pk, token)
        racha = 0  # fallos seguidos del servidor
        ultimo_error = ""
        while True:
            if not _sigue_a_cargo(campana, token):
                return campana  # otro request u otra corrida tomó la campaña: se retira
            if campana.cancelacion_pedida:
                _cerrar(campana, token, Campana.Estado.CANCELADA, "Se detuvo el envío. Lo enviado quedó enviado.")
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
                    token,
                    f"No se pudo conectar con el servidor de correo ({_error_corto(exc)}). "
                    "Cuando se normalice, reanudá: sigue con los pendientes.",
                )
                return campana
            try:
                for destinatario_id, email in pendientes:
                    if not _sigue_a_cargo(campana, token):
                        return campana
                    if campana.cancelacion_pedida:
                        _cerrar(
                            campana, token, Campana.Estado.CANCELADA, "Se detuvo el envío. Lo enviado quedó enviado."
                        )
                        return campana
                    if not _reclamar(destinatario_id):
                        continue  # lo tomó otra corrida
                    try:
                        conexion.send_messages([armar_mensaje(campana, email, conexion=conexion)])
                    except Exception as exc:
                        if _es_rechazo_del_destinatario(exc):
                            _anotar(destinatario_id, Destinatario.Estado.FALLIDO, error=_error_corto(exc))
                            racha = 0
                        else:
                            # Falla del servidor: el correo no salió. Vuelve a pendientes, se
                            # corta el lote (la conexión puede estar rota) y el próximo reabre.
                            _devolver(destinatario_id)
                            racha += 1
                            ultimo_error = _error_corto(exc)
                            _latir(campana.pk, token)
                            break
                    else:
                        _anotar(destinatario_id, Destinatario.Estado.ENVIADO)
                        racha = 0
                    _latir(campana.pk, token)
            finally:
                try:
                    conexion.close()
                except Exception:
                    logger.exception("Campaña %s: no se pudo cerrar la conexión SMTP", campana.pk)

            if racha >= MAX_FALLOS_SEGUIDOS:
                _dejar_interrumpida(
                    campana.pk,
                    token,
                    f"Se frenó tras {MAX_FALLOS_SEGUIDOS} fallos seguidos del servidor de correo "
                    f"(último: {ultimo_error}). Esos correos siguen pendientes: reanudá cuando se normalice.",
                )
                return campana

            conteos = _volcar_contadores(campana.pk, token)
            if conteos[Destinatario.Estado.PENDIENTE]:
                pausa = pausa_entre_lotes()
                if pausa and not _dormir_latiendo(campana, token, pausa, dormir):
                    return campana

        conteos = contar_por_estado(campana.pk)
        if conteos[Destinatario.Estado.EN_CURSO]:
            # Otra corrida tiene correos reclamados: el cierre lo hace la última que termine.
            return campana
        if conteos[Destinatario.Estado.FALLIDO]:
            _cerrar(campana, token, Campana.Estado.ENVIADA_CON_ERRORES)
        else:
            _cerrar(campana, token, Campana.Estado.ENVIADA)
        return campana
    except Exception as exc:  # noqa: BLE001 - la campaña es el único lugar donde se puede informar
        logger.exception("Campaña %s: error no previsto en el envío", campana.pk)
        try:
            _dejar_interrumpida(campana.pk, token, f"Error no previsto: {_error_corto(exc)}")
        except Exception:
            logger.exception("Campaña %s: tampoco se pudo registrar el error", campana.pk)
        return campana


def _en_un_hilo(funcion):
    threading.Thread(target=funcion, daemon=True).start()


def lanzar(campana, *, ejecutor=None):
    """Arranca el envío sin hacer esperar al request.

    El token de la corrida se toma **acá**, de la campaña que devolvió ``iniciar_envio`` o
    ``preparar_reanudacion``: si el hilo lo leyera de la base al arrancar y en el medio
    hubo otra reanudación, dos hilos compartirían token. ``ejecutor`` se inyecta para correr
    sincrónico en los tests: con el hilo de verdad, las pruebas serían una carrera.
    """
    token = campana.corrida

    def trabajo():
        try:
            correr(Campana.objects.get(pk=campana.pk), token=token)
        finally:
            # Django abre una conexión por hilo; sin esto queda colgada.
            connection.close()

    (ejecutor or _en_un_hilo)(trabajo)
