"""Las piezas que comparten el alta del caso, la mesa y la etapa 3 de Emergencia.

``programas.services.emergencia_alta`` (crear el caso), ``programas.services.emergencia``
(lo que le pasa después) y los módulos de la etapa 3 (``emergencia_alojar`` y los que
reexporta) usan la misma traza, el mismo permiso de la mesa, el mismo numerador y el
mismo primer candado (el del caso). Viven acá para que la dependencia vaya en un solo sentido —los dos
importan de este módulo, y ``emergencia`` reexporta el alta— sin un ciclo de imports
sostenido por un import diferido (``programas.tests.test_arquitectura``).

``emergencia`` las reexporta: quien las importa o las parcha desde ahí sigue andando.
El numerador es una hoja del orden de los candados que documenta aquel módulo.
"""

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from programas.models import CasoEmergencia, NumeradorEmergencia, TrazaCaso
from programas.services.emergencia_programa import puede_operar_la_mesa

SIN_PERMISO_DE_MESA = "No tenés permiso para operar la mesa de Emergencia."


def _exigir_mesa(usuario):
    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)


def _trazar(caso, usuario, accion, *, estado_anterior, detalle="", por_supervisor=False):
    """Una fila de ``TrazaCaso``: aditiva e inmutable, en la transacción de la acción.

    El detalle nombra a quienes trabajan en la mesa, nunca a la familia: la ficha de la
    persona vive en su legajo, con su propio control de acceso.
    """

    if por_supervisor:
        detalle = f"{detalle} · por supervisor" if detalle else "Por supervisor"
    return TrazaCaso.objects.create(
        caso=caso,
        usuario=usuario,
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=caso.estado,
        detalle=detalle,
        por_supervisor=por_supervisor,
    )


def _bloquear_numerador(serie, anio):
    """La fila del contador con ``FOR UPDATE``: quien numera espera acá al anterior."""

    return NumeradorEmergencia.objects.select_for_update().get(serie=serie, anio=anio)


def siguiente_numero(serie, momento=None):
    """El próximo número de ``serie`` («2026-000184»), bloqueando su contador.

    Una fila por serie y año con ``select_for_update``: quien numera espera al anterior y
    suma uno sobre lo que aquel dejó. Nunca ``MAX() + 1``. El año es el de la hora local.
    Tiene que correr dentro de una transacción: el candado se suelta con su commit, y si
    la transacción vuelve atrás el número también. La serie ``K`` es la de las entregas
    de kits.
    """

    anio = timezone.localtime(momento or timezone.now()).year
    NumeradorEmergencia.objects.get_or_create(serie=serie, anio=anio)
    numerador = _bloquear_numerador(serie, anio)
    numerador.ultimo += 1
    numerador.save(update_fields=["ultimo", "modificado"])
    return CasoEmergencia.formatear_numero(anio, numerador.ultimo)


def _nombre_de(usuario):
    """Nombre y apellido de quien trabaja en la mesa o en la guardia; ``"nadie"`` sin usuario."""

    if usuario is None:
        return "nadie"
    return usuario.get_full_name().strip() or usuario.get_username()


def _hora(momento):
    """«14:05», en hora local."""

    return f"{timezone.localtime(momento):%H:%M}"


def _bloquear_caso(caso):
    """La fila del caso con ``FOR UPDATE``, recién leída. **Siempre el primer candado.**

    Sin ``select_related``: un JOIN acá bloquearía también las filas que trae.
    """

    return CasoEmergencia.objects.select_for_update().get(pk=getattr(caso, "pk", caso))
