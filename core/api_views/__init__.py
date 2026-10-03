"""API de catálogos de `core`: **solo lectura**.

El ABM de la geografía es web (`configuracion/views/geografia.py`, con
`config.administrar`): nadie escribe por acá. Como `ModelViewSet`, en cambio, un
`DELETE /api/core/provincias/<id>/` con la sesión de cualquier usuario del
backoffice borraba la provincia y, en cascada, sus municipios y localidades
(SEC-13, auditoría oct-2026).
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api_permissions import BackofficeAutenticado

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
    retrieve=extend_schema(description="Obtiene una provincia específica"),
)
class ProvinciaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para provincias.

    El alta, la edición y la baja se hacen desde Configuración → Geografía.
    """

    queryset = Provincia.objects.all()
    serializer_class = ProvinciaSerializer
    permission_classes = [BackofficeAutenticado]
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
    retrieve=extend_schema(description="Obtiene un municipio específico"),
)
class MunicipioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para municipios.
    """

    queryset = Municipio.objects.select_related("provincia")
    serializer_class = MunicipioSerializer
    permission_classes = [BackofficeAutenticado]
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
    retrieve=extend_schema(description="Obtiene una localidad específica"),
)
class LocalidadViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para localidades.
    """

    queryset = Localidad.objects.select_related("municipio__provincia")
    serializer_class = LocalidadSerializer
    permission_classes = [BackofficeAutenticado]
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
    permission_classes = [BackofficeAutenticado]


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
    permission_classes = [BackofficeAutenticado]


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
    permission_classes = [BackofficeAutenticado]
