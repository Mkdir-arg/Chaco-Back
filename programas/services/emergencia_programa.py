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
#: E8 «Situación» (análisis 009, §3.2): la de las autoridades, que miran sin operar la mesa.
CAP_VER_SITUACION = "emergencia.ver_situacion"
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


def puede_ver_situacion(user):
    """¿Ve E8? ``emergencia.ver_situacion`` **o** ``emergencia.supervisar`` en el programa.

    Supervisar implica ver la situación (análisis 009, §3.2), igual que implica operar: la regla
    no depende de cómo se armó el rol. Operar sola no alcanza.
    """
    return puede_en_programa_emergencia(user, CAP_VER_SITUACION) or puede_supervisar_la_mesa(user)


def roles_en_app(user):
    """Qué accesos del módulo Emergencia abre ``user`` en la app de campo (RU-5).

    Devuelve ``{"relevar": bool, "llegadas": bool, "kits": bool, "dispositivo": bool}``:

    * ``relevar`` — es agente territorial: ``emergencia.relevar`` en el programa EMERGENCIA.
      Abre «Ingreso de familias» (M1).
    * ``llegadas`` — admite familias en algún dispositivo (:func:`admite_familias`). Abre
      «Llegada de familias» (M2).
    * ``kits`` — recibe kits en algún dispositivo (:func:`recibe_kits`). Abre «Recepción de
      kits» (M3).
    * ``dispositivo`` — ``llegadas or kits``: **opera de verdad** en algún dispositivo. Se
      mantiene por compatibilidad con la app que todavía no lee las dos de arriba.

    Las dos capacidades de la guardia van con alcance: integra el **Equipo** de algún
    dispositivo con un rol que la tiene, o administra el programa Dispositivos **y** su rol la
    tiene. El administrador del programa Dispositivos **sin** ninguna de las dos abre el módulo
    (H10, :func:`modulo_habilitado`), pero los servicios de alojar y de kits le niegan todo:
    para él las tres son ``False`` (PR 8), y la app no le ofrece pantallas que después le
    contestan 403. Puede pasar entonces que vengan todas en ``False``.

    La capacidad tildada en un rol **sin** Equipo no alcanza: no hay dispositivo sobre el
    que ejercerla. Y ninguna capacidad de otro programa (``becas.campo``,
    ``inspeccion.relevar``) entra en esta cuenta (RU §6 n.° 3).
    """
    llegadas = admite_familias(user)
    kits = recibe_kits(user)
    return {
        "relevar": puede_en_programa_emergencia(user, CAP_EMERGENCIA_RELEVAR),
        "llegadas": llegadas,
        "kits": kits,
        "dispositivo": llegadas or kits,
    }


def admite_familias(usuario):
    """¿``usuario`` admite familias en **algún** dispositivo? Lo que abre «Llegada de familias» (M2).

    ``dispositivo.admitir`` con alcance —en el Equipo de alguna institución, o en todas si
    además administra el programa Dispositivos—. La capacidad tildada en un rol **sin** Equipo
    no alcanza. Quien no pasa esto recibe 403; quien lo pasa y pide un dispositivo, una
    derivación o un caso que no son suyos, 404 (C2).
    """

    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    return dispositivos_en_alcance(usuario, CAP_ADMITIR).exists()


def recibe_kits(usuario):
    """¿``usuario`` recibe kits en **algún** dispositivo? Lo que abre «Recepción de kits» (web y M3).

    ``emergencia.recibir_kit`` con alcance: en el Equipo de alguna institución, o en todas si
    además administra el programa Dispositivos. La capacidad tildada en un rol **sin** Equipo
    no alcanza: no hay dispositivo sobre el que ejercerla. Quien no pasa esto recibe 403; quien
    lo pasa y pide un dispositivo o una entrega que no son suyos, 404 (plan §2, C2).

    Vive acá, junto a :func:`admite_familias`, y ``kits`` la reexporta: la dependencia va de
    ``kits`` hacia este módulo, nunca al revés.
    """

    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    return dispositivos_en_alcance(usuario, CAP_RECIBIR_KIT).exists()


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
