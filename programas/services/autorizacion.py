"""Autorización del Programa Becas: integra el RBAC (alcance de programa) con el
alcance fino por segmento del Coordinador (``AsignacionCoordinador``).

Regla (#79):
- **Admin del programa** (capacidad ``becas.configurar``): acceso total → todos
  los segmentos.
- **Coordinador** (``becas.revisar`` / ``becas.relevamientos`` pero sin
  ``becas.configurar``): solo los segmentos donde tiene una asignación activa.
- **Territorial** (solo ``becas.campo``) y cualquier otro: sin acceso de gestión.

El RBAC tiene alcance de *programa*, no de *segmento*; el alcance por segmento lo
aporta este módulo combinando la capacidad con ``AsignacionCoordinador``.
"""
from django.core.exceptions import PermissionDenied

from core import rbac
from programas.services.becas import coordinador_gestiona_segmento, get_segmentos_coordinador

CAP_CONFIGURAR = "becas.configurar"
CAPS_GESTION = ["becas.revisar", "becas.relevamientos"]

# Programa genérico que ancla el alcance del RBAC de Becas (sembrado por seed_becas).
PROGRAMA_BECAS_CODIGO = "BECAS"


def programa_becas():
    """Instancia genérica del Programa Becas, o None si no está sembrada."""
    from programas.models import Programa

    return Programa.objects.filter(codigo=PROGRAMA_BECAS_CODIGO).first()


def es_admin_becas(user, programa=None):
    """¿El usuario administra el programa Becas (capacidad ``becas.configurar``)?"""
    programa = programa or programa_becas()
    return rbac.puede(user, CAP_CONFIGURAR, programa=programa)


def es_coordinador_becas(user, programa=None):
    """¿El usuario puede gestionar/revisar Becas sin ser admin del programa?"""
    programa = programa or programa_becas()
    if es_admin_becas(user, programa=programa):
        return False
    return rbac.puede_alguna(user, CAPS_GESTION, programa=programa)


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
    if rbac.puede_alguna(user, CAPS_GESTION, programa=programa):
        return coordinador_gestiona_segmento(user, segmento)
    return False


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
    if rbac.puede_alguna(user, CAPS_GESTION, programa=programa):
        return get_segmentos_coordinador(user)
    return Segmento.objects.none()


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
