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
    # `OrderingFilter` es el único backend que lee `ordering`/`ordering_fields`:
    # sin él la paginación salía en el orden que quisiera el motor y dos páginas
    # consecutivas podían repetir o saltear filas (R0b-05).
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["dni", "genero", "activo"]
    search_fields = ["nombre", "apellido", "dni"]
    ordering_fields = ["apellido", "nombre", "creado"]
    # `pk` desempata: dos homónimos no tienen orden propio y la página 2 se los
    # volvía a traer. Es una columna indexada, así que no agrega costo.
    ordering = ["apellido", "nombre", "pk"]

    def get_queryset(self):
        """Sin una búsqueda de al menos 3 caracteres el **listado** no devuelve nada.

        La API contesta búsquedas, no listados: así una capacidad de lectura no
        alcanza para bajarse el padrón completo paginando.

        El mínimo vale solo para ``list``, que es la acción que enumera. Aplicado
        también a ``retrieve``, ``GET /api/legajos/ciudadanos/<pk>/`` daba **404
        con un ciudadano que existe** (R0b-04): nadie lo consume hoy, pero un 404
        que miente es lo que rompe al próximo que lo use. El pk ya hay que
        conocerlo para pedirlo, así que no habilita ninguna enumeración.
        """
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
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

    Exige ``ciudadano.sensible``: con solo ``IsAuthenticated`` cualquier cuenta
    de backoffice listaba las alertas con el **nombre del ciudadano y el texto
    de la alerta**, y ``cerrar`` silenciaba cualquiera por id (SEC-18 y R0b-06,
    auditoría oct-2026). SEC-18 le puso ``ciudadano.ver`` y el Cambio 179 la
    subió a ``ciudadano.sensible`` con **D-11**: es el mismo texto que entregan
    el WebSocket y ``alertas_ciudadano_api``, y el dato sensible pide la misma
    capacidad por cualquier canal. Deja de valer la excepción que la Ola 2 le
    había reservado («es la campana del navbar»): la campana también subió.
    """

    queryset = AlertaCiudadano.objects.select_related("ciudadano", "legajo", "cerrada_por")
    serializer_class = AlertaCiudadanoSerializer
    permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.sensible")]
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
