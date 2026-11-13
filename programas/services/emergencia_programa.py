"""El programa EMERGENCIA y la autorización con alcance sobre él (RU-6 y RU-7).

Es el espejo de ``programa_dispositivos`` / ``puede_en_programa_dispositivos``
(``programas/services/dispositivos.py``): las capacidades del módulo ``emergencia`` del
``CATALOGO`` son «de programa», así que se preguntan **siempre** con el programa
EMERGENCIA. Preguntarlas sin alcance contesta «la tiene por algún rol», que es la forma
en que un rol de otro programa terminaba abriendo un módulo ajeno.
"""

from core import rbac
from programas.services.programa_cache import programa_por_codigo

PROGRAMA_EMERGENCIA_CODIGO = rbac.CODIGO_PROGRAMA_EMERGENCIA

CAP_EMERGENCIA_RELEVAR = "emergencia.relevar"
CAP_EMERGENCIA_OPERAR = "emergencia.operar"
CAP_SUPERVISAR = "emergencia.supervisar"


def programa_emergencia(user=None):
    """El ``Programa`` EMERGENCIA (o ``None`` si no está sembrado), memoizado por request.

    Fachada sobre :func:`programas.services.programa_cache.programa_por_codigo`.
    """
    return programa_por_codigo(PROGRAMA_EMERGENCIA_CODIGO, user=user)


def puede_en_programa_emergencia(user, capacidad):
    """Evalúa una capacidad ``emergencia.*`` con alcance al programa EMERGENCIA.

    Sin el programa sembrado nadie puede nada (ni el superusuario): no hay contra qué
    evaluar el alcance, y fallar cerrado es lo que hace Dispositivos.
    """
    programa = programa_emergencia(user)
    return programa is not None and rbac.puede(user, capacidad, programa=programa)


def puede_supervisar_la_mesa(user):
    """``emergencia.supervisar`` en el programa: reasignar y actuar sobre casos ajenos (RU-13)."""
    return puede_en_programa_emergencia(user, CAP_SUPERVISAR)


def puede_operar_la_mesa(user):
    """¿Trabaja en la mesa? ``emergencia.operar`` **o** ``emergencia.supervisar`` en el programa.

    El supervisor hace todo lo del operador (tabla de RU §4) tenga o no tildada además la
    capacidad de operar: que su rol la traiga es una decisión de quien arma los roles, y la
    regla no puede depender de eso.
    """
    return puede_en_programa_emergencia(user, CAP_EMERGENCIA_OPERAR) or puede_supervisar_la_mesa(user)
