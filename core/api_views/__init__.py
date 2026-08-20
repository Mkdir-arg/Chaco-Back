from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Dia, Localidad, Mes, Municipio, Provincia, Sexo
from ..serializers import (
    DiaSerializer,
    LocalidadSerializer,
    MesSerializer,
    MunicipioSerializer,
    ProvinciaSerializer,
    SexoSerializer,
)


@extend_schema_view(
    list=extend_schema(description="Lista todas las provincias"),
    create=extend_schema(description="Crea una nueva provincia"),
    retrieve=extend_schema(description="Obtiene una provincia específica"),
    update=extend_schema(description="Actualiza una provincia"),
    partial_update=extend_schema(description="Actualiza parcialmente una provincia"),
    destroy=extend_schema(description="Elimina una provincia"),
)
class ProvinciaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar provincias.

    Permite realizar operaciones CRUD sobre las provincias del sistema.
    """

    queryset = Provincia.objects.all()
    serializer_class = ProvinciaSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["nombre"]
    ordering = ["nombre"]

    @extend_schema(description="Obtiene los municipios de una provincia")
    @action(detail=True, methods=["get"])
    def municipios(self, request, pk=None):
        """Obtiene los municipios de una provincia específica"""
        provincia = self.get_object()
        municipios = provincia.municipio_set.select_related("provincia")
        serializer = MunicipioSerializer(municipios, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(description="Lista todos los municipios"),
    create=extend_schema(description="Crea un nuevo municipio"),
    retrieve=extend_schema(description="Obtiene un municipio específico"),
    update=extend_schema(description="Actualiza un municipio"),
    partial_update=extend_schema(description="Actualiza parcialmente un municipio"),
    destroy=extend_schema(description="Elimina un municipio"),
)
class MunicipioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar municipios.
    """

    queryset = Municipio.objects.select_related("provincia")
    serializer_class = MunicipioSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["provincia"]
    search_fields = ["nombre"]
    ordering = ["nombre"]

    @extend_schema(description="Obtiene las localidades de un municipio")
    @action(detail=True, methods=["get"])
    def localidades(self, request, pk=None):
        """Obtiene las localidades de un municipio específico"""
        municipio = self.get_object()
        localidades = municipio.localidad_set.select_related("municipio__provincia")
        serializer = LocalidadSerializer(localidades, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(description="Lista todas las localidades"),
    create=extend_schema(description="Crea una nueva localidad"),
    retrieve=extend_schema(description="Obtiene una localidad específica"),
    update=extend_schema(description="Actualiza una localidad"),
    partial_update=extend_schema(description="Actualiza parcialmente una localidad"),
    destroy=extend_schema(description="Elimina una localidad"),
)
class LocalidadViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar localidades.
    """

    queryset = Localidad.objects.select_related("municipio__provincia")
    serializer_class = LocalidadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["municipio"]
    search_fields = ["nombre"]
    ordering = ["nombre"]


@extend_schema_view(
    list=extend_schema(description="Lista todos los sexos"),
    retrieve=extend_schema(description="Obtiene un sexo específico"),
)
class SexoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para sexos.
    """

    queryset = Sexo.objects.all()
    serializer_class = SexoSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(description="Lista todos los meses"),
    retrieve=extend_schema(description="Obtiene un mes específico"),
)
class MesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para meses.
    """

    queryset = Mes.objects.all()
    serializer_class = MesSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(description="Lista todos los días"),
    retrieve=extend_schema(description="Obtiene un día específico"),
)
class DiaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para días.
    """

    queryset = Dia.objects.all()
    serializer_class = DiaSerializer
    permission_classes = [IsAuthenticated]
