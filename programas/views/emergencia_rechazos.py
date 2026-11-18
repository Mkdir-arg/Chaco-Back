"""Cómo se le muestra al backoffice un rechazo de ``crear_caso`` (Cambio 484).

Lo usan «Nuevo caso» de la mesa y el Formulario 1 de la puerta del dispositivo. Es
orquestación HTTP —recibe el ``request`` y descuenta del tope del usuario—, por eso vive
en la capa de vistas y no en la de formularios.
"""

from django.core.exceptions import ValidationError

from programas.api.throttles import descontar_consulta_de_identidad
from programas.services.emergencia_alta import MENSAJE_DNI_REGISTRADO_SIN_CUPO, DniRegistrado


def rechazo_para_mostrar(request, error):
    """El rechazo tal como se le muestra a quien carga desde el backoffice.

    Un :class:`DniRegistrado` trae el nombre de la persona: descuenta de la cubeta de
    consultas de identidad del usuario, y agotada se reemplaza por un error sin el nombre
    (SEC-25). El resto pasa igual.
    """

    if isinstance(error, DniRegistrado) and descontar_consulta_de_identidad(request) is not None:
        return ValidationError({"dni": MENSAJE_DNI_REGISTRADO_SIN_CUPO})
    return error
