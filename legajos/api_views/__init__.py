from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api_permissions import BackofficeAutenticado, RequiereCapacidad

from ..models import (
    AlertaCiudadano,
    Ciudadano,
)
from ..serializers import (
    AlertaCiudadanoSerializer,
    CiudadanoSerializer,
)
from ..services import AlertasService, FiltrosUsuarioService

# Mínimo de caracteres del `?search=` para que la API conteste algo: menos que
# esto devuelve vacío en vez de volcar el padrón (SEC-02).
BUSQUEDA_MINIMA = 3


@extend_schema_view(
    list=extend_schema(description="Busca ciudadanos por nombre, apellido o DNI (mínimo 3 caracteres)"),
    retrieve=extend_schema(description="Obtiene un ciudadano específico"),
)
class CiudadanoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de consulta del padrón de ciudadanos.

    Es de **solo lectura** y exige la capacidad ``ciudadano.ver``: su único
    consumidor es el buscador de «Agregar familiar» del detalle de ciudadano
    (SEC-02, auditoría oct-2026). El alta y la edición van por el backoffice,
    que aplica sus propias reglas de negocio.
    """

    queryset = Ciudadano.objects.annotate(legajos_count=Count("inscripciones_programas"))
    serializer_class = CiudadanoSerializer
    permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["dni", "genero", "activo"]
    search_fields = ["nombre", "apellido", "dni"]
    ordering_fields = ["apellido", "nombre", "creado"]
    ordering = ["apellido", "nombre"]

    def get_queryset(self):
        """Sin una búsqueda de al menos 3 caracteres no se devuelve nada.

        La API contesta búsquedas, no listados: así una capacidad de lectura no
        alcanza para bajarse el padrón completo paginando.
        """
        queryset = super().get_queryset()
        busqueda = self.request.query_params.get("search", "").strip()
        if len(busqueda) < BUSQUEDA_MINIMA:
            return queryset.none()
        return queryset


@extend_schema_view(
    list=extend_schema(description="Lista todas las alertas del sistema"),
)
class AlertasViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar alertas del sistema.

    Exige ``ciudadano.ver``: con solo ``IsAuthenticated`` cualquier cuenta de
    backoffice listaba las alertas con el **nombre del ciudadano y el texto de
    la alerta**, y ``cerrar`` silenciaba cualquiera por id (SEC-18 y R0b-06,
    auditoría oct-2026). El contenido de la alerta es sensible: cuando se
    resuelva D-11, la Ola 2 sube esta capacidad a ``ciudadano.sensible``.
    """

    queryset = AlertaCiudadano.objects.select_related("ciudadano", "legajo", "cerrada_por")
    serializer_class = AlertaCiudadanoSerializer
    permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["prioridad", "tipo", "ciudadano"]
    ordering = ["-creado"]  # Ordenar por fecha de creación descendente

    def get_queryset(self):
        """Filtrar alertas según el usuario autenticado"""
        return FiltrosUsuarioService.obtener_alertas_usuario(self.request.user).select_related(
            "ciudadano", "legajo", "cerrada_por"
        )

    @extend_schema(description="Obtiene contador de alertas activas")
    @action(detail=False, methods=["get"])
    def count(self, request):
        """Obtiene el contador de alertas activas"""
        alertas_usuario = self.get_queryset()
        count = alertas_usuario.count()
        count_criticas = alertas_usuario.filter(prioridad="CRITICA").count()

        return Response({"count": count, "criticas": count_criticas})

    @extend_schema(description="Cierra una alerta específica")
    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        """Cierra una alerta del alcance del usuario.

        ``self.get_object()`` resuelve sobre ``get_queryset()``, que ya está
        acotado por ``FiltrosUsuarioService``: una alerta fuera del alcance es
        404, no un cierre silencioso. De paso mata el **500** que daba un `pk`
        no numérico, que antes llegaba crudo a ``cerrar_alerta`` (SEC-18).
        """
        alerta = self.get_object()
        AlertasService.cerrar_alerta(alerta.pk, request.user)
        return Response({"message": "Alerta cerrada correctamente"})
