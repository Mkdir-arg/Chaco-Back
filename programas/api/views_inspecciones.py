"""API de campo del relevamiento edilicio (MVP v2 de Dispositivos, tasks 38 y 39).

Lo que usa la app del agente territorial (`Chaco-mobile`) para traer sus tareas y mandar
el resultado y las fotos, también después de trabajar sin señal. Mismo molde que la API de
campo de Becas (`programas/api/views.py`): token de DRF —el mismo login,
``/api/becas/auth/token/``—, un permiso por recurso y la regla en el servicio.

* **Permiso propio**: `CampoInspeccionPermission` exige ``inspeccion.relevar`` con alcance
  al programa Dispositivos. ``becas.campo`` no abre esto, y ``inspeccion.relevar`` no abre
  los recursos de Becas.
* **Solo lo asignado**: el listado es `inspecciones_asignadas` (en curso) y el detalle
  `inspecciones_del_agente`. Lo ajeno contesta **404**, el mismo cuerpo que un id que no
  existe: no hay oráculo de existencia.
* **La vista no decide reglas**: `registrar_resultado` y `agregar_foto` validan estado,
  criticidad, tipo y tamaño de la foto, idempotencia y conflictos. Acá solo se traduce:
  `ValidationError` → 400, `InspeccionEnConflicto`/`InspeccionReasignada` → 409 con
  ``code``, cualquier otro `PermissionDenied` → 404.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import APIRootView

from programas.api.serializers_inspecciones import (
    FotoInspeccionCampoSerializer,
    FotoInspeccionEnvioSerializer,
    InspeccionCampoDetailSerializer,
    InspeccionCampoListSerializer,
    ResultadoInspeccionSerializer,
)
from programas.models import InspeccionEdificio
from programas.services.dispositivos import puede_en_programa_dispositivos
from programas.services.inspecciones import (
    CAP_RELEVAR,
    InspeccionEnConflicto,
    InspeccionReasignada,
    agregar_foto,
    inspecciones_asignadas,
    inspecciones_del_agente,
    inspecciones_para_envio,
    registrar_resultado,
)

MENSAJE_SIN_ACCESO = "El usuario no tiene acceso al relevamiento edilicio."

_RESPUESTAS_DE_ENVIO = {
    400: OpenApiResponse(
        description=(
            "El envío no es válido: falta `uuid_cliente`, criticidad fuera de la escala, foto que no es "
            "JPEG/PNG/WEBP de verdad —un HEIC/HEIF se rechaza acá: la app lo convierte— o que pasa de "
            "5 MB. Trae `detail` legible y el detalle por campo."
        )
    ),
    401: OpenApiResponse(description="Sin token o token inválido."),
    403: OpenApiResponse(description="El usuario no tiene la capacidad `inspeccion.relevar` en Dispositivos."),
    404: OpenApiResponse(description="No existe o no es del agente: mismo cuerpo en los dos casos."),
    409: OpenApiResponse(
        description=(
            "El servidor cambió mientras la app estaba sin conexión. `code`: `CANCELADA` (con el motivo en "
            "`detail`), `REASIGNADA`, `YA_REALIZADA` (otro resultado, con otro `uuid_cliente`), `UUID_EN_USO` "
            "(el identificador ya es de otra foto) o `ESTADO_NO_ADMITE` (el relevamiento quedó en un estado "
            "que no admite la operación; cuál es viene en `estado`). No se reintenta: se le muestra al agente."
        )
    ),
}


class CampoInspeccionPermission(BasePermission):
    """Exige ``inspeccion.relevar`` con alcance al programa Dispositivos (el agente)."""

    message = MENSAJE_SIN_ACCESO

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and puede_en_programa_dispositivos(user, CAP_RELEVAR))


class RaizApiInspecciones(APIRootView):
    """La raíz ``/api/dispositivos/``: autentica igual que el resto del namespace (R0-04)."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoInspeccionPermission]


def _respuesta_400(errores):
    """Un 400 con ``detail`` legible además del detalle por campo (patrón `rechazo_legible`)."""

    if isinstance(errores, dict):
        cuerpo = {
            campo: [str(m) for m in (msgs if isinstance(msgs, list) else [msgs])] for campo, msgs in errores.items()
        }
    else:
        cuerpo = {"non_field_errors": [str(m) for m in errores]}
    mensajes = [m for msgs in cuerpo.values() for m in msgs]
    cuerpo["detail"] = mensajes[0] if mensajes else "El envío no es válido."
    cuerpo.setdefault("non_field_errors", mensajes)
    return Response(cuerpo, status=status.HTTP_400_BAD_REQUEST)


def _respuesta_409(codigo, mensaje, inspeccion=None):
    cuerpo = {"detail": mensaje, "code": codigo}
    if inspeccion is not None:
        cuerpo["estado"] = inspeccion.estado
    return Response(cuerpo, status=status.HTTP_409_CONFLICT)


