from django.db.models import Q

from core.rbac import puede

from ..models import AlertaCiudadano, LegajoAtencion
from .linking import get_legajo_ids_for_programas, get_programa_ids_for_legajo_ids


class FiltrosUsuarioService:
    """Servicio para filtrar alertas según el usuario y sus permisos."""

    @staticmethod
    def obtener_alertas_usuario(usuario):
        if not usuario or not usuario.is_authenticated:
            return AlertaCiudadano.objects.none()

        if usuario.is_superuser:
            return AlertaCiudadano.objects.filter(activa=True)

        if puede(usuario, "config.administrar"):
            return AlertaCiudadano.objects.filter(activa=True)

        # Subqueries lazy (un solo SQL al evaluar), en vez de materializar
        # listas de IDs para cláusulas IN gigantes en cada poll del navbar.
        filtros = Q()
        legajos_propios = LegajoAtencion.objects.filter(responsable=usuario).values_list("id", flat=True)
        if legajos_propios.exists():
            filtros |= Q(legajo__responsable=usuario)
            programas_usuario = FiltrosUsuarioService._obtener_programas_usuario(usuario)
            filtros |= Q(legajo_id__in=get_legajo_ids_for_programas(programas_usuario))

        if not filtros:
            filtros = Q(prioridad="CRITICA")

        return AlertaCiudadano.objects.filter(filtros, activa=True)

    @staticmethod
    def _obtener_programas_usuario(usuario):
        legajo_ids = LegajoAtencion.objects.filter(responsable=usuario).values_list("id", flat=True)
        return get_programa_ids_for_legajo_ids(legajo_ids)

    @staticmethod
    def puede_ver_alerta(usuario, alerta):
        if not usuario or not usuario.is_authenticated:
            return False

        if usuario.is_superuser:
            return True

        alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(usuario)
        return alertas_usuario.filter(id=alerta.id).exists()

    @staticmethod
    def obtener_estadisticas_usuario(usuario):
        alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(usuario)

        return {
            "total": alertas_usuario.count(),
            "criticas": alertas_usuario.filter(prioridad="CRITICA").count(),
            "altas": alertas_usuario.filter(prioridad="ALTA").count(),
            "medias": alertas_usuario.filter(prioridad="MEDIA").count(),
            "bajas": alertas_usuario.filter(prioridad="BAJA").count(),
        }
