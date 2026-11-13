"""Lo que el módulo Emergencia necesita solo cuando el dato llega desde la app de campo.

Las reglas del caso están en ``programas.services.emergencia`` y valen para cualquier
origen. Acá va lo que es propio de un envío hecho desde un teléfono: qué se hace con la
hora que manda el cliente.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from programas.services.campo import ADELANTO_TOLERADO

#: Hasta dónde un ``relevado_en`` adelantado se toma por un reloj mal puesto. Más allá no
#: es un desfasaje: es una fecha que no se puede guardar.
ADELANTO_MAXIMO_DE_RELOJ = timedelta(hours=24)

RELEVADO_EN_FUTURO = (
    "La fecha del relevamiento es posterior a hoy. Revisá la fecha y la hora del teléfono y volvé a enviar."
)


def acotar_relevado_en(relevado_en, ahora=None):
    """La hora del teléfono al tocar «Enviar», lista para guardar (RN-1.8, RU-18).

    Es la **única** hora del cliente que guarda el módulo, y solo informa («relevado 14:20
    · enviado 16:05»): ningún tramo del SLA se calcula con ella. Por eso un pasado lejano
    se acepta tal cual —un envío puede esperar días sin señal— y lo que se mira es el
    futuro:

    * dentro de la tolerancia de la app de campo (``campo.ADELANTO_TOLERADO``) queda como
      vino;
    * adelantada hasta un día, se recorta a ``ahora``: es un reloj mal puesto, y rechazar
      el envío dejaría cada familia de ese teléfono en 400 hasta que alguien le arregle la
      hora (la lección K2 de Becas);
    * adelantada más de un día, ``ValidationError`` en ``relevado_en``: no hay hora del
      servidor que la reemplace con sentido y la bandeja mostraría un relevamiento que
      todavía no ocurrió.

    ``None`` se devuelve como ``None``: ``crear_caso`` pone entonces la hora del servidor.
    """
    if relevado_en is None:
        return None
    ahora = ahora or timezone.now()
    if relevado_en > ahora + ADELANTO_MAXIMO_DE_RELOJ:
        raise ValidationError({"relevado_en": RELEVADO_EN_FUTURO})
    if relevado_en > ahora + ADELANTO_TOLERADO:
        return ahora
    return relevado_en
