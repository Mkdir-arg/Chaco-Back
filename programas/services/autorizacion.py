"""Autorización del Programa Becas: integra el RBAC (alcance de programa) con el
alcance fino por segmento del Coordinador (``AsignacionCoordinador``).

Regla (#79):
- **Admin del programa** (capacidad ``becas.programa.administrar``): acceso
  total → todos los segmentos.
- **Coordinador** (alguna capacidad fina de Becas sin ``becas.programa.administrar``):
  solo los segmentos donde tiene una asignación activa.
- **Territorial** (solo ``becas.campo``) y cualquier otro: sin acceso de gestión.

El RBAC tiene alcance de *programa*, no de *segmento*; el alcance por segmento lo
aporta este módulo combinando la capacidad con ``AsignacionCoordinador``.
"""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from core import rbac
from programas.services.becas import coordinador_gestiona_segmento, get_segmentos_coordinador

CAP_ADMINISTRAR = "becas.programa.administrar"
CAP_CAMPO = "becas.campo"
CAP_REFERENTE = "becas.referente"
CAP_COORD_REGIONAL = "becas.coordinador_regional"


def _caps_gestion():
    """Capacidades finas de Becas que habilitan operar segmentos scoped.

    Es dinámica (no una lista fija): cualquier capacidad del catálogo cuyo
    código empiece con ``"becas."`` cuenta como "de gestión", salvo la
    capacidad paraguas (``CAP_ADMINISTRAR``, que da bypass total) y la de
    campo (``CAP_CAMPO``, que no opera segmentos desde el backoffice).
    """
    return [c for c in rbac.codigos_de_capacidad() if c.startswith("becas.") and c not in (CAP_ADMINISTRAR, CAP_CAMPO)]


CAPS_GESTION = _caps_gestion()

# Programa genérico que ancla el alcance del RBAC de Becas (sembrado por seed_becas).
PROGRAMA_BECAS_CODIGO = "BECAS"
_PROGRAMA_BECAS_CACHE_KEY = "programas:becas"


def programa_becas():
    """Instancia genérica del Programa Becas, o None si no está sembrada.

    Se consulta en casi todos los checks de autorización de Becas, así que se
    cachea 5 minutos. Solo se cachea cuando existe (cachear el None rompería
    los tests que siembran el programa después de la primera consulta).
    """
    from django.core.cache import cache

    from programas.models import Programa

    programa = cache.get(_PROGRAMA_BECAS_CACHE_KEY)
    if programa is None:
        programa = Programa.objects.filter(codigo=PROGRAMA_BECAS_CODIGO).first()
        if programa is not None:
            cache.set(_PROGRAMA_BECAS_CACHE_KEY, programa, 300)
    return programa


def es_admin_becas(user, programa=None):
    """¿El usuario administra el programa Becas (capacidad ``becas.programa.administrar``)?"""
    programa = programa or programa_becas()
    return rbac.puede(user, CAP_ADMINISTRAR, programa=programa)


def es_coordinador_becas(user, programa=None):
    """¿El usuario puede gestionar/revisar Becas sin ser admin del programa?"""
    programa = programa or programa_becas()
    if es_admin_becas(user, programa=programa):
        return False
    return rbac.puede_alguna(user, CAPS_GESTION, programa=programa)


def es_referente_becas(user, programa=None):
    programa = programa or programa_becas()
    return not es_admin_becas(user, programa=programa) and rbac.puede(user, CAP_REFERENTE, programa=programa)


def es_coordinador_regional_becas(user, programa=None):
    """¿El usuario opera acotado a los subsegmentos que tiene a cargo?

    A diferencia del Coordinador (que gestiona segmentos enteros), el alcance
    del Coordinador Regional es el subsegmento: ve el segmento que lo contiene
    solo como contexto y no puede configurarlo.
    """
    programa = programa or programa_becas()
    return not es_admin_becas(user, programa=programa) and rbac.puede(user, CAP_COORD_REGIONAL, programa=programa)


def subsegmentos_a_cargo(user):
    """Subsegmentos donde ``user`` es el referente asignado."""
    from programas.models import Subsegmento

    if user is None or not getattr(user, "is_authenticated", False):
        return Subsegmento.objects.none()
    return Subsegmento.objects.filter(referente=user)


def _segmentos_coordinador_regional(user):
    """Segmentos que contienen algún subsegmento a cargo de ``user``."""
    from programas.models import Segmento

    return Segmento.objects.filter(subsegmentos__referente=user).distinct()


