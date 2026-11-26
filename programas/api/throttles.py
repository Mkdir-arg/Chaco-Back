"""Los topes por usuario de la API de campo que se comparten con el backoffice.

Viven acá, y no en ``programas.api.views``, porque el backoffice de Emergencia también
descuenta de la cubeta de la consulta de identidad (Cambio 486) y no tiene por qué cargar
las vistas de la API para hacerlo. :func:`rechazo_para_mostrar` es la mitad del backoffice:
la usan dos vistas, y un helper compartido entre vistas no vive en ``programas/views/``.
"""

from django.core.exceptions import ValidationError
from rest_framework.throttling import UserRateThrottle

from programas.services.emergencia_alta import MENSAJE_DNI_REGISTRADO_SIN_CUPO, DniRegistrado


class ConsultaPersonasThrottle(UserRateThrottle):
    """SEC-25 · tope de la consulta de identidad de la app (``personas_campo``).

    **Por usuario, no por IP** (``UserRateThrottle`` toma ``request.user.pk``
    cuando hay sesión o token, que es siempre acá: el permiso corre antes que el
    throttle y un anónimo ya se fue en 403). Una cubeta por IP le cerraría la
    consulta a toda una región: los territoriales salen por el NAT de la
    operadora móvil. Es además la razón por la que esto **no** toca
    ``NUM_PROXIES``, que vale distinto en DEV (nginx) y en ECOM (ingress).

    El 429 no rompe nada en el teléfono instalado: ``RelevamientoDetailScreen``
    atrapa el error de la consulta, cae a carga manual y el caso entra sin
    validar (``Chaco-mobile@a66c2d3``). No pasa por la cola de sincronización,
    así que no hay ``FAILED_PERMANENT`` posible.
    """

    scope = "personas_campo"


class StockEscrituraThrottle(UserRateThrottle):
    """Tope por usuario de las escrituras de stock de la app (``stock_escritura``, PR 7b).

    Una entrega a una persona puede consultar al Registro de Personas, así que no queda sin tope; pero una guardia en
    plena distribución entrega a decenas de familias por hora, de modo que el límite es holgado. Por usuario, no por
    IP, por la misma razón que ``personas_campo``. La entrega no devuelve el nombre, pero un rechazo por la persona
    (sin datos, DNI de un fallecido) o por el saldo revela si el DNI existe: esos rechazos descuentan además de
    ``personas_campo`` (``descontar_consulta_de_identidad``); la entrega asentada no.
    """

    scope = "stock_escritura"


def descontar_consulta_de_identidad(request):
    """Descuenta una consulta de la cubeta ``personas_campo`` del usuario (SEC-25).

    El rechazo «DNI ya registrado» de ``crear_caso`` devuelve el nombre de la persona: es
    una consulta de identidad por otra puerta y cuenta igual, en la API y en el backoffice
    (Cambio 486). Devuelve ``None`` si quedaba cupo; si no, los segundos a esperar.
    """

    throttle = ConsultaPersonasThrottle()
    if throttle.allow_request(request, None):
        return None
    return throttle.wait() or 0


def rechazo_para_mostrar(request, error):
    """El rechazo de ``crear_caso`` tal como se le muestra a quien carga desde el backoffice.

    Un :class:`DniRegistrado` trae el nombre de la persona: descuenta de la cubeta de
    consultas de identidad del usuario, y agotada se reemplaza por un error sin el nombre
    (SEC-25). El resto pasa igual. Lo usan «Nuevo caso» de la mesa y el Formulario 1 de la
    puerta del dispositivo.
    """

    if isinstance(error, DniRegistrado) and descontar_consulta_de_identidad(request) is not None:
        return ValidationError({"dni": MENSAJE_DNI_REGISTRADO_SIN_CUPO})
    return error
