"""API REST de la app de campo de Becas (#82).

Auth por token (DRF authtoken). El territorial solo ve/gestiona SUS relevamientos
y formularios. Capacidad requerida: ``becas.campo``.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from core.rbac import puede
from programas.api.serializers import (
    AdjuntoFormularioSerializer,
    FormularioSerializer,
    RelevamientoDetailSerializer,
    RelevamientoListSerializer,
)
from programas.models import Formulario, Relevamiento
from programas.services.becas import resolver_ciudadano_offline
from programas.services.personas import consultar_persona

CAP = "becas.campo"
DNI_DUPLICADO_MENSAJE = "Este DNI ya fue relevado en este relevamiento."


def _normalizar_dni(value):
    return "".join(character for character in str(value or "") if character.isdigit())


def _formulario_por_dni(relevamiento, dni):
    dni = _normalizar_dni(dni)
    if not dni:
        return None
    return (
        relevamiento.formularios.filter(Q(ciudadano__dni=dni) | Q(datos_identificacion__dni=dni))
        .order_by("creado", "pk")
        .first()
    )


def _formulario_dni_existe(relevamiento, dni):
    return _formulario_por_dni(relevamiento, dni) is not None


def _captura_habilitada(relevamiento, capturado_en=None):
    """Permite operar hoy o sincronizar después una captura hecha en fecha."""
    if capturado_en is None:
        return relevamiento.habilitado_en(timezone.localdate())
    if capturado_en > timezone.now() + timedelta(minutes=5):
        return False
    return relevamiento.habilitado_en(timezone.localdate(capturado_en))


def _mensaje_pausa(relevamiento):
    pausa = relevamiento.pausa_efectiva
    if not pausa:
        return None
    return f"El relevamiento está pausado: {pausa.pausa_motivo}"


def _respuesta_pausa(relevamiento):
    mensaje = _mensaje_pausa(relevamiento)
    if mensaje:
        return Response({"detail": mensaje, "pausado": True}, status=status.HTTP_409_CONFLICT)
    return None


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


def _actualizar_validacion_identidad(formulario, datos_identificacion=None):
    datos = datos_identificacion if isinstance(datos_identificacion, dict) else formulario.datos_identificacion
    datos = datos if isinstance(datos, dict) else {}
    origen = str(datos.get("origen") or "").strip().lower()

    if origen in ("scan", "escaneo", "dni_scan"):
        validado = True
    elif origen in ("personas", "gran_base"):
        # Gran Base solo acredita identidad cuando devuelve ambos componentes.
        # Una correccion manual posterior no debe transformar una respuesta
        # incompleta en una validacion externa.
        validado = bool(str(datos.get("nombre") or "").strip() and str(datos.get("apellido") or "").strip())
    elif origen == "manual":
        validado = False
    else:
        # El cliente nunca puede autovalidarse sin un origen de confianza.
        validado = False

    if formulario.validado_renaper != validado:
        formulario.validado_renaper = validado
        formulario.save(update_fields=["validado_renaper", "modificado"])


@api_view(["POST"])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, CampoBecasPermission])
def consultar_persona_becas(request):
    dni = _normalizar_dni(request.data.get("dni"))
    sexo = str(request.data.get("sexo") or "").strip().upper()

    if not dni or sexo not in ("F", "M"):
        return Response(
            {"success": False, "error": "DNI y sexo (F o M) son requeridos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resultado = consultar_persona(dni, sexo)
    if not resultado.get("success"):
        return Response(
            {
                "success": False,
                "error": resultado.get("error") or "No se pudo validar con Base de Personas.",
            },
            status=(status.HTTP_404_NOT_FOUND if resultado.get("not_found") else status.HTTP_502_BAD_GATEWAY),
        )

    return Response(
        {
            "success": True,
            "data": resultado.get("data") or {},
            "datos_api": resultado.get("datos_api") or {},
        }
    )


class RelevamientoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]

    def get_queryset(self):
        queryset = (
            Relevamiento.objects.filter(territorial=self.request.user)
            .select_related("convocatoria__segmento", "convocatoria__subsegmento")
            .annotate(formularios_count=Count("formularios"))
            .order_by("-fecha_asignada")
        )
        if self.action == "list":
            queryset = queryset.filter(
                fecha_hasta__gte=timezone.localdate(),
            ).order_by("fecha_asignada", "nombre")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RelevamientoDetailSerializer
        return RelevamientoListSerializer

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        capturado_en = request.data.get("capturado_en")
        if capturado_en:
            try:
                capturado_en = serializers.DateTimeField().to_internal_value(capturado_en)
            except serializers.ValidationError:
                return Response(
                    {"capturado_en": "La fecha de captura no es válida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not _captura_habilitada(rel, capturado_en):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rel.estado == Relevamiento.Estado.EN_CURSO:
            return Response(RelevamientoListSerializer(rel).data)
        if rel.estado != Relevamiento.Estado.ASIGNADO:
            return Response({"detail": "Solo se puede iniciar un relevamiento asignado."}, status=400)
        rel.estado = Relevamiento.Estado.EN_CURSO
        rel.save(update_fields=["estado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        capturado_en = request.data.get("capturado_en")
        if capturado_en:
            try:
                capturado_en = serializers.DateTimeField().to_internal_value(capturado_en)
            except serializers.ValidationError:
                return Response(
                    {"capturado_en": "La fecha de captura no es válida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not _captura_habilitada(rel, capturado_en):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rel.estado not in (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO):
            return Response({"detail": "El relevamiento no está en curso."}, status=400)
        rel.estado = Relevamiento.Estado.FINALIZADO
        rel.fecha_finalizado = timezone.now()
        rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        if not rel.habilitado_en(timezone.localdate()):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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

        if respuesta := _respuesta_pausa(rel):
            return respuesta

        serializer = FormularioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            # Evita que dos dispositivos inserten simultáneamente el mismo DNI.
            rel = Relevamiento.objects.select_for_update().get(pk=rel.pk)
            if rel.estado != Relevamiento.Estado.EN_CURSO:
                return Response(
                    {"detail": "Solo se pueden cargar personas en un relevamiento en curso."},
                    status=status.HTTP_409_CONFLICT,
                )
            capturado_en = serializer.validated_data.get("capturado_en")
            if not _captura_habilitada(rel, capturado_en):
                return Response(
                    {"detail": "La captura se realizó fuera del período asignado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            client_uuid = serializer.validated_data.get("client_uuid")
            if client_uuid:
                existente = rel.formularios.filter(client_uuid=client_uuid).first()
                if existente:
                    return Response(FormularioSerializer(existente).data, status=status.HTTP_200_OK)
            if rel.formularios.count() >= rel.cupo_maximo:
                return Response(
                    {
                        "detail": "Se alcanzó el cupo del relevamiento. No se pueden cargar nuevas personas.",
                        "code": "CUPO_RELEVAMIENTO_COMPLETO",
                        "cupo_maximo": rel.cupo_maximo,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            datos_identificacion = serializer.validated_data.get("datos_identificacion") or {}
            dni = _normalizar_dni(datos_identificacion.get("dni"))
            datos_identificacion["dni"] = dni
            formulario_existente = _formulario_por_dni(rel, dni)
            formulario = serializer.save(
                relevamiento=rel,
                created_by=request.user,
                conflicto_duplicado=formulario_existente is not None,
                duplicado_de=formulario_existente,
            )
            _actualizar_validacion_identidad(formulario, datos_identificacion)
            resolver_ciudadano_offline(formulario)
            formulario.refresh_from_db()
        return Response(FormularioSerializer(formulario).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="dni-existe")
    def dni_existe(self, request, pk=None):
        rel = self.get_object()
        dni = _normalizar_dni(request.query_params.get("dni"))
        if not dni:
            return Response({"dni": "El DNI es requerido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"existe": _formulario_dni_existe(rel, dni)})


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
        formulario = serializer.instance
        if mensaje := _mensaje_pausa(formulario.relevamiento):
            raise ValidationError({"detail": mensaje})
        capturado_en = formulario.capturado_en or serializer.validated_data.get("capturado_en")
        if not _captura_habilitada(formulario.relevamiento, capturado_en):
            raise ValidationError({"detail": "El relevamiento está fuera de su período asignado."})
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

        if respuesta := _respuesta_pausa(formulario.relevamiento):
            return respuesta

        if not _captura_habilitada(formulario.relevamiento, formulario.capturado_en):
            return Response(
                {"detail": "El relevamiento está fuera de su período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdjuntoFormularioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjunto = serializer.save(formulario=formulario)
        return Response(AdjuntoFormularioSerializer(adjunto).data, status=status.HTTP_201_CREATED)