def _segmentos_referente(user):
    from programas.models import Segmento

    try:
        asignacion = user.asignacion_referente
    except ObjectDoesNotExist:
        return Segmento.objects.none()
    return get_segmentos_coordinador(asignacion.coordinador)


def puede_gestionar_segmento(user, segmento, programa=None):
    """¿``user`` puede gestionar/revisar el ``segmento``?

    Admin del programa → siempre. Coordinador → solo si tiene asignación activa
    sobre ese segmento. Resto → no.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    programa = programa or programa_becas()
    if es_admin_becas(user, programa=programa):
        return True
    if es_referente_becas(user, programa=programa):
        return _segmentos_referente(user).filter(pk=segmento.pk).exists()
    # Antes de la rama de Coordinador: el Regional no tiene AsignacionCoordinador,
    # su alcance sale del subsegmento. Acá "gestionar" es el permiso de entrada al
    # segmento; lo que puede hacer adentro lo acotan sus capacidades y los
    # querysets de subsegmentos/convocatorias.
    if es_coordinador_regional_becas(user, programa=programa):
        return _segmentos_coordinador_regional(user).filter(pk=segmento.pk).exists()
    if rbac.puede_alguna(user, CAPS_GESTION, programa=programa):
        return coordinador_gestiona_segmento(user, segmento)
    return False


def puede_operar_subsegmento(user, subsegmento, programa=None):
    """¿``user`` puede operar **este** subsegmento?

    Para casi todos los roles alcanza con poder gestionar el segmento padre.
    El Coordinador Regional es la excepción: su alcance es el subsegmento, así
    que sin este chequeo podría abrir el de un par del mismo segmento.
    """
    programa = programa or programa_becas()
    if not puede_gestionar_segmento(user, subsegmento.segmento, programa=programa):
        return False
    if es_coordinador_regional_becas(user, programa=programa):
        return subsegmento.referente_id == getattr(user, "pk", None)
    return True


def segmentos_visibles(user, programa=None):
    """Queryset de ``Segmento`` que el usuario puede gestionar/revisar.

    Admin → todos; Coordinador → solo asignados; resto → ninguno. Pensado para
    aplicar el scoping **en la query** de las vistas (no en el template).
    """
    from programas.models import Segmento

    if user is None or not getattr(user, "is_authenticated", False):
        return Segmento.objects.none()
    programa = programa or programa_becas()
    if es_admin_becas(user, programa=programa):
        return Segmento.objects.all()
    if es_referente_becas(user, programa=programa):
        return _segmentos_referente(user)
    if es_coordinador_regional_becas(user, programa=programa):
        return _segmentos_coordinador_regional(user)
    if rbac.puede_alguna(user, CAPS_GESTION, programa=programa):
        return get_segmentos_coordinador(user)
    return Segmento.objects.none()


def subsegmentos_visibles(user, programa=None):
    """Queryset de ``Subsegmento`` cuyo segmento el usuario puede gestionar/revisar.

    El Coordinador Regional es la excepción: ve el segmento como contexto pero
    solo sus subsegmentos, así que si un segmento tiene tres a cargo de tres
    personas distintas, cada una ve únicamente el suyo.
    """
    from programas.models import Subsegmento

    if es_coordinador_regional_becas(user, programa=programa):
        return subsegmentos_a_cargo(user)
    return Subsegmento.objects.filter(segmento__in=segmentos_visibles(user, programa=programa))


def convocatorias_visibles(user, programa=None):
    from programas.models import Convocatoria

    if es_coordinador_regional_becas(user, programa=programa):
        # Solo las de sus subsegmentos: una convocatoria a nivel segmento
        # (``subsegmento`` nulo) queda fuera de su alcance.
        return Convocatoria.objects.filter(subsegmento__in=subsegmentos_a_cargo(user))
    return Convocatoria.objects.filter(segmento__in=segmentos_visibles(user, programa=programa))


def segmentos_para_gestion_territoriales(user):
    if es_referente_becas(user):
        return _segmentos_referente(user)
    if es_coordinador_regional_becas(user):
        return _segmentos_coordinador_regional(user)
    return get_segmentos_coordinador(user)


def requisitos_visibles(user, programa=None):
    """Queryset de ``RequisitoNativo`` cuyo segmento el usuario puede gestionar/revisar.

    ``RequisitoNativo.segmento`` nunca es nulo (incluso para requisitos de
    subsegmento), así que un solo filtro por segmento alcanza.
    """
    from programas.models import RequisitoNativo

    return RequisitoNativo.objects.filter(segmento__in=segmentos_visibles(user, programa=programa))


def _usuarios_con_capacidad_en_programa(codigos, programa=None):
    """Usuarios activos con alguna de ``codigos`` vía un rol activo del Programa Becas.

    Por capacidad RBAC (rol activo con ``RolMeta.programa`` = Becas y algún
    permiso de ``codigos``), no por nombre de grupo — así cualquier rol que
    otorgue esas capacidades habilita al usuario, no solo el grupo sembrado
    puntual ("Becas — Coordinador", "Becas — Territorial"). Mismo patrón que
    ``core.rbac.usuarios_que_administran_programa``.
    """
    from django.contrib.auth import get_user_model

    programa = programa or programa_becas()
    programa_pk = getattr(programa, "pk", programa)
    codenames = [rbac.codename_de(c) for c in codigos]
    User = get_user_model()
    return (
        User.objects.filter(is_active=True)
        .filter(
            groups__meta__activo=True,
            groups__meta__programa=programa_pk,
            groups__permissions__codename__in=codenames,
        )
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


def usuarios_coordinadores_becas(programa=None):
    """Usuarios activos con capacidad de gestión de Becas (``CAPS_GESTION``),
    candidatos a ser asignados como coordinador de un segmento.
    """
    return (
        _usuarios_con_capacidad_en_programa(CAPS_GESTION, programa=programa)
        .exclude(
            groups__permissions__codename__in=[
                rbac.codename_de(CAP_ADMINISTRAR),
                rbac.codename_de(CAP_REFERENTE),
                rbac.codename_de(CAP_COORD_REGIONAL),
            ]
        )
        .distinct()
    )


def usuarios_coordinadores_regionales_becas(programa=None):
    """Usuarios activos con ``becas.coordinador_regional``, candidatos a ser
    referentes de un subsegmento.
    """
    return _usuarios_con_capacidad_en_programa([CAP_COORD_REGIONAL], programa=programa).exclude(
        groups__permissions__codename=rbac.codename_de(CAP_ADMINISTRAR)
    )


def usuarios_territoriales_becas(programa=None, segmento=None):
    """Usuarios activos con capacidad de campo (``CAP_CAMPO``), candidatos a
    ser asignados como territorial de un relevamiento.

    Con ``segmento`` se acota a los territoriales asignados a ese segmento
    (``AsignacionTerritorial``: un territorial → un segmento).
    """
    qs = _usuarios_con_capacidad_en_programa([CAP_CAMPO], programa=programa)
    if segmento is not None:
        qs = qs.filter(asignacion_territorial__segmento=segmento)
    return qs


def grupos_territoriales_becas(programa=None):
    """Roles (grupos) activos del Programa Becas que otorgan ``becas.campo``.

    Los usa el ABM de Usuarios para exigir el segmento asignado cuando se
    tilda un rol territorial (por capacidad, no por nombre del grupo).
    """
    from django.contrib.auth.models import Group

    programa = programa or programa_becas()
    programa_pk = getattr(programa, "pk", programa)
    return Group.objects.filter(
        meta__activo=True,
        meta__programa=programa_pk,
        permissions__codename=rbac.codename_de(CAP_CAMPO),
    ).distinct()


def _grupos_con_capacidad(codigo, programa=None):
    from django.contrib.auth.models import Group

    programa = programa or programa_becas()
    return (
        Group.objects.filter(
            meta__activo=True,
            meta__programa=getattr(programa, "pk", programa),
            permissions__codename=rbac.codename_de(codigo),
        )
        .exclude(permissions__codename=rbac.codename_de(CAP_ADMINISTRAR))
        .distinct()
    )


def grupos_referentes_becas(programa=None):
    return _grupos_con_capacidad(CAP_REFERENTE, programa=programa)


class SegmentoScopedMixin:
    """Mixin para CBV de Becas: scoping por segmento.

    Expone :meth:`segmentos_visibles` (para filtrar querysets) y
    :meth:`assert_puede_gestionar_segmento` (para validar el acceso a un objeto
    concreto, levantando ``PermissionDenied`` → 403).
    """

    def segmentos_visibles(self):
        return segmentos_visibles(self.request.user)

    def assert_puede_gestionar_segmento(self, segmento):
        if not puede_gestionar_segmento(self.request.user, segmento):
            raise PermissionDenied("No tiene acceso a este segmento.")

    def assert_puede_operar_subsegmento(self, subsegmento):
        if not puede_operar_subsegmento(self.request.user, subsegmento):
            raise PermissionDenied("No tiene acceso a este subsegmento.")