def _ejecutar(operacion, inspeccion):
    """Corre la operación del servicio y traduce sus excepciones. Devuelve ``(resultado, respuesta)``."""

    try:
        return operacion(), None
    except InspeccionReasignada as error:
        return None, _respuesta_409(error.codigo, str(error))
    except InspeccionEnConflicto as error:
        inspeccion.refresh_from_db(fields=["estado"])
        return None, _respuesta_409(error.codigo, error.messages[0], inspeccion)
    except PermissionDenied:
        # Lo que el servicio no le deja tocar es, para la app, algo que no existe.
        raise NotFound() from None
    except ValidationError as error:
        return None, _respuesta_400(error.message_dict if hasattr(error, "error_dict") else error.messages)


@extend_schema_view(
    list=extend_schema(
        description=(
            "La agenda del agente: sus relevamientos **en curso**, por vencimiento. Lo que deja de aparecer "
            "se reasignó, se canceló o ya se realizó; el detalle dice cuál de las dos últimas."
        )
    ),
    retrieve=extend_schema(
        description=(
            "Un relevamiento asignado al agente, en cualquier estado (el cancelado trae su motivo), con las "
            "fotos ya recibidas. Lo ajeno —y lo reasignado a otro— es 404."
        ),
        responses={200: InspeccionCampoDetailSerializer, 404: _RESPUESTAS_DE_ENVIO[404]},
    ),
)
class InspeccionViewSet(viewsets.ReadOnlyModelViewSet):
    """Las tareas del agente y el envío del resultado y las fotos."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoInspeccionPermission]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    # Como la agenda de Becas (G1-03): la lista se sirve completa. Está acotada por
    # naturaleza a lo que el agente tiene en curso.
    pagination_class = None
    # Solo para el esquema (RED-37): `get_queryset()` lo pisa y necesita `request.user`.
    queryset = InspeccionEdificio.objects.none()

    def get_queryset(self):
        user = self.request.user
        if self.action == "list":
            return inspecciones_asignadas(user).order_by("fecha_vencimiento", "pk")
        if self.action in ("resultado", "fotos"):
            return inspecciones_para_envio(user)
        return inspecciones_del_agente(user).select_related("edificio").prefetch_related("fotos")

    def get_object(self):
        """El 404 de DRF arrastra el mensaje de Django («No InspeccionEdificio matches…»):
        acá sale el mismo cuerpo genérico que el respaldo del servicio en `_ejecutar`."""

        try:
            return super().get_object()
        except Http404:
            raise NotFound() from None

    def get_serializer_class(self):
        if self.action == "list":
            return InspeccionCampoListSerializer
        return InspeccionCampoDetailSerializer

    def _detalle(self, inspeccion):
        fresca = InspeccionEdificio.objects.select_related("edificio").prefetch_related("fotos").get(pk=inspeccion.pk)
        return InspeccionCampoDetailSerializer(fresca).data

    @extend_schema(
        request=ResultadoInspeccionSerializer,
        responses={200: InspeccionCampoDetailSerializer, **_RESPUESTAS_DE_ENVIO},
        description=(
            "Registra la criticidad y las observaciones y deja el relevamiento realizado. Idempotente por "
            "`uuid_cliente`: el reenvío del mismo devuelve 200 con el relevamiento como quedó."
        ),
    )
    @action(detail=True, methods=["post"], parser_classes=[JSONParser])
    def resultado(self, request, pk=None):
        inspeccion = self.get_object()
        entrada = ResultadoInspeccionSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_400(entrada.errors)
        datos = entrada.validated_data
        _, respuesta = _ejecutar(
            lambda: registrar_resultado(
                request.user,
                inspeccion,
                criticidad=datos["criticidad"],
                observaciones=datos["observaciones"],
                uuid_resultado=datos["uuid_cliente"],
            ),
            inspeccion,
        )
        return respuesta or Response(self._detalle(inspeccion))

    @extend_schema(
        request={"multipart/form-data": FotoInspeccionEnvioSerializer},
        responses={
            201: FotoInspeccionCampoSerializer,
            200: OpenApiResponse(
                response=FotoInspeccionCampoSerializer,
                description="Reenvío: esa foto (`uuid_cliente`) ya había llegado y se devuelve la misma.",
            ),
            **_RESPUESTAS_DE_ENVIO,
        },
        description=(
            "Suma una foto al relevamiento, en curso o ya realizado (la app sin conexión las manda después del "
            "resultado). Una por request. Idempotente por `uuid_cliente`."
        ),
    )
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def fotos(self, request, pk=None):
        inspeccion = self.get_object()
        entrada = FotoInspeccionEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_400(entrada.errors)
        datos = entrada.validated_data
        foto, respuesta = _ejecutar(
            lambda: agregar_foto(
                request.user,
                inspeccion,
                datos["archivo"],
                datos["descripcion"],
                uuid_cliente=datos["uuid_cliente"],
            ),
            inspeccion,
        )
        if respuesta is not None:
            return respuesta
        codigo = status.HTTP_200_OK if foto.ya_existia else status.HTTP_201_CREATED
        return Response(FotoInspeccionCampoSerializer(foto).data, status=codigo)
