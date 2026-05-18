from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models import Count
from ..models import (
    Ciudadano,
    Derivacion,
    AlertaCiudadano,
)
from ..serializers import (
    CiudadanoSerializer,
    DerivacionSerializer,
    AlertaCiudadanoSerializer,
)
from ..services import AlertasService, FiltrosUsuarioService


@extend_schema_view(
    list=extend_schema(description="Lista todos los ciudadanos"),
    create=extend_schema(description="Crea un nuevo ciudadano"),
    retrieve=extend_schema(description="Obtiene un ciudadano específico"),
    update=extend_schema(description="Actualiza un ciudadano"),
    partial_update=extend_schema(description="Actualiza parcialmente un ciudadano"),
    destroy=extend_schema(description="Elimina un ciudadano")
)
class CiudadanoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar ciudadanos.
    
    Permite realizar operaciones CRUD sobre los ciudadanos del sistema.
    """
    queryset = Ciudadano.objects.annotate(legajos_count=Count('inscripciones_programas'))
    serializer_class = CiudadanoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['dni', 'genero', 'activo']
    search_fields = ['nombre', 'apellido', 'dni']
    ordering_fields = ['apellido', 'nombre', 'creado']
    ordering = ['apellido', 'nombre']


@extend_schema_view(
    list=extend_schema(description="Lista todas las derivaciones"),
    create=extend_schema(description="Crea una nueva derivación"),
    retrieve=extend_schema(description="Obtiene una derivación específica"),
    update=extend_schema(description="Actualiza una derivación"),
    partial_update=extend_schema(description="Actualiza parcialmente una derivación"),
    destroy=extend_schema(description="Elimina una derivación")
)
class DerivacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar derivaciones entre dispositivos.
    """
    queryset = Derivacion.objects.select_related('legajo', 'actividad_destino')
    serializer_class = DerivacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estado', 'urgencia', 'actividad_destino']
    ordering = ['-creado']


@extend_schema_view(
    list=extend_schema(description="Lista todas las alertas del sistema"),
)
class AlertasViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar alertas del sistema.
    """
    queryset = AlertaCiudadano.objects.select_related('ciudadano', 'legajo', 'cerrada_por')
    serializer_class = AlertaCiudadanoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['prioridad', 'tipo', 'ciudadano']
    ordering = ['-creado']  # Ordenar por fecha de creación descendente
    
    def get_queryset(self):
        """Filtrar alertas según el usuario autenticado"""
        return FiltrosUsuarioService.obtener_alertas_usuario(self.request.user).select_related('ciudadano', 'legajo', 'cerrada_por')
    
    @extend_schema(description="Obtiene contador de alertas activas")
    @action(detail=False, methods=['get'])
    def count(self, request):
        """Obtiene el contador de alertas activas"""
        alertas_usuario = self.get_queryset()
        count = alertas_usuario.count()
        count_criticas = alertas_usuario.filter(prioridad='CRITICA').count()
        
        return Response({
            'count': count,
            'criticas': count_criticas
        })
    
    @extend_schema(description="Cierra una alerta específica")
    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        """Cierra una alerta específica"""
        success = AlertasService.cerrar_alerta(pk, request.user)
        
        if success:
            return Response({'message': 'Alerta cerrada correctamente'})
        else:
            return Response(
                {'error': 'Alerta no encontrada'}, 
                status=status.HTTP_404_NOT_FOUND
            )
