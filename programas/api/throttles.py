"""Los topes por usuario de la API de campo que se comparten con el backoffice.

Viven acá, y no en ``programas.api.views``, porque el backoffice de Emergencia también
descuenta de la cubeta de la consulta de identidad (Cambio 482) y no tiene por qué cargar
las vistas de la API para hacerlo.
"""

from rest_framework.throttling import UserRateThrottle


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


def descontar_consulta_de_identidad(request):
    """Descuenta una consulta de la cubeta ``personas_campo`` del usuario (SEC-25).

    El rechazo «DNI ya registrado» de ``crear_caso`` devuelve el nombre de la persona: es
    una consulta de identidad por otra puerta y cuenta igual, en la API y en el backoffice
    (Cambio 482). Devuelve ``None`` si quedaba cupo; si no, los segundos a esperar.
    """

    throttle = ConsultaPersonasThrottle()
    if throttle.allow_request(request, None):
        return None
    return throttle.wait() or 0
