"""API REST de la app de campo de Becas (#82).

Auth por token (DRF authtoken). El territorial solo ve/gestiona SUS relevamientos
y formularios. Capacidad requerida: ``becas.campo``.
"""

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from core.rbac import puede
from legajos.services.consulta_renaper import consultar_datos_renaper
from programas.api.serializers import (
    AdjuntoFormularioSerializer,
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


def _normalizar_datos_renaper(resultado, dni, sexo):
    datos = resultado.get("data") or {}
    return {
        "dni": datos.get("dni") or dni,
        "apellido": datos.get("apellido") or "",
        "nombre": datos.get("nombre") or "",
        "fecha_nacimiento": datos.get("fecha_nacimiento") or "",
        "sexo": datos.get("sexo") or datos.get("genero") or sexo,
    }


def _actualizar_validacion_identidad(formulario, datos_identificacion=None):
    datos = datos_identificacion if isinstance(datos_identificacion, dict) else formulario.datos_identificacion
    datos = datos if isinstance(datos, dict) else {}
    origen = str(datos.get("origen") or "").strip().lower()

    if origen in ("scan", "escaneo", "dni_scan", "renaper"):
        validado = True
    elif origen == "manual":
        validado = False
    else:
        validado = bool(formulario.validado_renaper)

    if formulario.validado_renaper != validado:
        formulario.validado_renaper = validado
        formulario.save(update_fields=["validado_renaper", "modificado"])


@api_view(["POST"])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, CampoBecasPermission])
def consultar_renaper_becas(request):
    dni = str(request.data.get("dni") or "").strip()
    sexo = str(request.data.get("sexo") or "").strip().upper()

    if not dni or not sexo:
        return Response(
            {"success": False, "error": "DNI y sexo son requeridos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resultado = consultar_datos_renaper(dni, sexo)
    if not resultado.get("success"):
        return Response(
            {
                "success": False,
                "error": resultado.get("error") or "No se pudo validar con RENAPER.",
                "fallecido": bool(resultado.get("fallecido")),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
            "success": True,
            "data": _normalizar_datos_renaper(resultado, dni, sexo),
            "datos_api": resultado.get("datos_api") or {},
        }
    )


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
        _actualizar_validacion_identidad(
            formulario,
            serializer.validated_data.get("datos_identificacion"),
        )
        resolver_ciudadano_offline(formulario)
        formulario.refresh_from_db()
        return Response(FormularioSerializer(formulario).data, status=status.HTTP_201_CREATED)


class FormularioViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = FormularioSerializer

    def get_queryset(self):
        return Formulario.objects.filter(relevamiento__territorial=self.request.user).select_related(
            "relevamiento", "ciudadano"
        )

    def perform_update(self, serializer):
        formulario = serializer.save()
        _actualizar_validacion_identidad(
            formulario,
            serializer.validated_data.get("datos_identificacion"),
        )
        resolver_ciudadano_offline(formulario)

    @action(detail=True, methods=["get", "post"])
    def adjuntos(self, request, pk=None):
        """Sube (multipart) o lista los archivos de los campos tipo ARCHIVO del
        formulario (fotos DNI, certificado de domicilio, etc. — #82).

        Reemplaza el placeholder ``{"pendiente_upload": true}`` que la app de
        campo guardaba en ``data`` sin subir nunca el archivo real.
        """
        formulario = self.get_object()
        if request.method == "GET":
            return Response(AdjuntoFormularioSerializer(formulario.adjuntos.all(), many=True).data)

        serializer = AdjuntoFormularioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjunto = serializer.save(formulario=formulario)
        return Response(AdjuntoFormularioSerializer(adjunto).data, status=status.HTTP_201_CREATED)
