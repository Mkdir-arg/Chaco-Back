"""El programa EMERGENCIA y la autorización con alcance sobre él (RU-6 y RU-7).

Es el espejo de ``programa_dispositivos`` / ``puede_en_programa_dispositivos``
(``programas/services/dispositivos.py``): las capacidades del módulo ``emergencia`` del
``CATALOGO`` son «de programa», así que se preguntan **siempre** con el programa
EMERGENCIA. Preguntarlas sin alcance contesta «la tiene por algún rol», que es la forma
en que un rol de otro programa terminaba abriendo un módulo ajeno.
"""

from core import rbac
from programas.services.dispositivos import (
    dispositivos_en_alcance,
    dispositivos_operados,
    puede_configurar_dispositivos,
)
from programas.services.programa_cache import programa_por_codigo

PROGRAMA_EMERGENCIA_CODIGO = rbac.CODIGO_PROGRAMA_EMERGENCIA

CAP_EMERGENCIA_RELEVAR = "emergencia.relevar"
CAP_EMERGENCIA_OPERAR = "emergencia.operar"
CAP_SUPERVISAR = "emergencia.supervisar"
#: Las dos de la guardia del dispositivo. Son del programa **Dispositivos** (RU-8, hallazgo
#: H3 del plan): se evalúan con el Equipo de cada institución, no con el programa EMERGENCIA.
CAP_ADMITIR = "dispositivo.admitir"
CAP_RECIBIR_KIT = "emergencia.recibir_kit"


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


def roles_en_app(user):
    """Qué accesos del módulo Emergencia abre ``user`` en la app de campo (RU-5).

    Devuelve ``{"relevar": bool, "dispositivo": bool}``:

    * ``relevar`` — es agente territorial: ``emergencia.relevar`` en el programa EMERGENCIA.
      Abre «Ingreso de familias» (M1).
    * ``dispositivo`` — **opera de verdad** en algún dispositivo: tiene ``dispositivo.admitir``
      o ``emergencia.recibir_kit`` con alcance (:func:`opera_en_algun_dispositivo`): integra
      el **Equipo** de alguno con un rol que la tiene, o administra el programa Dispositivos
      **y** su rol la tiene. Abre «Llegada de familias» (M2) y «Recepción de kits» (M3).

      El administrador del programa Dispositivos **sin** ninguna de las dos abre el módulo
      (H10, :func:`modulo_habilitado`), pero los servicios de alojar y de kits le niegan
      todo: para él ``dispositivo`` es ``False`` (PR 8), y la app no le ofrece pantallas que
      después le contestan 403. Puede pasar entonces que vengan los dos en ``False``.

    La capacidad tildada en un rol **sin** Equipo no alcanza: no hay dispositivo sobre el
    que ejercerla. Y ninguna capacidad de otro programa (``becas.campo``,
    ``inspeccion.relevar``) entra en esta cuenta (RU §6 n.° 3).

    Cuesta a lo sumo tres consultas chicas y ninguna si el usuario no tiene las capacidades
    en el programa: ``dispositivos_operados`` corta antes de ir al Equipo.
    """
    return {
        "relevar": puede_en_programa_emergencia(user, CAP_EMERGENCIA_RELEVAR),
        "dispositivo": opera_en_algun_dispositivo(user),
    }


def opera_en_algun_dispositivo(user):
    """¿``user`` puede admitir familias o recibir kits en **algún** dispositivo? (perfil, PR 8).

    Es la misma regla que aplican los servicios (``puede_operar_dispositivo``) en forma de
    «existe alguno»: la capacidad en el programa Dispositivos y el alcance —el Equipo, o todo
    si además administra el programa—. A lo sumo cuatro consultas chicas.
    """
    return (
        dispositivos_en_alcance(user, CAP_ADMITIR).exists() or dispositivos_en_alcance(user, CAP_RECIBIR_KIT).exists()
    )


def _es_de_la_guardia(user):
    return (
        dispositivos_operados(user, CAP_ADMITIR).exists()
        or dispositivos_operados(user, CAP_RECIBIR_KIT).exists()
        or puede_configurar_dispositivos(user)
    )


def modulo_habilitado(user):
    """¿``user`` abre el módulo Emergencia de la app? **La única regla de acceso** (H10).

    La consultan el login (``"emergencia"`` en ``modulos``) y los permisos de
    ``/api/emergencia/``: si cada uno escribiera la suya, el login le ofrecería a alguien
    un módulo que después le contesta 403, o al revés. Es verdadera cuando
    :func:`roles_en_app` da algún acceso, y también para el administrador del programa
    Dispositivos sin ``dispositivo.admitir`` ni ``emergencia.recibir_kit`` (H10: el login no
    cambia); a ese el perfil le contesta ``dispositivo: false``.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return puede_en_programa_emergencia(user, CAP_EMERGENCIA_RELEVAR) or _es_de_la_guardia(user)
