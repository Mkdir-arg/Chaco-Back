"""API REST de la app de campo de Becas (#82).

Auth por token (DRF authtoken). El territorial solo ve/gestiona SUS relevamientos
y formularios. Capacidad requerida: ``becas.campo``.
"""
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from core.rbac import puede
from programas.api.serializers import (
    FormularioSerializer,
    RelevamientoDetailSerializer,
    RelevamientoListSerializer,
)
from programas.models import Formulario, Relevamiento
from programas.services.becas import resolver_ciudadano_offline

CAP = "becas.campo"


class CampoBecasPermission(BasePermission):
    """Exige la capacidad ``becas.campo`` (territorial / app de campo)."""

    message = "El usuario no tiene acceso a la app de campo de Becas."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and puede(user, CAP))


class ObtainCampoToken(ObtainAuthToken):
    """Login de la app de campo: valida credenciales y exige ``becas.campo``."""

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not puede(user, CAP):
            return Response(
                {"detail": "El usuario no tiene acceso a la app de campo de Becas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user_id": user.pk, "username": user.username})


class RelevamientoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]

    def get_queryset(self):
        return (
            Relevamiento.objects.filter(territorial=self.request.user)
            .select_related("convocatoria__segmento", "convocatoria__subsegmento")
            .order_by("-fecha_asignada")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RelevamientoDetailSerializer
        return RelevamientoListSerializer

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        rel = self.get_object()
        if rel.estado != Relevamiento.Estado.ASIGNADO:
            return Response({"detail": "Solo se puede iniciar un relevamiento asignado."}, status=400)
        rel.estado = Relevamiento.Estado.EN_CURSO
        rel.save(update_fields=["estado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        rel = self.get_object()
        if rel.estado not in (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO):
            return Response({"detail": "El relevamiento no está en curso."}, status=400)
        rel.estado = Relevamiento.Estado.FINALIZADO
        rel.fecha_finalizado = timezone.now()
        rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        rel = self.get_object()
        if rel.estado != Relevamiento.Estado.FINALIZADO:
            return Response({"detail": "Solo se puede reabrir un relevamiento finalizado."}, status=400)
        rel.estado = Relevamiento.Estado.EN_CURSO
        rel.fecha_finalizado = None
        rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["get", "post"])
    def formularios(self, request, pk=None):
        rel = self.get_object()
        if request.method == "GET":
            qs = rel.formularios.select_related("ciudadano").order_by("-creado")
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(FormularioSerializer(page, many=True).data)
            return Response(FormularioSerializer(qs, many=True).data)

        serializer = FormularioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        formulario = serializer.save(relevamiento=rel, created_by=request.user)
        resolver_ciudadano_offline(formulario)
        formulario.refresh_from_db()
        return Response(FormularioSerializer(formulario).data, status=status.HTTP_201_CREATED)


class FormularioViewSet(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]
    serializer_class = FormularioSerializer

    def get_queryset(self):
        return Formulario.objects.filter(
            relevamiento__territorial=self.request.user
        ).select_related("relevamiento", "ciudadano")

    def perform_update(self, serializer):
        formulario = serializer.save()
        resolver_ciudadano_offline(formulario)
