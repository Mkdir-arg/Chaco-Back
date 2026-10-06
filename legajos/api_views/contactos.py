from datetime import datetime, timedelta

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api_permissions import BackofficeAutenticado
from core.utils_fechas import q_rango_local

from ..models.contactos import HistorialContacto
from ..serializers.contactos import (
    HistorialContactoListSerializer,
    HistorialContactoSerializer,
)


class HistorialContactoViewSet(viewsets.ModelViewSet):
    queryset = HistorialContacto.objects.select_related("legajo", "profesional").all()
    permission_classes = [BackofficeAutenticado, IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["tipo_contacto", "estado", "seguimiento_requerido", "profesional"]
    search_fields = ["motivo", "resumen", "legajo__codigo"]
    ordering_fields = ["fecha_contacto", "creado"]
    ordering = ["-fecha_contacto"]

    def get_serializer_class(self):
        if self.action == "list":
            return HistorialContactoListSerializer
        return HistorialContactoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        legajo_id = self.request.query_params.get("legajo", None)
        if legajo_id:
            queryset = queryset.filter(legajo_id=legajo_id)

        fecha_desde = self.request.query_params.get("fecha_desde", None)
        fecha_hasta = self.request.query_params.get("fecha_hasta", None)

        # Rango local: ``fecha_contacto__date`` se traduce a ``CONVERT_TZ``, que en
        # ECOM —MariaDB sin tablas de zona horaria— devuelve NULL (DIS-01).
        if fecha_desde:
            queryset = queryset.filter(q_rango_local("fecha_contacto", desde=fecha_desde))
        if fecha_hasta:
            queryset = queryset.filter(q_rango_local("fecha_contacto", hasta=fecha_hasta))

        return queryset

    @action(detail=False, methods=["get"])
    def estadisticas(self, request):
        """Estadísticas de contactos"""
        queryset = self.get_queryset()

        stats = {
            "total_contactos": queryset.count(),
            "por_tipo": dict(queryset.values_list("tipo_contacto").annotate(Count("id"))),
            "por_estado": dict(queryset.values_list("estado").annotate(Count("id"))),
            "pendientes_seguimiento": queryset.filter(seguimiento_requerido=True).count(),
            "ultimo_mes": queryset.filter(fecha_contacto__gte=datetime.now() - timedelta(days=30)).count(),
        }

        return Response(stats)


# `VinculoFamiliarViewSet` y su router (`legajos/urls/api_contactos.py`) se borraron con
# LEG-03: nunca estuvieron montados —el front recibía un 404 en cada carga del legajo— y
# montarlos tal cual listaba los vínculos de **todos** los ciudadanos, porque el filtro
# leía `?ciudadano=` y el JS mandaba `?ciudadano_principal=`, que no estaba en
# `filterset_fields`: la consulta volvía sin filtro. El default D-L03 es retirar la
# solapa; si alguna vez se repone, va con `RequiereCapacidad("ciudadano.ver")`, el filtro
# corregido y `SearchFilter` en el buscador (opción A de la ficha).
